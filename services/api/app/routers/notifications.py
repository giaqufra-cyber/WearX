"""Notifiche nell'app, telefoni per i push, preferenze (seduta 18).

Ogni persona vede e tocca solo le proprie notifiche e i propri telefoni.
"""

from __future__ import annotations

import base64
import binascii
import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentAuth
from app.db import get_session
from app.errors import ApiError
from app.notifications import CATEGORY, render
from app.profiles import CurrentProfile
from app.ratelimit import rate_limit
from app.routers.media import MediaUrls, media_urls

router = APIRouter(prefix="/v1", tags=["notifications"])

Session = Annotated[AsyncSession, Depends(get_session)]
PAGE = 30
MAX_TOKENS = 10
# Formato dei token del servizio push di Expo.
EXPO_TOKEN_RE = re.compile(r"^Expo(nent)?PushToken\[[A-Za-z0-9_-]{10,200}\]$")


# ---------- Modelli ----------


class NotificationActor(BaseModel):
    nickname: str
    account_type: Literal["private", "business"]
    # Il profilo si può aprire (un maggiorenne non apre i profili dei 16-17).
    can_open: bool


class NotificationPost(BaseModel):
    id: uuid.UUID
    blurhash: str | None
    thumb: MediaUrls | None


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: Literal[
        "follow_request",
        "new_follower",
        "follow_accepted",
        "vote_milestone",
        "moderation",
        "appeal_decided",
        "export_ready",
    ]
    title: str
    body: str
    # Percorso nell'app da aprire al tocco.
    url: str
    created_at: datetime
    read: bool
    actor: NotificationActor | None
    post: NotificationPost | None


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    unread: int


class UnreadOut(BaseModel):
    unread: int


class MarkRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    all: bool = False

    @model_validator(mode="after")
    def one_of(self) -> MarkRead:
        if (self.ids is None) == (not self.all):
            raise ValueError("indica 'ids' oppure 'all': true")
        return self


class PushTokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=250)
    platform: Literal["ios", "android"]


class NotificationSettings(BaseModel):
    follows: bool
    votes: bool
    moderation: bool


class NotificationSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    follows: bool | None = None
    votes: bool | None = None
    moderation: bool | None = None


# ---------- Lista ----------


