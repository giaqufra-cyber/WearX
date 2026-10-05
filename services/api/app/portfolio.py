"""Ordine del portfolio e copertina (sez. 6.5).

Ordine: `portfolio_rank` DECRESCENTE (prima la chiave più alta), a parità di chiave l'id.
Copertina: il primo fit. Finché l'utente non tocca l'ordine è il più recente; dal primo
riordino resta quello scelto (`profiles.portfolio_cover_id`) e i fit nuovi entrano subito
sotto la copertina invece di prenderne il posto.

Tutte le funzioni che cambiano le chiavi di una persona prendono prima il lock della sua riga
profilo: due riordini (o un riordino e una pubblicazione) della stessa persona passano uno alla
volta e non possono produrre la stessa chiave.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ranking import MAX_KEY_LEN, key_between, key_now, spread_keys

_ORDER = "order by portfolio_rank desc, id desc"
_MINE = "author_id = :uid and status <> 'deleted'"


async def lock_portfolio(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    """Lock della riga profilo; restituisce la copertina scelta se è ancora valida."""
    cover = await session.scalar(
        text("select portfolio_cover_id from app.profiles where id = :uid for update"),
        {"uid": user_id},
    )
    if cover is None:
        return None
    alive = await session.scalar(
        text(f"select 1 from app.posts where id = :id and {_MINE}"),
        {"id": cover, "uid": user_id},
    )
    return cover if alive else None


async def _rank(session: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> str | None:
    value = await session.scalar(
        text(f"select portfolio_rank from app.posts where id = :id and {_MINE}"),
        {"id": post_id, "uid": user_id},
    )
    return None if value is None else str(value)


async def _below(
    session: AsyncSession, user_id: uuid.UUID, rank: str | None, exclude: uuid.UUID | None
) -> str | None:
    """Chiave più alta strettamente sotto `rank` (rank=None: la più alta di tutte)."""
    value = await session.scalar(
        text(
            f"""select portfolio_rank from app.posts
                 where {_MINE} and id is distinct from cast(:ex as uuid)
                   and (cast(:r as text) is null or portfolio_rank < cast(:r as text) collate "C")
                 {_ORDER} limit 1"""
        ),
        {"uid": user_id, "r": rank, "ex": exclude},
    )
    return None if value is None else str(value)


async def rebalance(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Riscrive tutte le chiavi della persona, corte e distanziate, senza cambiare l'ordine."""
    ids = list(
        (
            await session.execute(
                text(f"select id from app.posts where {_MINE} {_ORDER}"), {"uid": user_id}
            )
        ).scalars()
    )
    keys = spread_keys(len(ids))
    if ids:
        await session.execute(
            text(
                """update app.posts p set portfolio_rank = k.key
                     from unnest(cast(:ids as uuid[]), cast(:keys as text[])) as k(id, key)
                    where p.id = k.id"""
            ),
            {"ids": ids, "keys": keys},
        )


async def new_post_rank(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Chiave per un fit appena pubblicato: in cima, oppure subito sotto la copertina scelta."""
    cover = await lock_portfolio(session, user_id)
    for attempt in range(2):
        if cover is not None:
            high = await _rank(session, user_id, cover)
            low = await _below(session, user_id, high, None)
        else:
            high = None
            low = await _below(session, user_id, None, None)
            now = key_now()
            if low is None or low < now:
                return now
        key = _safe_between(low, high)
        if key is not None and len(key) <= MAX_KEY_LEN:
            return key
        if attempt == 0:
            await rebalance(session, user_id)
    raise RuntimeError("chiave del portfolio non calcolabile")


def _safe_between(low: str | None, high: str | None) -> str | None:
    try:
        return key_between(low, high)
    except ValueError:  # chiavi uguali o non valide (dati vecchi): si ribilancia
        return None


async def move_after(
    session: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID, after_id: uuid.UUID | None
) -> None:
    """Mette `post_id` subito dopo `after_id` (None: in testa, cioè copertina).
    Chi chiama ha già verificato che entrambi i post siano della persona e non eliminati."""
    await lock_portfolio(session, user_id)
    duplicates = await session.scalar(
        text(f"select count(*) - count(distinct portfolio_rank) from app.posts where {_MINE}"),
        {"uid": user_id},
    )
    if duplicates:  # dati vecchi con chiavi uguali: l'ordine "subito dopo" non sarebbe preciso
        await rebalance(session, user_id)
    for attempt in range(2):
        if after_id is None:
            high = None
            low = await _below(session, user_id, None, post_id)
        else:
            high = await _rank(session, user_id, after_id)
            low = await _below(session, user_id, high, post_id)
        current = await _rank(session, user_id, post_id)
        if (
            current is not None
            and (low is None or current > low)
            and (high is None or current < high)
        ):
            break  # è già lì
        key = _safe_between(low, high)
        if key is not None and len(key) <= MAX_KEY_LEN:
            await session.execute(
                text("update app.posts set portfolio_rank = :k where id = :id"),
                {"k": key, "id": post_id},
            )
            break
        if attempt == 0:
            await rebalance(session, user_id)
    else:
        raise RuntimeError("chiave del portfolio non calcolabile")
    await _pin_first_as_cover(session, user_id)


async def _pin_first_as_cover(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text(
            f"""update app.profiles set portfolio_cover_id = (
                  select id from app.posts where {_MINE} {_ORDER} limit 1)
                where id = :uid"""
        ),
        {"uid": user_id},
    )


async def after_post_deleted(session: AsyncSession, user_id: uuid.UUID, post_id: uuid.UUID) -> None:
    """Se è stata eliminata la copertina scelta, la copertina diventa il fit che ora è primo."""
    cover = await session.scalar(
        text("select portfolio_cover_id from app.profiles where id = :uid for update"),
        {"uid": user_id},
    )
    if cover == post_id:
        await _pin_first_as_cover(session, user_id)
