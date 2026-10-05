"""Verifica dei token di accesso emessi da Supabase Auth (sez. 11.1 della specifica).

Regole:
- solo algoritmi asimmetrici (ES256, RS256): niente HS256, niente "none". Così un token
  firmato usando la chiave pubblica come segreto HMAC (attacco di confusione) viene rifiutato;
- firma verificata con le chiavi del JWKS di Supabase, tenute in cache 10 minuti;
- se arriva un `kid` sconosciuto si ricarica il JWKS, ma al massimo una volta al minuto
  (altrimenti chiunque potrebbe farci martellare Supabase con token inventati);
- obbligatori: exp, iat, sub, iss (deve essere il nostro progetto), aud (`authenticated`);
- utenti anonimi di Supabase non ammessi.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, Request

from app.config import get_settings
from app.errors import ApiError

logger = logging.getLogger("wearx.auth")

_BEARER_CHALLENGE = {"WWW-Authenticate": 'Bearer realm="wearx"'}
_MIN_REFRESH_INTERVAL = 60.0


def _unauthorized(code: str, title: str) -> ApiError:
    return ApiError(401, code, title, headers=_BEARER_CHALLENGE)


class JwksCache:
    """Chiavi pubbliche di Supabase con scadenza e ricarica limitata."""

    def __init__(self, url: str, ttl_seconds: int, client: httpx.AsyncClient | None = None):
        self.url = url
        self.ttl = ttl_seconds
        self._client = client
        self._keys: dict[str, jwt.PyJWK] = {}
        # "Mai scaricato": il primo uso scarica sempre. (Con 0.0, su una macchina accesa da meno
        # di 60 s — un'istanza Cloud Run appena avviata — l'orologio monotono è sotto i 60 s e
        # le chiavi non si scaricavano: tutti gli accessi rifiutati per un minuto. Seduta 23.)
        self._fetched_at = float("-inf")
        self._lock = asyncio.Lock()

    async def _fetch(self) -> None:
        client = self._client or httpx.AsyncClient(timeout=5.0)
        try:
            response = await client.get(self.url)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        finally:
            if self._client is None:
                await client.aclose()
        keys: dict[str, jwt.PyJWK] = {}
        for raw in data.get("keys", []):
            kid = raw.get("kid")
            # Si accettano solo chiavi pubbliche asimmetriche: una chiave "oct" (segreto
            # condiviso) nel JWKS non deve mai diventare valida per verificare firme.
            if not kid or raw.get("kty") not in ("EC", "RSA", "OKP"):
                continue
            try:
                keys[kid] = jwt.PyJWK(raw)
            except jwt.PyJWKError:
                logger.warning("Chiave JWKS non valida ignorata", extra={"kid": kid})
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def get(self, kid: str) -> jwt.PyJWK | None:
        now = time.monotonic()
        expired = now - self._fetched_at > self.ttl
        unknown = kid not in self._keys
        can_refresh = now - self._fetched_at > _MIN_REFRESH_INTERVAL
        if expired or (unknown and can_refresh):
            async with self._lock:
                # Un'altra richiesta potrebbe aver già ricaricato nel frattempo.
                if time.monotonic() - self._fetched_at > min(self.ttl, _MIN_REFRESH_INTERVAL):
                    try:
                        await self._fetch()
                    except (httpx.HTTPError, ValueError):
                        logger.exception("Impossibile scaricare il JWKS di Supabase")
                        # Si tengono le chiavi vecchie e si riprova tra 30 s, non a ogni richiesta.
                        self._fetched_at = time.monotonic() - self.ttl + 30
                        if not self._keys:
                            raise ApiError(
                                503, "auth.unavailable", "Accesso momentaneamente non verificabile"
                            ) from None
        return self._keys.get(kid)


_jwks: JwksCache | None = None


def get_jwks() -> JwksCache:
    global _jwks
    if _jwks is None:
        settings = get_settings()
        _jwks = JwksCache(settings.jwks_url, settings.jwks_cache_seconds)
    return _jwks


def set_jwks(cache: JwksCache | None) -> None:
    """Per i test: sostituisce la cache delle chiavi."""
    global _jwks
    _jwks = cache


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: uuid.UUID
    session_id: str | None
    aal: str | None


async def verify_token(token: str, jwks: JwksCache) -> AuthContext:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise _unauthorized("auth.invalid_token", "Token non valido") from None

    alg = header.get("alg")
    kid = header.get("kid")
    if alg not in settings.jwt_algorithms or not isinstance(kid, str):
        raise _unauthorized("auth.invalid_token", "Token non valido")

    key = await jwks.get(kid)
    if key is None:
        raise _unauthorized("auth.invalid_token", "Token non valido")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key=key,
            algorithms=list(settings.jwt_algorithms),
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_seconds,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("auth.token_expired", "Sessione scaduta") from None
    except jwt.PyJWTError:
        raise _unauthorized("auth.invalid_token", "Token non valido") from None

    if claims.get("is_anonymous") is True:
        raise ApiError(403, "auth.anonymous_not_allowed", "Serve un account WearX")
    if claims.get("role") not in (None, "authenticated"):
        raise _unauthorized("auth.invalid_token", "Token non valido")
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except ValueError:
        raise _unauthorized("auth.invalid_token", "Token non valido") from None

    session_id = claims.get("session_id")
    aal = claims.get("aal")
    return AuthContext(
        user_id=user_id,
        session_id=session_id if isinstance(session_id, str) else None,
        aal=aal if isinstance(aal, str) else None,
    )


async def current_auth(request: Request) -> AuthContext:
    """Dipendenza FastAPI: utente autenticato (con o senza profilo WearX).

    Il risultato resta in request.state: più dipendenze nella stessa richiesta
    (limite di frequenza, profilo) non verificano il token due volte.
    """
    cached = getattr(request.state, "auth", None)
    if isinstance(cached, AuthContext):
        return cached
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("auth.required", "Accesso richiesto")
    ctx = await verify_token(token.strip(), get_jwks())
    request.state.auth = ctx
    return ctx


CurrentAuth = Annotated[AuthContext, Depends(current_auth)]
