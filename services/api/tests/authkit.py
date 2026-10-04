"""Strumenti di test per l'autenticazione: chiavi vere, JWKS simulato, token firmati."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app.auth import JwksCache
from app.config import get_settings

ISSUER = get_settings().jwt_issuer


class KeySet:
    def __init__(self) -> None:
        self.ec_key = ec.generate_private_key(ec.SECP256R1())
        self.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.ec_kid = f"ec-{uuid.uuid4().hex[:8]}"
        self.rsa_kid = f"rsa-{uuid.uuid4().hex[:8]}"
        self.fetches = 0

    def jwks(self) -> dict[str, Any]:
        ec_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self.ec_key.public_key()))
        ec_jwk.update(kid=self.ec_kid, alg="ES256", use="sig")
        rsa_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.rsa_key.public_key()))
        rsa_jwk.update(kid=self.rsa_kid, alg="RS256", use="sig")
        # Una chiave simmetrica nel JWKS non deve mai essere usata per verificare.
        oct_jwk = {"kty": "oct", "kid": "shared-secret", "k": "c2VncmV0bw"}
        return {"keys": [ec_jwk, rsa_jwk, oct_jwk]}

    def cache(self) -> JwksCache:
        def handler(request: httpx.Request) -> httpx.Response:
            self.fetches += 1
            return httpx.Response(200, json=self.jwks())

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return JwksCache(get_settings().jwks_url, ttl_seconds=600, client=client)

    def public_pem(self) -> bytes:
        return self.ec_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def token(
        self,
        sub: uuid.UUID | str | None,
        *,
        alg: str = "ES256",
        kid: str | None = None,
        lifetime: int = 3600,
        **overrides: Any,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(sub) if sub is not None else None,
            "iss": ISSUER,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + lifetime,
            "session_id": str(uuid.uuid4()),
            "aal": "aal1",
            "is_anonymous": False,
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        if alg == "ES256":
            return jwt.encode(
                claims, self.ec_key, algorithm="ES256", headers={"kid": kid or self.ec_kid}
            )
        if alg == "RS256":
            return jwt.encode(
                claims, self.rsa_key, algorithm="RS256", headers={"kid": kid or self.rsa_kid}
            )
        raise ValueError(alg)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
