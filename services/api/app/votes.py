"""Regole dei voti (sez. 6.7).

- Anonimato: nei voti non c'è l'id di chi vota, solo `voter_key` = HMAC-SHA256(pepper, id).
  Senza il pepper (segreto del server) non si risale alla persona; con il pepper si può solo
  riconoscere "stesso votante" per impedire il doppio voto e gli abusi.
- Peso al momento del voto (base_weight): metà per gli account creati da meno di 24 ore, metà per
  i dispositivi non verificati (attestazione in modalità "soft"). Il peso usato nelle
  statistiche (weight) è il peso base per il fattore dei segnali di abuso (vote_flags).
- Media pubblicata (seduta 22): le persone vedono valori aggiornati una volta all'ora, la media
  solo da SHOW_MIN_VOTES voti e solo quando dall'ultima volta sono arrivati almeno
  PUBLISH_BATCH voti nuovi o cambiati: dal cambio della media non si ricava il voto di nessuno.
- Conferma dello stile: la chiediamo ai primi CONFIRM_SAMPLE votanti; con almeno
  CONFIRM_MIN risposte, sotto il 70% di "sì" il post esce dalla pagina dello stile.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

log = logging.getLogger("wearx.votes")

CONFIRM_SAMPLE = 30
CONFIRM_MIN = 10
MATCH_THRESHOLD = 0.70
NEW_ACCOUNT_AGE = timedelta(hours=24)
NEW_ACCOUNT_WEIGHT = 0.5
UNVERIFIED_DEVICE_WEIGHT = 0.5
# Media pubblicata: da quanti voti si mostra e quanti voti nuovi servono per aggiornarla.
SHOW_MIN_VOTES = 5
PUBLISH_BATCH = 3


def voter_key(user_id: uuid.UUID) -> bytes:
    pepper = get_settings().vote_pepper.get_secret_value().encode()
    return hmac.new(pepper, b"vote:" + user_id.bytes, hashlib.sha256).digest()


def vote_weight(account_created_at: datetime, now: datetime | None = None) -> float:
    current = now or datetime.now(UTC)
    return NEW_ACCOUNT_WEIGHT if current - account_created_at < NEW_ACCOUNT_AGE else 1.0


def device_weight(attested: bool) -> float:
    """Peso legato al dispositivo; in modalità "required" il voto senza attestazione è rifiutato
    prima (qui non si arriva)."""
    mode = get_settings().attestation_mode
    if mode == "off" or attested:
        return 1.0
    return UNVERIFIED_DEVICE_WEIGHT


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


AverageNote = Literal["few_votes", "next_update"]


def shown_average(shown_wsum: float, shown_wcount: float) -> float | None:
    return round(shown_wsum / shown_wcount, 1) if shown_wcount > 0 else None


def average_note(shown_count: int, average: float | None) -> AverageNote | None:
    """Perché la media non c'è: pochi voti, oppure arriva con il prossimo aggiornamento."""
    if average is not None:
        return None
    return "few_votes" if shown_count < SHOW_MIN_VOTES else "next_update"


# ---------- Pubblicazione oraria ----------


