"""Raccolta degli eventi d'uso (seduta 18), con lista consentita.

Si raccolgono SOLO i quattro eventi che servono agli Insight per chi pubblica (seduta 19):
fit visto nel feed, fit aperto, tocco sul link di un negozio, profilo visitato. Nient'altro:
nessun evento libero, nessun campo libero, nessun identificativo del telefono, nessun IP.

- Chi l'ha fatto è salvato come pseudonimo (HMAC con un segreto del server): serve a contare
  le persone diverse, non a sapere chi sono.
- I propri fit e il proprio profilo non contano.
- Gli eventi grezzi restano circa 3 mesi (partizioni mensili), poi restano solo i totali.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.people import NICKNAME_RE
from app.profiles import CurrentProfile
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1", tags=["events"])

Session = Annotated[AsyncSession, Depends(get_session)]
MAX_AGE = timedelta(hours=24)  # eventi rimasti nel telefono senza rete

Source = Literal["feed", "style", "profile", "post"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Quando è successo (l'app li manda a gruppi); più vecchi di 24 ore si scartano.
    at: datetime | None = None


class PostImpression(_Base):
    name: Literal["post_impression"]
    post_id: uuid.UUID
    source: Source


class PostOpen(_Base):
    name: Literal["post_open"]
    post_id: uuid.UUID
    source: Source


class ShopClick(_Base):
    name: Literal["shop_click"]
    post_id: uuid.UUID
    item: int = Field(ge=0, le=19)


class ProfileView(_Base):
    name: Literal["profile_view"]
    nickname: str = Field(min_length=3, max_length=20)


Event = Annotated[PostImpression | PostOpen | ShopClick | ProfileView, Field(discriminator="name")]


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[Event] = Field(min_length=1, max_length=50)


class EventsAccepted(BaseModel):
    accepted: int


def actor_key(user_id: uuid.UUID) -> bytes:
    pepper = get_settings().vote_pepper.get_secret_value().encode()
    # Prefisso diverso da quello dei voti: i due pseudonimi non si possono collegare.
    return hmac.new(pepper, b"event:" + user_id.bytes, hashlib.sha256).digest()[:16]


@router.post(
    "/events",
    response_model=EventsAccepted,
    status_code=202,
    dependencies=[Depends(rate_limit("events", 360, 3600))],
)
async def collect(body: EventBatch, viewer: CurrentProfile, session: Session) -> EventsAccepted:
    now = datetime.now(UTC)
    post_ids = {e.post_id for e in body.events if not isinstance(e, ProfileView)}
    nicknames = {
        e.nickname
        for e in body.events
        if isinstance(e, ProfileView) and NICKNAME_RE.fullmatch(e.nickname)
    }
    authors: dict[uuid.UUID, uuid.UUID] = {}
    if post_ids:
        authors = dict(
            (
                await session.execute(
                    text(
                        """select id, author_id from app.posts
                            where id = any(:ids) and status in ('active', 'style_rejected')"""
                    ),
                    {"ids": list(post_ids)},
                )
            ).all()
        )
    profiles: dict[str, uuid.UUID] = {}
    if nicknames:
        profiles = {
            nick.lower(): pid
            for nick, pid in (
                await session.execute(
                    text(
                        """select nickname::text, id from app.profiles
                            where nickname = any(cast(:n as citext[])) and status = 'active'"""
                    ),
                    {"n": list(nicknames)},
                )
            ).all()
        }

    key = actor_key(viewer.id)
    rows: list[dict[str, object]] = []
    for event in body.events:
        at = event.at or now
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        if at > now + timedelta(minutes=5) or at < now - MAX_AGE:
            continue
        at = min(at, now)
        if isinstance(event, ProfileView):
            profile = profiles.get(event.nickname.lower())
            if profile is None or profile == viewer.id:
                continue
            rows.append(
                {
                    "name": event.name,
                    "post": None,
                    "props": json.dumps({"profile_id": str(profile)}),
                    "ts": at,
                }
            )
            continue
        author = authors.get(event.post_id)
        if author is None or author == viewer.id:
            continue
        props = json.dumps(
            {"item": event.item} if isinstance(event, ShopClick) else {"source": event.source}
        )
        rows.append({"name": event.name, "post": event.post_id, "props": props, "ts": at})

    if rows:
        await session.execute(
            text(
                """insert into app.events (actor_key, name, post_id, props, ts)
                   values (:key, :name, :post, cast(:props as jsonb), :ts)"""
            ),
            [{**row, "key": key} for row in rows],
        )
        await session.commit()
    return EventsAccepted(accepted=len(rows))
