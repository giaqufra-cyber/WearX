"""Firma dei webhook: HMAC-SHA256 su "<timestamp>.<corpo>", header `t=<unix>,v1=<hex>`.

Il timestamp entra nella firma e ha una tolleranza: un webhook catturato non si può
rigiocare più tardi. Il confronto è a tempo costante.
"""

from __future__ import annotations

import hashlib
import hmac

from app.age.base import WebhookRejected

HEADER = "x-wearx-signature"


def _mac(secret: str, timestamp: int, body: bytes) -> str:
    message = str(timestamp).encode() + b"." + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def sign(secret: str, body: bytes, timestamp: int) -> str:
    return f"t={timestamp},v1={_mac(secret, timestamp, body)}"


def verify(secret: str, header: str | None, body: bytes, now: int, tolerance: int) -> None:
    if not header:
        raise WebhookRejected("firma assente")
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts["t"][0])
    except (KeyError, ValueError):
        raise WebhookRejected("timestamp non valido") from None
    if abs(now - timestamp) > tolerance:
        raise WebhookRejected("timestamp fuori tolleranza")
    expected = _mac(secret, timestamp, body)
    # Più firme v1 ammesse: serve durante la rotazione del segreto.
    if not any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", [])):
        raise WebhookRejected("firma non valida")
