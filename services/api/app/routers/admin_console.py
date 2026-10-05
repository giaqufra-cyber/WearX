"""Pannello dello staff (seduta 17): chi sono, numeri del giorno, fit e persone da controllare,
stili, staff, registro di audit.

- Moderatori e admin: numeri, fit (in qualsiasi stato), ricerca persone, riattivazione.
- Solo admin: stili, staff, registro di audit.
Ogni scrittura finisce nel registro di audit; anche aprire un fit o una persona viene registrato
(chi ha guardato cosa), come per la scheda persona della seduta 16.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.link_check import block_domain, unblock_domain
from app.links import normalize_shop_url
from app.moderation import actions
from app.people import profile_id_by_nickname
from app.post_views import ItemOut, LinkOut, MediaOut
from app.routers.media import media_urls
from app.staff import CurrentAdmin, CurrentStaff, audit

router = APIRouter(prefix="/v1/admin", tags=["admin"])

Session = Annotated[AsyncSession, Depends(get_session)]
SLUG_RE = re.compile(r"^[a-z0-9-]{2,40}$")
TONE_RE = re.compile(r"^#[0-9A-F]{6}$")


# ---------- Chi sono e numeri ----------


class StaffMe(BaseModel):
    role: Literal["moderator", "admin"]
    nickname: str | None


@router.get("/me", response_model=StaffMe)
async def me(staff: CurrentStaff, session: Session) -> StaffMe:
    nickname = await session.scalar(
        text("select nickname::text from app.profiles where id = :id"), {"id": staff.id}
    )
    return StaffMe(role=staff.role, nickname=nickname)


class OpenReports(BaseModel):
    p0: int
    p1: int
    p2: int
    overdue: int


class Stats(BaseModel):
    users: int
    users_new_7d: int
    posts_today: int
    posts_7d: int
    votes_today: int
    reports: OpenReports
    appeals_open: int
    suspended: int


@router.get("/stats", response_model=Stats)
async def stats(staff: CurrentStaff, session: Session) -> Stats:
    row = (
        (
            await session.execute(
                text(
                    """select
                     (select count(*) from app.profiles) as users,
                     (select count(*) from app.profiles
                       where created_at > now() - interval '7 days') as users_new_7d,
                     (select count(*) from app.posts
                       where published_at >= date_trunc('day', now())) as posts_today,
                     (select count(*) from app.posts
                       where published_at > now() - interval '7 days') as posts_7d,
                     (select count(*) from app.votes
                       where created_at >= date_trunc('day', now())) as votes_today,
                     (select count(*) from app.appeals where status = 'open') as appeals_open,
                     (select count(*) from app.profiles where status = 'suspended') as suspended"""
                )
            )
        )
        .mappings()
        .one()
    )
    groups = (
        await session.execute(
            text(
                """select min(priority) as p, min(created_at) as first_at
                     from app.reports where status in ('open', 'in_review')
                    group by target_type, target_id"""
            )
        )
    ).all()
    counts = {0: 0, 1: 0, 2: 0}
    overdue = await session.scalar(
        text(
            """select count(*) from (
                 select min(priority) as p, min(created_at) as first_at
                   from app.reports where status in ('open', 'in_review')
                  group by target_type, target_id) g
                where g.first_at + case g.p when 0 then interval '1 hour'
                                            when 1 then interval '24 hours'
                                            else interval '72 hours' end < now()"""
        )
    )
    for p, _ in groups:
        counts[int(p)] += 1
    return Stats(
        **row,
        reports=OpenReports(p0=counts[0], p1=counts[1], p2=counts[2], overdue=int(overdue or 0)),
    )


# ---------- Fit ----------


class ReportLine(BaseModel):
    reason: str
    details: str | None
    status: str
    auto: bool
    created_at: datetime


class AdminPost(BaseModel):
    id: uuid.UUID
    status: str
    author: str
    author_status: str
    minor_author: bool
    style: str
    caption: str | None
    created_at: datetime
    media: list[MediaOut]
    items: list[ItemOut]
    vote_count: int
    average: float | None
    reports: list[ReportLine]


@router.get("/posts/{post_id}", response_model=AdminPost)
async def post(post_id: uuid.UUID, staff: CurrentStaff, session: Session) -> AdminPost:
    row = (
        (
            await session.execute(
                text(
                    """select p.id, p.status::text as status, a.nickname::text as author,
                              a.status::text as author_status, p.minor_author,
                              s.name as style, p.caption, p.created_at,
                              coalesce(st.vote_count, 0) as vote_count,
                              case when st.vote_wcount > 0
                                   then round((st.vote_wsum / st.vote_wcount)::numeric, 1)
                              end as average
                         from app.posts p
                         join app.profiles a on a.id = p.author_id
                         join app.styles s on s.id = p.style_id
                         left join app.post_stats st on st.post_id = p.id
                        where p.id = :id"""
                ),
                {"id": post_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "post.not_found", "Post non trovato")
    media = [
        MediaOut(
            position=m["position"],
            width=m["width"],
            height=m["height"],
            blurhash=m["blurhash"],
            urls=media_urls(m["upload_id"], list(m["variants"])),
        )
        for m in (
            await session.execute(
                text(
                    """select position, width, height, blurhash, upload_id, variants
                         from app.post_media where post_id = :id and upload_id is not null
                        order by position"""
                ),
                {"id": post_id},
            )
        ).mappings()
    ]
    items = [
        ItemOut(
            position=i["position"],
            brand=i["brand"],
            name=i["name"],
            price_cents=i["price_cents"],
            currency=i["currency"],
            link=LinkOut(id=i["link_id"], domain=i["domain"], status=i["link_status"], url=i["url"])
            if i["link_id"]
            else None,
            media_position=i["media_position"],
            pin_x=float(i["pin_x"]) if i["pin_x"] is not None else None,
            pin_y=float(i["pin_y"]) if i["pin_y"] is not None else None,
        )
        for i in (
            await session.execute(
                text(
                    """select i.*, l.id as link_id, l.url, l.domain, l.status::text as link_status
                         from app.post_items i left join app.links l on l.id = i.link_id
                        where i.post_id = :id order by i.position"""
                ),
                {"id": post_id},
            )
        ).mappings()
    ]
    reports = [
        ReportLine(**r)
        for r in (
            await session.execute(
                text(
                    """select reason, details, status, auto, created_at from app.reports
                        where target_type = 'post' and target_id = :id
                        order by created_at desc limit 50"""
                ),
                {"id": post_id},
            )
        ).mappings()
    ]
    await audit(session, staff, "admin.view_post", f"post:{post_id}", {})
    await session.commit()
    return AdminPost(
        **{**row, "average": float(row["average"]) if row["average"] is not None else None},
        media=media,
        items=items,
        reports=reports,
    )


# ---------- Persone ----------


class UserRow(BaseModel):
    nickname: str
    status: str
    age_band: str
    account_type: str
    created_at: datetime
    posts: int


@router.get("/users", response_model=list[UserRow])
async def users(
    staff: CurrentStaff,
    session: Session,
    q: Annotated[str, Query(min_length=1, max_length=20)],
) -> list[UserRow]:
    prefix = re.sub(r"[^a-z0-9._]", "", q.strip().lower())
    if not prefix:
        return []
    rows = (
        await session.execute(
            text(
                """select p.nickname::text as nickname, p.status::text as status,
                          p.age_band::text as age_band, p.account_type::text as account_type,
                          p.created_at,
                          (select count(*) from app.posts x
                            where x.author_id = p.id and x.status <> 'deleted') as posts
                     from app.profiles p
                    where p.nickname::text like :prefix
                    order by p.nickname::text limit 20"""
            ),
            {"prefix": prefix.replace("_", r"\_") + "%"},
        )
    ).mappings()
    return [UserRow(**r) for r in rows]


class ReinstateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=2, max_length=1000)


@router.post("/users/{nickname}/reinstate", status_code=status.HTTP_204_NO_CONTENT)
async def reinstate(
    nickname: str, body: ReinstateIn, staff: CurrentStaff, session: Session
) -> Response:
    """Riattiva un account sospeso e toglie la sospensione della pubblicazione."""
    user_id = await profile_id_by_nickname(session, nickname)
    if user_id is None:
        raise ApiError(404, "user.not_found", "Profilo non trovato")
    changed = await session.scalar(
        text(
            """update app.profiles
                  set status = case when status = 'suspended' then 'active'::app.user_status
                                    else status end,
                      posting_blocked_until = null
                where id = :id
                  and (status = 'suspended' or posting_blocked_until > now())
                returning id"""
        ),
        {"id": user_id},
    )
    if changed is None:
        raise ApiError(409, "user.not_restricted", "Questa persona non ha limitazioni")
    await actions.record(
        session,
        target_type="profile",
        target_id=user_id,
        action="restore",
        ground="staff_review",
        automated=False,
        actor_id=staff.id,
        subject_id=user_id,
        statement=actions.statement_for("restore", "staff_review", automated=False),
    )
    await audit(session, staff, "admin.reinstate", f"profile:{user_id}", {"note": body.note})
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Stili (solo admin) ----------


class AdminStyle(BaseModel):
    slug: str
    name: str
    tagline: str
    tone: str
    min_age_band: Literal["16_17", "18_plus"]
    active_from: date | None
    active_until: date | None
    sort_order: int
    is_active: bool
    members: int
    posts_7d: int


class StyleFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=40)
    tagline: str | None = Field(default=None, min_length=2, max_length=90)
    tone: str | None = None
    min_age_band: Literal["16_17", "18_plus"] | None = None
    active_from: date | None = None
    active_until: date | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _check(self) -> StyleFields:
        if self.tone is not None and not TONE_RE.fullmatch(self.tone):
            raise ValueError("tone deve essere #RRGGBB (maiuscolo)")
        if self.active_from and self.active_until and self.active_until < self.active_from:
            raise ValueError("active_until prima di active_from")
        return self


class StyleCreate(StyleFields):
    slug: str
    name: str = Field(min_length=2, max_length=40)
    tagline: str = Field(min_length=2, max_length=90)
    tone: str = "#2A2A2E"

    @model_validator(mode="after")
    def _slug(self) -> StyleCreate:
        if not SLUG_RE.fullmatch(self.slug):
            raise ValueError("slug: minuscole, numeri e trattini (2-40)")
        return self


_STYLE_SELECT = """
    select s.slug, s.name, s.tagline, s.tone, s.min_age_band::text as min_age_band,
           s.active_from, s.active_until, s.sort_order, s.is_active,
           (select count(*) from app.style_memberships m where m.style_id = s.id) as members,
           (select count(*) from app.posts p where p.style_id = s.id
              and p.published_at > now() - interval '7 days') as posts_7d
      from app.styles s
