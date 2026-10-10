"""Come appare un post a chi lo guarda: modelli di risposta e caricamento IN BLOCCO
(una manciata di query per una pagina intera di feed, mai una query per post)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.avatars import AvatarOut, avatar_out
from app.links import go_url
from app.post_access import AUTHOR_SHOWN_SQL, POST_VISIBLE_SQL
from app.profiles import Profile
from app.routers.media import MediaUrls, media_urls
from app.votes import (
    CONFIRM_SAMPLE,
    AverageNote,
    average_note,
    shown_average,
    style_match,
    voter_key,
)


class StyleRef(BaseModel):
    slug: str
    name: str
    tone: str


class AuthorRef(BaseModel):
    nickname: str
    account_type: Literal["private", "business"]
    # Foto profilo (seduta 27), solo quando l'autore è mostrato.
    avatar: AvatarOut | None = None


class LinkOut(BaseModel):
    id: uuid.UUID
    domain: str
    # pending: non ancora controllato; broken: la pagina non esiste più.
    status: Literal["pending", "safe", "blocked", "broken"]
    # Assente se il link è stato bloccato dai controlli.
    url: str | None
    # Da aprire nell'app: passa dal redirect firmato (controllo al momento del clic).
    go_url: str | None = None
    # Il sito appartiene all'autore del fit (account Business con dominio verificato).
    verified: bool = False


class ItemOut(BaseModel):
    position: int
    brand: str
    name: str
    # Assente se l'autore nasconde i prezzi (tranne che a sé stesso).
    price_cents: int | None
    currency: str
    link: LinkOut | None
    media_position: int | None
    pin_x: float | None
    pin_y: float | None


class MediaOut(BaseModel):
    position: int
    width: int
    height: int
    blurhash: str
    urls: MediaUrls


class VoteSummary(BaseModel):
    # Il tuo voto (null se non hai votato).
    mine: int | None
    my_style_confirm: bool | None
    # Media e numero si vedono solo dopo aver votato (o se il post è tuo): nessuno si fa
    # influenzare dal voto degli altri. vote_count è null anche se l'autore lo nasconde.
    # Sono i valori PUBBLICATI (aggiornati ogni ora, la media da 5 voti): seduta 22.
    average: float | None
    vote_count: int | None
    # Perché la media manca (se manca): "few_votes" (meno di 5) o "next_update" (in arrivo).
    average_note: AverageNote | None = None
    # Ultimo aggiornamento dei valori pubblicati.
    stats_updated_at: datetime | None = None
    # Quota di conferme dello stile (0-1), quando le risposte sono abbastanza.
    style_match: float | None
    # Mostrare la domanda "È davvero <stile>?" insieme al voto.
    ask_style_confirm: bool


class PostOut(BaseModel):
    id: uuid.UUID
    status: Literal["processing", "active", "style_rejected", "hidden_moderation", "deleted"]
    style: StyleRef
    # Assente quando il post è anonimo per chi guarda.
    author: AuthorRef | None
    is_own: bool
    caption: str | None
    media: list[MediaOut]
    items: list[ItemOut]
    published_at: datetime | None
    created_at: datetime
    # Solo per l'autore: si può ancora cambiare stile? In quale capsula è?
    restyle_available: bool | None = None
    capsule_id: uuid.UUID | None = None
    vote: VoteSummary


def _as_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _summary(viewer: Profile, row: Any) -> VoteSummary:
    own = row["author_id"] == viewer.id
    reveal = own or row["mine"] is not None
    average = shown_average(row["shown_wsum"], row["shown_wcount"]) if reveal else None
    show_count = reveal and (own or not row["hide_vote_count"])
    # La domanda sullo stile va ai primi votanti: qui contano i valori in tempo reale.
    sampling = row["confirm_yes"] + row["confirm_no"] < CONFIRM_SAMPLE
    return VoteSummary(
        mine=row["mine"],
        my_style_confirm=row["my_confirm"],
        average=average,
        vote_count=row["shown_count"] if show_count else None,
        average_note=average_note(row["shown_count"], average) if reveal else None,
        stats_updated_at=row["shown_at"] if reveal else None,
        style_match=(
            style_match(row["shown_confirm_yes"], row["shown_confirm_no"]) if reveal else None
        ),
        ask_style_confirm=not own
        and row["mine"] is None
        and row["status"] == "active"
        and sampling,
    )


async def posts_out(
    session: AsyncSession, viewer: Profile, post_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PostOut]:
    """Post visibili a `viewer` tra quelli chiesti (gli altri mancano dal risultato)."""
    if not post_ids:
        return {}
    params = {"ids": post_ids, "viewer": viewer.id, "adult": viewer.is_adult}
    rows = (
        (
            await session.execute(
                text(
                    f"""select p.id, p.status::text as status, p.caption, p.author_id,
                               p.restyle_used, p.published_at, p.created_at, p.capsule_id,
                               s.slug, s.name, s.tone,
                               a.nickname::text as nickname,
                               a.account_type::text as account_type, a.hide_prices,
                               a.hide_vote_count,
                               au.id as avatar_id, au.variants as avatar_variants,
                               au.blurhash as avatar_blurhash,
                               {AUTHOR_SHOWN_SQL} as author_shown,
                               coalesce(st.shown_count, 0) as shown_count,
                               coalesce(st.shown_wsum, 0) as shown_wsum,
                               coalesce(st.shown_wcount, 0) as shown_wcount,
                               coalesce(st.shown_confirm_yes, 0) as shown_confirm_yes,
                               coalesce(st.shown_confirm_no, 0) as shown_confirm_no,
                               st.shown_at,
                               coalesce(st.confirm_yes, 0) as confirm_yes,
                               coalesce(st.confirm_no, 0) as confirm_no,
                               v.score as mine, v.style_confirm as my_confirm
                          from app.posts p
                          join app.profiles a on a.id = p.author_id
                          left join app.media_uploads au on au.id = a.avatar_upload_id
                          join app.styles s on s.id = p.style_id
                          left join app.post_stats st on st.post_id = p.id
                          left join app.votes v on v.post_id = p.id and v.voter_key = :k
                         where p.id = any(:ids) and {POST_VISIBLE_SQL}"""
                ),
                {**params, "k": voter_key(viewer.id)},
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        return {}
    visible = [r["id"] for r in rows]
    media: dict[uuid.UUID, list[MediaOut]] = defaultdict(list)
    for m in (
        await session.execute(
            text(
                """select post_id, position, width, height, blurhash, upload_id, variants
                     from app.post_media where post_id = any(:ids) order by post_id, position"""
            ),
            {"ids": visible},
        )
    ).mappings():
        media[m["post_id"]].append(
            MediaOut(
                position=m["position"],
                width=m["width"],
                height=m["height"],
                blurhash=m["blurhash"],
                urls=media_urls(m["upload_id"], list(m["variants"])),
            )
        )
    items: dict[uuid.UUID, list[Any]] = defaultdict(list)
    for i in (
        await session.execute(
            text(
                """select i.post_id, i.position, i.brand, i.name, i.price_cents, i.currency,
                          i.media_position, i.pin_x, i.pin_y,
                          l.id as link_id, l.url, l.domain, l.status::text as link_status,
                          exists (select 1 from app.business_domains bd
                                    join app.posts p on p.id = i.post_id
                                   where bd.user_id = p.author_id and bd.verified_at is not null
                                     and (l.domain = bd.domain or l.domain like '%.' || bd.domain))
                            as link_verified
                     from app.post_items i left join app.links l on l.id = i.link_id
                    where i.post_id = any(:ids) order by i.post_id, i.position"""
            ),
            {"ids": visible},
        )
    ).mappings():
        items[i["post_id"]].append(i)

    out: dict[uuid.UUID, PostOut] = {}
    for row in rows:
        own = row["author_id"] == viewer.id
        hide_prices = row["hide_prices"] and not own
        out[row["id"]] = PostOut(
            id=row["id"],
            status=row["status"],
            style=StyleRef(slug=row["slug"], name=row["name"], tone=row["tone"]),
            author=AuthorRef(
                nickname=row["nickname"],
                account_type=row["account_type"],
                avatar=avatar_out(row["avatar_id"], row["avatar_variants"], row["avatar_blurhash"]),
            )
            if row["author_shown"]
            else None,
            is_own=own,
            caption=row["caption"],
            media=media[row["id"]],
            items=[
                ItemOut(
                    position=i["position"],
                    brand=i["brand"],
                    name=i["name"],
                    price_cents=None if hide_prices else i["price_cents"],
                    currency=i["currency"],
                    link=LinkOut(
                        id=i["link_id"],
                        domain=i["domain"],
                        status=i["link_status"],
                        url=None if i["link_status"] == "blocked" else i["url"],
                        go_url=None
                        if i["link_status"] == "blocked"
                        else go_url(i["link_id"], row["id"], i["position"]),
                        verified=i["link_verified"],
                    )
                    if i["link_id"]
                    else None,
                    media_position=i["media_position"],
                    pin_x=_as_float(i["pin_x"]),
                    pin_y=_as_float(i["pin_y"]),
                )
                for i in items[row["id"]]
            ],
            published_at=row["published_at"],
            created_at=row["created_at"],
            restyle_available=(not row["restyle_used"]) if own else None,
            capsule_id=row["capsule_id"] if own else None,
            vote=_summary(viewer, row),
        )
    return out


async def post_out(session: AsyncSession, viewer: Profile, post_id: uuid.UUID) -> PostOut | None:
    return (await posts_out(session, viewer, [post_id])).get(post_id)
