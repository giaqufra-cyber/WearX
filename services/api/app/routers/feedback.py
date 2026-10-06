"""Feedback dei tester (seduta 25): "Segnala un problema" dall'app e la sua lista nel pannello.

Il messaggio arriva con versione dell'app, sistema e schermata (per riprodurre il problema). Lo
staff lo legge, lo segna come visto o risolto e può annotarlo; ogni modifica va nel registro di
audit. Dieci messaggi al giorno per persona bastano a un tester e fermano chi riempie la coda.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.profiles import CurrentProfileAnyStatus
from app.ratelimit import rate_limit
from app.staff import CurrentStaff, audit

router = APIRouter(tags=["feedback"])
Session = Annotated[AsyncSession, Depends(get_session)]

Kind = Literal["bug", "idea", "other"]
Status = Literal["new", "seen", "done"]


def _clean(value: str) -> str:
    # Spazi in fondo e righe vuote ripetute via; il testo resta com'è (lo legge solo lo staff).
    lines = [line.rstrip() for line in value.strip().splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out)


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    message: str = Field(min_length=3, max_length=2000)
    app_version: str = Field(min_length=1, max_length=20, pattern=r"^[0-9A-Za-z.+-]+$")
    platform: Literal["ios", "android", "web"]
    os_version: str | None = Field(default=None, max_length=20)
    # Percorso della schermata (es. "/post/[id]"): mai id o nickname.
    screen: str | None = Field(default=None, max_length=100, pattern=r"^/[A-Za-z0-9_\-/\[\]()]*$")

    @field_validator("message")
    @classmethod
    def _message(cls, value: str) -> str:
        cleaned = _clean(value)
        if len(cleaned) < 3:
            raise ValueError("Scrivi almeno qualche parola")
        return cleaned


class FeedbackCreated(BaseModel):
    id: uuid.UUID
    created_at: datetime


@router.post(
    "/v1/feedback",
    response_model=FeedbackCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("feedback", 10, 86400))],
)
async def send_feedback(
    body: FeedbackIn, profile: CurrentProfileAnyStatus, session: Session
) -> FeedbackCreated:
    row = (
        await session.execute(
            text(
                """insert into app.feedback
                     (author_id, kind, message, app_version, platform, os_version, screen)
                   values (:author, cast(:kind as app.feedback_kind), :message, :app_version,
                           :platform, :os_version, :screen)
                   returning id, created_at"""
            ),
            {"author": profile.id, **body.model_dump()},
        )
    ).one()
    await session.commit()
    return FeedbackCreated(id=row.id, created_at=row.created_at)


# ---------- Pannello dello staff ----------


class AdminFeedback(BaseModel):
    id: uuid.UUID
    author: str
    kind: Kind
    message: str
    app_version: str
    platform: str
    os_version: str | None
    screen: str | None
    status: Status
    staff_note: str | None
    created_at: datetime
    updated_at: datetime


class FeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status
    staff_note: str | None = Field(default=None, max_length=500)


class FeedbackCounts(BaseModel):
    new: int
    seen: int
    done: int


class FeedbackPage(BaseModel):
    items: list[AdminFeedback]
    counts: FeedbackCounts


_ADMIN_SELECT = """select f.id, p.nickname::text as author, f.kind::text as kind, f.message,
                          f.app_version, f.platform, f.os_version, f.screen,
                          f.status::text as status, f.staff_note, f.created_at, f.updated_at
                     from app.feedback f join app.profiles p on p.id = f.author_id"""


@router.get("/v1/admin/feedback", response_model=FeedbackPage)
async def list_feedback(
    staff: CurrentStaff,
    session: Session,
    state: Annotated[Literal["open", "done", "all"], Query(alias="status")] = "open",
    kind: Kind | None = None,
) -> FeedbackPage:
    where = {
        "open": "f.status <> 'done'",
        "done": "f.status = 'done'",
        "all": "true",
    }[state]
    rows = (
        (
            await session.execute(
                text(
                    f"""{_ADMIN_SELECT}
                        where {where} and (cast(:kind as text) is null or f.kind::text = :kind)
                        order by f.created_at desc limit 300"""
                ),
                {"kind": kind},
            )
        )
        .mappings()
        .all()
    )
    counts = (
        (
            await session.execute(
                text(
                    """select count(*) filter (where status = 'new') as new,
                              count(*) filter (where status = 'seen') as seen,
                              count(*) filter (where status = 'done') as done
                         from app.feedback"""
                )
            )
        )
        .mappings()
        .one()
    )
    return FeedbackPage(items=[AdminFeedback(**r) for r in rows], counts=FeedbackCounts(**counts))


@router.patch("/v1/admin/feedback/{feedback_id}", response_model=AdminFeedback)
async def update_feedback(
    feedback_id: uuid.UUID, body: FeedbackUpdate, staff: CurrentStaff, session: Session
) -> AdminFeedback:
    note = " ".join(body.staff_note.split()) if body.staff_note else None
    updated = await session.scalar(
        text(
            """update app.feedback
                  set status = cast(:status as app.feedback_status), staff_note = :note,
                      updated_at = now()
                where id = :id returning id"""
        ),
        {"id": feedback_id, "status": body.status, "note": note},
    )
    if updated is None:
        raise ApiError(404, "feedback.not_found", "Messaggio non trovato")
    await audit(
        session, staff, "admin.feedback", f"feedback:{feedback_id}", {"status": body.status}
    )
    await session.commit()
    row = (
        (await session.execute(text(f"{_ADMIN_SELECT} where f.id = :id"), {"id": feedback_id}))
        .mappings()
        .one()
    )
    return AdminFeedback(**row)
