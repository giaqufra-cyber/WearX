"""Fornitore finto, per sviluppo e test (mai in produzione: lo impedisce la configurazione).

Si comporta come uno vero: rimanda a una pagina "del fornitore" (servita dall'API sotto
/v1/dev/fake-age) dove si sceglie l'esito, poi invia un webhook firmato.
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from collections.abc import Mapping
from datetime import date
from urllib.parse import urlencode

from app.age import signing
from app.age.base import ALL_METHODS, Method, StartResult, WebhookRejected, WebhookResult
from app.config import get_settings


class FakeAgeProvider:
    name = "fake"
    methods: tuple[Method, ...] = ALL_METHODS

    async def start(
        self, verification_id: uuid.UUID, method: Method, return_url: str
    ) -> StartResult:
        settings = get_settings()
        ref = secrets.token_urlsafe(18)
        query = urlencode({"method": method, "return_url": return_url})
        url = f"{settings.public_api_url.rstrip('/')}/v1/dev/fake-age/{ref}?{query}"
        return StartResult(redirect_url=url, provider_ref=ref)

    def parse_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookResult:
        settings = get_settings()
        signing.verify(
            settings.age_webhook_secret.get_secret_value(),
            headers.get(signing.HEADER),
            body,
            now=int(time.time()),
            tolerance=settings.age_webhook_tolerance_seconds,
        )
        try:
            data = json.loads(body)
            birth = data.get("birth_date")
            return WebhookResult(
                provider_ref=str(data["ref"]),
                outcome=data["outcome"],
                age_band=data.get("age_band"),
                birth_date=date.fromisoformat(birth) if birth else None,
            )
        except (ValueError, KeyError, TypeError):
            raise WebhookRejected("corpo non valido") from None

    @staticmethod
    def build_webhook(
        ref: str,
        outcome: str,
        age_band: str | None = None,
        birth_date: date | None = None,
        timestamp: int | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        """Corpo e header di un webhook firmato (usato dalla pagina di prova e dai test)."""
        body = json.dumps(
            {
                "ref": ref,
                "outcome": outcome,
                "age_band": age_band,
                "birth_date": birth_date.isoformat() if birth_date else None,
            }
        ).encode()
        secret = get_settings().age_webhook_secret.get_secret_value()
        ts = timestamp if timestamp is not None else int(time.time())
        header = signing.sign(secret, body, ts)
        return body, {signing.HEADER: header, "content-type": "application/json"}
