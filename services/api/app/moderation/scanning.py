"""Controlli automatici sulle foto, prima che escano dalla quarantena (sez. 14.2).

Due livelli, ognuno dietro un'interfaccia, così i servizi esterni si collegano senza toccare
il resto:
- HashMatcher: confronto con liste di impronte. Sempre attiva la lista locale
  (`app.blocked_hashes`: foto rimosse dai moderatori + impronte inserite su indicazione delle
  autorità). Il servizio esterno per il materiale pedopornografico noto (PhotoDNA, Thorn Safer)
  si aggiunge con `set_hash_matchers` quando l'accesso è concesso.
- ImageClassifier: punteggi 0-1 per categoria (nudità, sesso, violenza, armi, odio). Finché il
  fornitore non è scelto (Rekognition, Vision SafeSearch, Hive) non classifica nulla.

`decide` è una funzione pura: dato l'esito dei due livelli e l'età di chi carica dice se la foto
passa, è bloccata o passa ma va rivista da una persona. Per i 16-17 le soglie sono più severe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Category = Literal["nudity", "sexual", "violence", "weapons", "hate"]
CATEGORIES: tuple[Category, ...] = ("nudity", "sexual", "violence", "weapons", "hate")

# Due foto con impronta percettiva a distanza <= 6 bit su 64 sono "la stessa foto"
# (ritagliata, ricompressa, leggermente modificata).
PHASH_MAX_DISTANCE = 6

# (blocca da, rivedi da). Sopra la prima soglia la foto non passa; tra le due passa ma il fit
# finisce in coda di revisione. Valori iniziali: si tarano con il fornitore scelto.
THRESHOLDS_ADULT: dict[Category, tuple[float, float]] = {
    "sexual": (0.85, 0.50),
    "nudity": (0.92, 0.65),
    "violence": (0.90, 0.60),
    "weapons": (0.95, 0.70),
    "hate": (0.85, 0.50),
}
THRESHOLDS_MINOR: dict[Category, tuple[float, float]] = {
    "sexual": (0.60, 0.30),
    "nudity": (0.70, 0.40),
    "violence": (0.80, 0.50),
    "weapons": (0.90, 0.60),
    "hate": (0.70, 0.40),
}


@dataclass(frozen=True, slots=True)
class HashHit:
    kind: Literal["csam", "removed"]
    source: str


@dataclass(frozen=True, slots=True)
class UploadDecision:
    verdict: Literal["allow", "review", "block"]
    # Perché: "hash:csam", "hash:removed", "label:sexual"...
    reason: str | None = None
    # Materiale illegale noto: si sospende l'account e si apre un caso P0.
    incident: bool = False
    labels: dict[str, float] = field(default_factory=dict)


class HashMatcher(Protocol):
    async def match(self, session: AsyncSession, sha256: bytes, phash: int) -> HashHit | None: ...


class ImageClassifier(Protocol):
    async def classify(self, image: bytes) -> dict[str, float]: ...


class LocalHashList:
    """Impronte in `app.blocked_hashes`: uguale (sha256) o quasi uguale (phash)."""

    async def match(self, session: AsyncSession, sha256: bytes, phash: int) -> HashHit | None:
        row = (
            await session.execute(
                text(
                    """select kind, source from app.blocked_hashes
                        where sha256 = :sha
                           or (phash is not null
                               and bit_count(cast(phash # :ph as bit(64))) <= :dist)
                        order by (kind = 'csam') desc
                        limit 1"""
                ),
                {"sha": sha256, "ph": _signed(phash), "dist": PHASH_MAX_DISTANCE},
            )
        ).first()
        return HashHit(kind=row[0], source=row[1]) if row else None


class NoClassifier:
    async def classify(self, image: bytes) -> dict[str, float]:
        return {}


def _signed(phash: int) -> int:
    """Le impronte sono 64 bit senza segno; PostgreSQL bigint è con segno."""
    return phash - (1 << 64) if phash >= 1 << 63 else phash


def decide(hit: HashHit | None, labels: dict[str, float], *, minor: bool) -> UploadDecision:
    if hit is not None:
        return UploadDecision(
            verdict="block", reason=f"hash:{hit.kind}", incident=hit.kind == "csam"
        )
    thresholds = THRESHOLDS_MINOR if minor else THRESHOLDS_ADULT
    clean: dict[str, float] = {c: float(labels[c]) for c in CATEGORIES if c in labels}
    review_reason = None
    for category in CATEGORIES:
        score = clean.get(category, 0.0)
        block_at, review_at = thresholds[category]
        if score >= block_at:
            return UploadDecision(verdict="block", reason=f"label:{category}", labels=clean)
        if score >= review_at and review_reason is None:
            review_reason = f"label:{category}"
    if review_reason:
        return UploadDecision(verdict="review", reason=review_reason, labels=clean)
    return UploadDecision(verdict="allow", labels=clean)


_matchers: list[HashMatcher] = [LocalHashList()]
_classifier: ImageClassifier = NoClassifier()


def set_hash_matchers(matchers: list[HashMatcher] | None) -> None:
    """La lista locale resta sempre; qui si aggiungono i servizi esterni (o finti nei test)."""
    global _matchers
    _matchers = [LocalHashList(), *(matchers or [])]


def set_classifier(classifier: ImageClassifier | None) -> None:
    global _classifier
    _classifier = classifier or NoClassifier()


async def scan_image(
    session: AsyncSession, image: bytes, sha256: bytes, phash: int, *, minor: bool
) -> UploadDecision:
    hit = None
    for matcher in _matchers:
        found = await matcher.match(session, sha256, phash)
        if found and (hit is None or found.kind == "csam"):
            hit = found
        if hit and hit.kind == "csam":
            break
    labels = {} if hit else await _classifier.classify(image)
    return decide(hit, labels, minor=minor)
