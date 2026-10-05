"""Privacy e sicurezza (seduta 20): dispositivi collegati, archivio dei dati, cancellazione."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentAuth
from app.db import get_session
from app.errors import ApiError
from app.privacy import DELETION_GRACE
from app.profiles import CurrentProfile, CurrentProfileAnyStatus
from app.queue import get_queue
from app.ratelimit import rate_limit
from app.storage import get_store

router = APIRouter(prefix="/v1/me", tags=["privacy"])

Session = Annotated[AsyncSession, Depends(get_session)]
EXPORT_URL_TTL = 3600


# ---------- Dispositivi ----------


class DeviceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=80)
    platform: Literal["ios", "android", "web"]
    app_version: str | None = Field(default=None, max_length=20)


class DeviceOut(BaseModel):
    id: str
    label: str
    platform: Literal["ios", "android", "web"]
    app_version: str | None
    created_at: datetime
    last_seen: datetime
    current: bool


def _clean_label(label: str) -> str:
    # Solo testo semplice su una riga (il nome arriva dal telefono).
    return " ".join("".join(c for c in label if c.isprintable()).split())[:80] or "Dispositivo"


@router.put(
    "/devices/current",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("device_seen", 120, 3600))],
)
async def device_seen(
    body: DeviceIn, viewer: CurrentProfileAnyStatus, auth: CurrentAuth, session: Session
) -> Response:
    """L'app dice "sono qui" all'avvio e quando torna in primo piano."""
    if auth.session_id:
        await session.execute(
            text(
                """insert into app.devices (session_id, user_id, label, platform, app_version)
                   values (:sid, :me, :label, :platform, :version)
                   on conflict (session_id) do update
                      set label = excluded.label, platform = excluded.platform,
                          app_version = excluded.app_version, last_seen = now()
                    where app.devices.user_id = excluded.user_id"""
            ),
            {
                "sid": auth.session_id,
                "me": viewer.id,
                "label": _clean_label(body.label),
                "platform": body.platform,
                "version": body.app_version,
            },
        )
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices", response_model=list[DeviceOut])
async def devices(viewer: CurrentProfile, auth: CurrentAuth, session: Session) -> list[DeviceOut]:
    rows = (
        (
            await session.execute(
                text(
                    """select session_id as id, label, platform, app_version, created_at,
                              last_seen, session_id = cast(:sid as text) as current
                         from app.devices
                        where user_id = :me and revoked_at is null
                        order by session_id = cast(:sid as text) desc, last_seen desc
                        limit 50"""
                ),
                {"me": viewer.id, "sid": auth.session_id},
            )
        )
        .mappings()
        .all()
    )
    return [DeviceOut(**r) for r in rows]


async def _revoke(
    session: AsyncSession, user_id: object, where: str, params: dict[str, object]
) -> int:
    revoked = (
        (
            await session.execute(
                text(
                    f"""update app.devices set revoked_at = now()
                     where user_id = :me and revoked_at is null and {where}
                    returning session_id"""
                ),
                {"me": user_id, **params},
            )
        )
        .scalars()
        .all()
    )
    if revoked:
        # Quei telefoni smettono subito di ricevere i push.
        await session.execute(
            text("delete from app.push_tokens where user_id = :me and session_id = any(:sids)"),
            {"me": user_id, "sids": list(revoked)},
        )
    return len(revoked)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: str, viewer: CurrentProfile, auth: CurrentAuth, session: Session
) -> Response:
    """Esci da un altro dispositivo. Per questo dispositivo si usa "Esci" (normale)."""
    if device_id == auth.session_id:
        raise ApiError(422, "device.current", "Per questo dispositivo usa Esci")
    if not await _revoke(session, viewer.id, "session_id = :sid", {"sid": device_id}):
        raise ApiError(404, "device.not_found", "Dispositivo non trovato")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class RevokedOut(BaseModel):
    revoked: int


@router.post("/devices/revoke-others", response_model=RevokedOut)
async def revoke_others(viewer: CurrentProfile, auth: CurrentAuth, session: Session) -> RevokedOut:
    """Esci da tutti gli altri dispositivi (dopo un cambio di password, o per sicurezza)."""
    count = await _revoke(
        session,
        viewer.id,
        "session_id <> coalesce(cast(:sid as text), '')",
        {"sid": auth.session_id},
    )
    await session.commit()
    return RevokedOut(revoked=count)


# ---------- Archivio dei dati ----------


class ExportOut(BaseModel):
    id: str
    status: Literal["pending", "ready", "failed", "expired"]
    created_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None
    size_bytes: int | None
    # Indirizzo di download (1 ora), solo se pronto.
    url: str | None


async def _latest_export(session: AsyncSession, user_id: object) -> ExportOut | None:
    row = (
        (
            await session.execute(
                text(
                    """select id::text as id, status, created_at, ready_at, expires_at,
                              size_bytes, storage_key
                         from app.data_exports where user_id = :me
                        order by created_at desc limit 1"""
                ),
                {"me": user_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    url = (
        get_store().signed_url(row["storage_key"], EXPORT_URL_TTL)
        if row["status"] == "ready" and row["storage_key"]
        else None
    )
    return ExportOut(**{k: v for k, v in row.items() if k != "storage_key"}, url=url)


@router.get("/export", response_model=ExportOut | None)
async def get_export(viewer: CurrentProfile, session: Session) -> ExportOut | None:
    return await _latest_export(session, viewer.id)


@router.post("/export", response_model=ExportOut, status_code=status.HTTP_202_ACCEPTED)
async def request_export(viewer: CurrentProfile, session: Session) -> ExportOut:
    """Un archivio al giorno (se l'ultimo non è fallito). Se uno è in preparazione, è quello."""
    latest = await _latest_export(session, viewer.id)
    if latest is not None and latest.status == "pending":
        return latest
    if latest is not None and latest.status != "failed":
        recent = await session.scalar(
            text(
                """select 1 from app.data_exports
                    where user_id = :me and status <> 'failed'
                      and created_at > now() - interval '24 hours'"""
            ),
            {"me": viewer.id},
        )
        if recent:
            raise ApiError(429, "export.too_soon", "Puoi chiedere un nuovo archivio domani")
    export_id = await session.scalar(
        text("insert into app.data_exports (user_id) values (:me) returning id"),
        {"me": viewer.id},
    )
    await session.commit()
    await get_queue().enqueue("export_data", str(export_id), job_id=f"export:{export_id}")
    created = await _latest_export(session, viewer.id)
    assert created is not None
    return created


# ---------- Cancellazione dell'account ----------


class DeletionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Il proprio nickname, per conferma.
    nickname: str = Field(min_length=1, max_length=40)


class DeletionOut(BaseModel):
    delete_after: datetime


@router.post(
    "/deletion",
    response_model=DeletionOut,
    dependencies=[Depends(rate_limit("deletion", 10, 3600))],
)
async def request_deletion(
    body: DeletionIn, viewer: CurrentProfileAnyStatus, auth: CurrentAuth, session: Session
) -> DeletionOut:
    """Cancella l'account tra 30 giorni. Da subito: invisibile agli altri, niente push, fuori
    dagli altri dispositivi. Entro i 30 giorni si annulla rientrando nell'app."""
    if body.nickname.strip().lstrip("@").lower() != viewer.nickname.lower():
        raise ApiError(422, "deletion.confirm_mismatch", "Il nickname non corrisponde")
    if viewer.status == "suspended":
        # Durante una sospensione i dati possono servire a verifiche e alle autorità.
        raise ApiError(409, "deletion.suspended", "Account sospeso: scrivi al supporto")
    if viewer.status == "pending_deletion":
        raise ApiError(409, "deletion.already", "Cancellazione già chiesta")
    delete_after = await session.scalar(
        text(
            """update app.profiles
                  set status = 'pending_deletion', deletion_requested_at = now(),
                      delete_after = now() + cast(:grace as interval)
                where id = :me
               returning delete_after"""
        ),
        {"me": viewer.id, "grace": DELETION_GRACE},
    )
    await _revoke(
        session,
        viewer.id,
        "session_id <> coalesce(cast(:sid as text), '')",
        {"sid": auth.session_id},
    )
    await session.execute(
        text("delete from app.push_tokens where user_id = :me"), {"me": viewer.id}
    )
    await session.commit()
    assert isinstance(delete_after, datetime)
    return DeletionOut(delete_after=delete_after)


@router.delete("/deletion", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_deletion(viewer: CurrentProfileAnyStatus, session: Session) -> Response:
    """Ci ho ripensato: l'account torna com'era."""
    if viewer.status != "pending_deletion":
        raise ApiError(409, "deletion.none", "Nessuna cancellazione in corso")
    await session.execute(
        text(
            """update app.profiles
                  set status = 'active', deletion_requested_at = null, delete_after = null
                where id = :me and status = 'pending_deletion'"""
        ),
        {"me": viewer.id},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class DeletionStatus(BaseModel):
    pending: bool
    delete_after: datetime | None


@router.get("/deletion", response_model=DeletionStatus)
async def deletion_status(viewer: CurrentProfileAnyStatus, session: Session) -> DeletionStatus:
    after = await session.scalar(
        text(
            "select delete_after from app.profiles where id = :me and status = 'pending_deletion'"
        ),
        {"me": viewer.id},
    )
    return DeletionStatus(pending=after is not None, delete_after=after)
