"""Fornitore attivo, scelto dalla configurazione."""

from __future__ import annotations

from app.age.base import AgeProvider
from app.age.fake import FakeAgeProvider
from app.config import get_settings


def get_provider() -> AgeProvider:
    name = get_settings().age_provider
    if name == "fake":
        return FakeAgeProvider()
    raise RuntimeError(f"Fornitore di verifica dell'età sconosciuto: {name}")
