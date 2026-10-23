"""Fit salvati e archivio (seduta 32).

Salvati: i fit degli altri che vuoi ritrovare. Sono solo tuoi: l'autore vede quante volte un
suo fit è stato salvato, mai da chi, e non riceve notifiche. Un fit salvato che non puoi più
vedere (archiviato, eliminato, blocco, autore sospeso...) sparisce dall'elenco da solo.

Archivio: un tuo fit archiviato sparisce per tutti gli altri (feed, profilo, pagina dello stile,
link diretti) ma non si cancella. Voti, capi e capsula restano; rimesso dall'archivio torna nel
portfolio al suo posto.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.avatars import avatar_out
from app.db import get_session
from app.errors import ApiError
from app.post_access import AUTHOR_SHOWN_SQL, POST_VISIBLE_SQL
from app.post_views import AuthorRef, PostOut
from app.profiles import CurrentProfile, Profile
from app.ratelimit import rate_limit
from app.routers.portfolio import PortfolioTile, make_tile
from app.routers.posts import _load_post, _own_post, _post_out
from app.votes import voter_key

router = APIRouter(prefix="/v1", tags=["saved"])

Session = Annotated[AsyncSession, Depends(get_session)]
PAGE_DEFAULT, PAGE_MAX = 24, 60


class SavedOut(BaseModel):
    saved: bool


class TilePage(BaseModel):
    items: list[PortfolioTile]
    next_cursor: str | None


def _encode(ts: datetime, post_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{post_id}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, post_id = raw.split("|")
        return datetime.fromisoformat(ts), uuid.UUID(post_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ApiError(400, "saved.invalid_cursor", "Cursore non valido") from exc


# Colonne di una casella della griglia (come in portfolio.make_tile).
_TILE_COLUMNS = """
    p.id, p.author_id, p.status::text as status, p.caption, p.capsule_id,
    s.slug, s.name, s.tone, a.hide_vote_count,
    coalesce(st.shown_count, 0) as vote_count,
    coalesce(st.shown_wsum, 0) as vote_wsum,
    coalesce(st.shown_wcount, 0) as vote_wcount,
    v.score as mine,
    m.width, m.height, m.blurhash, m.upload_id, m.variants,
    (select count(*) from app.post_media mm where mm.post_id = p.id) as media_count
"""

_TILE_JOINS = """
    join app.profiles a on a.id = p.author_id
    join app.styles s on s.id = p.style_id
    left join app.post_stats st on st.post_id = p.id
    left join app.votes v on v.post_id = p.id and v.voter_key = :k
    left join app.post_media m on m.post_id = p.id and m.position = 0
