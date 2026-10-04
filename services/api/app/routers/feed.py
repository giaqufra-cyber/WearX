"""GET /v1/feed: i fit dei tuoi stili (o di uno stile), una pagina alla volta."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.feed import feed_page
from app.post_views import PostOut, posts_out
from app.profiles import VISIBLE_STYLE_SQL, CurrentProfile
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1", tags=["feed"])

Session = Annotated[AsyncSession, Depends(get_session)]


class FeedOut(BaseModel):
    items: list[PostOut]
    # Da passare come ?cursor= per la pagina successiva; null = fine del feed.
    next_cursor: str | None
    # Perché è vuoto, per mostrare il messaggio giusto: nessuno stile seguito o nessun fit.
    empty_reason: Literal["no_styles", "no_posts"] | None = None


@router.get(
    "/feed",
    response_model=FeedOut,
    dependencies=[Depends(rate_limit("feed", 600, 3600))],
)
async def get_feed(
    profile: CurrentProfile,
    session: Session,
    style: Annotated[str | None, Query(max_length=40)] = None,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
) -> FeedOut:
    params = {"uid": profile.id, "adult": profile.is_adult}
    if style:
        style_id = await session.scalar(
            text(f"select s.id from app.styles s where s.slug = :slug and {VISIBLE_STYLE_SQL}"),
            {**params, "slug": style},
        )
        if style_id is None:
            raise ApiError(404, "style.not_found", "Stile non trovato")
        styles = [int(style_id)]
    else:
        styles = [
            int(r[0])
            for r in await session.execute(
                text(
                    f"""select s.id from app.style_memberships m
                          join app.styles s on s.id = m.style_id
                         where m.user_id = :uid and {VISIBLE_STYLE_SQL}"""
                ),
                params,
            )
        ]
        if not styles:
            return FeedOut(items=[], next_cursor=None, empty_reason="no_styles")

    page = await feed_page(session, profile, styles, style or "", cursor)
    loaded = await posts_out(session, profile, page.ids)
    items = [loaded[i] for i in page.ids if i in loaded]  # stesso ordine, spariti esclusi
    empty = "no_posts" if not items and cursor is None and page.next_cursor is None else None
    return FeedOut(items=items, next_cursor=page.next_cursor, empty_reason=empty)
