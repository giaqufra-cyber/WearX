"""Portfolio (sez. 6.5): profilo di una persona, griglia dei suoi fit, ordine, capsule.

Chi vede cosa:
- il proprio portfolio sempre, compresi i fit fuori stile o nascosti dalla moderazione;
- quello di un account Business, o di un account privato che segui (richiesta accettata);
- altrimenti l'intestazione dice solo nickname, tipo, bio, numero di fit e di follower, e la
  griglia risponde 403 `profile.private`;
- con un blocco, o se è un 16-17 e tu sei maggiorenne, la persona "non esiste" (404):
  regole in `app/people.py`.
Le medie seguono la regola dei post: un fit altrui mostra la media solo se l'hai votato.
"""

from __future__ import annotations

import base64
import binascii
import re
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.people import FollowState, find_person
from app.portfolio import lock_portfolio, move_after
from app.post_access import POST_VISIBLE_SQL
from app.post_views import MediaOut, StyleRef
from app.profiles import VISIBLE_STYLE_SQL, CurrentProfile, Profile
from app.ratelimit import rate_limit
from app.routers.media import media_urls
from app.text_policy import clean_text
from app.votes import voter_key

router = APIRouter(prefix="/v1", tags=["portfolio"])

Session = Annotated[AsyncSession, Depends(get_session)]

MAX_CAPSULES = 12
CAPSULE_NAME_MAX = 30
PAGE_DEFAULT = 30
PAGE_MAX = 60
# La media complessiva di un'altra persona si mostra solo se mescola almeno 3 fit votati:
# con un fit solo sarebbe la media di quel fit, che si vede soltanto dopo averlo votato.
PUBLIC_AVERAGE_MIN_POSTS = 3


# ---------- Modelli ----------


class CapsuleOut(BaseModel):
    id: uuid.UUID
    name: str
    post_count: int


class UserStats(BaseModel):
    posts: int
    # null se non si possono vedere (account privato, poche medie, numero voti nascosto).
    average: float | None
    votes: int | None


class Relationship(BaseModel):
    # Tu verso questa persona: nessun follow, richiesta in attesa, la segui.
    following: FollowState
    # Questa persona ti segue (richiesta accettata).
    follows_you: bool


class UserOut(BaseModel):
    nickname: str
    bio: str | None
    account_type: Literal["private", "business"]
    is_self: bool
    can_view_posts: bool
    styles: list[StyleRef]
    stats: UserStats
    capsules: list[CapsuleOut]
    followers: int
    following: int
    relationship: Relationship
    # Solo sul proprio profilo: richieste di follow da accettare.
    pending_requests: int | None = None
    # Account Business: i siti del negozio verificati.
    verified_domains: list[str] = []


class PortfolioTile(BaseModel):
    id: uuid.UUID
    status: Literal["processing", "active", "style_rejected", "hidden_moderation", "deleted"]
    style: StyleRef
    caption: str | None
    capsule_id: uuid.UUID | None
    media_count: int
    # Prima foto del carosello.
    photo: MediaOut | None
    # Il tuo voto; media e numero di voti con le stesse regole del post.
    mine: int | None
    average: float | None
    vote_count: int | None


class PortfolioPage(BaseModel):
    items: list[PortfolioTile]
    next_cursor: str | None
    # Il primo fit del portfolio (la copertina), anche quando la pagina è filtrata.
    cover_id: uuid.UUID | None


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    post_id: uuid.UUID
    # Il fit che deve precedere `post_id`; null = in testa (diventa la copertina).
    after_id: uuid.UUID | None


class CapsuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)


# ---------- Chi guarda chi ----------


def _visible(viewer: Profile) -> dict[str, Any]:
    return {"viewer": viewer.id, "adult": viewer.is_adult}


def _avg(wsum: float | Decimal, wcount: float | Decimal) -> float | None:
    return round(float(wsum) / float(wcount), 1) if wcount else None


# ---------- Profilo ----------