def _encode(ts: datetime, nid: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{nid}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, nid = raw.split("|")
        return datetime.fromisoformat(ts), uuid.UUID(nid)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ApiError(400, "notifications.invalid_cursor", "Cursore non valido") from exc


# Visibili: chi ha causato la notifica è ancora attivo, e una richiesta di follow compare solo
# finché è in attesa (ritirata o decisa altrove sparisce).
_VISIBLE = """
      n.user_id = :me
  and (n.actor_id is null or a.status = 'active')
  and (n.type <> 'follow_request' or exists (
        select 1 from app.follows f
         where f.follower_id = n.actor_id and f.followee_id = n.user_id
           and f.status = 'pending'))
"""


async def _unread(session: AsyncSession, me: uuid.UUID) -> int:
    count = await session.scalar(
        text(
            f"""select count(*) from app.notifications n
                  left join app.profiles a on a.id = n.actor_id
                 where {_VISIBLE} and n.read_at is null"""
        ),
        {"me": me},
    )
    return int(count or 0)


@router.get("/notifications", response_model=NotificationPage)
async def notifications(
    viewer: CurrentProfile,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> NotificationPage:
    after = _decode(cursor) if cursor else None
    rows = (
        (
            await session.execute(
                text(
                    f"""select n.id, n.type, n.payload, n.created_at, n.read_at, n.post_id,
                               a.nickname::text as actor, a.account_type::text as actor_type,
                               a.age_band::text as actor_band, p.caption,
                               m.upload_id, m.variants, m.blurhash
                          from app.notifications n
                          left join app.profiles a on a.id = n.actor_id
                          left join app.posts p on p.id = n.post_id and p.status <> 'deleted'
                          left join app.post_media m on m.post_id = p.id and m.position = 0
                         where {_VISIBLE}
                           and (cast(:ts as timestamptz) is null
                                or (n.created_at, n.id) < (cast(:ts as timestamptz), :nid))
                         order by n.created_at desc, n.id desc
                         limit :limit"""
                ),
                {
                    "me": viewer.id,
                    "ts": after[0] if after else None,
                    "nid": after[1] if after else uuid.UUID(int=0),
                    "limit": PAGE + 1,
                },
            )
        )
        .mappings()
        .all()
    )
    page = rows[:PAGE]
    items = [_item(viewer.is_adult, r) for r in page]
    return NotificationPage(
        items=items,
        next_cursor=_encode(page[-1]["created_at"], page[-1]["id"]) if len(rows) > PAGE else None,
        unread=await _unread(session, viewer.id),
    )


def _item(viewer_adult: bool, row: Any) -> NotificationOut:
    shown = render(
        row["type"],
        row["payload"],
        actor=row["actor"],
        caption=row["caption"],
        post_id=row["post_id"],
    )
    actor = (
        NotificationActor(
            nickname=row["actor"],
            account_type=row["actor_type"],
            can_open=not viewer_adult or row["actor_band"] == "18_plus",
        )
        if row["actor"]
        else None
    )
    post = None
    if row["post_id"] is not None and row["blurhash"] is not None:
        smallest = sorted(row["variants"] or [])[:1]
        post = NotificationPost(
            id=row["post_id"],
            blurhash=row["blurhash"],
            thumb=media_urls(row["upload_id"], smallest) if smallest else None,
        )
    url = shown.url
    if actor is not None and not actor.can_open and url.startswith("/user/"):
        url = "/notifications"
    return NotificationOut(
        id=row["id"],
        type=row["type"],
        title=shown.title,
        body=shown.body,
        url=url,
        created_at=row["created_at"],
        read=row["read_at"] is not None,
        actor=actor,
        post=post,
    )


@router.get("/notifications/unread", response_model=UnreadOut)
async def unread(viewer: CurrentProfile, session: Session) -> UnreadOut:
    return UnreadOut(unread=await _unread(session, viewer.id))


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(body: MarkRead, viewer: CurrentProfile, session: Session) -> Response:
    await session.execute(
        text(
            """update app.notifications set read_at = now()
                where user_id = :me and read_at is null
                  and (cast(:all as boolean) or id = any(:ids))"""
        ),
        {"me": viewer.id, "all": body.all, "ids": body.ids or []},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Telefoni ----------


@router.put(
    "/me/push-tokens",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("push_token", 30, 3600))],
)
async def register_token(
    body: PushTokenIn, viewer: CurrentProfile, auth: CurrentAuth, session: Session
) -> Response:
    """Registra il telefono per i push. Lo stesso telefono passato a un altro account cambia
    proprietario (un telefono riceve i push di un solo account: quello con cui è entrato)."""
    if not EXPO_TOKEN_RE.fullmatch(body.token):
        raise ApiError(422, "push.bad_token", "Token push non valido")
    await session.execute(
        text(
            """insert into app.push_tokens (token, user_id, platform, session_id)
               values (:token, :me, :platform, :sid)
               on conflict (token) do update
                  set user_id = excluded.user_id, platform = excluded.platform,
                      session_id = excluded.session_id,
                      last_seen = now(),
                      created_at = case when app.push_tokens.user_id = excluded.user_id
                                        then app.push_tokens.created_at else now() end"""
        ),
        {"token": body.token, "me": viewer.id, "platform": body.platform, "sid": auth.session_id},
    )
    # Al massimo 10 telefoni: i più vecchi escono.
    await session.execute(
        text(
            """delete from app.push_tokens where user_id = :me and token in (
                 select token from app.push_tokens where user_id = :me
                  order by last_seen desc offset :keep)"""
        ),
        {"me": viewer.id, "keep": MAX_TOKENS},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/push-tokens/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_token(token: str, viewer: CurrentProfile, session: Session) -> Response:
    """All'uscita dall'account: quel telefono non riceve più push. Ripetibile."""
    await session.execute(
        text("delete from app.push_tokens where token = :token and user_id = :me"),
        {"token": token, "me": viewer.id},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Preferenze ----------


async def _settings(session: AsyncSession, me: uuid.UUID) -> NotificationSettings:
    row = (
        await session.execute(
            text(
                """select notify_follows, notify_votes, notify_moderation
                     from app.profiles where id = :me"""
            ),
            {"me": me},
        )
    ).one()
    return NotificationSettings(follows=row[0], votes=row[1], moderation=row[2])


@router.get("/me/notification-settings", response_model=NotificationSettings)
async def get_settings_(viewer: CurrentProfile, session: Session) -> NotificationSettings:
    return await _settings(session, viewer.id)


@router.patch("/me/notification-settings", response_model=NotificationSettings)
async def patch_settings(
    body: NotificationSettingsPatch, viewer: CurrentProfile, session: Session
) -> NotificationSettings:
    """Quali push ricevere. La lista nell'app resta completa."""
    changes = body.model_dump(exclude_none=True)
    for category, on in changes.items():
        # Colonne fisse (nessun testo dell'utente nella query).
        column = {"follows": "notify_follows", "votes": "notify_votes"}.get(
            category, "notify_moderation"
        )
        await session.execute(
            text(f"update app.profiles set {column} = :on where id = :me"),
            {"on": on, "me": viewer.id},
        )
        if not on:
            # I push già in coda di quel tipo non partono più.
            types = [t for t, c in CATEGORY.items() if c == category]
            await session.execute(
                text(
                    """update app.notifications set push_state = 'none'
                        where user_id = :me and push_state = 'pending' and type = any(:types)"""
                ),
                {"me": viewer.id, "types": types},
            )
    await session.commit()
    return await _settings(session, viewer.id)
