"""Profili WearX: lettura dal database e dipendenze per gli endpoint che richiedono un profilo."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, current_auth
from app.db import get_session
from app.errors import ApiError


@dataclass(frozen=True, slots=True)
class Profile:
    id: uuid.UUID
    nickname: str
    bio: str | None
    account_type: Literal["private", "business"]
    age_band: Literal["16_17", "18_plus"]
    adult_on: date | None
    hide_prices: bool
    hide_vote_count: bool
    status: Literal["active", "suspended", "pending_deletion"]
    created_at: datetime

    @property
    def is_adult(self) -> bool:
        return self.age_band == "18_plus"


_PROFILE_SQL = text(
    """
    select id, nickname::text as nickname, bio, account_type::text as account_type,
           age_band::text as age_band, adult_on, hide_prices, hide_vote_count,
           status::text as status, created_at
      from app.profiles where id = :id
    """
)


async def load_profile(session: AsyncSession, user_id: uuid.UUID) -> Profile | None:
    row = (await session.execute(_PROFILE_SQL, {"id": user_id})).mappings().first()
    return Profile(**row) if row else None


async def joined_style_slugs(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await session.execute(
        text(
            """select s.slug from app.style_memberships m join app.styles s on s.id = m.style_id
                where m.user_id = :id order by s.sort_order, s.id"""
        ),
        {"id": user_id},
    )
    return [r[0] for r in rows]


async def _profile_for(request: Request, session: AsyncSession, allow_suspended: bool) -> Profile:
    auth: AuthContext = await current_auth(request)
    profile = await load_profile(session, auth.user_id)
    if profile is None:
        raise ApiError(409, "onboarding.required", "Completa la registrazione per continuare")
    if profile.status == "suspended" and not allow_suspended:
        raise ApiError(403, "account.suspended", "Account sospeso")
    return profile


async def current_profile(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Profile:
    """Utente autenticato con profilo attivo."""
    return await _profile_for(request, session, allow_suspended=False)


async def current_profile_any_status(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Profile:
    """Come sopra ma ammette account sospesi: serve all'app per mostrare la schermata giusta."""
    return await _profile_for(request, session, allow_suspended=True)


CurrentProfile = Annotated[Profile, Depends(current_profile)]
CurrentProfileAnyStatus = Annotated[Profile, Depends(current_profile_any_status)]