async def publish_stats(session: AsyncSession) -> int:
    """Copia i valori in tempo reale in quelli pubblicati (lavoro orario).

    Il conteggio si aggiorna sempre; media e conferme dello stile solo con almeno SHOW_MIN_VOTES
    voti e almeno PUBLISH_BATCH voti nuovi o cambiati dall'ultima media pubblicata (o la prima
    volta che il fit arriva a SHOW_MIN_VOTES voti). Sotto SHOW_MIN_VOTES la media sparisce.
    """
    result = await session.execute(
        text(
            """with due as (
                 select post_id,
                        vote_count >= :min and (unpublished_writes >= :batch
                                                or shown_wcount = 0) as publish_avg
                   from app.post_stats
                  where vote_count <> shown_count or unpublished_writes > 0
                     or (vote_count < :min and shown_wcount > 0)
                  for update skip locked
               )
               update app.post_stats st set
                 shown_count = st.vote_count,
                 shown_wsum = case when st.vote_count < :min then 0
                                   when due.publish_avg then st.vote_wsum
                                   else st.shown_wsum end,
                 shown_wcount = case when st.vote_count < :min then 0
                                     when due.publish_avg then st.vote_wcount
                                     else st.shown_wcount end,
                 shown_confirm_yes = case when due.publish_avg then st.confirm_yes
                                          else st.shown_confirm_yes end,
                 shown_confirm_no = case when due.publish_avg then st.confirm_no
                                         else st.shown_confirm_no end,
                 unpublished_writes = case when due.publish_avg then 0
                                           else st.unpublished_writes end,
                 shown_at = now()
                 from due
                where st.post_id = due.post_id"""
        ),
        {"min": SHOW_MIN_VOTES, "batch": PUBLISH_BATCH},
    )
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


# ---------- Segnali di abuso ----------

# Stesso voto (±1) su almeno 30 fit in 7 giorni: comportamento da script.
SAME_SCORE_MIN_VOTES = 30
SAME_SCORE_WINDOW = timedelta(days=7)
# Almeno 8 voti in 24 ore sui fit dello stesso autore, tutti altissimi o tutti bassissimi:
# spinta o affossamento mirato.
AUTHOR_BURST_MIN_VOTES = 8
AUTHOR_BURST_WINDOW = timedelta(hours=24)
AUTHOR_BURST_HIGH = 95
AUTHOR_BURST_LOW = 10
FLAG_DURATION = timedelta(days=30)

# Fattore dei segnali attivi per un voto: il più basso tra quelli che lo riguardano.
FLAG_FACTOR_SQL = """coalesce((select min(f.factor) from app.vote_flags f
                                where f.voter_key = {key} and f.lifted_at is null
                                  and {created} < f.expires_at
                                  and (f.author_id is null or f.author_id = {author})), 1)"""


async def recompute_stats(session: AsyncSession, post_ids: list[uuid.UUID]) -> None:
    """Ricalcola dai voti le statistiche in tempo reale (dopo un cambio di pesi).

    I voti con peso 0 non contano neppure nel numero dei voti né nell'istogramma.
    Il ricalcolo conta come un aggiornamento da pubblicare al prossimo giro.
    """
    if not post_ids:
        return
    await session.execute(
        text(
            """update app.post_stats st set
                 vote_count = agg.c, vote_sum = agg.s, vote_wsum = agg.ws, vote_wcount = agg.wc,
                 hist = agg.h,
                 unpublished_writes = greatest(st.unpublished_writes, :batch),
                 updated_at = now()
                 from (
                   select p.id as post_id,
                          count(v.*) filter (where v.weight > 0) as c,
                          coalesce(sum(v.score) filter (where v.weight > 0), 0) as s,
                          coalesce(sum(v.score * v.weight::float8), 0) as ws,
                          coalesce(sum(v.weight::float8), 0) as wc,
                          array(select count(x.*) filter (where x.weight > 0
                                                          and (x.score - 1) / 10 + 1 = b)::int
                                  from generate_series(1, 10) b
                                  left join app.votes x on x.post_id = p.id
                                 group by b order by b) as h
                     from unnest(cast(:ids as uuid[])) as p(id)
                     left join app.votes v on v.post_id = p.id
                    group by p.id
                 ) agg
                where st.post_id = agg.post_id"""
        ),
        {"ids": post_ids, "batch": PUBLISH_BATCH},
    )


