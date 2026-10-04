"""Caricamento delle foto (sez. 7).

1. POST /v1/media/uploads             -> POST firmato verso l'archivio (quarantena)
2. il telefono carica direttamente sull'archivio
3. POST /v1/media/uploads/{id}/complete -> in coda al worker
4. GET  /v1/media/uploads/{id}          -> stato; quando è pronta, URL firmati delle varianti
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.media.keys import quarantine_key, variant_key
from app.profiles import CurrentProfile
from app.queue import get_queue
from app.ratelimit import rate_limit
from app.storage import get_store

router = APIRouter(prefix="/v1/media", tags=["media"])

Session = Annotated[AsyncSession, Depends(get_session)]
ContentType = Literal["image/jpeg", "image/png", "image/webp"]
UploadStatus = Literal["pending", "processing", "ready", "rejected"]


class UploadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_type: ContentType
    size_bytes: int = Field(gt=0)


class UploadTarget(BaseModel):
    """POST multipart: tutti i `fields` e per ultimo il file nel campo `file`."""

    url: str
    fields: dict[str, str]


class MediaUrls(BaseModel):
    # Larghezza in pixel -> URL firmato (scade dopo media_url_ttl_seconds).
    variants: dict[int, str]
    expires_at: datetime


class UploadOut(BaseModel):
    id: uuid.UUID
    status: UploadStatus
    reject_reason: str | None = None
    width: int | None = None
    height: int | None = None
    blurhash: str | None = None
    urls: MediaUrls | None = None
    # Solo alla creazione.
    upload: UploadTarget | None = None
    max_bytes: int | None = None
    upload_expires_at: datetime | None = None


_SELECT = """select id, status::text as status, reject_reason, width, height, blurhash,
                    variants, created_at
               from app.media_uploads where id = :id and owner_id = :uid"""


def media_urls(upload_id: uuid.UUID, variants: list[int]) -> MediaUrls:
    settings = get_settings()
    store = get_store()
    ttl = settings.media_url_ttl_seconds
    return MediaUrls(
        variants={w: store.signed_url(variant_key(upload_id, w), ttl) for w in sorted(variants)},
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
    )


def _out(row: Any) -> UploadOut:
    ready = row["status"] == "ready"
    return UploadOut(
        id=row["id"],
        status=row["status"],
        reject_reason=row["reject_reason"],
        width=row["width"],
        height=row["height"],
        blurhash=row["blurhash"],
        urls=media_urls(row["id"], list(row["variants"])) if ready else None,
    )


async def _load(session: AsyncSession, upload_id: uuid.UUID, owner: uuid.UUID) -> Any:
    row = (await session.execute(text(_SELECT), {"id": upload_id, "uid": owner})).mappings().first()
    if row is None:
        # Stessa risposta per "non esiste" e "non è tuo".
        raise ApiError(404, "media.not_found", "Foto non trovata")
    return row


@router.post(
    "/uploads",
    response_model=UploadOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("media_upload", 60, 3600))],
)
async def create_upload(body: UploadIn, profile: CurrentProfile, session: Session) -> UploadOut:
    settings = get_settings()
    if body.size_bytes > settings.upload_max_bytes:
        raise ApiError(
            422,
            "media.too_large",
            "La foto è troppo pesante",
            extra={"max_bytes": settings.upload_max_bytes},
        )
    pending = await session.scalar(
        text(
            """select count(*) from app.media_uploads
                where owner_id = :uid and status in ('pending', 'processing')
                  and created_at > now() - interval '24 hours'"""
        ),
        {"uid": profile.id},
    )
    if int(pending or 0) >= settings.max_pending_uploads:
        raise ApiError(429, "media.too_many_pending", "Troppe foto in caricamento: finisci prima")

    upload_id = uuid.uuid4()
    await session.execute(
        text(
            """insert into app.media_uploads (id, owner_id, content_type, declared_bytes)
               values (:id, :uid, :ct, :size)"""
        ),
        {"id": upload_id, "uid": profile.id, "ct": body.content_type, "size": body.size_bytes},
    )
    await session.commit()
    target = get_store().presign_upload(
        quarantine_key(upload_id),
        body.content_type,
        settings.upload_max_bytes,
        settings.upload_url_ttl_seconds,
    )
    return UploadOut(
        id=upload_id,
        status="pending",
        upload=UploadTarget(url=target.url, fields=target.fields),
        max_bytes=settings.upload_max_bytes,
        upload_expires_at=datetime.now(UTC) + timedelta(seconds=settings.upload_url_ttl_seconds),
    )


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=UploadOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("media_complete", 120, 3600))],
)
async def complete_upload(
    upload_id: uuid.UUID, profile: CurrentProfile, session: Session
) -> UploadOut:
    settings = get_settings()
    row = await _load(session, upload_id, profile.id)
    if row["status"] != "pending":
        return _out(row)  # già completato: stessa risposta (richiesta ripetuta)

    store = get_store()
    key = quarantine_key(upload_id)
    size = await store.size(key)
    if size is None:
        raise ApiError(409, "media.not_uploaded", "La foto non è ancora arrivata")
    if size > settings.upload_max_bytes:
        await store.delete(key)
        await session.execute(
            text(
                """update app.media_uploads
                      set status = 'rejected', reject_reason = 'too_large', processed_at = now()
                    where id = :id"""
            ),
            {"id": upload_id},
        )
        await session.commit()
        raise ApiError(422, "media.too_large", "La foto è troppo pesante")

    updated = await session.execute(
        text(
            """update app.media_uploads set status = 'processing', uploaded_at = now()
                where id = :id and status = 'pending'"""
        ),
        {"id": upload_id},
    )
    await session.commit()
    if getattr(updated, "rowcount", 0):
        await get_queue().enqueue("process_upload", str(upload_id), job_id=f"upload:{upload_id}")
    return _out(await _load(session, upload_id, profile.id))


@router.get("/uploads/{upload_id}", response_model=UploadOut)
async def get_upload(upload_id: uuid.UUID, profile: CurrentProfile, session: Session) -> UploadOut:
    return _out(await _load(session, upload_id, profile.id))


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    upload_id: uuid.UUID, profile: CurrentProfile, session: Session
) -> Response:
    """Toglie una foto non ancora pubblicata (es. tolta dal carosello prima di postare)."""
    row = (
        (
            await session.execute(
                text(
                    """delete from app.media_uploads
                        where id = :id and owner_id = :uid and attached_at is null
                    returning variants"""
                ),
                {"id": upload_id, "uid": profile.id},
            )
        )
        .mappings()
        .first()
    )
    await session.commit()
    if row is None:
        raise ApiError(404, "media.not_found", "Foto non trovata")
    keys = [quarantine_key(upload_id)]
    keys += [variant_key(upload_id, w) for w in row["variants"] or []]
    await get_store().delete(*keys)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
