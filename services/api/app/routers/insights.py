"""Insight: come vanno i tuoi fit (seduta 19). Solo i dati di chi chiede, con le soglie minime
di `app.insights` (numeri tra 1 e 4 nascosti, medie solo con almeno 5 voti)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.insights import THRESHOLD, change, mask, rome_today
from app.profiles import CurrentProfile
from app.routers.media import MediaUrls, media_urls

router = APIRouter(prefix="/v1", tags=["insights"])

Session = Annotated[AsyncSession, Depends(get_session)]
TOP = 5
PERIODS = (7, 28, 90)


class Metric(BaseModel):
    # None = tra 1 e 4 ("meno di 5").
    value: int | None
    # Variazione % rispetto al periodo precedente (None se uno dei due è sotto la soglia).
    change: float | None


class InsightTotals(BaseModel):
    impressions: Metric
    opens: Metric
    votes: Metric
    shop_clicks: Metric
    profile_views: Metric
    # Media dei voti ricevuti nel periodo, solo con almeno 5 voti.
    average: float | None


class InsightPoint(BaseModel):
    # Primo giorno del gruppo (un giorno, o il lunedì della settimana per i 90 giorni).
    start: date
    impressions: int | None
    votes: int | None


class InsightPost(BaseModel):
    id: uuid.UUID
    caption: str | None
    style: str
    blurhash: str | None
    thumb: MediaUrls | None
    impressions: int | None
    votes: int | None
    average: float | None
    shop_clicks: int | None


class InsightsOut(BaseModel):
    days: Literal[7, 28, 90]
    start: date
    end: date
    # Quando è stato fatto l'ultimo riepilogo (None: mai).
    updated_at: datetime | None
    threshold: int
    bucket: Literal["day", "week"]
    totals: InsightTotals
    series: list[InsightPoint]
    top_posts: list[InsightPost]


async def _sums(session: AsyncSession, me: uuid.UUID, start: date, end: date) -> dict[str, int]:
    row = (
        (
            await session.execute(
                text(
                    """select coalesce(sum(impressions), 0) as impressions,
                              coalesce(sum(opens), 0) as opens,
                              coalesce(sum(votes), 0) as votes,
                              coalesce(sum(vote_sum), 0) as vote_sum,
                              coalesce(sum(shop_clicks), 0) as shop_clicks,
                              (select coalesce(sum(profile_views), 0)
                                 from app.insight_profile_daily
                                where author_id = :me and day between :start and :end)
                                as profile_views
                         from app.insight_daily
                        where author_id = :me and day between :start and :end"""
                ),
                {"me": me, "start": start, "end": end},
            )
        )
        .mappings()
        .one()
    )
    return {k: int(v) for k, v in row.items()}


def _average(votes: int, vote_sum: int) -> float | None:
    return round(vote_sum / votes, 1) if votes >= THRESHOLD else None


@router.get("/me/insights", response_model=InsightsOut)
async def insights(
    viewer: CurrentProfile,
    session: Session,
    days: Annotated[int, Query(description="Periodo: 7, 28 o 90 giorni")] = 7,
) -> InsightsOut:
    if not get_settings().feature_flags.get("insights", False):
        raise ApiError(404, "insights.disabled", "Insight non disponibili")
    if days not in PERIODS:
        raise ApiError(422, "insights.bad_period", "Periodo non valido: 7, 28 o 90 giorni")
    # Il riepilogo arriva fino a ieri.
    end = rome_today(datetime.now().astimezone()) - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    current = await _sums(session, viewer.id, start, end)
    previous = await _sums(
        session, viewer.id, start - timedelta(days=days), start - timedelta(days=1)
    )

    def metric(name: str) -> Metric:
        return Metric(value=mask(current[name]), change=change(current[name], previous[name]))

    bucket: Literal["day", "week"] = "week" if days == 90 else "day"
    step = timedelta(weeks=1) if bucket == "week" else timedelta(days=1)
    series_rows = (
        await session.execute(
            text(
                """select greatest(g.start::date, cast(:start as date)) as start,
                          coalesce(sum(d.impressions), 0) as impressions,
                          coalesce(sum(d.votes), 0) as votes
                     from generate_series(
                            case when :bucket = 'week'
                                 then date_trunc('week', cast(:start as date))
                                 else cast(:start as date) end,
                            cast(:end as date), cast(:step as interval)) as g(start)
                     left join app.insight_daily d
                       on d.author_id = :me and d.day between :start and :end
                      and d.day >= g.start::date
                      and d.day < (g.start + cast(:step as interval))::date
                    group by g.start order by g.start"""
            ),
            {"me": viewer.id, "start": start, "end": end, "bucket": bucket, "step": step},
        )
    ).all()

    top_rows = (
        (
            await session.execute(
                text(
                    """select d.post_id, p.caption, s.name as style,
                              sum(d.impressions) as impressions, sum(d.votes) as votes,
                              sum(d.vote_sum) as vote_sum, sum(d.shop_clicks) as shop_clicks,
                              m.upload_id, m.variants, m.blurhash
                         from app.insight_daily d
                         join app.posts p on p.id = d.post_id and p.status <> 'deleted'
                         join app.styles s on s.id = p.style_id
                         left join app.post_media m on m.post_id = p.id and m.position = 0
                        where d.author_id = :me and d.day between :start and :end
                        group by d.post_id, p.caption, s.name, m.upload_id, m.variants,
                                 m.blurhash
                        order by sum(d.impressions) desc, sum(d.votes) desc, d.post_id
                        limit :top"""
                ),
                {"me": viewer.id, "start": start, "end": end, "top": TOP},
            )
        )
        .mappings()
        .all()
    )
    updated_at = await session.scalar(
        text("select finished_at from app.job_runs where name = 'insights'")
    )
    return InsightsOut(
        days=cast(Literal[7, 28, 90], days),
        start=start,
        end=end,
        updated_at=updated_at,
        threshold=THRESHOLD,
        bucket=bucket,
        totals=InsightTotals(
            impressions=metric("impressions"),
            opens=metric("opens"),
            votes=metric("votes"),
            shop_clicks=metric("shop_clicks"),
            profile_views=metric("profile_views"),
            average=_average(current["votes"], current["vote_sum"]),
        ),
        series=[
            InsightPoint(start=r[0], impressions=mask(int(r[1])), votes=mask(int(r[2])))
            for r in series_rows
        ],
        top_posts=[_post(r) for r in top_rows],
    )


def _post(row: Any) -> InsightPost:
    smallest = sorted(row["variants"] or [])[:1]
    votes = int(row["votes"])
    return InsightPost(
        id=row["post_id"],
        caption=row["caption"],
        style=row["style"],
        blurhash=row["blurhash"],
        thumb=media_urls(row["upload_id"], smallest) if smallest and row["upload_id"] else None,
        impressions=mask(int(row["impressions"])),
        votes=mask(votes),
        average=_average(votes, int(row["vote_sum"])),
        shop_clicks=mask(int(row["shop_clicks"])),
    )
