"""Stili proposti dalla community (seduta 30).

- Chi non trova uno stile lo propone (nome, categoria, descrizione facoltativa): la proposta parte
  con la sua richiesta. Se esiste già uno stile con quel nome si risponde 409 `style.exists` con
  lo slug; se esiste già una proposta aperta con quel nome, la richiesta va su quella.
- Gli altri la "vogliono" anche loro (una richiesta a testa, si può ritirare).
- Alla soglia (`style_proposal_threshold`) lo stile si attiva da solo, nella categoria scelta,
  e chi l'ha chiesto ci entra (se non ha già il massimo di stili).
- I nomi passano dalle stesse regole dei testi (caratteri, parole offensive). Lo staff può
  respingere una proposta aperta o spegnere lo stile dal pannello.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.i18n import N_
from app.profiles import CurrentProfile, Profile
from app.ratelimit import rate_limit
from app.routers.styles import MAX_MEMBERSHIPS, StyleCategory
from app.staff import CurrentStaff, audit
from app.text_policy import clean_text

router = APIRouter(prefix="/v1", tags=["styles"])
Session = Annotated[AsyncSession, Depends(get_session)]

NAME_MAX = 30
TAGLINE_MAX = 60
# Proposte aperte a testa: evita che una persona riempia l'elenco.
MAX_OPEN_PER_USER = 3
# Toni per gli stili nati da una proposta (scuri, leggibili con il testo chiaro sopra).
TONES = ["#2F3A4A", "#3A2F4A", "#4A2F3A", "#2F4A3A", "#4A3F2A", "#2A3F4A", "#3F2A2A", "#2A2A3F"]


class ProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    category: StyleCategory
    tagline: str | None = Field(default=None, max_length=120)


class ProposalOut(BaseModel):
    id: uuid.UUID
    name: str
    tagline: str | None
    category: StyleCategory
    supports: int
    threshold: int
    supported: bool
    mine: bool
    status: Literal["open", "approved", "rejected"]
    # Slug dello stile, quando la proposta è stata approvata.
    style: str | None
    created_at: datetime


class ProposalList(BaseModel):
    items: list[ProposalOut]
    threshold: int


class ProposalCreated(BaseModel):
    proposal: ProposalOut
    # false: c'era già una proposta aperta con questo nome e la richiesta è andata su quella.
    created: bool


def name_key(name: str) -> str:
    """Chiave del nome: senza accenti, minuscole, solo lettere e numeri ("Avant-Garde" ==
    "avant garde")."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def slug_for(name: str) -> str:
    return (name_key(name).replace(" ", "-") or "stile")[:36].strip("-")


def _threshold() -> int:
    return get_settings().style_proposal_threshold


_SELECT = """
    select p.id, p.name, p.tagline, p.category, p.status::text as status, p.created_at,
           s.slug as style,
           (select count(*) from app.style_proposal_supports x where x.proposal_id = p.id)::int
             as supports,
           exists(select 1 from app.style_proposal_supports x
                   where x.proposal_id = p.id and x.user_id = :uid) as supported,
           coalesce(p.created_by = :uid, false) as mine
      from app.style_proposals p
      left join app.styles s on s.id = p.style_id
"""


def _out(row: dict) -> ProposalOut:  # type: ignore[type-arg]
    return ProposalOut(**row, threshold=_threshold())


