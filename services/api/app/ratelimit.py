"""Limiti di frequenza su Redis (sez. 8 della specifica).

Algoritmo: finestra scorrevole approssimata con due contatori (finestra corrente e precedente,
pesata per la parte ancora sovrapposta). Un solo script Lua: atomico e un solo giro di rete.

Se Redis non risponde si lascia passare la richiesta e si scrive un avviso: meglio un limite
non applicato per qualche secondo che l'app ferma. Le protezioni critiche (OTP, login) restano
comunque in Supabase Auth.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

from fastapi import Request
from redis.exceptions import RedisError

from app.auth import current_auth
from app.config import get_settings
from app.errors import ApiError
from app.redis_client import get_redis

logger = logging.getLogger("wearx.ratelimit")

_SCRIPT = """
local current = tonumber(redis.call('INCR', KEYS[1]))
if current == 1 then redis.call('PEXPIRE', KEYS[1], ARGV[1] * 2) end
local previous = tonumber(redis.call('GET', KEYS[2]) or '0')
return {current, previous}
"""


def client_ip(request: Request) -> str:
    settings = get_settings()
    mode = "cloudflare" if settings.trust_proxy_headers else settings.proxy_mode
    if mode == "cloudflare":
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            return forwarded.strip()
    elif mode == "google":
        # Google aggiunge in fondo l'IP da cui arriva la connessione: è l'unico affidabile.
        chain = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
        if chain and chain[-1]:
            return chain[-1]
    return request.client.host if request.client else "unknown"


async def hit(name: str, subject: str, limit: int, window_seconds: int) -> None:
    """Conta una richiesta; se il limite è superato solleva 429 con Retry-After."""
    now = time.time()
    window = int(now // window_seconds)
    elapsed_fraction = (now % window_seconds) / window_seconds
    key_now = f"rl:{name}:{subject}:{window}"
    key_prev = f"rl:{name}:{subject}:{window - 1}"
    try:
        pending = get_redis().eval(_SCRIPT, 2, key_now, key_prev, str(window_seconds * 1000))
        result = await cast(Awaitable[list[Any]], pending)
    except RedisError:
        logger.warning("Redis non disponibile: limite non applicato", extra={"limit": name})
        return
    current, previous = int(result[0]), int(result[1])
    estimated = previous * (1 - elapsed_fraction) + current
    if estimated > limit:
        retry_after = max(1, math.ceil(window_seconds * (1 - elapsed_fraction)))
        raise ApiError(
            429,
            "rate.limited",
            "Troppe richieste, riprova tra poco",
            headers={"Retry-After": str(retry_after)},
            extra={"limit": name},
        )


def rate_limit(
    name: str, limit: int, window_seconds: int, by: Literal["ip", "user"] = "user"
) -> Callable[[Request], Awaitable[None]]:
    """Dipendenza FastAPI. `by="user"` richiede un token valido (verificato qui)."""

    async def dependency(request: Request) -> None:
        if by == "ip":
            subject = client_ip(request)
        else:
            auth = await current_auth(request)
            subject = str(auth.user_id)
        await hit(name, subject, limit, window_seconds)

    return dependency