"""


# ---------- Salvati ----------


@router.put(
    "/posts/{post_id}/save",
    response_model=SavedOut,
    dependencies=[Depends(rate_limit("post_save", 300, 86400))],
)
async def save_post(post_id: uuid.UUID, viewer: CurrentProfile, session: Session) -> SavedOut:
    row = await _load_post(session, viewer, post_id)  # 404 se non lo vedi
    if row["author_id"] == viewer.id:
        raise ApiError(422, "save.own", "I tuoi fit sono già nel tuo profilo")
    if row["status"] not in ("active", "style_rejected"):
        raise ApiError(404, "post.not_found", "Post non trovato")
    await session.execute(
        text(
            """insert into app.saved_posts (user_id, post_id) values (:me, :id)
               on conflict do nothing"""
        ),
        {"me": viewer.id, "id": post_id},
    )
    await session.commit()
    return SavedOut(saved=True)


@router.delete("/posts/{post_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_post(post_id: uuid.UUID, viewer: CurrentProfile, session: Session) -> Response:
    """Ripetibile, e funziona anche su un fit che non vedi più."""
    await session.execute(
        text("delete from app.saved_posts where user_id = :me and post_id = :id"),
        {"me": viewer.id, "id": post_id},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/saved", response_model=TilePage)
async def list_saved(
    viewer: CurrentProfile,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> TilePage:
    """I fit salvati, dal più recente. Solo quelli che puoi ancora vedere."""
    after = _decode(cursor) if cursor else None
    rows = (
        (
            await session.execute(
                text(
                    f"""select {_TILE_COLUMNS}, sv.created_at as saved_at,
                               a.nickname::text as nickname,
                               a.account_type::text as account_type,
                               au.id as avatar_id, au.variants as avatar_variants,
                               au.blurhash as avatar_blurhash,
                               {AUTHOR_SHOWN_SQL} as author_shown
                          from app.saved_posts sv
                          join app.posts p on p.id = sv.post_id
                          {_TILE_JOINS}
                          left join app.media_uploads au on au.id = a.avatar_upload_id
                         where sv.user_id = :viewer and p.author_id <> :viewer
                           and {POST_VISIBLE_SQL}
                           and (cast(:ts as timestamptz) is null
                                or (sv.created_at, p.id)
                                   < (cast(:ts as timestamptz), cast(:cid as uuid)))
                         order by sv.created_at desc, p.id desc
                         limit :limit"""  # noqa: S608 - frammenti costanti, nessun input
                ),
                _params(viewer, after, limit),
            )
        )
        .mappings()
        .all()
    )
    page = rows[:limit]
    return TilePage(
        items=[make_tile(r, False, _author(r)) for r in page],
        next_cursor=_encode(page[-1]["saved_at"], page[-1]["id"]) if len(rows) > limit else None,
    )


def _author(row: Any) -> AuthorRef | None:
    if not row["author_shown"]:
        return None
    return AuthorRef(
        nickname=row["nickname"],
        account_type=row["account_type"],
        avatar=avatar_out(row["avatar_id"], row["avatar_variants"], row["avatar_blurhash"]),
    )


def _params(
    viewer: Profile, after: tuple[datetime, uuid.UUID] | None, limit: int
) -> dict[str, Any]:
    return {
        "viewer": viewer.id,
        "adult": viewer.is_adult,
        "k": voter_key(viewer.id),
        "ts": after[0] if after else None,
        "cid": after[1] if after else None,
        "limit": limit + 1,
    }


# ---------- Archivio ----------


async def _set_archived(
    session: AsyncSession, profile: Profile, post_id: uuid.UUID, archived: bool
) -> PostOut:
    row = await _own_post(session, profile, post_id)  # 404 se non c'è, 403 se non è tuo
    if row["status"] == "processing":
        raise ApiError(409, "post.not_ready", "Il fit è ancora in elaborazione")
    await session.execute(
        text(
            """update app.posts
                  set archived_at = case when cast(:on as boolean)
                                         then coalesce(archived_at, now()) end
                where id = :id"""
        ),
        {"on": archived, "id": post_id},
    )
    await session.commit()
    return await _post_out(session, profile, post_id)


@router.post(
    "/posts/{post_id}/archive",
    response_model=PostOut,
    dependencies=[Depends(rate_limit("post_archive", 120, 3600))],
)
async def archive_post(post_id: uuid.UUID, profile: CurrentProfile, session: Session) -> PostOut:
    return await _set_archived(session, profile, post_id, True)


@router.delete(
    "/posts/{post_id}/archive",
    response_model=PostOut,
    dependencies=[Depends(rate_limit("post_archive", 120, 3600))],
)
async def unarchive_post(post_id: uuid.UUID, profile: CurrentProfile, session: Session) -> PostOut:
    """Rimetti nel portfolio: torna al posto di prima (l'ordine non è cambiato)."""
    return await _set_archived(session, profile, post_id, False)


@router.get("/me/archive", response_model=TilePage)
async def list_archive(
    profile: CurrentProfile,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> TilePage:
    """I tuoi fit archiviati, dall'ultimo archiviato."""
    after = _decode(cursor) if cursor else None
    rows = (
        (
            await session.execute(
                text(
                    f"""select {_TILE_COLUMNS}, p.archived_at
                          from app.posts p
                          {_TILE_JOINS}
                         where p.author_id = :viewer and p.archived_at is not null
                           and p.status <> 'deleted'
                           and (cast(:ts as timestamptz) is null
                                or (p.archived_at, p.id)
                                   < (cast(:ts as timestamptz), cast(:cid as uuid)))
                         order by p.archived_at desc, p.id desc
                         limit :limit"""  # noqa: S608 - frammenti costanti, nessun input
                ),
                _params(profile, after, limit),
            )
        )
        .mappings()
        .all()
    )
    page = rows[:limit]
    return TilePage(
        items=[make_tile(r, True) for r in page],
        next_cursor=_encode(page[-1]["archived_at"], page[-1]["id"]) if len(rows) > limit else None,
    )
