"""Strumenti dello staff (sez. 14.3): coda delle segnalazioni, decisioni, sanzioni, reclami.

- La coda raggruppa le segnalazioni sullo stesso contenuto e le ordina per priorità e anzianità,
  con la scadenza (P0 1 ora, P1 24 ore, P2 72 ore).
- Una decisione chiude tutte le segnalazioni aperte su quel contenuto, scrive l'azione con la
  motivazione per l'autore e una riga nel registro di audit.
- "dismiss" su un contenuto nascosto in automatico lo rende di nuovo visibile; su un account
  sospeso in automatico lo riattiva.
L'interfaccia web dello staff arriva con la seduta 17.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.moderation import actions
from app.moderation.reports import SLA
from app.people import profile_id_by_nickname
from app.routers.media import MediaUrls, media_urls
from app.staff import CurrentStaff, audit
from app.storage import get_store

router = APIRouter(prefix="/v1/admin", tags=["admin"])

Session = Annotated[AsyncSession, Depends(get_session)]
Decision = Literal["dismiss", "hide", "remove", "restore", "none"]
SanctionChoice = Literal["none", "auto", "warn", "limit_posting", "ban"]


# ---------- Modelli ----------


class PostPreview(BaseModel):
    caption: str | None
    style: str
    status: str
    photo: MediaUrls | None


class QueueItem(BaseModel):
    target_type: Literal["post", "profile", "link"]
    target_id: uuid.UUID
    priority: int
    reasons: dict[str, int]
    reports: int
    automated: bool
    first_at: datetime
    due_at: datetime
    overdue: bool
    subject: str | None
    subject_status: str | None
    post: PostPreview | None
    details: list[str]


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: Literal["post", "profile", "link"]
    target_id: uuid.UUID
    decision: Decision
    sanction: SanctionChoice = "none"
    # Motivo della decisione (uno dei motivi di segnalazione).
    ground: str = Field(min_length=2, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class DecisionOut(BaseModel):
    actions: list[uuid.UUID]
    sanction: str | None
    resolved_reports: int


class ActionOut(BaseModel):
    id: uuid.UUID
    action: str
    ground: str
    automated: bool
    created_at: datetime
    expires_at: datetime | None
    statement: str
    appeal_status: str | None
    reversed_at: datetime | None = None


class UserCase(BaseModel):
    nickname: str
    status: str
    age_band: str
    account_type: str
    posting_blocked_until: datetime | None
    strikes: int
    next_sanction: str
    open_reports: int
    actions: list[ActionOut]


class SanctionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sanction: Literal["warn", "limit_posting", "ban"]
    ground: str = Field(min_length=2, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class AppealItem(BaseModel):
    id: uuid.UUID
    nickname: str | None
    text: str
    created_at: datetime
    action: ActionOut


class AppealDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["uphold", "reverse"]
    note: str = Field(min_length=2, max_length=1000)


# ---------- Coda ----------


@router.get("/reports/queue", response_model=list[QueueItem])
async def queue(
    staff: CurrentStaff,
    session: Session,
    priority: Annotated[int | None, Query(ge=0, le=2)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[QueueItem]:
    rows = (
        (
            await session.execute(
                text(
                    """select r.target_type, r.target_id, min(r.priority) as priority,
                              count(*) as reports, bool_or(r.auto) as automated,
                              min(r.created_at) as first_at,
                              array_agg(r.reason) as reasons,
                              (array_remove(
                                 array_agg(r.details order by r.created_at desc), null))[1:5]
                                as details
                         from app.reports r
                        where r.status in ('open', 'in_review')
                          and (cast(:prio as int) is null or r.priority = :prio)
                        group by r.target_type, r.target_id
                        order by min(r.priority), min(r.created_at)
                        limit :limit"""
                ),
                {"prio": priority, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    posts = [r["target_id"] for r in rows if r["target_type"] == "post"]
    previews: dict[uuid.UUID, Any] = {}
    if posts:
        for p in (
            await session.execute(
                text(
                    """select p.id, p.caption, p.status::text as status, s.name as style,
                              a.nickname::text as nickname, a.status::text as author_status,
                              m.upload_id, m.variants
                         from app.posts p
                         join app.styles s on s.id = p.style_id
                         join app.profiles a on a.id = p.author_id
                         left join app.post_media m on m.post_id = p.id and m.position = 0
                        where p.id = any(:ids)"""
                ),
                {"ids": posts},
            )
        ).mappings():
            previews[p["id"]] = p
    profiles = [r["target_id"] for r in rows if r["target_type"] == "profile"]
    people: dict[uuid.UUID, Any] = {}
    if profiles:
        for p in (
            await session.execute(
                text(
                    """select id, nickname::text as nickname, status::text as status
                         from app.profiles where id = any(:ids)"""
                ),
                {"ids": profiles},
            )
        ).mappings():
            people[p["id"]] = p

    now = datetime.now(UTC)
    out = []
    for r in rows:
        reasons: dict[str, int] = {}
        for reason in r["reasons"]:
            reasons[reason] = reasons.get(reason, 0) + 1
        due = r["first_at"] + SLA[r["priority"]]
        preview, subject, subject_status = None, None, None
        if r["target_type"] == "post" and r["target_id"] in previews:
            p = previews[r["target_id"]]
            # Foto mostrate sfocate dall'interfaccia: qui solo l'URL firmato della più piccola.
            photo = (
                media_urls(p["upload_id"], [min(p["variants"])])
                if p["upload_id"] and p["variants"]
                else None
            )
            preview = PostPreview(
                caption=p["caption"], style=p["style"], status=p["status"], photo=photo
            )
            subject, subject_status = p["nickname"], p["author_status"]
        elif r["target_type"] == "profile" and r["target_id"] in people:
            subject = people[r["target_id"]]["nickname"]
            subject_status = people[r["target_id"]]["status"]
        out.append(
            QueueItem(
                target_type=r["target_type"],
                target_id=r["target_id"],
                priority=r["priority"],
                reasons=reasons,
                reports=r["reports"],
                automated=r["automated"],
                first_at=r["first_at"],
                due_at=due,
                overdue=now > due,
                subject=subject,
                subject_status=subject_status,
                post=preview,
                details=list(r["details"] or []),
            )
        )
    return out


async def _subject(session: AsyncSession, target_type: str, target_id: uuid.UUID) -> uuid.UUID:
    if target_type == "profile":
        found = await session.scalar(
            text("select id from app.profiles where id = :id"), {"id": target_id}
        )
    elif target_type == "post":
        found = await session.scalar(
            text("select author_id from app.posts where id = :id"), {"id": target_id}
        )
    else:
        found = await session.scalar(
            text(
                """select p.author_id from app.post_items i join app.posts p on p.id = i.post_id
                    where i.link_id = :id limit 1"""
            ),
            {"id": target_id},
        )
    if found is None:
        raise ApiError(404, "resource.not_found", "Contenuto non trovato")
    assert isinstance(found, uuid.UUID)
    return found


async def _last_automatic(
    session: AsyncSession, target_type: str, target_id: uuid.UUID, action: str
) -> bool:
    row = await session.scalar(
        text(
            """select automated from app.moderation_actions
                where target_type = :tt and target_id = :tid and action in (:a, 'restore')
                order by created_at desc limit 1"""
        ),
        {"tt": target_type, "tid": target_id, "a": action},
    )
    return bool(row)


@router.post("/reports/decide", response_model=DecisionOut)
async def decide(body: DecisionIn, staff: CurrentStaff, session: Session) -> DecisionOut:
    if body.ground not in actions.GROUNDS:
        raise ApiError(422, "moderation.bad_ground", "Motivo non valido")
    if body.target_type != "post" and body.decision in ("hide", "remove", "restore"):
        raise ApiError(422, "moderation.bad_decision", "Decisione non valida per questo contenuto")
    subject = await _subject(session, body.target_type, body.target_id)
    # Le decisioni precedenti contano prima di registrare quella di adesso.
    previous_strikes = await actions.strikes(session, subject)
    created: list[uuid.UUID] = []
    storage_keys: list[str] = []
    sanction: actions.Sanction | None = None
    try:
        if body.decision == "hide":
            action_id = await actions.hide_post(
                session, body.target_id, ground=body.ground, automated=False, actor_id=staff.id
            )
            created += [action_id] if action_id else []
        elif body.decision == "remove":
            action_id, storage_keys = await actions.remove_post(
                session, body.target_id, ground=body.ground, actor_id=staff.id
            )
            created += [action_id] if action_id else []
        elif body.decision in ("restore", "dismiss"):
            # Annulla le misure automatiche prese in attesa della revisione.
            if body.target_type == "post" and (
                body.decision == "restore"
                or await _last_automatic(session, "post", body.target_id, "hide")
            ):
                # Si annulla la decisione che l'ha nascosto (con l'eventuale sanzione collegata).
                hide_id = await session.scalar(
                    text(
                        """select id from app.moderation_actions
                            where target_type = 'post' and target_id = :id and action = 'hide'
                              and reversed_at is null
                            order by created_at desc limit 1"""
                    ),
                    {"id": body.target_id},
                )
                action_id = (
                    await actions.reverse(
                        session, hide_id, actor_id=staff.id, ground="review_cleared"
                    )
                    if hide_id is not None
                    else await actions.restore_post(
                        session, body.target_id, ground="review_cleared", actor_id=staff.id
                    )
                )
                created += [action_id] if action_id else []
            if body.decision == "dismiss" and await _last_automatic(
                session, "profile", subject, "suspend"
            ):
                status = await session.scalar(
                    text("select status::text from app.profiles where id = :id"), {"id": subject}
                )
                last = await session.scalar(
                    text(
                        """select id from app.moderation_actions
                            where target_type = 'profile' and target_id = :id
                              and action = 'suspend' and automated
                            order by created_at desc limit 1"""
                    ),
                    {"id": subject},
                )
                if status == "suspended" and last is not None:
                    restored = await actions.reverse(
                        session, last, actor_id=staff.id, ground="review_cleared"
                    )
                    created += [restored] if restored else []

        if body.sanction != "none" and body.decision != "dismiss":
            sanction = (
                actions.next_sanction(previous_strikes)
                if body.sanction == "auto"
                else body.sanction
            )
            if body.ground == "minor_safety" and body.sanction == "auto":
                sanction = "ban"  # P0 confermato: chiusura immediata (sez. 14.3)
            created.append(
                await actions.sanction_user(
                    session,
                    subject,
                    sanction,
                    ground=body.ground,
                    actor_id=staff.id,
                    linked=any(created) and body.decision in ("hide", "remove"),
                )
            )

        resolved = await session.scalar(
            text(
                """with done as (
                     update app.reports set status = :st, resolved_at = now(), resolved_by = :me
                      where target_type = :tt and target_id = :tid
                        and status in ('open', 'in_review')
                     returning 1)
                   select count(*) from done"""
            ),
            {
                "st": "dismissed" if body.decision == "dismiss" else "actioned",
                "me": staff.id,
                "tt": body.target_type,
                "tid": body.target_id,
            },
        )
        await audit(
            session,
            staff,
            "moderation.decide",
            f"{body.target_type}:{body.target_id}",
            {
                "decision": body.decision,
                "sanction": sanction,
                "ground": body.ground,
                "note": body.note,
                "actions": created,
            },
        )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    if storage_keys:
        await get_store().delete(*storage_keys)
    return DecisionOut(actions=created, sanction=sanction, resolved_reports=int(resolved or 0))


# ---------- Persone ----------


async def _actions_of(session: AsyncSession, user_id: uuid.UUID) -> list[ActionOut]:
    rows = (
        await session.execute(
            text(
                """select m.id, m.action, m.ground, m.automated, m.created_at, m.expires_at,
                          m.statement, a.status as appeal_status, m.reversed_at
                     from app.moderation_actions m
                     left join app.appeals a on a.action_id = m.id
                    where m.subject_id = :id order by m.created_at desc limit 200"""
            ),
            {"id": user_id},
        )
    ).mappings()
    return [ActionOut(**r) for r in rows]


async def _staff_target(session: AsyncSession, nickname: str) -> uuid.UUID:
    user_id = await profile_id_by_nickname(session, nickname)
    if user_id is None:
        raise ApiError(404, "user.not_found", "Profilo non trovato")
    return user_id


@router.get("/users/{nickname}", response_model=UserCase)
async def user_case(nickname: str, staff: CurrentStaff, session: Session) -> UserCase:
    user_id = await _staff_target(session, nickname)
    row = (
        (
            await session.execute(
                text(
                    """select nickname::text as nickname, status::text as status,
                              age_band::text as age_band, account_type::text as account_type,
                              posting_blocked_until,
                              (select count(*) from app.reports r
                                where r.status in ('open', 'in_review')
                                  and ((r.target_type = 'profile' and r.target_id = p.id)
                                       or (r.target_type = 'post' and r.target_id in (
                                             select id from app.posts where author_id = p.id))))
                                as open_reports
                         from app.profiles p where id = :id"""
                ),
                {"id": user_id},
            )
        )
        .mappings()
        .one()
    )
    strikes = await actions.strikes(session, user_id)
    await audit(session, staff, "moderation.view_user", f"profile:{user_id}", {})
    await session.commit()
    return UserCase(
        **row,
        strikes=strikes,
        next_sanction=actions.next_sanction(strikes),
        actions=await _actions_of(session, user_id),
    )


@router.post("/users/{nickname}/sanction", response_model=ActionOut)
async def sanction(
    nickname: str, body: SanctionIn, staff: CurrentStaff, session: Session
) -> ActionOut:
    if body.ground not in actions.GROUNDS:
        raise ApiError(422, "moderation.bad_ground", "Motivo non valido")
    user_id = await _staff_target(session, nickname)
    action_id = await actions.sanction_user(
        session, user_id, body.sanction, ground=body.ground, actor_id=staff.id
    )
    await audit(
        session,
        staff,
        "moderation.sanction",
        f"profile:{user_id}",
        {"sanction": body.sanction, "ground": body.ground, "note": body.note},
    )
    await session.commit()
    return next(a for a in await _actions_of(session, user_id) if a.id == action_id)


# ---------- Reclami ----------


@router.get("/appeals", response_model=list[AppealItem])
async def appeals(staff: CurrentStaff, session: Session) -> list[AppealItem]:
    rows = (
        (
            await session.execute(
                text(
                    """select ap.id, p.nickname::text as nickname, ap.text, ap.created_at,
                              m.id as action_id, m.action, m.ground, m.automated,
                              m.created_at as action_at, m.expires_at, m.statement
                         from app.appeals ap
                         join app.moderation_actions m on m.id = ap.action_id
                         left join app.profiles p on p.id = ap.user_id
                        where ap.status = 'open'
                        order by ap.created_at
                        limit 100"""
                ),
            )
        )
        .mappings()
        .all()
    )
    return [
        AppealItem(
            id=r["id"],
            nickname=r["nickname"],
            text=r["text"],
            created_at=r["created_at"],
            action=ActionOut(
                id=r["action_id"],
                action=r["action"],
                ground=r["ground"],
                automated=r["automated"],
                created_at=r["action_at"],
                expires_at=r["expires_at"],
                statement=r["statement"],
                appeal_status="open",
            ),
        )
        for r in rows
    ]


@router.post("/appeals/{appeal_id}", response_model=AppealItem)
async def decide_appeal(
    appeal_id: uuid.UUID, body: AppealDecisionIn, staff: CurrentStaff, session: Session
) -> AppealItem:
    row = (
        await session.execute(
            text(
                """select action_id, user_id, status from app.appeals
                    where id = :id for update"""
            ),
            {"id": appeal_id},
        )
    ).first()
    if row is None:
        raise ApiError(404, "appeal.not_found", "Reclamo non trovato")
    if row[2] != "open":
        raise ApiError(409, "appeal.decided", "Reclamo già deciso")
    actor = await session.scalar(
        text("select actor_id from app.moderation_actions where id = :id"), {"id": row[0]}
    )
    if actor == staff.id:
        # Il reclamo lo decide una persona diversa da chi ha preso la decisione (art. 20).
        raise ApiError(409, "appeal.same_moderator", "Serve un altro moderatore")
    try:
        if body.decision == "reverse":
            await actions.reverse(session, row[0], actor_id=staff.id)
        await session.execute(
            text(
                """update app.appeals set status = :st, decided_at = now(), decided_by = :me,
                          decision_note = :note
                    where id = :id"""
            ),
            {
                "st": "reversed" if body.decision == "reverse" else "upheld",
                "me": staff.id,
                "note": body.note,
                "id": appeal_id,
            },
        )
        await audit(
            session,
            staff,
            "moderation.appeal",
            f"appeal:{appeal_id}",
            {"decision": body.decision, "note": body.note},
        )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    item = (
        await session.execute(
            text(
                """select ap.text, ap.created_at, p.nickname::text, m.action, m.ground,
                          m.automated, m.created_at, m.expires_at, m.statement, ap.status
                     from app.appeals ap join app.moderation_actions m on m.id = ap.action_id
                     left join app.profiles p on p.id = ap.user_id where ap.id = :id"""
            ),
            {"id": appeal_id},
        )
    ).one()
    return AppealItem(
        id=appeal_id,
        nickname=item[2],
        text=item[0],
        created_at=item[1],
        action=ActionOut(
            id=row[0],
            action=item[3],
            ground=item[4],
            automated=item[5],
            created_at=item[6],
            expires_at=item[7],
            statement=item[8],
            appeal_status=item[9],
        ),
    )
