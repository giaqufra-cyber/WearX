"""Foto profilo (seduta 27).

È un caricamento come quelli dei fit: passa dagli stessi controlli (quarantena, scansione,
varianti) e poi viene "agganciato" al profilo (`attached_at`, così la pulizia dei caricamenti mai
usati non lo cancella). Regole:
- solo una foto pronta, tua e non ancora usata (né in un post né come altra foto profilo);
- una foto che il classificatore manda "da rivedere" non diventa foto profilo: nel profilo non
  c'è una coda di revisione come per i fit, quindi si rifiuta subito;
- cambiando o togliendo la foto, la precedente si cancella (database e archivio).
La vede chi può vedere il profilo (stesse regole di `people.find_person`).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.media.keys import quarantine_key, variant_key
from app.routers.media import MediaUrls, media_urls


class AvatarOut(BaseModel):
    blurhash: str
    urls: MediaUrls


def avatar_out(upload_id: Any, variants: Any, blurhash: Any) -> AvatarOut | None:
    """Da colonne di una query (left join su media_uploads): None se non c'è la foto."""
    if upload_id is None or not variants or blurhash is None:
        return None
    return AvatarOut(blurhash=str(blurhash), urls=media_urls(upload_id, list(variants)))


async def load_avatar(session: AsyncSession, profile_id: uuid.UUID) -> AvatarOut | None:
    row = (
        await session.execute(
            text(
                """select u.id, u.variants, u.blurhash from app.profiles p
                     join app.media_uploads u on u.id = p.avatar_upload_id
                    where p.id = :id"""
            ),
            {"id": profile_id},
        )
    ).first()
    return avatar_out(*row) if row else None


async def _drop_upload(session: AsyncSession, upload_id: uuid.UUID) -> tuple[list[str], Any]:
    row = (
        await session.execute(
            text(
                """delete from app.media_uploads where id = :id
                returning variants, sha256, phash"""
            ),
            {"id": upload_id},
        )
    ).first()
    if row is None:
        return [], None
    variants, sha, phash = row
    keys = [quarantine_key(upload_id)] + [variant_key(upload_id, w) for w in variants or []]
    return keys, (sha, phash)


async def detach_avatar(session: AsyncSession, profile_id: uuid.UUID) -> tuple[list[str], Any]:
    """Toglie la foto profilo attuale (la colonna del profilo torna null da sola: on delete set
    null). Restituisce le chiavi da cancellare dall'archivio dopo il commit e (sha256, phash)
    della foto tolta (None se non c'era)."""
    current = await session.scalar(
        text("select avatar_upload_id from app.profiles where id = :id"), {"id": profile_id}
    )
    if current is None:
        return [], None
    return await _drop_upload(session, current)


async def replace_avatar(
    session: AsyncSession, profile_id: uuid.UUID, upload_id: uuid.UUID | None
) -> list[str]:
    """Nuova foto profilo (o nessuna, con None). Restituisce le chiavi della foto precedente da
    cancellare dall'archivio dopo il commit."""
    current = await session.scalar(
        text("select avatar_upload_id from app.profiles where id = :id"), {"id": profile_id}
    )
    if upload_id == current:
        return []
    if upload_id is not None:
        # Prima i controlli sulla foto nuova: se non va bene, resta quella di prima.
        await _attach(session, profile_id, upload_id)
    if current is None:
        return []
    keys, _ = await _drop_upload(session, current)
    return keys


async def _attach(session: AsyncSession, profile_id: uuid.UUID, upload_id: uuid.UUID) -> None:
    row = (
        (
            await session.execute(
                text(
                    """select status::text as status, attached_at is not null as used,
                              needs_review
                         from app.media_uploads where id = :id and owner_id = :uid"""
                ),
                {"id": upload_id, "uid": profile_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["status"] != "ready" or row["used"]:
        raise ApiError(422, "avatar.unavailable", "La foto non è pronta o non è tua")
    if row["needs_review"]:
        raise ApiError(
            422, "avatar.not_allowed", "Questa foto non può essere usata come foto profilo"
        )
    await session.execute(
        text("update app.media_uploads set attached_at = now() where id = :id"),
        {"id": upload_id},
    )
    await session.execute(
        text("update app.profiles set avatar_upload_id = :u where id = :id"),
        {"u": upload_id, "id": profile_id},
    )
