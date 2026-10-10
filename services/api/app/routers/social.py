"""Follow, richieste e blocchi (sez. 6.6 e 14.1).

- Seguire un account Business: subito. Seguire un account privato: richiesta da accettare.
- Un maggiorenne non può nemmeno trovare un 16-17enne (404), quindi non può chiedergli il follow.
- Bloccare toglie i follow e le richieste nei due sensi; da quel momento l'uno per l'altro
  "non esistono" (profilo, griglia, fit nel feed). Si può bloccare chiunque si conosca per
  nickname, anche chi non si vede: è una protezione, non deve dipendere dalla visibilità.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.avatars import AvatarOut, avatar_out
from app.db import get_session
from app.errors import ApiError
from app.notifications import follow_request_handled, forget_between, notify
from app.people import FollowState, find_person, not_found, profile_id_by_nickname
from app.profiles import CurrentProfile, Profile
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1", tags=["social"])

Session = Annotated[AsyncSession, Depends(get_session)]
PAGE = 50


# ---------- Modelli ----------


class FollowOut(BaseModel):
    following: FollowState


class PersonOut(BaseModel):
    nickname: str
    account_type: Literal["private", "business"]
    # Foto profilo (non negli account bloccati).
    avatar: AvatarOut | None = None
    # Da quando (richiesta, follow o blocco).
    since: datetime


class PeoplePage(BaseModel):
    items: list[PersonOut]
    next_cursor: str | None


class RequestDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nickname: str = Field(min_length=1, max_length=40)
    decision: Literal["accept", "reject"]


# ---------- Seguire ----------


@router.post(
    "/users/{nickname}/follow",
    response_model=FollowOut,
    dependencies=[Depends(rate_limit("follow", 100, 86400))],
)
async def follow(nickname: str, viewer: CurrentProfile, session: Session) -> FollowOut:
    person = await find_person(session, viewer, nickname)
    if person.is_self:
        raise ApiError(422, "follow.self", "Non puoi seguire te stesso")
    initial = "accepted" if person.account_type == "business" else "pending"
    created = await session.scalar(
        text(
            """insert into app.follows (follower_id, followee_id, status)
               values (:me, :them, cast(:status as app.follow_status))
               on conflict (follower_id, followee_id) do nothing
               returning status::text"""
        ),
        {"me": viewer.id, "them": person.id, "status": initial},
    )
    if created is not None:
        await notify(
            session,
            user_id=person.id,
            type="follow_request" if created == "pending" else "new_follower",
            actor_id=viewer.id,
            dedupe_key=f"follow:{viewer.id}",
        )
    state = await session.scalar(
        text(
            """select status::text from app.follows
                where follower_id = :me and followee_id = :them"""
        ),
        {"me": viewer.id, "them": person.id},
    )
    await session.commit()
    return FollowOut(following=state)


@router.delete("/users/{nickname}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow(nickname: str, viewer: CurrentProfile, session: Session) -> Response:
    """Smetti di seguire, oppure ritira la richiesta. Ripetibile."""
    target = await profile_id_by_nickname(session, nickname)
    if target is not None:
        await session.execute(
            text("delete from app.follows where follower_id = :me and followee_id = :them"),
            {"me": viewer.id, "them": target},
        )
        # Richiesta ritirata: sparisce anche dalle notifiche di chi l'aveva ricevuta.
        await follow_request_handled(session, followee=target, follower=viewer.id, accepted=False)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Elenchi ----------


def _encode(ts: datetime, nickname: str) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{nickname}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, nickname = raw.split("|")
        return datetime.fromisoformat(ts), nickname
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ApiError(400, "people.invalid_cursor", "Cursore non valido") from exc


# Elenchi: sempre e solo dati della persona che chiede (:me). Tabelle e filtri sono costanti.
_LISTS: dict[str, tuple[str, str, str]] = {
    # nome: (tabella, filtro, colonna dell'altra persona)
    "requests": ("app.follows", "x.followee_id = :me and x.status = 'pending'", "x.follower_id"),
    "followers": ("app.follows", "x.followee_id = :me and x.status = 'accepted'", "x.follower_id"),
    "following": ("app.follows", "x.follower_id = :me and x.status = 'accepted'", "x.followee_id"),
    "blocks": ("app.blocks", "x.blocker_id = :me", "x.blocked_id"),
}


async def _people(
    session: AsyncSession, viewer: Profile, kind: str, cursor: str | None
) -> PeoplePage:
    table, where, other = _LISTS[kind]
    after = _decode(cursor) if cursor else None
    # Negli elenchi di follow non compaiono account sospesi; nei blocchi sì (per sbloccarli).
    active = "" if kind == "blocks" else "and p.status = 'active'"
    rows = (
        (
            await session.execute(
                text(
                    f"""select p.nickname::text as nickname,
                               p.account_type::text as account_type, x.created_at as since,
                               u.id as avatar_id, u.variants as avatar_variants,
                               u.blurhash as avatar_blurhash
                          from {table} x
                          join app.profiles p on p.id = {other}
                          left join app.media_uploads u on u.id = p.avatar_upload_id
                         where {where} {active}
                           and (cast(:ts as timestamptz) is null
                                or (x.created_at, p.nickname::text)
                                   < (cast(:ts as timestamptz), cast(:nick as text)))
                         order by x.created_at desc, p.nickname::text desc
                         limit :limit"""
                ),
                {
                    "me": viewer.id,
                    "ts": after[0] if after else None,
                    "nick": after[1] if after else None,
                    "limit": PAGE + 1,
                },
            )
        )
        .mappings()
        .all()
    )
    page = rows[:PAGE]
    return PeoplePage(
        items=[
            PersonOut(
                nickname=r["nickname"],
                account_type=r["account_type"],
                since=r["since"],
                avatar=None
                if kind == "blocks"
                else avatar_out(r["avatar_id"], r["avatar_variants"], r["avatar_blurhash"]),
            )
            for r in page
        ],
        next_cursor=_encode(page[-1]["since"], page[-1]["nickname"]) if len(rows) > PAGE else None,
    )


Cursor = Annotated[str | None, Query(max_length=200)]


@router.get("/me/follow-requests", response_model=PeoplePage)
async def follow_requests(
    viewer: CurrentProfile, session: Session, cursor: Cursor = None
) -> PeoplePage:
    return await _people(session, viewer, "requests", cursor)


@router.get("/me/followers", response_model=PeoplePage)
async def followers(viewer: CurrentProfile, session: Session, cursor: Cursor = None) -> PeoplePage:
    return await _people(session, viewer, "followers", cursor)


@router.get("/me/following", response_model=PeoplePage)
async def following(viewer: CurrentProfile, session: Session, cursor: Cursor = None) -> PeoplePage:
    return await _people(session, viewer, "following", cursor)


@router.get("/me/blocks", response_model=PeoplePage)
async def blocks(viewer: CurrentProfile, session: Session, cursor: Cursor = None) -> PeoplePage:
    return await _people(session, viewer, "blocks", cursor)


# ---------- Richieste ----------


@router.post(
    "/me/follow-requests",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("follow_decision", 300, 3600))],
)
async def decide_request(
    body: RequestDecision, viewer: CurrentProfile, session: Session
) -> Response:
    requester = await profile_id_by_nickname(session, body.nickname)
    row: Any = None
    if requester is not None:
        row = (
            (
                await session.execute(
                    text(
                        """select a.age_band::text as age_band from app.follows f
                             join app.profiles a on a.id = f.follower_id
                            where f.follower_id = :them and f.followee_id = :me
                              and f.status = 'pending'
                            for update of f"""
                    ),
                    {"them": requester, "me": viewer.id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise ApiError(404, "follow.request_not_found", "Richiesta non trovata")
    accept = body.decision == "accept"
    if accept and not viewer.is_adult and row["age_band"] == "18_plus":
        # Un adulto non può seguire un 16-17enne (la richiesta può esistere solo se nel
        # frattempo chi l'ha fatta ha compiuto 18 anni).
        accept = False
    if accept:
        await session.execute(
            text(
                """update app.follows set status = 'accepted'
                    where follower_id = :them and followee_id = :me"""
            ),
            {"them": requester, "me": viewer.id},
        )
    else:
        await session.execute(
            text("delete from app.follows where follower_id = :them and followee_id = :me"),
            {"them": requester, "me": viewer.id},
        )
    assert requester is not None
    await follow_request_handled(session, followee=viewer.id, follower=requester, accepted=accept)
    if accept:
        await notify(
            session,
            user_id=requester,
            type="follow_accepted",
            actor_id=viewer.id,
            dedupe_key=f"accepted:{viewer.id}",
        )
    await session.commit()
    if body.decision == "accept" and not accept:
        raise ApiError(409, "follow.not_allowed", "Questa persona non può seguirti")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/followers/{nickname}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_follower(nickname: str, viewer: CurrentProfile, session: Session) -> Response:
    """Togli un follower (o rifiuta la sua richiesta): non vede più il tuo portfolio."""
    them = await profile_id_by_nickname(session, nickname)
    if them is not None:
        await session.execute(
            text("delete from app.follows where follower_id = :them and followee_id = :me"),
            {"them": them, "me": viewer.id},
        )
        await follow_request_handled(session, followee=viewer.id, follower=them, accepted=False)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Blocchi ----------


@router.put(
    "/users/{nickname}/block",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("block", 60, 3600))],
)
async def block(nickname: str, viewer: CurrentProfile, session: Session) -> Response:
    them = await profile_id_by_nickname(session, nickname)
    if them is None:
        raise not_found()
    if them == viewer.id:
        raise ApiError(422, "block.self", "Non puoi bloccare te stesso")
    await session.execute(
        text(
            """insert into app.blocks (blocker_id, blocked_id) values (:me, :them)
               on conflict do nothing"""
        ),
        {"me": viewer.id, "them": them},
    )
    await session.execute(
        text(
            """delete from app.follows
                where (follower_id = :me and followee_id = :them)
                   or (follower_id = :them and followee_id = :me)"""
        ),
        {"me": viewer.id, "them": them},
    )
    await forget_between(session, viewer.id, them)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{nickname}/block", status_code=status.HTTP_204_NO_CONTENT)
async def unblock(nickname: str, viewer: CurrentProfile, session: Session) -> Response:
    """Sblocca. I follow tolti dal blocco non tornano: vanno richiesti di nuovo."""
    them = await profile_id_by_nickname(session, nickname)
    if them is not None:
        await session.execute(
            text("delete from app.blocks where blocker_id = :me and blocked_id = :them"),
            {"me": viewer.id, "them": them},
        )
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
