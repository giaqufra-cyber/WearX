"""Segnalazioni dall'app (art. 16 DSA), avvisi di moderazione e reclami (art. 17 e 20).

- Si segnala solo ciò che si vede (un fit, un profilo, un link di un fit visibile); i propri
  contenuti no. 20 segnalazioni al giorno.
- Gli avvisi elencano ogni decisione che riguarda la persona, con la motivazione.
- Reclamo: uno per decisione, entro 6 mesi, anche da account sospeso.
"""

from __future__ import annotations

import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.moderation.actions import appeal_deadline, ground_label
from app.moderation.reports import SLA, Reason, TargetType, file_report
from app.people import find_person
from app.post_access import POST_VISIBLE_SQL
from app.profiles import CurrentProfile, CurrentProfileAnyStatus
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1", tags=["moderation"])

Session = Annotated[AsyncSession, Depends(get_session)]


# ---------- Modelli ----------


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: TargetType
    # Fit o link: id. Profilo: nickname (gli id delle persone non sono mai esposti).
    target_id: uuid.UUID | None = None
    nickname: str | None = Field(default=None, max_length=40)
    reason: Reason
    details: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _target(self) -> ReportIn:
        if self.target_type == "profile" and not self.nickname:
            raise ValueError("per un profilo serve il nickname")
        if self.target_type != "profile" and self.target_id is None:
            raise ValueError("serve target_id")
        return self


class ReportOut(BaseModel):
    id: uuid.UUID
    priority: int
    # Entro quando una persona la guarda (sez. 14.3).
    review_within_hours: int


class AppealOut(BaseModel):
    status: Literal["open", "upheld", "reversed"]
    created_at: datetime
    decided_at: datetime | None
    decision_note: str | None


class NoticeOut(BaseModel):
    id: uuid.UUID
    action: Literal[
        "hide", "remove", "restyle", "suspend", "ban", "restore", "warn", "limit_posting"
    ]
    reason: str
    statement: str
    automated: bool
    created_at: datetime
    expires_at: datetime | None
    # Il fit coinvolto (se è ancora visibile all'autore).
    post_id: uuid.UUID | None
    # Su cosa: un fit, il profilo (bio e foto) o l'account.
    target_type: Literal["post", "profile", "link"] = "post"
    appeal: AppealOut | None
    can_appeal: bool
    appeal_until: datetime | None


class AppealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


# ---------- Segnalare ----------


def _free_text(raw: str | None, max_chars: int) -> str | None:
    """Testo di chi segnala o fa reclamo: può citare le parole offensive che segnala, quindi
    niente filtro di parole; solo caratteri invisibili tolti e lunghezza."""
    if raw is None:
        return None
    value = unicodedata.normalize("NFC", raw).strip()
    value = "".join(
        ch for ch in value if ch == "\n" or unicodedata.category(ch) not in ("Cc", "Cf", "Co", "Cs")
    )
    if len(value) > max_chars:
        raise ApiError(422, "text.too_long", f"Il testo può avere al massimo {max_chars} caratteri")
    return value or None


