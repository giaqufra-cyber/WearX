"""Controlli di moderazione sulle foto prima della pubblicazione.

Seduta 8: interfaccia e implementazione "lascia passare". Nella seduta 16 qui arrivano il
confronto con le liste di hash di materiale vietato (servizio esterno) e il classificatore.
Una foto bloccata non esce mai dalla quarantena.
"""

from __future__ import annotations

from typing import Literal, Protocol

Verdict = Literal["allow", "block"]


class MediaScanner(Protocol):
    async def scan(self, image: bytes, sha256: bytes, phash: int) -> Verdict: ...


class AllowAllScanner:
    async def scan(self, image: bytes, sha256: bytes, phash: int) -> Verdict:
        return "allow"


_scanner: MediaScanner = AllowAllScanner()


def get_scanner() -> MediaScanner:
    return _scanner


def set_scanner(scanner: MediaScanner | None) -> None:
    global _scanner
    _scanner = scanner or AllowAllScanner()
