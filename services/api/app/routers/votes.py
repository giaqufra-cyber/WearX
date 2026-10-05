"""Voto su un post: PUT /v1/posts/{id}/vote (sez. 6.7).

Voto e statistiche cambiano nella STESSA transazione, sotto il lock della riga delle
statistiche: con mille voti in contemporanea conteggi e somme restano esatti.
Il voto si può cambiare; la risposta sulla conferma dello stile no (vale la prima).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.post_access import POST_VISIBLE_SQL
from app.post_views import VoteSummary, post_out
from app.profiles import CurrentProfile, Profile
from app.ratelimit import rate_limit
from app.votes import (
    CONFIRM_SAMPLE,
    FLAG_FACTOR_SQL,
    bucket,
    device_weight,
    style_rejected,
    vote_weight,
    voter_key,
)

router = APIRouter(prefix="/v1/posts", tags=["votes"])

Session = Annotated[AsyncSession, Depends(get_session)]


class VoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: int = Field(ge=1, le=100)
    # "È davvero <stile>?" — solo se la domanda è stata posta (ask_style_confirm).
    style_confirm: bool | None = None


async def _votable_post(session: AsyncSession, profile: Profile, post_id: uuid.UUID) -> Any:
    row = (
        (
            await session.execute(
                text(
                    f"""select p.id, p.author_id, p.status::text as status
                          from app.posts p
                          join app.profiles a on a.id = p.author_id
                          join app.styles s on s.id = p.style_id
                         where p.id = :id and {POST_VISIBLE_SQL}"""
                ),
                {"id": post_id, "viewer": profile.id, "adult": profile.is_adult},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "post.not_found", "Post non trovato")
    if row["author_id"] == profile.id:
        raise ApiError(403, "vote.own_post", "Non puoi votare i tuoi fit")
    if row["status"] not in ("active", "style_rejected"):
        raise ApiError(409, "vote.not_allowed", "Questo post non si può votare")
    return row


@router.put(
    "/{post_id}/vote",
    response_model=VoteSummary,
    dependencies=[
        Depends(rate_limit("vote", 300, 3600)),
        # Raffica: più di un voto ogni secondo e mezzo per un minuto non è una persona.
        Depends(rate_limit("vote_burst", 40, 60)),
    ],
)
async def vote(
    post_id: uuid.UUID, body: VoteIn, profile: CurrentProfile, session: Session
) -> VoteSummary:
    if get_settings().attestation_mode == "required" and not profile.session_attested:
        raise ApiError(
            403, "device.not_verified", "Serve l'app ufficiale su un dispositivo verificato"
        )
    post = await _votable_post(session, profile, post_id)
    key = voter_key(profile.id)
    base_weight = vote_weight(profile.created_at) * device_weight(profile.session_attested)
    flag_factor = float(
        await session.scalar(
            text("select " + FLAG_FACTOR_SQL.format(key=":k", created="now()", author=":author")),
            {"k": key, "author": post["author_id"]},
        )
        or 0.0
    )
    weight = base_weight * flag_factor
    new_bucket = bucket(body.score)
    try:
        # Il lock sulle statistiche mette in fila i voti dello stesso post.
        stats = (
            (
                await session.execute(
                    text(
                        """select confirm_yes, confirm_no from app.post_stats
                            where post_id = :p for update"""
                    ),
                    {"p": post_id},
                )
            )
            .mappings()
            .one()
        )
        previous = (
            (
                await session.execute(
                    text(
                        """select score, style_confirm, weight from app.votes
                            where post_id = :p and voter_key = :k"""
                    ),
                    {"p": post_id, "k": key},
                )
            )
            .mappings()
            .first()
        )
        sampling = stats["confirm_yes"] + stats["confirm_no"] < CONFIRM_SAMPLE
        if previous is None:
            confirm = body.style_confirm if sampling and post["status"] == "active" else None
            await session.execute(
                text(
                    """insert into app.votes
                         (post_id, voter_key, score, style_confirm, weight, base_weight)
                       values (:p, :k, :s, :c, cast(:w as real), cast(:bw as real))"""
                ),
                {
                    "p": post_id,
                    "k": key,
                    "s": body.score,
                    "c": confirm,
                    "w": weight,
                    "bw": base_weight,
                },
            )
            # I voti neutralizzati (peso 0) non entrano né nel numero né nell'istogramma.
            counted = 1 if weight > 0 else 0
            await session.execute(
                text(
                    """update app.post_stats set
                         vote_count = vote_count + cast(:n as integer),
                         vote_sum = vote_sum + cast(:s as integer) * cast(:n as integer),
                         vote_wsum = vote_wsum + :s * cast(:w as double precision),
                         vote_wcount = vote_wcount + cast(:w as double precision),
                         hist[:b] = hist[:b] + cast(:n as integer),
                         unpublished_writes = unpublished_writes + 1,
                         confirm_yes = confirm_yes
                           + (case when cast(:c as boolean) is true then 1 else 0 end),
                         confirm_no = confirm_no
                           + (case when cast(:c as boolean) is false then 1 else 0 end),
                         updated_at = now()
                       where post_id = :p"""
                ),
                {
                    "p": post_id,
                    "s": body.score,
                    "w": weight,
                    "b": new_bucket,
                    "c": confirm,
                    "n": counted,
                },
            )
        elif previous["score"] != body.score:
            # Voto cambiato: si sposta la differenza, il conteggio resta uguale.
            old_weight = float(previous["weight"])
            await session.execute(
                text(
                    """update app.votes set score = :s
                        where post_id = :p and voter_key = :k"""
                ),
                {"p": post_id, "k": key, "s": body.score},
            )
            old_b = bucket(previous["score"])
            # Stessa fascia di 10 punti: l'istogramma non cambia (e PostgreSQL non accetta
            # due assegnazioni allo stesso elemento nella stessa istruzione).
            hist = (
                ""
                if old_b == new_bucket or old_weight <= 0
                else ", hist[:old_b] = hist[:old_b] - 1, hist[:new_b] = hist[:new_b] + 1"
            )
            await session.execute(
                text(
                    f"""update app.post_stats set
                         vote_sum = vote_sum + cast(:delta as integer) * cast(:n as integer),
                         vote_wsum = vote_wsum + :delta * cast(:w as double precision),
                         unpublished_writes = unpublished_writes + 1,
                         updated_at = now(){hist}
                       where post_id = :p"""
                ),
                {
                    "p": post_id,
                    "delta": body.score - previous["score"],
                    "w": old_weight,
                    "n": 1 if old_weight > 0 else 0,
                    "old_b": old_b,
                    "new_b": new_bucket,
                },
            )
        counts = (
            (
                await session.execute(
                    text("select confirm_yes, confirm_no from app.post_stats where post_id = :p"),
                    {"p": post_id},
                )
            )
            .mappings()
            .one()
        )
        if post["status"] == "active" and style_rejected(
            counts["confirm_yes"], counts["confirm_no"]
        ):
            # Sotto il 70% di match: il post esce dalla pagina dello stile (resta nel portfolio;
            # l'autore può cambiargli stile una volta).
            await session.execute(
                text("update app.posts set status = 'style_rejected' where id = :p"), {"p": post_id}
            )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    out = await post_out(session, profile, post_id)
    if out is None:  # sparito nel frattempo (es. eliminato)
        raise ApiError(404, "post.not_found", "Post non trovato")
    return out.vote
