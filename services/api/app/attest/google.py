"""Verifica di Play Integrity (Android), richiesta "standard".

L'app chiede a Google Play un token per la nostra sfida (requestHash); il server lo fa decifrare
a Google (decodeIntegrityToken) con un account di servizio e controlla:
- stessa app (nome del pacchetto) e stessa sfida, token recente (10 minuti);
- app riconosciuta da Google Play (installata dallo store, non modificata);
- telefono che supera i controlli di integrità (MEETS_DEVICE_INTEGRITY).
Su Google Cloud si usa l'identità del servizio (nessuna chiave); altrove un account di servizio
(JSON con chiave privata: SEGRETO, solo nel secret manager).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt

from app.attest.apple import AttestationError

SCOPE = "https://www.googleapis.com/auth/playintegrity"
DECODE_URL = "https://playintegrity.googleapis.com/v1/{package}:decodeIntegrityToken"
MAX_AGE_MS = 10 * 60 * 1000


@dataclass(frozen=True, slots=True)
class IntegrityVerdict:
    device: list[str]
    app: str
    licensing: str | None


class TokenDecoder(Protocol):
    async def decode(self, package: str, token: str) -> dict[str, Any]: ...


class TokenSource(Protocol):
    async def token(self) -> str: ...


class ServiceAccountTokens:
    """Token OAuth da un account di servizio (JSON con chiave privata: SEGRETO)."""

    def __init__(self, service_account_json: str, client: httpx.AsyncClient) -> None:
        info = json.loads(service_account_json)
        self._email: str = info["client_email"]
        self._key: str = info["private_key"]
        self._token_uri: str = info.get("token_uri", "https://oauth2.googleapis.com/token")
        self._client = client
        self._cached: tuple[str, float] | None = None

    async def token(self) -> str:
        if self._cached and self._cached[1] > time.time() + 60:
            return self._cached[0]
        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": self._email,
                "scope": SCOPE,
                "aud": self._token_uri,
                "iat": now,
                "exp": now + 3600,
            },
            self._key,
            algorithm="RS256",
        )
        response = await self._client.post(
            self._token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        response.raise_for_status()
        body = response.json()
        self._cached = (body["access_token"], now + int(body.get("expires_in", 3600)))
        return self._cached[0]


class MetadataTokens:
    """Su Google Cloud (Cloud Run): token dell'identità del servizio dal metadata server.
    Nessuna chiave da custodire; i permessi sono quelli dell'account di servizio."""

    URL = (
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    )

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._cached: tuple[str, float] | None = None

    async def token(self) -> str:
        if self._cached and self._cached[1] > time.time() + 60:
            return self._cached[0]
        response = await self._client.get(
            self.URL, params={"scopes": SCOPE}, headers={"Metadata-Flavor": "Google"}
        )
        response.raise_for_status()
        body = response.json()
        self._cached = (body["access_token"], time.time() + int(body.get("expires_in", 3600)))
        return self._cached[0]


class GooglePlayDecoder:
    """Chiama decodeIntegrityToken con il token OAuth della fonte scelta."""

    def __init__(self, tokens: TokenSource, client: httpx.AsyncClient) -> None:
        self._tokens = tokens
        self._client = client

    async def decode(self, package: str, token: str) -> dict[str, Any]:
        access = await self._tokens.token()
        response = await self._client.post(
            DECODE_URL.format(package=package),
            headers={"authorization": f"Bearer {access}"},
            json={"integrity_token": token},
        )
        if response.status_code == 400:
            raise AttestationError("token di integrità non valido")
        response.raise_for_status()
        payload = response.json().get("tokenPayloadExternal")
        if not isinstance(payload, dict):
            raise AttestationError("risposta di Google senza verdetto")
        return payload


def check_verdict(
    payload: dict[str, Any], *, package: str, challenge: str, now_ms: int | None = None
) -> IntegrityVerdict:
    request = payload.get("requestDetails") or {}
    app = payload.get("appIntegrity") or {}
    device = payload.get("deviceIntegrity") or {}
    account = payload.get("accountDetails") or {}
    if request.get("requestPackageName") != package:
        raise AttestationError("pacchetto diverso")
    if request.get("requestHash") != challenge:
        raise AttestationError("sfida diversa")
    current = now_ms if now_ms is not None else int(time.time() * 1000)
    try:
        issued = int(request.get("timestampMillis", 0))
    except (TypeError, ValueError) as exc:
        raise AttestationError("orario del token non valido") from exc
    if abs(current - issued) > MAX_AGE_MS:
        raise AttestationError("token troppo vecchio")
    verdict = str(app.get("appRecognitionVerdict", ""))
    if verdict != "PLAY_RECOGNIZED":
        raise AttestationError(f"app non riconosciuta da Google Play ({verdict or '-'})")
    labels = [str(x) for x in device.get("deviceRecognitionVerdict") or []]
    if "MEETS_DEVICE_INTEGRITY" not in labels:
        raise AttestationError("telefono senza integrità di sistema")
    licensing = account.get("appLicensingVerdict")
    return IntegrityVerdict(device=labels, app=verdict, licensing=licensing)
