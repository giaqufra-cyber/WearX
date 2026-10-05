"""Eliminazione di un fit (dall'autore o dalla moderazione): resta solo la riga del post per i
conteggi storici; capi, foto e caricamenti spariscono. Non fa commit: chi chiama decide."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.keys import variant_key
from app.portfolio import after_post_deleted


@dataclass(frozen=True, slots=True)
class Purged:
    # Varianti da cancellare dall'archivio DOPO il commit.
    storage_keys: list[str]
    # Impronte delle foto (per non farle ricaricare se rimosse dalla moderazione).
    hashes: list[tuple[bytes | None, int | None]]


async def purge_post(session: AsyncSession, post_id: uuid.UUID, author_id: uuid.UUID) -> Purged:
    media = (
        (
            await session.execute(
                text(
                    """select upload_id, variants, sha256, phash from app.post_media
                        where post_id = :id"""
                ),
                {"id": post_id},
            )
        )
        .mappings()
        .all()
    )
    await session.execute(
        text(
            """update app.posts set status = 'deleted', deleted_at = now(), caption = null,
                      capsule_id = null
                where id = :id"""
        ),
        {"id": post_id},
    )
    await after_post_deleted(session, author_id, post_id)
    await session.execute(text("delete from app.post_items where post_id = :id"), {"id": post_id})
    await session.execute(text("delete from app.post_media where post_id = :id"), {"id": post_id})
    uploads = [m["upload_id"] for m in media if m["upload_id"] is not None]
    if uploads:
        await session.execute(
            text("delete from app.media_uploads where id = any(:ids)"), {"ids": uploads}
        )
    return Purged(
        storage_keys=[
            variant_key(m["upload_id"], w)
            for m in media
            if m["upload_id"] is not None
            for w in m["variants"]
        ],
        hashes=[(m["sha256"], m["phash"]) for m in media],
    )
