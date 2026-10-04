"""Dall'esito del fornitore alla decisione di WearX. Funzione pura, testata a parte.

Regole (sez. 11.2 e decisione D3 sui minori):
- con data di nascita da documento/SPID/CIE, vale quella;
- con la sola stima (selfie) si confronta con la data dichiarata in registrazione e,
  se le due fasce non coincidono, si sceglie quella più protettiva o si chiede un
  metodo con documento;
- "sotto i 16" è definitivo solo se viene da un documento: una stima bassa chiede
  un altro metodo, non blocca l'account.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.age.base import WebhookResult

FailureReason = Literal["underage", "inconsistent", "not_completed"]


@dataclass(frozen=True, slots=True)
class Decision:
    status: Literal["passed", "failed"]
    age_band: Literal["16_17", "18_plus"] | None = None
    adult_on: date | None = None
    failure_reason: FailureReason | None = None


def add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 febbraio -> 1 marzo
        return date(day.year + years, 3, 1)


def age_on(birth: date, today: date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _failed(reason: FailureReason) -> Decision:
    return Decision(status="failed", failure_reason=reason)


def _passed(adult_on: date, today: date) -> Decision:
    if adult_on <= today:
        return Decision(status="passed", age_band="18_plus")
    return Decision(status="passed", age_band="16_17", adult_on=adult_on)


def decide(result: WebhookResult, declared_adult_on: date | None, today: date) -> Decision:
    if result.outcome != "passed":
        return _failed("not_completed")

    if result.birth_date is not None:
        if age_on(result.birth_date, today) < 16:
            return _failed("underage")
        return _passed(add_years(result.birth_date, 18), today)

    band = result.age_band
    if band is None:
        return _failed("not_completed")
    if band == "under_16":
        return _failed("inconsistent")
    declared_minor = declared_adult_on is None or declared_adult_on > today
    if band == "18_plus":
        if declared_adult_on is None:
            return _failed("inconsistent")
        # Il fornitore dice 18+, la data dichiarata no: vale la più protettiva.
        return _passed(declared_adult_on, today)
    # band == "16_17"
    if not declared_minor or declared_adult_on is None:
        # Dichiarato maggiorenne ma stimato 16-17: serve un documento.
        return _failed("inconsistent")
    return _passed(declared_adult_on, today)
