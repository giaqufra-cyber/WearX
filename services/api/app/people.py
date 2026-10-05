"""Chi può vedere chi (sez. 6.6 e 14.1). Unico punto per trovare una persona dal nickname.

Una persona "non esiste" (404 identico a un nickname inesistente) se:
- c'è un blocco, in una qualsiasi direzione;
- l'account non è attivo (sospeso, in cancellazione), tranne per sé stessi;
- è un utente 16-17 e chi guarda è maggiorenne: i profili dei 16-17 si vedono solo tra 16-17.
Il portfolio si vede se: sei tu, è un account Business, oppure lo segui (richiesta accettata).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.profiles import Profile

NICKNAME_RE = re.compile(r"^[A-Za-z0-9._]{3,20}$")

FollowState = Literal["none", "pending", "accepted"]


@dataclass(frozen=True, slots=True)
class Person:
    id: uuid.UUID
    nickname: str
    bio: str | None
    account_type: Literal["private", "business"]
    age_band: Literal["16_17", "18_plus"]
    hide_vote_count: bool
    is_self: bool
    can_view: bool
    # Il rapporto tra chi guarda e questa persona.
    following: FollowState
    follows_you: bool


_PERSON_SQL = text(
    """select a.id, a.nickname::text as nickname, a.bio,
              a.account_type::text as account_type, a.age_band::text as age_band,
              a.hide_vote_count, a.id = :viewer as is_self,
              coalesce((select f.status::text from app.follows f
                         where f.follower_id = :viewer and f.followee_id = a.id), 'none')
                as following,
              exists (select 1 from app.follows f
                       where f.follower_id = a.id and f.followee_id = :viewer
                         and f.status = 'accepted') as follows_you
         from app.profiles a
        where a.nickname = :nick
          and (a.status = 'active' or a.id = :viewer)
          and (a.id = :viewer or a.age_band = '18_plus' or not cast(:adult as boolean))
          and not exists (
            select 1 from app.blocks b
             where (b.blocker_id = :viewer and b.blocked_id = a.id)
                or (b.blocker_id = a.id and b.blocked_id = :viewer))"""
)


def not_found() -> ApiError:
    return ApiError(404, "user.not_found", "Profilo non trovato")


async def find_person(session: AsyncSession, viewer: Profile, nickname: str) -> Person:
    if not NICKNAME_RE.fullmatch(nickname):
        raise not_found()
    row = (
        (
            await session.execute(
                _PERSON_SQL,
                {"nick": nickname.lower(), "viewer": viewer.id, "adult": viewer.is_adult},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    can_view = bool(
        row["is_self"] or row["account_type"] == "business" or row["following"] == "accepted"
    )
    return Person(**row, can_view=can_view)


async def profile_id_by_nickname(session: AsyncSession, nickname: str) -> uuid.UUID | None:
    """Solo l'id, senza regole di visibilità: per bloccare e sbloccare chiunque."""
    if not NICKNAME_RE.fullmatch(nickname):
        return None
    value = await session.scalar(
        text("select id from app.profiles where nickname = :nick"), {"nick": nickname.lower()}
    )
    return value if isinstance(value, uuid.UUID) else None
