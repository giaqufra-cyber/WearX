"""Staff di moderazione: chi è nella tabella `app.staff`, con il secondo fattore attivo.

Ogni azione dello staff finisce in `admin_audit_log` (il ruolo dell'API non può modificarlo
né cancellarlo: vedi migrazione 0001).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentAuth
from app.config import get_settings
from app.db import get_session
from app.errors import ApiError


@dataclass(frozen=True, slots=True)
class Staff:
    id: uuid.UUID
    role: Literal["moderator", "admin"]


async def current_staff(
    auth: CurrentAuth, session: Annotated[AsyncSession, Depends(get_session)]
) -> Staff:
    role = await session.scalar(
        text("select role from app.staff where user_id = :id"), {"id": auth.user_id}
    )
    if role is None:
        # Per chi non è staff gli strumenti di moderazione "non esistono".
        raise ApiError(404, "resource.not_found", "Risorsa non trovata")
    if get_settings().staff_require_mfa and auth.aal != "aal2":
        raise ApiError(403, "staff.mfa_required", "Serve l'accesso con il secondo fattore")
    return Staff(id=auth.user_id, role=role)


CurrentStaff = Annotated[Staff, Depends(current_staff)]


async def audit(
    session: AsyncSession, staff: Staff, action: str, target: str, details: dict[str, Any]
) -> None:
    await session.execute(
        text(
            """insert into app.admin_audit_log (admin_id, action, target, details)
               values (:admin, :action, :target, cast(:details as jsonb))"""
        ),
        {
            "admin": staff.id,
            "action": action,
            "target": target,
            "details": json.dumps(details, default=str),
        },
    )
