"""Stili: elenco e ricerca, pagina dello stile, entrare e uscire (sez. 6.3).

Regole:
- i 16-17enni non vedono e non possono entrare negli stili 18+ (per loro "non esistono");
- gli stili fuori stagione o disattivati non si vedono;
- si resta sempre in almeno uno stile: il feed è fatto dei tuoi stili.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.profiles import VISIBLE_STYLE_SQL, CurrentProfile, Profile
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1", tags=["styles"])

Session = Annotated[AsyncSession, Depends(get_session)]

MAX_MEMBERSHIPS = 30
SEARCH_MAX_LENGTH = 40
# Soglia di somiglianza per la ricerca "tollerante" (refusi, parole parziali).
WORD_SIMILARITY = 0.35


StyleCategory = Literal["stili", "sport", "accessori", "beauty", "sottoculture", "occasioni"]


class StyleCard(BaseModel):
    slug: str
    name: str
    tagline: str
    tone: str
    min_age_band: Literal["16_17", "18_plus"]
    seasonal: bool
    active_until: date | None
    member_count: int
    joined: bool
    category: StyleCategory = "stili"


class StyleDetail(StyleCard):
    # Fit pubblicati nell'ultima settimana (la griglia dei post arriva con il feed).
    posts_last_7_days: int


class StyleList(BaseModel):
    items: list[StyleCard]
    total: int


_CARD_COLUMNS = """
    s.slug, s.name, s.tagline, s.tone, s.min_age_band::text as min_age_band,
    (s.active_until is not null) as seasonal, s.active_until,
    (select count(*) from app.style_memberships c where c.style_id = s.id)::int as member_count,
    exists(select 1 from app.style_memberships j
            where j.style_id = s.id and j.user_id = :uid) as joined,
    s.category