@router.get("/users/{nickname}", response_model=UserOut)
async def get_user(nickname: str, viewer: CurrentProfile, session: Session) -> UserOut:
    target = await find_person(session, viewer, nickname)
    params = {**_visible(viewer), "author": target.id}
    stats = (
        (
            await session.execute(
                text(
                    f"""select count(*) as posts,
                               coalesce(sum(st.vote_count), 0) as votes,
                               coalesce(sum(st.vote_wsum), 0) as wsum,
                               coalesce(sum(st.vote_wcount), 0) as wcount,
                               count(*) filter (where st.vote_count > 0) as voted_posts
                          from app.posts p
                          join app.profiles a on a.id = p.author_id
                          join app.styles s on s.id = p.style_id
                          left join app.post_stats st on st.post_id = p.id
                         where p.author_id = :author and {POST_VISIBLE_SQL}"""
                ),
                params,
            )
        )
        .mappings()
        .one()
    )
    own, can_view = bool(target.is_self), bool(target.can_view)
    average = _avg(stats["wsum"], stats["wcount"])
    if not own and (not can_view or stats["voted_posts"] < PUBLIC_AVERAGE_MIN_POSTS):
        average = None
    votes = int(stats["votes"]) if own or (can_view and not target.hide_vote_count) else None

    styles: list[StyleRef] = []
    capsules: list[CapsuleOut] = []
    if can_view:
        styles = [
            StyleRef(slug=r["slug"], name=r["name"], tone=r["tone"])
            for r in (
                await session.execute(
                    text(
                        f"""select s.slug, s.name, s.tone from app.style_memberships m
                              join app.styles s on s.id = m.style_id
                             where m.user_id = :author and {VISIBLE_STYLE_SQL}
                             order by m.joined_at, s.sort_order"""
                    ),
                    params,
                )
            ).mappings()
        ]
        capsules = await _capsules(session, viewer, target.id, include_empty=own)
    counts = (
        await session.execute(
            text(
                """select
                     (select count(*) from app.follows f join app.profiles p on p.id = f.follower_id
                       where f.followee_id = :id and f.status = 'accepted'
                         and p.status = 'active') as followers,
                     (select count(*) from app.follows f join app.profiles p on p.id = f.followee_id
                       where f.follower_id = :id and f.status = 'accepted'
                         and p.status = 'active') as following,
                     (select count(*) from app.follows f
                       where f.followee_id = :id and f.status = 'pending') as pending"""
            ),
            {"id": target.id},
        )
    ).one()
    domains: list[str] = []
    if target.account_type == "business":
        domains = list(
            (
                await session.execute(
                    text(
                        """select domain from app.business_domains
                            where user_id = :id and verified_at is not null order by domain"""
                    ),
                    {"id": target.id},
                )
            ).scalars()
        )
    return UserOut(
        verified_domains=domains,
        followers=int(counts[0]),
        following=int(counts[1]),
        pending_requests=int(counts[2]) if own else None,
        relationship=Relationship(following=target.following, follows_you=target.follows_you),
        nickname=target.nickname,
        bio=target.bio,
        account_type=target.account_type,
        is_self=own,
        can_view_posts=can_view,
        styles=styles,
        stats=UserStats(posts=int(stats["posts"]), average=average, votes=votes),
        capsules=capsules,
    )


async def _capsules(
    session: AsyncSession, viewer: Profile, owner: uuid.UUID, *, include_empty: bool
) -> list[CapsuleOut]:
    rows = (
        await session.execute(
            text(
                f"""select c.id, c.name, count(p.id) as post_count
                      from app.capsules c
                      left join (app.posts p
                                 join app.profiles a on a.id = p.author_id
                                 join app.styles s on s.id = p.style_id)
                        on p.capsule_id = c.id and {POST_VISIBLE_SQL}
                     where c.owner_id = :owner
                     group by c.id
                     order by c.position, c.created_at"""
            ),
            {**_visible(viewer), "owner": owner},
        )
    ).mappings()
    return [
        CapsuleOut(id=r["id"], name=r["name"], post_count=int(r["post_count"]))
        for r in rows
        if include_empty or r["post_count"] > 0
    ]


# ---------- Griglia ----------


