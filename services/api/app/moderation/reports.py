"""Segnalazioni (art. 16 DSA) con priorità e azioni immediate (sez. 14.3).

- P0 sicurezza dei minori: il fit segnalato si nasconde subito, in attesa del moderatore
  (entro 1 ora). L'account si sospende in automatico con una corrispondenza di hash oppure con
  segnalazioni P0 da almeno 2 persone diverse (account di almeno 24 ore): con una sola
  segnalazione chiunque potrebbe far sospendere chiunque.
- P1 (nudità, molestie): il fit si nasconde dopo segnalazioni da 3 persone diverse con account
  di almeno 24 ore (account appena creati non contano: difesa dai gruppi di finti account).
- P2: nessuna azione automatica, revisione entro 72 ore.
Una persona ha una sola segnalazione aperta per contenuto (ripetere non conta di più).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.moderation.actions import hide_post, suspend_pending_review

Reason = Literal[
    "nudity",
    "minor_safety",
    "harassment",
    "spam",
    "wrong_style",
    "dangerous_link",
    "stolen_photo",
    "other",
]
TargetType = Literal["post", "profile", "link"]

PRIORITY: dict[str, int] = {
    "minor_safety": 0,
    "nudity": 1,
    "harassment": 1,
    "spam": 2,
    "wrong_style": 2,
    "dangerous_link": 2,
    "stolen_photo": 2,
    "other": 2,
}
# Tempo massimo per la revisione umana, per priorità.
SLA = {0: timedelta(hours=1), 1: timedelta(hours=24), 2: timedelta(hours=72)}
AUTO_HIDE_REPORTERS = 3
P0_SUSPEND_REPORTERS = 2
TRUSTED_ACCOUNT_AGE = timedelta(hours=24)


async def _independent_reporters(
    session: AsyncSession, target_type: str, target_id: uuid.UUID, max_priority: int
) -> int:
    count = await session.scalar(
        text(
            """select count(distinct r.reporter_id) from app.reports r
                 join app.profiles p on p.id = r.reporter_id
                where r.target_type = :tt and r.target_id = :tid
                  and r.status in ('open', 'in_review') and r.priority <= :prio
                  and p.status = 'active' and p.created_at <= now() - cast(:age as interval)"""
        ),
        {"tt": target_type, "tid": target_id, "prio": max_priority, "age": TRUSTED_ACCOUNT_AGE},
    )
    return int(count or 0)


async def file_report(
    session: AsyncSession,
    *,
    reporter_id: uuid.UUID | None,
    target_type: TargetType,
    target_id: uuid.UUID,
    reason: str,
    details: str | None,
    subject_id: uuid.UUID | None,
    auto: bool = False,
) -> tuple[uuid.UUID, bool]:
    """Registra la segnalazione e applica le azioni immediate. Restituisce (id, nuova)."""
    priority = PRIORITY[reason]
    if reporter_id is not None:
        existing = await session.scalar(
            text(
                """select id from app.reports
                    where reporter_id = :me and target_type = :tt and target_id = :tid
                      and status in ('open', 'in_review')"""
            ),
            {"me": reporter_id, "tt": target_type, "tid": target_id},
        )
        if existing is not None:
            return existing, False
    report_id = await session.scalar(
        text(
            """insert into app.reports
                 (reporter_id, target_type, target_id, reason, details, priority, auto)
               values (:me, :tt, :tid, :reason, :details, :prio, :auto)
               on conflict do nothing
               returning id"""
        ),
        {
            "me": reporter_id,
            "tt": target_type,
            "tid": target_id,
            "reason": reason,
            "details": details,
            "prio": priority,
            "auto": auto,
        },
    )
    if report_id is None:  # stessa segnalazione arrivata due volte insieme
        report_id = await session.scalar(
            text(
                """select id from app.reports
                    where reporter_id = :me and target_type = :tt and target_id = :tid
                      and status in ('open', 'in_review')"""
            ),
            {"me": reporter_id, "tt": target_type, "tid": target_id},
        )
        assert isinstance(report_id, uuid.UUID)
        return report_id, False
    assert isinstance(report_id, uuid.UUID)

    if target_type == "post" and not auto:
        if priority == 0:
            await hide_post(
                session, target_id, ground="minor_safety", automated=True, actor_id=None
            )
        elif priority == 1 and (
            await _independent_reporters(session, "post", target_id, 1) >= AUTO_HIDE_REPORTERS
        ):
            await hide_post(
                session, target_id, ground="community_reports", automated=True, actor_id=None
            )
    if priority == 0 and subject_id is not None and not auto:
        # Segnalazioni P0 sulla persona (sul profilo o su suoi fit) da più persone diverse.
        reporters = await session.scalar(
            text(
                """select count(distinct r.reporter_id) from app.reports r
                     join app.profiles p on p.id = r.reporter_id
                    where r.status in ('open', 'in_review') and r.priority = 0
                      and p.status = 'active' and p.created_at <= now() - cast(:age as interval)
                      and ((r.target_type = 'profile' and r.target_id = :uid)
                           or (r.target_type = 'post' and r.target_id in (
                                 select id from app.posts where author_id = :uid)))"""
            ),
            {"uid": subject_id, "age": TRUSTED_ACCOUNT_AGE},
        )
        if int(reporters or 0) >= P0_SUSPEND_REPORTERS:
            await suspend_pending_review(session, subject_id, ground="minor_safety")
    return report_id, True