"""
# I più seguiti per primi (seduta 29), poi l'ordine scelto dallo staff.
_POPULAR = "(select count(*) from app.style_memberships c where c.style_id = s.id) desc"


def _params(profile: Profile, **extra: Any) -> dict[str, Any]:
    return {"uid": profile.id, "adult": profile.is_adult, **extra}


async def _card(session: AsyncSession, profile: Profile, slug: str) -> StyleCard:
    row = (
        (
            await session.execute(
                text(
                    f"select {_CARD_COLUMNS} from app.styles s "
                    f"where s.slug = :slug and {VISIBLE_STYLE_SQL}"
                ),
                _params(profile, slug=slug),
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        # Stessa risposta per "non esiste", "fuori stagione" e "riservato ai 18+".
        raise ApiError(404, "style.not_found", "Stile non trovato")
    return StyleCard.model_validate(dict(row))


def _like_pattern(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/styles", response_model=StyleList)
async def list_styles(
    profile: CurrentProfile,
    session: Session,
    q: Annotated[str | None, Query(max_length=SEARCH_MAX_LENGTH)] = None,
    category: StyleCategory | None = None,
) -> StyleList:
    query = " ".join((q or "").split())  # spazi multipli e a capo -> uno spazio
    # Filtro per categoria: valore controllato dal Literal, passato come parametro.
    in_category = "and (cast(:category as text) is null or s.category = :category)"
    if not query:
        sql = (
            f"select {_CARD_COLUMNS} from app.styles s where {VISIBLE_STYLE_SQL} {in_category} "
            f"order by {_POPULAR}, s.sort_order, s.id"
        )
        params = _params(profile, category=category)
    else:
        # Prima chi contiene il testo (anche senza accenti: "gala" trova "Galà"),
        # poi le somiglianze per refusi ("jppo" trova "Jappo").
        sql = f"""
            select {_CARD_COLUMNS} from app.styles s
             where {VISIBLE_STYLE_SQL} {in_category}
               and (app.fold(s.name || ' ' || s.tagline) like app.fold(:pattern) escape '\\'
                    or word_similarity(app.fold(:q), app.fold(s.name || ' ' || s.tagline))
                       >= :threshold)
             order by (app.fold(s.name) like app.fold(:prefix) escape '\\') desc,
                      (app.fold(s.name || ' ' || s.tagline) like app.fold(:pattern) escape '\\')
                        desc,
                      word_similarity(app.fold(:q), app.fold(s.name || ' ' || s.tagline)) desc,
                      {_POPULAR}, s.sort_order, s.id
        """
        params = _params(
            profile,
            category=category,
            q=query,
            pattern=_like_pattern(query),
            prefix=_like_pattern(query)[1:],
            threshold=WORD_SIMILARITY,
        )
    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [StyleCard.model_validate(dict(r)) for r in rows]
    return StyleList(items=items, total=len(items))


@router.get("/me/styles", response_model=StyleList)
async def my_styles(profile: CurrentProfile, session: Session) -> StyleList:
    rows = (
        (
            await session.execute(
                text(
                    f"""select {_CARD_COLUMNS} from app.styles s
                          join app.style_memberships m on m.style_id = s.id and m.user_id = :uid
                         where {VISIBLE_STYLE_SQL}
                         order by m.joined_at, s.sort_order"""
                ),
                _params(profile),
            )
        )
        .mappings()
        .all()
    )
    items = [StyleCard.model_validate(dict(r)) for r in rows]
    return StyleList(items=items, total=len(items))


@router.get("/styles/{slug}", response_model=StyleDetail)
async def get_style(slug: str, profile: CurrentProfile, session: Session) -> StyleDetail:
    card = await _card(session, profile, slug)
    recent = await session.scalar(
        text(
            """select count(*) from app.posts p join app.styles s on s.id = p.style_id
                where s.slug = :slug and p.status = 'active'
                  and p.published_at > now() - interval '7 days'"""
        ),
        {"slug": slug},
    )
    return StyleDetail(**card.model_dump(), posts_last_7_days=int(recent or 0))


async def _lock_memberships(session: AsyncSession, profile: Profile) -> None:
    # Le modifiche agli stili di una persona passano una alla volta: due "esci" in parallelo
    # non possono lasciarla senza stili.
    await session.execute(
        text("select 1 from app.profiles where id = :uid for update"), {"uid": profile.id}
    )


@router.put(
    "/styles/{slug}/membership",
    response_model=StyleCard,
    dependencies=[Depends(rate_limit("style_membership", 60, 3600))],
)
async def join_style(slug: str, profile: CurrentProfile, session: Session) -> StyleCard:
    card = await _card(session, profile, slug)
    if card.joined:
        return card
    await _lock_memberships(session, profile)
    count = await session.scalar(
        text("select count(*) from app.style_memberships where user_id = :uid"),
        {"uid": profile.id},
    )
    if int(count or 0) >= MAX_MEMBERSHIPS:
        await session.rollback()
        raise ApiError(409, "style.limit", f"Puoi seguire al massimo {MAX_MEMBERSHIPS} stili")
    await session.execute(
        text(
            """insert into app.style_memberships (user_id, style_id)
               select :uid, id from app.styles where slug = :slug
               on conflict do nothing"""
        ),
        {"uid": profile.id, "slug": slug},
    )
    await session.commit()
    return await _card(session, profile, slug)


@router.delete(
    "/styles/{slug}/membership",
    response_model=StyleCard,
    dependencies=[Depends(rate_limit("style_membership", 60, 3600))],
)
async def leave_style(slug: str, profile: CurrentProfile, session: Session) -> StyleCard:
    card = await _card(session, profile, slug)
    if not card.joined:
        return card
    await _lock_memberships(session, profile)
    others = await session.scalar(
        text(
            f"""select count(*) from app.style_memberships m join app.styles s on s.id = m.style_id
                 where m.user_id = :uid and s.slug <> :slug and {VISIBLE_STYLE_SQL}"""
        ),
        _params(profile, slug=slug),
    )
    if int(others or 0) == 0:
        await session.rollback()
        raise ApiError(
            409, "style.last_membership", "Resta almeno in uno stile: il tuo feed è fatto di questi"
        )
    await session.execute(
        text(
            """delete from app.style_memberships m using app.styles s
                where s.id = m.style_id and m.user_id = :uid and s.slug = :slug"""
        ),
        {"uid": profile.id, "slug": slug},
    )
    await session.commit()
    return await _card(session, profile, slug)
