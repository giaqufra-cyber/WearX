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
    # L'accesso usato per questa richiesta è stato tolto dalla persona (Dispositivi collegati).
    session_revoked: bool = False

    @property
    def is_adult(self) -> bool:
        return self.age_band == "18_plus"


_PROFILE_SQL = text(
    """
    select id, nickname::text as nickname, bio, account_type::text as account_type,
           age_band::text as age_band, adult_on, hide_prices, hide_vote_count,
           status::text as status, created_at,
           exists (select 1 from app.devices d
                    where d.session_id = cast(:sid as text) and d.revoked_at is not null)
             as session_revoked
      from app.profiles where id = :id
    """
)


async def load_profile(
    session: AsyncSession, user_id: uuid.UUID, session_id: str | None = None
) -> Profile | None:
    params = {"id": user_id, "sid": session_id}
    row = (await session.execute(_PROFILE_SQL, params)).mappings().first()
    if row is None:
        return None
    if (
        row["age_band"] == "16_17"
        and row["adult_on"] is not None
        and row["adult_on"] <= date.today()
    ):
        # Ha compiuto 18 anni: passa alla fascia 18+ (sez. 11.2). Una sola volta, poi è salvato.
        await session.execute(text("select app.promote_adults(:id)"), {"id": user_id})
        await session.commit()
        row = (await session.execute(_PROFILE_SQL, params)).mappings().first()
        assert row is not None
    return Profile(**row)


# Stili "visibili": attivi oggi e permessi alla fascia d'età (i 16-17 non vedono i 18+).
VISIBLE_STYLE_SQL = """
    s.is_active
    and (s.active_from is null or s.active_from <= current_date)
    and (s.active_until is null or s.active_until >= current_date)
    and (cast(:adult as boolean) or s.min_age_band <> '18_plus')
"""


async def joined_style_slugs(session: AsyncSession, profile: Profile) -> list[str]:
    rows = await session.execute(
        text(
            "select s.slug from app.style_memberships m join app.styles s on s.id = m.style_id "
            f"where m.user_id = :id and {VISIBLE_STYLE_SQL} order by m.joined_at, s.sort_order"
        ),
        {"id": profile.id, "adult": profile.is_adult},
    )
    return [r[0] for r in rows]


async def _profile_for(request: Request, session: AsyncSession, allow_suspended: bool) -> Profile:
    auth: AuthContext = await current_auth(request)
    profile = await load_profile(session, auth.user_id, auth.session_id)
    if profile is None:
        raise ApiError(409, "onboarding.required", "Completa la registrazione per continuare")
    if profile.session_revoked:
        # Dispositivo tolto dalla persona: questo accesso non vale più (anche se rinnovato).
        raise ApiError(401, "auth.session_revoked", "Accesso terminato da un altro dispositivo")
    if profile.status == "suspended" and not allow_suspended:
        raise ApiError(403, "account.suspended", "Account sospeso")
    if profile.status == "pending_deletion" and not allow_suspended:
        raise ApiError(403, "account.pending_deletion", "Account in cancellazione")
    return profile


async def current_profile(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Profile:
    """Utente autenticato con profilo attivo."""
    return await _profile_for(request, session, allow_suspended=False)


async def current_profile_any_status(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> Profile:
    """Come sopra ma ammette account sospesi o in cancellazione: serve all'app per mostrare la
    schermata giusta (e per annullare la cancellazione)."""
    return await _profile_for(request, session, allow_suspended=True)


CurrentProfile = Annotated[Profile, Depends(current_profile)]
CurrentProfileAnyStatus = Annotated[Profile, Depends(current_profile_any_status)]
