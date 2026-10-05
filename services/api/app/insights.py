"""Insight per chi pubblica (seduta 19): riepilogo notturno degli eventi e dei voti.

Ogni notte (3:40, ora italiana) si ricalcolano i totali di ieri e dell'altro ieri (gli eventi
possono arrivare fino a 24 ore dopo, quando il telefono torna in rete). Il calcolo cancella e
riscrive il giorno: si può ripetere quante volte si vuole con lo stesso risultato.

Cosa si conta, per fit e per giorno (data italiana):
- visualizzazioni, aperture, click sui negozi: PERSONE DIVERSE (pseudonimi distinti);
- voti ricevuti quel giorno e loro somma (per la media del periodo);
- visite al profilo: persone diverse, per autore.

Soglie (si applicano in lettura, `mask`): un numero tra 1 e 4 non si mostra ("meno di 5"),
perché con numeri così piccoli chi pubblica potrebbe capire chi ha guardato o votato. Lo zero
si mostra (non rivela nessuno). Le medie dei voti esistono solo per periodi con almeno 5 voti e
mai giorno per giorno.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ROME = ZoneInfo("Europe/Rome")
THRESHOLD = 5
HISTORY_DAYS = 90  # gli eventi grezzi restano ~3 mesi: più indietro non c'è nulla da contare


def mask(value: int) -> int | None:
    """0 resta 0; da 1 a 4 diventa None ("meno di 5"); da 5 in su si mostra."""
    return value if value == 0 or value >= THRESHOLD else None


def change(current: int, previous: int) -> float | None:
    """Variazione percentuale rispetto al periodo prima, solo se entrambi superano la soglia."""
    if current < THRESHOLD or previous < THRESHOLD:
        return None
    return round((current - previous) / previous * 100, 1)


def rome_today(now: datetime) -> date:
    return now.astimezone(ROME).date()


def bounds(day: date) -> tuple[datetime, datetime]:
    lo = datetime.combine(day, time(0), tzinfo=ROME)
    hi = datetime.combine(day + timedelta(days=1), time(0), tzinfo=ROME)
    return lo, hi


_POSTS_SQL = text(
    """
    with ev as (
      select post_id,
             count(distinct actor_key) filter (where name = 'post_impression') as impressions,
             count(distinct actor_key) filter (where name = 'post_open') as opens,
             count(distinct actor_key) filter (where name = 'shop_click') as clicks
        from app.events
       where ts >= :lo and ts < :hi and post_id is not null
       group by post_id
    ), vt as (
      select post_id, count(*) as votes, sum(score) as vote_sum
        from app.votes
       where created_at >= :lo and created_at < :hi
       group by post_id
    ), totals as (
      select coalesce(ev.post_id, vt.post_id) as post_id,
             coalesce(ev.impressions, 0) as impressions, coalesce(ev.opens, 0) as opens,
             coalesce(ev.clicks, 0) as clicks,
             coalesce(vt.votes, 0) as votes, coalesce(vt.vote_sum, 0) as vote_sum
        from ev full join vt on vt.post_id = ev.post_id
    )
    insert into app.insight_daily
      (author_id, day, post_id, impressions, opens, votes, vote_sum, shop_clicks)
    select p.author_id, :day, t.post_id, t.impressions, t.opens, t.votes, t.vote_sum, t.clicks
      from totals t join app.posts p on p.id = t.post_id
    """
)

_PROFILES_SQL = text(
    """
    insert into app.insight_profile_daily (author_id, day, profile_views)
    select p.id, :day, count(distinct e.actor_key)
      from app.events e
      join app.profiles p on p.id = cast(e.props ->> 'profile_id' as uuid)
     where e.name = 'profile_view' and e.ts >= :lo and e.ts < :hi
     group by p.id
    """
)


async def aggregate_day(session: AsyncSession, day: date) -> None:
    """Ricalcola i totali di un giorno (cancella e riscrive)."""
    lo, hi = bounds(day)
    params: dict[str, Any] = {"day": day, "lo": lo, "hi": hi}
    await session.execute(text("delete from app.insight_daily where day = :day"), params)
    await session.execute(text("delete from app.insight_profile_daily where day = :day"), params)
    await session.execute(_POSTS_SQL, params)
    await session.execute(_PROFILES_SQL, params)


async def aggregate_recent(session: AsyncSession, now: datetime | None = None) -> int:
    """Lavoro notturno: ieri e l'altro ieri; alla primissima esecuzione, gli ultimi 90 giorni."""
    now = now or datetime.now(ROME)
    today = rome_today(now)
    ran_before = await session.scalar(text("select 1 from app.job_runs where name = 'insights'"))
    back = 2 if ran_before else HISTORY_DAYS
    days = [today - timedelta(days=n) for n in range(back, 0, -1)]
    for day in days:
        await aggregate_day(session, day)
    await session.execute(
        text(
            """insert into app.job_runs (name, finished_at, details)
               values ('insights', now(), cast(:details as jsonb))
               on conflict (name) do update
                  set finished_at = excluded.finished_at, details = excluded.details"""
        ),
        {"details": f'{{"through": "{days[-1].isoformat()}"}}'},
    )
    await session.commit()
    return len(days)