@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("report", 20, 86400))],
)
async def report(
    body: ReportIn, profile: CurrentProfile, session: Session, response: Response
) -> ReportOut:
    details = _free_text(body.details, 500)
    subject: uuid.UUID | None
    if body.target_type == "profile":
        person = await find_person(session, profile, body.nickname or "")
        if person.is_self:
            raise ApiError(422, "report.own_content", "Non puoi segnalare te stesso")
        target_id, subject = person.id, person.id
    else:
        assert body.target_id is not None
        target_id = body.target_id
        if body.target_type == "post":
            post_filter = "p.id = :id"
        else:
            post_filter = "p.id in (select i.post_id from app.post_items i where i.link_id = :id)"
        row = (
            await session.execute(
                text(
                    f"""select p.author_id from app.posts p
                          join app.profiles a on a.id = p.author_id
                          join app.styles s on s.id = p.style_id
                         where {post_filter} and {POST_VISIBLE_SQL}
                         limit 1"""
                ),
                {"id": target_id, "viewer": profile.id, "adult": profile.is_adult},
            )
        ).first()
        if row is None:
            code = "post.not_found" if body.target_type == "post" else "link.not_found"
            raise ApiError(404, code, "Contenuto non trovato")
        subject = row[0]
        if body.target_type == "post" and subject == profile.id:
            raise ApiError(422, "report.own_content", "Non puoi segnalare un tuo fit")
    try:
        report_id, created = await file_report(
            session,
            reporter_id=profile.id,
            target_type=body.target_type,
            target_id=target_id,
            reason=body.reason,
            details=details,
            subject_id=subject,
        )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    if not created:
        response.status_code = status.HTTP_200_OK
    priority = {"minor_safety": 0, "nudity": 1, "harassment": 1}.get(body.reason, 2)
    return ReportOut(
        id=report_id,
        priority=priority,
        review_within_hours=int(SLA[priority].total_seconds() // 3600),
    )


# ---------- Avvisi e reclami ----------


@router.get("/me/moderation", response_model=list[NoticeOut])
async def my_notices(profile: CurrentProfileAnyStatus, session: Session) -> list[NoticeOut]:
    rows = (
        (
            await session.execute(
                text(
                    """select m.id, m.action, m.ground, m.statement, m.automated, m.created_at,
                              m.expires_at, m.target_type, m.target_id,
                              (select p.status::text from app.posts p
                                where m.target_type = 'post' and p.id = m.target_id)
                                as post_status,
                              a.status as appeal_status, a.created_at as appeal_at,
                              a.decided_at, a.decision_note,
                              -- Sanzione decisa insieme a un'azione sul fit: il reclamo si fa
                              -- sul fit e vale per entrambe.
                              (m.action in ('warn', 'limit_posting', 'ban') and exists (
                                 select 1 from app.moderation_actions c
                                  where c.subject_id = m.subject_id
                                    and c.created_at = m.created_at
                                    and c.action in ('hide', 'remove'))) as follows_content
                         from app.moderation_actions m
                         left join app.appeals a on a.action_id = m.id
                        where m.subject_id = :me
                        order by m.created_at desc
                        limit 100"""
                ),
                {"me": profile.id},
            )
        )
        .mappings()
        .all()
    )
    now = datetime.now(UTC)
    out = []
    for r in rows:
        deadline = appeal_deadline(r["created_at"])
        appealable = r["action"] != "restore" and not r["follows_content"]
        out.append(
            NoticeOut(
                id=r["id"],
                action=r["action"],
                reason=ground_label(r["ground"]),
                statement=r["statement"],
                automated=r["automated"],
                created_at=r["created_at"],
                expires_at=r["expires_at"],
                post_id=r["target_id"]
                if r["target_type"] == "post" and r["post_status"] not in (None, "deleted")
                else None,
                target_type=r["target_type"],
                appeal=AppealOut(
                    status=r["appeal_status"],
                    created_at=r["appeal_at"],
                    decided_at=r["decided_at"],
                    decision_note=r["decision_note"],
                )
                if r["appeal_status"]
                else None,
                can_appeal=appealable and r["appeal_status"] is None and now <= deadline,
                appeal_until=deadline if appealable else None,
            )
        )
    return out


@router.post(
    "/me/moderation/{action_id}/appeal",
    response_model=AppealOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("appeal", 10, 86400))],
)
async def appeal(
    action_id: uuid.UUID, body: AppealIn, profile: CurrentProfileAnyStatus, session: Session
) -> AppealOut:
    text_value = _free_text(body.text, 1000)
    if not text_value:
        raise ApiError(422, "appeal.text_required", "Spiega perché pensi che sia un errore")
    row = (
        await session.execute(
            text(
                """select action, created_at from app.moderation_actions
                    where id = :id and subject_id = :me"""
            ),
            {"id": action_id, "me": profile.id},
        )
    ).first()
    if row is None:
        raise ApiError(404, "moderation.not_found", "Decisione non trovata")
    if row[0] == "restore" or await session.scalar(
        text(
            """select exists (select 1 from app.moderation_actions c, app.moderation_actions m
                               where m.id = :id and m.action in ('warn', 'limit_posting', 'ban')
                                 and c.subject_id = m.subject_id and c.created_at = m.created_at
                                 and c.action in ('hide', 'remove'))"""
        ),
        {"id": action_id},
    ):
        raise ApiError(422, "appeal.not_allowed", "Il reclamo si fa sulla decisione sul fit")
    if datetime.now(UTC) > appeal_deadline(row[1]):
        raise ApiError(409, "appeal.expired", "Il tempo per il reclamo è scaduto")
    created = (
        await session.execute(
            text(
                """insert into app.appeals (action_id, user_id, text) values (:a, :me, :t)
                   on conflict (action_id) do nothing
                   returning status, created_at, decided_at, decision_note"""
            ),
            {"a": action_id, "me": profile.id, "t": text_value},
        )
    ).first()
    if created is None:
        raise ApiError(409, "appeal.exists", "Hai già fatto reclamo per questa decisione")
    await session.commit()
    return AppealOut(
        status=created[0], created_at=created[1], decided_at=created[2], decision_note=created[3]
    )