def _encode_cursor(rank: str, post_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{rank}|{post_id}".encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        rank, post_id = raw.split("|")
        if not re.fullmatch(r"[0-9A-Za-z]{1,64}", rank):
            raise ValueError(rank)
        return rank, uuid.UUID(post_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ApiError(400, "portfolio.invalid_cursor", "Cursore non valido") from exc


@router.get("/users/{nickname}/posts", response_model=PortfolioPage)
async def get_user_posts(
    nickname: str,
    viewer: CurrentProfile,
    session: Session,
    capsule: uuid.UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> PortfolioPage:
    target = await find_person(session, viewer, nickname)
    if not target.can_view:
        raise ApiError(403, "profile.private", "Questo account è privato")
    if capsule is not None:
        owner = await session.scalar(
            text("select owner_id from app.capsules where id = :id"), {"id": capsule}
        )
        if owner != target.id:
            raise ApiError(404, "capsule.not_found", "Capsula non trovata")
    after = _decode_cursor(cursor) if cursor else None
    params: dict[str, Any] = {
        **_visible(viewer),
        "author": target.id,
        "capsule": capsule,
        "r": after[0] if after else None,
        "cid": after[1] if after else None,
        "limit": limit + 1,
        "k": voter_key(viewer.id),
    }
    base = f"""from app.posts p
                 join app.profiles a on a.id = p.author_id
                 join app.styles s on s.id = p.style_id
                where p.author_id = :author and {POST_VISIBLE_SQL}"""
    rows = (
        (
            await session.execute(
                text(
                    f"""select p.id, p.status::text as status, p.caption, p.capsule_id,
                               p.portfolio_rank, s.slug, s.name, s.tone, a.hide_vote_count,
                               coalesce(st.vote_count, 0) as vote_count,
                               coalesce(st.vote_wsum, 0) as vote_wsum,
                               coalesce(st.vote_wcount, 0) as vote_wcount,
                               v.score as mine,
                               m.width, m.height, m.blurhash, m.upload_id, m.variants,
                               (select count(*) from app.post_media mm
                                 where mm.post_id = p.id) as media_count
                          from app.posts p
                          join app.profiles a on a.id = p.author_id
                          join app.styles s on s.id = p.style_id
                          left join app.post_stats st on st.post_id = p.id
                          left join app.votes v on v.post_id = p.id and v.voter_key = :k
                          left join app.post_media m on m.post_id = p.id and m.position = 0
                         where p.author_id = :author and {POST_VISIBLE_SQL}
                           and (cast(:capsule as uuid) is null or p.capsule_id = :capsule)
                           and (cast(:r as text) is null
                                or (p.portfolio_rank, p.id)
                                   < (cast(:r as text) collate "C", cast(:cid as uuid)))
                         order by p.portfolio_rank desc, p.id desc
                         limit :limit"""
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    cover_id = await session.scalar(
        text(f"select p.id {base} order by p.portfolio_rank desc, p.id desc limit 1"),
        params,
    )
    own = bool(target.is_self)
    page = rows[:limit]
    return PortfolioPage(
        items=[_tile(row, own) for row in page],
        next_cursor=_encode_cursor(str(page[-1]["portfolio_rank"]), page[-1]["id"])
        if len(rows) > limit
        else None,
        cover_id=cover_id,
    )


def _tile(row: Any, own: bool) -> PortfolioTile:
    reveal = own or row["mine"] is not None
    return PortfolioTile(
        id=row["id"],
        status=row["status"],
        style=StyleRef(slug=row["slug"], name=row["name"], tone=row["tone"]),
        caption=row["caption"],
        capsule_id=row["capsule_id"],
        media_count=int(row["media_count"]),
        photo=MediaOut(
            position=0,
            width=row["width"],
            height=row["height"],
            blurhash=row["blurhash"],
            urls=media_urls(row["upload_id"], list(row["variants"])),
        )
        if row["upload_id"] is not None
        else None,
        mine=row["mine"],
        average=_avg(row["vote_wsum"], row["vote_wcount"]) if reveal else None,
        vote_count=int(row["vote_count"])
        if own or (reveal and not row["hide_vote_count"])
        else None,
    )


# ---------- Ordine e copertina ----------


async def _own_alive(session: AsyncSession, profile: Profile, post_id: uuid.UUID) -> bool:
    found = await session.scalar(
        text(
            """select 1 from app.posts
                where id = :id and author_id = :uid and status <> 'deleted'"""
        ),
        {"id": post_id, "uid": profile.id},
    )
    return found is not None


@router.put(
    "/me/portfolio/order",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("portfolio_order", 300, 3600))],
)
async def reorder(body: OrderIn, profile: CurrentProfile, session: Session) -> Response:
    try:
        if not await _own_alive(session, profile, body.post_id):
            raise ApiError(404, "post.not_found", "Post non trovato")
        if body.after_id is not None and (
            body.after_id == body.post_id or not await _own_alive(session, profile, body.after_id)
        ):
            raise ApiError(422, "portfolio.bad_position", "Posizione non valida")
        await move_after(session, profile.id, body.post_id, body.after_id)
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Capsule ----------


def _capsule_name(raw: str) -> str:
    name = clean_text(raw, field="Il nome della capsula", max_chars=CAPSULE_NAME_MAX)
    if not name:
        raise ApiError(422, "capsule.name_required", "Dai un nome alla capsula")
    return name


async def _name_taken(
    session: AsyncSession, owner: uuid.UUID, name: str, exclude: uuid.UUID | None
) -> bool:
    found = await session.scalar(
        text(
            """select 1 from app.capsules
                where owner_id = :owner and lower(name) = lower(:name)
                  and id is distinct from cast(:ex as uuid)"""
        ),
        {"owner": owner, "name": name, "ex": exclude},
    )
    return found is not None


_TAKEN = ApiError(409, "capsule.name_taken", "Hai già una capsula con questo nome")


@router.get("/me/capsules", response_model=list[CapsuleOut])
async def list_capsules(profile: CurrentProfile, session: Session) -> list[CapsuleOut]:
    return await _capsules(session, profile, profile.id, include_empty=True)


@router.post(
    "/me/capsules",
    response_model=CapsuleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("capsule_edit", 120, 3600))],
)
async def create_capsule(body: CapsuleIn, profile: CurrentProfile, session: Session) -> CapsuleOut:
    name = _capsule_name(body.name)
    try:
        await lock_portfolio(session, profile.id)  # conteggio e posizione senza gare
        count, top = (
            await session.execute(
                text(
                    """select count(*), coalesce(max(position) + 1, 0)
                         from app.capsules where owner_id = :owner"""
                ),
                {"owner": profile.id},
            )
        ).one()
        if count >= MAX_CAPSULES:
            raise ApiError(409, "capsule.limit", f"Puoi avere al massimo {MAX_CAPSULES} capsule")
        if await _name_taken(session, profile.id, name, None):
            raise _TAKEN
        capsule_id = await session.scalar(
            text(
                """insert into app.capsules (owner_id, name, position)
                   values (:owner, :name, :pos) returning id"""
            ),
            {"owner": profile.id, "name": name, "pos": top},
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _TAKEN from exc
    except BaseException:
        await session.rollback()
        raise
    return CapsuleOut(id=capsule_id, name=name, post_count=0)


async def _own_capsule(session: AsyncSession, profile: Profile, capsule_id: uuid.UUID) -> None:
    owner = await session.scalar(
        text("select owner_id from app.capsules where id = :id"), {"id": capsule_id}
    )
    if owner != profile.id:
        raise ApiError(404, "capsule.not_found", "Capsula non trovata")


@router.patch(
    "/me/capsules/{capsule_id}",
    response_model=CapsuleOut,
    dependencies=[Depends(rate_limit("capsule_edit", 120, 3600))],
)
async def rename_capsule(
    capsule_id: uuid.UUID, body: CapsuleIn, profile: CurrentProfile, session: Session
) -> CapsuleOut:
    await _own_capsule(session, profile, capsule_id)
    name = _capsule_name(body.name)
    try:
        if await _name_taken(session, profile.id, name, capsule_id):
            raise _TAKEN
        await session.execute(
            text("update app.capsules set name = :name where id = :id"),
            {"name": name, "id": capsule_id},
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _TAKEN from exc
    except BaseException:
        await session.rollback()
        raise
    found = await _capsules(session, profile, profile.id, include_empty=True)
    return next(c for c in found if c.id == capsule_id)


@router.delete(
    "/me/capsules/{capsule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("capsule_edit", 120, 3600))],
)
async def delete_capsule(
    capsule_id: uuid.UUID, profile: CurrentProfile, session: Session
) -> Response:
    await _own_capsule(session, profile, capsule_id)
    # I fit restano nel portfolio: perdono solo la capsula (on delete set null).
    await session.execute(text("delete from app.capsules where id = :id"), {"id": capsule_id})
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
