"""Regole dei voti (sez. 6.7).

- Anonimato: nei voti non c'è l'id di chi vota, solo `voter_key` = HMAC-SHA256(pepper, id).
  Senza il pepper (segreto del server) non si risale alla persona; con il pepper si può solo
  riconoscere "stesso votante" per impedire il doppio voto e gli abusi.
- Peso: i voti di account appena creati contano la metà (difesa minima contro account usa e
  getta; la seduta 22 aggiunge attestazione del dispositivo e anomalie).
- Conferma dello stile: la chiediamo ai primi CONFIRM_SAMPLE votanti; con almeno
  CONFIRM_MIN risposte, sotto il 70% di "sì" il post esce dalla pagina dello stile.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

from app.config import get_settings

CONFIRM_SAMPLE = 30
CONFIRM_MIN = 10
MATCH_THRESHOLD = 0.70
NEW_ACCOUNT_AGE = timedelta(hours=24)
NEW_ACCOUNT_WEIGHT = 0.5


def voter_key(user_id: uuid.UUID) -> bytes:
    pepper = get_settings().vote_pepper.get_secret_value().encode()
    return hmac.new(pepper, b"vote:" + user_id.bytes, hashlib.sha256).digest()


def vote_weight(account_created_at: datetime, now: datetime | None = None) -> float:
    current = now or datetime.now(UTC)
    return NEW_ACCOUNT_WEIGHT if current - account_created_at < NEW_ACCOUNT_AGE else 1.0


def bucket(score: int) -> int:
    """Indice (1-10, come gli array di PostgreSQL) della fascia di 10 punti del voto."""
    return (score - 1) // 10 + 1


def style_match(confirm_yes: int, confirm_no: int) -> float | None:
    """Quota di "sì" sulla conferma dello stile; None finché le risposte sono poche."""
    total = confirm_yes + confirm_no
    return None if total < CONFIRM_MIN else confirm_yes / total


def style_rejected(confirm_yes: int, confirm_no: int) -> bool:
    match = style_match(confirm_yes, confirm_no)
    return match is not None and match < MATCH_THRESHOLD