async def _one(session: AsyncSession, profile: Profile, proposal_id: uuid.UUID) -> ProposalOut:
    row = (
        (
            await session.execute(
                text(_SELECT + " where p.id = :id"), {"uid": profile.id, "id": proposal_id}
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["status"] == "rejected":
        raise ApiError(404, "proposal.not_found", "Proposta non trovata")
    return _out(dict(row))


@router.get("/style-proposals", response_model=ProposalList)
async def list_proposals(
    profile: CurrentProfile,
    session: Session,
    q: Annotated[str | None, Query(max_length=40)] = None,
) -> ProposalList:
    """Proposte aperte, dalle più richieste."""
    key = name_key(q or "")
    rows = (
        (
            await session.execute(
                text(
                    _SELECT
                    + """ where p.status = 'open'
                            and (cast(:key as text) = '' or p.name_key like '%' || :key || '%')
                          order by supports desc, p.created_at desc
                          limit 100"""
                ),
                {"uid": profile.id, "key": key},
            )
        )
        .mappings()
        .all()
    )
    return ProposalList(items=[_out(dict(r)) for r in rows], threshold=_threshold())


@router.post(
    "/style-proposals",
    response_model=ProposalCreated,
    dependencies=[Depends(rate_limit("style_proposal", 10, 86400))],
)
async def propose(body: ProposalIn, profile: CurrentProfile, session: Session) -> ProposalCreated:
    name = clean_text(body.name, field=N_("Il nome dello stile"), max_chars=NAME_MAX)
    tagline = clean_text(body.tagline, field=N_("La descrizione"), max_chars=TAGLINE_MAX)
    key = name_key(name or "")
    if not name or len(key) < 2:
        raise ApiError(422, "proposal.bad_name", "Scrivi un nome di almeno due lettere")

    existing = await session.scalar(
        text(
            """select slug from app.styles
                where is_active and (slug = :slug or app.fold(name) = app.fold(:name))
                limit 1"""
        ),
        {"slug": slug_for(name), "name": name},
    )
    if existing:
        raise ApiError(409, "style.exists", "Questo stile c'è già", extra={"slug": existing})

    same = await session.scalar(
        text("select id from app.style_proposals where status = 'open' and name_key = :key"),
        {"key": key},
    )
    if same is not None:
        return ProposalCreated(proposal=await _support(session, profile, same), created=False)

    open_mine = await session.scalar(
        text(
            """select count(*) from app.style_proposals
                where created_by = :uid and status = 'open'"""
        ),
        {"uid": profile.id},
    )
    if int(open_mine or 0) >= MAX_OPEN_PER_USER:
        raise ApiError(
            409,
            "proposal.limit",
            "Hai già {max} proposte aperte: aspetta che arrivino alla soglia",
            params={"max": MAX_OPEN_PER_USER},
        )
    try:
        proposal_id = await session.scalar(
            text(
                """insert into app.style_proposals (name, name_key, tagline, category, created_by)
                   values (:name, :key, :tagline, :category, :uid) returning id"""
            ),
            {
                "name": name,
                "key": key,
                "tagline": tagline,
                "category": body.category,
                "uid": profile.id,
            },
        )
    except IntegrityError:
        # Stesso nome proposto da un altro nello stesso istante: si sostiene quella.
        await session.rollback()
        same = await session.scalar(
            text("select id from app.style_proposals where status = 'open' and name_key = :key"),
            {"key": key},
        )
        if same is None:
            raise
        return ProposalCreated(proposal=await _support(session, profile, same), created=False)
    assert isinstance(proposal_id, uuid.UUID)
    return ProposalCreated(proposal=await _support(session, profile, proposal_id), created=True)


@router.put(
    "/style-proposals/{proposal_id}/support",
    response_model=ProposalOut,
    dependencies=[Depends(rate_limit("style_proposal_support", 60, 3600))],
)
async def support(proposal_id: uuid.UUID, profile: CurrentProfile, session: Session) -> ProposalOut:
    return await _support(session, profile, proposal_id)


@router.delete(
    "/style-proposals/{proposal_id}/support",
    response_model=ProposalOut,
    dependencies=[Depends(rate_limit("style_proposal_support", 60, 3600))],
)
async def withdraw(
    proposal_id: uuid.UUID, profile: CurrentProfile, session: Session
) -> ProposalOut:
    status = await session.scalar(
        text("select status::text from app.style_proposals where id = :id for update"),
        {"id": proposal_id},
    )
    if status is None or status == "rejected":
        raise ApiError(404, "proposal.not_found", "Proposta non trovata")
    if status == "open":
        await session.execute(
            text(
                """delete from app.style_proposal_supports
                    where proposal_id = :id and user_id = :uid"""
            ),
            {"id": proposal_id, "uid": profile.id},
        )
    await session.commit()
    return await _one(session, profile, proposal_id)


async def _support(session: AsyncSession, profile: Profile, proposal_id: uuid.UUID) -> ProposalOut:
    # Lucchetto sulla proposta: due richieste insieme non creano lo stile due volte.
    row = (
        (
            await session.execute(
                text(
                    """select status::text as status, name, tagline, category
                         from app.style_proposals where id = :id for update"""
                ),
                {"id": proposal_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["status"] == "rejected":
        await session.rollback()
        raise ApiError(404, "proposal.not_found", "Proposta non trovata")
    if row["status"] == "open":
        await session.execute(
            text(
                """insert into app.style_proposal_supports (proposal_id, user_id)
                   values (:id, :uid) on conflict do nothing"""
            ),
            {"id": proposal_id, "uid": profile.id},
        )
        count = await session.scalar(
            text("select count(*) from app.style_proposal_supports where proposal_id = :id"),
            {"id": proposal_id},
        )
        if int(count or 0) >= _threshold():
            await _approve(session, proposal_id, dict(row))
    await session.commit()
    return await _one(session, profile, proposal_id)


async def _approve(session: AsyncSession, proposal_id: uuid.UUID, proposal: dict) -> None:  # type: ignore[type-arg]
    """Crea lo stile e ci fa entrare chi l'ha chiesto. Nella transazione del chiamante."""
    base = slug_for(proposal["name"])
    slug, n = base, 1
    while await session.scalar(text("select 1 from app.styles where slug = :s"), {"s": slug}):
        n += 1
        slug = f"{base}-{n}"
    tone = TONES[sum(map(ord, slug)) % len(TONES)]
    style_id = await session.scalar(
        text(
            """insert into app.styles (slug, name, tagline, tone, category, sort_order)
               values (:slug, :name, :tagline, :tone, :category, 1000) returning id"""
        ),
        {
            "slug": slug,
            "name": proposal["name"],
            "tagline": proposal["tagline"] or "Proposto dalla community",
            "tone": tone,
            "category": proposal["category"],
        },
    )
    await session.execute(
        text(
            """update app.style_proposals
                  set status = 'approved', style_id = :sid, decided_at = now()
                where id = :id"""
        ),
        {"sid": style_id, "id": proposal_id},
    )
    await session.execute(
        text(
            """insert into app.style_memberships (user_id, style_id)
               select x.user_id, :sid from app.style_proposal_supports x
                 join app.profiles p on p.id = x.user_id and p.status = 'active'
                where x.proposal_id = :id
                  and (select count(*) from app.style_memberships m
                        where m.user_id = x.user_id) < :max
               on conflict do nothing"""
        ),
        {"sid": style_id, "id": proposal_id, "max": MAX_MEMBERSHIPS},
    )


# ---------- Staff ----------


class AdminProposal(BaseModel):
    id: uuid.UUID
    name: str
    tagline: str | None
    category: str
    status: Literal["open", "approved", "rejected"]
    supports: int
    proposer: str | None
    style: str | None
    staff_note: str | None
    created_at: datetime


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=300)


@router.get("/admin/style-proposals", response_model=list[AdminProposal])
async def admin_list(
    staff: CurrentStaff,
    session: Session,
    status: Literal["open", "approved", "rejected"] = "open",
) -> list[AdminProposal]:
    rows = await session.execute(
        text(
            """select p.id, p.name, p.tagline, p.category, p.status::text as status,
                      p.staff_note, p.created_at, a.nickname::text as proposer, s.slug as style,
                      (select count(*) from app.style_proposal_supports x
                        where x.proposal_id = p.id)::int as supports
                 from app.style_proposals p
                 left join app.profiles a on a.id = p.created_by
                 left join app.styles s on s.id = p.style_id
                where p.status = cast(:status as app.proposal_status)
                order by supports desc, p.created_at desc
                limit 200"""
        ),
        {"status": status},
    )
    return [AdminProposal(**r) for r in rows.mappings()]


@router.post("/admin/style-proposals/{proposal_id}/reject", response_model=AdminProposal)
async def admin_reject(
    proposal_id: uuid.UUID, body: RejectIn, staff: CurrentStaff, session: Session
) -> AdminProposal:
    updated = await session.scalar(
        text(
            """update app.style_proposals
                  set status = 'rejected', decided_by = :me, decided_at = now(), staff_note = :note
                where id = :id and status = 'open' returning id"""
        ),
        {"id": proposal_id, "me": staff.id, "note": body.note},
    )
    if updated is None:
        raise ApiError(404, "proposal.not_found", "Nessuna proposta aperta con questo id")
    await audit(
        session, staff, "admin.proposal_reject", f"proposal:{proposal_id}", {"note": body.note}
    )
    await session.commit()
    rows = await admin_list(staff, session, status="rejected")
    return next(r for r in rows if r.id == proposal_id)
