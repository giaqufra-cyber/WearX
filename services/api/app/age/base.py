"""Contratto che ogni fornitore di verifica dell'età deve rispettare.

Il fornitore vero (decisione D5) si aggiunge implementando `AgeProvider`: il resto dell'API
(sessioni, webhook, decisione sull'esito) non cambia.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

Method = Literal["selfie_estimation", "id_document", "spid", "cie"]
ProviderBand = Literal["under_16", "16_17", "18_plus"]
Outcome = Literal["passed", "failed", "cancelled"]

ALL_METHODS: tuple[Method, ...] = ("selfie_estimation", "spid", "cie", "id_document")
# Metodi che leggono la data di nascita da un documento o da un'identità digitale.
AUTHORITATIVE_METHODS: frozenset[str] = frozenset({"id_document", "spid", "cie"})


class WebhookRejected(Exception):
    """Firma assente o non valida, timestamp fuori tolleranza, corpo illeggibile."""


@dataclass(frozen=True, slots=True)
class StartResult:
    redirect_url: str
    provider_ref: str


@dataclass(frozen=True, slots=True)
class WebhookResult:
    provider_ref: str
    outcome: Outcome
    # Fascia d'età stimata o letta dal fornitore (None se la verifica non è riuscita).
    age_band: ProviderBand | None = None
    # Data di nascita, solo dai metodi con documento/identità digitale. Non viene salvata:
    # serve a calcolare la fascia e la data dei 18 anni.
    birth_date: date | None = None


class AgeProvider(Protocol):
    name: str
    methods: tuple[Method, ...]

    async def start(
        self, verification_id: uuid.UUID, method: Method, return_url: str
    ) -> StartResult:
        """Apre una verifica presso il fornitore; restituisce la pagina dove mandare l'utente."""
        ...

    def parse_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookResult:
        """Verifica la firma e legge l'esito. Solleva WebhookRejected se qualcosa non torna."""
        ...