async def reweigh_voter(session: AsyncSession, key: bytes) -> list[uuid.UUID]:
    """Riapplica ai voti di un votante i segnali attivi; restituisce i fit cambiati."""
    factor = FLAG_FACTOR_SQL.format(key="v.voter_key", created="v.created_at", author="p.author_id")
    rows = await session.execute(
        text(
            f"""update app.votes v
                   set weight = v.base_weight * {factor}
                  from app.posts p
                 where p.id = v.post_id and v.voter_key = :k
                   and v.weight is distinct from v.base_weight * {factor}
             returning v.post_id"""
        ),
        {"k": key},
    )
    changed = sorted({r[0] for r in rows})
    await recompute_stats(session, changed)
    return changed


async def _flag(
    session: AsyncSession,
    key: bytes,
    rule: str,
    author_id: uuid.UUID | None,
    detail: str,
) -> bool:
    exists = await session.scalar(
        text(
            """select 1 from app.vote_flags
                where voter_key = :k and rule = :rule
                  and author_id is not distinct from :author
                  and lifted_at is null and expires_at > now()"""
        ),
        {"k": key, "rule": rule, "author": author_id},
    )
    if exists:
        return False
    flag_id = await session.scalar(
        text(
            """insert into app.vote_flags
                 (voter_key, author_id, rule, factor, detail, expires_at)
               values (:k, :author, :rule, 0, cast(:detail as jsonb),
                       now() + cast(:duration as interval))
               returning id"""
        ),
        {"k": key, "author": author_id, "rule": rule, "detail": detail, "duration": FLAG_DURATION},
    )
    changed = await reweigh_voter(session, key)
    await session.execute(
        text("update app.vote_flags set votes_affected = :n where id = :id"),
        {"n": len(changed), "id": flag_id},
    )
    return True


async def detect_vote_abuse(session: AsyncSession) -> int:
    """Lavoro orario: cerca i comportamenti da script o mirati e ne neutralizza i voti."""
    import json

    found = 0
    same = (
        (
            await session.execute(
                text(
                    """select voter_key, count(*) as n, min(score) as lo, max(score) as hi
                     from app.votes
                    where created_at > now() - cast(:window as interval)
                    group by voter_key
                   having count(*) >= :min and max(score) - min(score) <= 2"""
                ),
                {"window": SAME_SCORE_WINDOW, "min": SAME_SCORE_MIN_VOTES},
            )
        )
        .mappings()
        .all()
    )
    for row in same:
        detail = json.dumps({"votes": row["n"], "scores": [row["lo"], row["hi"]], "days": 7})
        found += await _flag(session, bytes(row["voter_key"]), "same_score", None, detail)
    burst = (
        (
            await session.execute(
                text(
                    """select v.voter_key, p.author_id, count(*) as n,
                          min(v.score) as lo, max(v.score) as hi
                     from app.votes v join app.posts p on p.id = v.post_id
                    where v.created_at > now() - cast(:window as interval)
                    group by v.voter_key, p.author_id
                   having count(*) >= :min
                      and (min(v.score) >= :high or max(v.score) <= :low)"""
                ),
                {
                    "window": AUTHOR_BURST_WINDOW,
                    "min": AUTHOR_BURST_MIN_VOTES,
                    "high": AUTHOR_BURST_HIGH,
                    "low": AUTHOR_BURST_LOW,
                },
            )
        )
        .mappings()
        .all()
    )
    for row in burst:
        detail = json.dumps({"votes": row["n"], "scores": [row["lo"], row["hi"]], "hours": 24})
        found += await _flag(
            session, bytes(row["voter_key"]), "author_burst", row["author_id"], detail
        )
    await session.commit()
    if found:
        log.warning("voti sospetti neutralizzati: %s votanti", found)
    return found


async def lift_flag(session: AsyncSession, flag_id: int, staff_id: uuid.UUID) -> bool:
    """Lo staff ripristina i voti di un segnale (falso positivo)."""
    key = await session.scalar(
        text(
            """update app.vote_flags set lifted_at = now(), lifted_by = :staff
                where id = :id and lifted_at is null returning voter_key"""
        ),
        {"id": flag_id, "staff": staff_id},
    )
    if key is None:
        return False
    await reweigh_voter(session, bytes(key))
    return True
