"""Post (sez. 6.4): pubblicazione con foto pronte e capi taggati, modifica, eliminazione.

Regole di autorizzazione (verificate dalla suite di test IDOR):
- un post che non puoi vedere risponde 404, uguale a un post inesistente;
- un post che vedi ma non è tuo: 403 post.not_owner su modifica/eliminazione;
- si pubblicano solo foto tue, pronte e non già usate in un altro post.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.links import normalize_shop_url
from app.media.keys import variant_key
from app.post_access import AUTHOR_SHOWN_SQL, POST_VISIBLE_SQL
from app.profiles import CurrentProfile, Profile
from app.ranking import key_now
from app.ratelimit import rate_limit
from app.redis_client import get_redis
from app.routers.media import MediaUrls, media_urls
from app.storage import get_store
from app.text_policy import clean_text

router = APIRouter(prefix="/v1/posts", tags=["posts"])

Session = Annotated[AsyncSession, Depends(get_session)]

MAX_MEDIA = 10
MAX_ITEMS = 8
CAPTION_MAX_CHARS = 140
CAPTION_MAX_LINES = 3
Currency = Literal["EUR", "USD", "GBP", "CHF"]
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
IDEMPOTENCY_TTL = 24 * 3600


# ---------- Modelli ----------


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    currency: Currency = "EUR"
    url: str | None = Field(default=None, max_length=2048)
    # Su quale foto del carosello sta il capo e dove (0-1 da sinistra/alto).
    media_position: int | None = Field(default=None, ge=0, lt=MAX_MEDIA)
    pin_x: float | None = Field(default=None, ge=0, le=1)
    pin_y: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _pins(self) -> ItemIn:
        if (self.pin_x is None) != (self.pin_y is None):
            raise ValueError("pin_x e pin_y vanno insieme")
        if self.pin_x is not None and self.media_position is None:
            raise ValueError("il punto sulla foto richiede media_position")
        return self


class PostIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: str = Field(min_length=2, max_length=40)
    caption: str | None = Field(default=None, max_length=1000)
    # Caricamenti pronti, nell'ordine del carosello.
    media: list[uuid.UUID] = Field(min_length=1, max_length=MAX_MEDIA)
    items: list[ItemIn] = Field(default_factory=list, max_length=MAX_ITEMS)


class PostPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    caption: str | None = Field(default=None, max_length=1000)
    # Sostituisce tutti i capi.
    items: list[ItemIn] | None = Field(default=None, max_length=MAX_ITEMS)
    # Cambio di stile: una sola volta per post.
    style: str | None = Field(default=None, min_length=2, max_length=40)


class StyleRef(BaseModel):
    slug: str
    name: str
    tone: str


class AuthorRef(BaseModel):
    nickname: str
    account_type: Literal["private", "business"]


class LinkOut(BaseModel):
    id: uuid.UUID
    domain: str
    status: Literal["pending", "safe", "blocked"]
    # Assente se il link è stato bloccato dai controlli.
    url: str | None


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
    # Solo per l'autore: si può ancora cambiare stile?
    restyle_available: bool | None = None


# ---------- Lettura ----------


async def _load_post(session: AsyncSession, viewer: Profile, post_id: uuid.UUID) -> Any:
    row = (
        (
            await session.execute(
                text(
                    f"""select p.id, p.status::text as status, p.caption, p.author_id,
                               p.restyle_used, p.published_at, p.created_at,
                               s.slug, s.name, s.tone,
                               a.nickname::text as nickname,
                               a.account_type::text as account_type, a.hide_prices,
                               {AUTHOR_SHOWN_SQL} as author_shown
                          from app.posts p
                          join app.profiles a on a.id = p.author_id
                          join app.styles s on s.id = p.style_id
                         where p.id = :id and {POST_VISIBLE_SQL}"""
                ),
                {"id": post_id, "viewer": viewer.id, "adult": viewer.is_adult},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "post.not_found", "Post non trovato")
    return row


async def _post_out(session: AsyncSession, viewer: Profile, row: Any) -> PostOut:
    own = row["author_id"] == viewer.id
    media_rows = (
        (
            await session.execute(
                text(
                    """select position, width, height, blurhash, upload_id, variants
                         from app.post_media where post_id = :id order by position"""
                ),
                {"id": row["id"]},
            )
        )
        .mappings()
        .all()
    )
    item_rows = (
        (
            await session.execute(
                text(
                    """select i.position, i.brand, i.name, i.price_cents, i.currency,
                              i.media_position, i.pin_x, i.pin_y,
                              l.id as link_id, l.url, l.domain, l.status::text as link_status
                         from app.post_items i left join app.links l on l.id = i.link_id
                        where i.post_id = :id order by i.position"""
                ),
                {"id": row["id"]},
            )
        )
        .mappings()
        .all()
    )
    hide_prices = row["hide_prices"] and not own

    def as_float(value: Decimal | None) -> float | None:
        return float(value) if value is not None else None

    return PostOut(
        id=row["id"],
        status=row["status"],
        style=StyleRef(slug=row["slug"], name=row["name"], tone=row["tone"]),
        author=AuthorRef(nickname=row["nickname"], account_type=row["account_type"])
        if row["author_shown"]
        else None,
        is_own=own,
        caption=row["caption"],
        media=[
            MediaOut(
                position=m["position"],
                width=m["width"],
                height=m["height"],
                blurhash=m["blurhash"],
                urls=media_urls(m["upload_id"], list(m["variants"])),
            )
            for m in media_rows
        ],
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
                )
                if i["link_id"]
                else None,
                media_position=i["media_position"],
                pin_x=as_float(i["pin_x"]),
                pin_y=as_float(i["pin_y"]),
            )
            for i in item_rows
        ],
        published_at=row["published_at"],
        created_at=row["created_at"],
        restyle_available=(not row["restyle_used"]) if own else None,
    )


# ---------- Supporto alla scrittura ----------


async def _style_id(session: AsyncSession, profile: Profile, slug: str) -> int:
    style_id = await session.scalar(
        text(
            """select id from app.styles s
                where s.slug = :slug and s.is_active
                  and (s.active_from is null or s.active_from <= current_date)
                  and (s.active_until is null or s.active_until >= current_date)
                  and (cast(:adult as boolean) or s.min_age_band <> '18_plus')"""
        ),
        {"slug": slug, "adult": profile.is_adult},
    )
    if style_id is None:
        raise ApiError(422, "style.not_found", "Stile non disponibile")
    return int(style_id)


async def _write_items(
    session: AsyncSession, post_id: uuid.UUID, items: list[ItemIn], media_count: int
) -> None:
    await session.execute(text("delete from app.post_items where post_id = :id"), {"id": post_id})
    for position, item in enumerate(items):
        if item.media_position is not None and item.media_position >= media_count:
            raise ApiError(422, "item.bad_media_position", "Il capo punta a una foto che non c'è")
        brand = clean_text(item.brand, field="Il brand", max_chars=60)
        name = clean_text(item.name, field="Il nome del capo", max_chars=80)
        if not brand or not name:
            raise ApiError(422, "item.incomplete", "Ogni capo ha bisogno di brand e nome")
        link_id = None
        if item.url:
            url, domain = normalize_shop_url(item.url)
            link_id = await session.scalar(
                text(
                    """insert into app.links (url, domain) values (:url, :domain)
                       on conflict (url) do update set url = excluded.url
                       returning id"""
                ),
                {"url": url, "domain": domain},
            )
        await session.execute(
            text(
                """insert into app.post_items
                     (post_id, position, brand, name, price_cents, currency, link_id,
                      media_position, pin_x, pin_y)
                   values (:post, :pos, :brand, :name, :price, :currency, :link,
                           :media_pos, :x, :y)"""
            ),
            {
                "post": post_id,
                "pos": position,
                "brand": brand,
                "name": name,
                "price": item.price_cents,
                "currency": item.currency,
                "link": link_id,
                "media_pos": item.media_position,
                "x": item.pin_x,
                "y": item.pin_y,
            },
        )


def _caption(raw: str | None) -> str | None:
    return clean_text(
        raw, field="La didascalia", max_chars=CAPTION_MAX_CHARS, max_lines=CAPTION_MAX_LINES
    )


# ---------- Endpoint ----------


@router.post(
    "",
    response_model=PostOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("post_create", 20, 3600))],
)
async def create_post(
    body: PostIn,
    profile: CurrentProfile,
    session: Session,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PostOut:
    if len(set(body.media)) != len(body.media):
        raise ApiError(422, "media.duplicate", "La stessa foto compare due volte")

    redis_key = None
    if idempotency_key is not None:
        if not IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise ApiError(422, "request.invalid", "Idempotency-Key non valida")
        redis_key = f"idem:post:{profile.id}:{idempotency_key}"
        claimed = await get_redis().set(redis_key, "pending", nx=True, ex=IDEMPOTENCY_TTL)
        if not claimed:
            previous = await get_redis().get(redis_key)
            if previous and previous != "pending":
                # Stessa richiesta ripetuta (rete instabile): stesso post, nessun duplicato.
                response.status_code = status.HTTP_200_OK
                row = await _load_post(session, profile, uuid.UUID(previous))
                return await _post_out(session, profile, row)
            raise ApiError(409, "request.in_progress", "Pubblicazione già in corso")

    try:
        post_id = await _insert_post(session, profile, body)
    except BaseException:
        if redis_key:
            await get_redis().delete(redis_key)
        raise
    if redis_key:
        await get_redis().set(redis_key, str(post_id), ex=IDEMPOTENCY_TTL)
    row = await _load_post(session, profile, post_id)
    return await _post_out(session, profile, row)


async def _insert_post(session: AsyncSession, profile: Profile, body: PostIn) -> uuid.UUID:
    style_id = await _style_id(session, profile, body.style)
    caption = _caption(body.caption)
    try:
        # Le foto si "prenotano" con un solo UPDATE: due post in parallelo non possono
        # usare la stessa foto.
        claimed = (
            (
                await session.execute(
                    text(
                        """update app.media_uploads set attached_at = now()
                            where id = any(:ids) and owner_id = :uid and status = 'ready'
                              and attached_at is null
                        returning id, width, height, blurhash, sha256, phash, variants"""
                    ),
                    {"ids": body.media, "uid": profile.id},
                )
            )
            .mappings()
            .all()
        )
        if len(claimed) != len(body.media):
            raise ApiError(
                422, "media.unavailable", "Una o più foto non sono pronte o non sono tue"
            )
        by_id = {m["id"]: m for m in claimed}
        post_id = uuid.uuid4()
        await session.execute(
            text(
                """insert into app.posts
                     (id, author_id, style_id, caption, status, portfolio_rank, published_at)
                   values (:id, :uid, :style, :caption, 'active', :rank, now())"""
            ),
            {
                "id": post_id,
                "uid": profile.id,
                "style": style_id,
                "caption": caption,
                "rank": key_now(),
            },
        )
        for position, upload_id in enumerate(body.media):
            m = by_id[upload_id]
            await session.execute(
                text(
                    """insert into app.post_media
                         (post_id, position, storage_key, width, height, blurhash, sha256,
                          phash, upload_id, variants)
                       values (:post, :pos, :key, :w, :h, :bh, :sha, :ph, :upload, :variants)"""
                ),
                {
                    "post": post_id,
                    "pos": position,
                    "key": f"media/{upload_id}",
                    "w": m["width"],
                    "h": m["height"],
                    "bh": m["blurhash"],
                    "sha": m["sha256"],
                    "ph": m["phash"],
                    "upload": upload_id,
                    "variants": list(m["variants"]),
                },
            )
        await _write_items(session, post_id, body.items, len(body.media))
        await session.execute(
            text("insert into app.post_stats (post_id) values (:id)"), {"id": post_id}
        )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return post_id


@router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: uuid.UUID, profile: CurrentProfile, session: Session) -> PostOut:
    row = await _load_post(session, profile, post_id)
    return await _post_out(session, profile, row)


async def _own_post(session: AsyncSession, profile: Profile, post_id: uuid.UUID) -> Any:
    row = await _load_post(session, profile, post_id)  # 404 se non lo vedi
    if row["author_id"] != profile.id:
        raise ApiError(403, "post.not_owner", "Puoi modificare solo i tuoi post")
    return row


@router.patch(
    "/{post_id}",
    response_model=PostOut,
    dependencies=[Depends(rate_limit("post_edit", 60, 3600))],
)
async def update_post(
    post_id: uuid.UUID, body: PostPatch, profile: CurrentProfile, session: Session
) -> PostOut:
    row = await _own_post(session, profile, post_id)
    try:
        await session.execute(
            text("select 1 from app.posts where id = :id for update"), {"id": post_id}
        )
        if "caption" in body.model_fields_set:
            await session.execute(
                text("update app.posts set caption = :c where id = :id"),
                {"c": _caption(body.caption), "id": post_id},
            )
        if body.items is not None:
            media_count = await session.scalar(
                text("select count(*) from app.post_media where post_id = :id"), {"id": post_id}
            )
            await _write_items(session, post_id, body.items, int(media_count or 0))
        if body.style is not None and body.style != row["slug"]:
            if row["restyle_used"]:
                raise ApiError(
                    409, "post.restyle_used", "Lo stile di un post si cambia una volta sola"
                )
            style_id = await _style_id(session, profile, body.style)
            await session.execute(
                text(
                    """update app.posts set style_id = :s, restyle_used = true,
                              status = case when status = 'style_rejected' then 'active'
                                            else status end
                        where id = :id"""
                ),
                {"s": style_id, "id": post_id},
            )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return await _post_out(session, profile, await _load_post(session, profile, post_id))


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: uuid.UUID, profile: CurrentProfile, session: Session) -> Response:
    await _own_post(session, profile, post_id)
    media = (
        (
            await session.execute(
                text(
                    """select upload_id, variants from app.post_media
                        where post_id = :id and upload_id is not null"""
                ),
                {"id": post_id},
            )
        )
        .mappings()
        .all()
    )
    await session.execute(
        text(
            """update app.posts set status = 'deleted', deleted_at = now(), caption = null
                where id = :id"""
        ),
        {"id": post_id},
    )
    # Capi e foto spariscono subito; resta solo la riga del post (per i conteggi storici).
    await session.execute(text("delete from app.post_items where post_id = :id"), {"id": post_id})
    await session.execute(text("delete from app.post_media where post_id = :id"), {"id": post_id})
    await session.execute(
        text("delete from app.media_uploads where id = any(:ids)"),
        {"ids": [m["upload_id"] for m in media]},
    )
    await session.commit()
    keys = [variant_key(m["upload_id"], w) for m in media for w in m["variants"]]
    if keys:
        await get_store().delete(*keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