"""


@router.get("/styles", response_model=list[AdminStyle])
async def list_styles(admin: CurrentAdmin, session: Session) -> list[AdminStyle]:
    rows = await session.execute(text(_STYLE_SELECT + " order by s.sort_order, s.name"))
    return [AdminStyle(**r) for r in rows.mappings()]


async def _style(session: AsyncSession, slug: str) -> AdminStyle:
    row = (
        (await session.execute(text(_STYLE_SELECT + " where s.slug = :slug"), {"slug": slug}))
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "style.not_found", "Stile non trovato")
    return AdminStyle(**row)


def _clean(body: StyleFields) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    for key in ("name", "tagline"):
        if key in values and values[key] is not None:
            values[key] = " ".join(str(values[key]).split())
    return values


@router.post("/styles", response_model=AdminStyle, status_code=status.HTTP_201_CREATED)
async def create_style(body: StyleCreate, admin: CurrentAdmin, session: Session) -> AdminStyle:
    values = _clean(body)
    values.setdefault("sort_order", 100)
    values.setdefault("is_active", True)
    values.setdefault("min_age_band", "16_17")
    try:
        await session.execute(
            text(
                """insert into app.styles
                     (slug, name, tagline, tone, min_age_band, active_from, active_until,
                      sort_order, is_active)
                   values (:slug, :name, :tagline, :tone, cast(:min_age_band as app.age_band),
                           :active_from, :active_until, :sort_order, :is_active)"""
            ),
            {"active_from": None, "active_until": None, **values},
        )
        await audit(session, admin, "admin.style_create", f"style:{body.slug}", values)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "style.slug_taken", "Esiste già uno stile con questo slug") from exc
    return await _style(session, body.slug)


_STYLE_COLUMNS = (
    "name",
    "tagline",
    "tone",
    "min_age_band",
    "active_from",
    "active_until",
    "sort_order",
    "is_active",
)


@router.patch("/styles/{slug}", response_model=AdminStyle)
async def update_style(
    slug: str, body: StyleFields, admin: CurrentAdmin, session: Session
) -> AdminStyle:
    current = await _style(session, slug)
    values = _clean(body)
    if not values:
        return current
    start = values.get("active_from", current.active_from)
    end = values.get("active_until", current.active_until)
    if start and end and end < start:
        raise ApiError(422, "style.bad_dates", "La fine viene prima dell'inizio")
    assert set(values) <= set(_STYLE_COLUMNS)  # nomi di colonna da una lista fissa
    assignments = ", ".join(
        f"{col} = cast(:{col} as app.age_band)" if col == "min_age_band" else f"{col} = :{col}"
        for col in values
    )
    await session.execute(
        text(f"update app.styles set {assignments} where slug = :slug"),
        {**values, "slug": slug},
    )
    await audit(session, admin, "admin.style_update", f"style:{slug}", values)
    await session.commit()
    return await _style(session, slug)


# ---------- Staff (solo admin) ----------


class StaffRow(BaseModel):
    nickname: str | None
    role: Literal["moderator", "admin"]
    created_at: datetime


class StaffIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["moderator", "admin"]


@router.get("/staff", response_model=list[StaffRow])
async def list_staff(admin: CurrentAdmin, session: Session) -> list[StaffRow]:
    rows = await session.execute(
        text(
            """select p.nickname::text as nickname, s.role, s.created_at
                 from app.staff s left join app.profiles p on p.id = s.user_id
                order by s.created_at"""
        )
    )
    return [StaffRow(**r) for r in rows.mappings()]


async def _admins(session: AsyncSession) -> int:
    return int(
        await session.scalar(text("select count(*) from app.staff where role = 'admin'")) or 0
    )


@router.put("/staff/{nickname}", response_model=StaffRow)
async def put_staff(
    nickname: str, body: StaffIn, admin: CurrentAdmin, session: Session
) -> StaffRow:
    user_id = await profile_id_by_nickname(session, nickname)
    if user_id is None:
        raise ApiError(404, "user.not_found", "Profilo non trovato")
    if user_id == admin.id and body.role != "admin" and await _admins(session) <= 1:
        raise ApiError(409, "staff.last_admin", "Serve almeno un amministratore")
    row = (
        await session.execute(
            text(
                """insert into app.staff (user_id, role) values (:id, :role)
                   on conflict (user_id) do update set role = excluded.role
                   returning role, created_at"""
            ),
            {"id": user_id, "role": body.role},
        )
    ).one()
    await audit(session, admin, "admin.staff_set", f"profile:{user_id}", {"role": body.role})
    await session.commit()
    return StaffRow(nickname=nickname.lower(), role=row[0], created_at=row[1])


@router.delete("/staff/{nickname}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(nickname: str, admin: CurrentAdmin, session: Session) -> Response:
    user_id = await profile_id_by_nickname(session, nickname)
    if user_id is None:
        raise ApiError(404, "user.not_found", "Profilo non trovato")
    role = await session.scalar(
        text("select role from app.staff where user_id = :id"), {"id": user_id}
    )
    if role == "admin" and await _admins(session) <= 1:
        raise ApiError(409, "staff.last_admin", "Serve almeno un amministratore")
    await session.execute(text("delete from app.staff where user_id = :id"), {"id": user_id})
    await audit(session, admin, "admin.staff_remove", f"profile:{user_id}", {})
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Registro di audit (solo admin) ----------


class AuditRow(BaseModel):
    id: int
    staff: str | None
    action: str
    target: str | None
    details: dict[str, Any] | None
    ts: datetime


class AuditPage(BaseModel):
    items: list[AuditRow]
    next_cursor: int | None


@router.get("/audit", response_model=AuditPage)
async def audit_log(
    admin: CurrentAdmin,
    session: Session,
    cursor: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditPage:
    rows = (
        (
            await session.execute(
                text(
                    """select l.id, p.nickname::text as staff, l.action, l.target, l.details, l.ts
                         from app.admin_audit_log l
                         left join app.profiles p on p.id = l.admin_id
                        where cast(:cursor as bigint) is null or l.id < :cursor
                        order by l.id desc limit :limit"""
                ),
                {"cursor": cursor, "limit": limit + 1},
            )
        )
        .mappings()
        .all()
    )
    page = rows[:limit]
    return AuditPage(
        items=[AuditRow(**r) for r in page],
        next_cursor=page[-1]["id"] if len(rows) > limit else None,
    )


# ---------- Domini bloccati (moderatori e admin) ----------


class BlockedDomainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = Field(min_length=3, max_length=255)
    reason: str = Field(min_length=3, max_length=200)


class BlockedDomainOut(BaseModel):
    domain: str
    reason: str
    created_at: datetime
    links: int


@router.get("/blocked-domains", response_model=list[BlockedDomainOut])
async def blocked_domains(staff: CurrentStaff, session: Session) -> list[BlockedDomainOut]:
    rows = (
        (
            await session.execute(
                text(
                    """select b.domain, b.reason, b.created_at,
                              (select count(*) from app.links l
                                where l.domain = b.domain or l.domain like '%.' || b.domain)
                                as links
                         from app.blocked_domains b order by b.created_at desc limit 500"""
                )
            )
        )
        .mappings()
        .all()
    )
    return [BlockedDomainOut(**r) for r in rows]


@router.post("/blocked-domains", response_model=BlockedDomainOut, status_code=201)
async def add_blocked_domain(
    body: BlockedDomainIn, staff: CurrentStaff, session: Session
) -> BlockedDomainOut:
    value = body.domain.strip()
    _, domain = normalize_shop_url(value if "://" in value else f"https://{value}")
    reason = " ".join(body.reason.split())
    count = await block_domain(session, domain, reason, staff.id)
    await audit(session, staff, "admin.block_domain", f"domain:{domain}", {"reason": reason})
    await session.commit()
    created = await session.scalar(
        text("select created_at from app.blocked_domains where domain = :d"), {"d": domain}
    )
    return BlockedDomainOut(domain=domain, reason=reason, created_at=created, links=count)


@router.delete("/blocked-domains/{domain}", status_code=204)
async def remove_blocked_domain(domain: str, staff: CurrentStaff, session: Session) -> Response:
    await unblock_domain(session, domain.lower())
    await audit(session, staff, "admin.unblock_domain", f"domain:{domain.lower()}", {})
    await session.commit()
    return Response(status_code=204)
