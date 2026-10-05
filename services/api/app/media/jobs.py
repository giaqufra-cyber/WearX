"""Lavori del worker sulle foto: elaborazione di un caricamento e pulizia periodica."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from sqlalchemy import text

from app.config import get_settings
from app.db import session_scope
from app.media.keys import quarantine_key, variant_key
from app.media.processing import Processed, process_image
from app.moderation.actions import suspend_pending_review
from app.moderation.reports import file_report
from app.moderation.scanning import UploadDecision, scan_image
from app.storage import get_store

log = logging.getLogger("wearx.media")

PENDING_TTL_HOURS = 24
UNATTACHED_TTL_DAYS = 7


async def _reject(upload_id: uuid.UUID, reason: str) -> None:
    async with session_scope() as session:
        await session.execute(
            text(
                """update app.media_uploads
                      set status = 'rejected', reject_reason = :reason, processed_at = now()
                    where id = :id and status = 'processing'"""
            ),
            {"id": upload_id, "reason": reason},
        )
        await session.commit()


async def _incident(owner: uuid.UUID, decision: UploadDecision) -> None:
    """Materiale illegale noto: account sospeso subito e caso P0 per i moderatori (entro 1 ora).
    La foto non viene salvata: restano solo le impronte nella lista e il caso aperto."""
    async with session_scope() as session:
        await suspend_pending_review(session, owner, ground="csam_hash_match")
        await file_report(
            session,
            reporter_id=None,
            target_type="profile",
            target_id=owner,
            reason="minor_safety",
            details=f"Controllo automatico: {decision.reason}",
            subject_id=owner,
            auto=True,
        )
        await session.commit()
    log.error("corrispondenza con lista di materiale illegale", extra={"owner": str(owner)})


async def process_upload(ctx: dict[str, Any], upload_id: str) -> str:
    """Prende la foto dalla quarantena, la controlla e la pulisce, salva le varianti.
    In ogni caso l'originale (con i suoi metadati) viene cancellato."""
    uid = uuid.UUID(upload_id)
    settings = get_settings()
    store = get_store()
    async with session_scope() as session:
        status = await session.scalar(
            text("select status::text from app.media_uploads where id = :id"), {"id": uid}
        )
    if status != "processing":
        return f"skip:{status}"  # già fatto (lavoro ripetuto) o annullato

    key = quarantine_key(uid)
    try:
        data = await store.get(key, settings.upload_max_bytes)
    except Exception:
        log.exception("quarantena illeggibile", extra={"upload_id": upload_id})
        await _reject(uid, "processing_error")
        return "rejected:processing_error"

    try:
        if len(data) > settings.upload_max_bytes:
            await _reject(uid, "too_large")
            return "rejected:too_large"

        result = await asyncio.to_thread(process_image, data)
        if not isinstance(result, Processed):
            await _reject(uid, result.reason)
            return f"rejected:{result.reason}"

        async with session_scope() as session:
            owner, minor = (
                await session.execute(
                    text(
                        """select u.owner_id, p.age_band = '16_17' from app.media_uploads u
                             join app.profiles p on p.id = u.owner_id where u.id = :id"""
                    ),
                    {"id": uid},
                )
            ).one()
            decision = await scan_image(session, data, result.sha256, result.phash, minor=minor)
        if decision.verdict == "block":
            if decision.incident:
                await _incident(owner, decision)
            await _reject(uid, "blocked")
            log.warning(
                "foto bloccata dai controlli",
                extra={"upload_id": upload_id, "reason": decision.reason},
            )
            return "rejected:blocked"

        for width, webp in result.variants.items():
            await store.put(variant_key(uid, width), webp, "image/webp")

        async with session_scope() as session:
            await session.execute(
                text(
                    """update app.media_uploads
                          set status = 'ready', width = :w, height = :h, blurhash = :bh,
                              sha256 = :sha, phash = :ph, variants = :variants,
                              scan_labels = cast(:labels as jsonb), needs_review = :review,
                              processed_at = now()
                        where id = :id and status = 'processing'"""
                ),
                {
                    "id": uid,
                    "w": result.width,
                    "h": result.height,
                    "bh": result.blurhash,
                    "sha": result.sha256,
                    "ph": result.phash,
                    "variants": sorted(result.variants),
                    "labels": json.dumps(decision.labels),
                    "review": decision.verdict == "review",
                },
            )
            await session.commit()
        return "ready"
    except Exception:
        log.exception("elaborazione fallita", extra={"upload_id": upload_id})
        await _reject(uid, "processing_error")
        return "rejected:processing_error"
    finally:
        await store.delete(key)


async def cleanup_uploads(ctx: dict[str, Any]) -> int:
    """Caricamenti mai completati (24 ore) e foto mai usate in un post (7 giorni)."""
    store = get_store()
    async with session_scope() as session:
        stale = (
            (
                await session.execute(
                    text(
                        """update app.media_uploads
                          set status = 'rejected', reject_reason = 'expired', processed_at = now()
                        where status = 'pending'
                          and created_at < now() - make_interval(hours => :hours)
                       returning id"""
                    ),
                    {"hours": PENDING_TTL_HOURS},
                )
            )
            .scalars()
            .all()
        )
        unused = (
            await session.execute(
                text(
                    """delete from app.media_uploads
                         where attached_at is null and status in ('ready', 'rejected')
                           and created_at < now() - make_interval(days => :days)
                       returning id, variants"""
                ),
                {"days": UNATTACHED_TTL_DAYS},
            )
        ).all()
        await session.commit()
    keys = [quarantine_key(u) for u in stale]
    for upload_id, variants in unused:
        keys.append(quarantine_key(upload_id))
        keys.extend(variant_key(upload_id, w) for w in variants or [])
    for i in range(0, len(keys), 900):
        await store.delete(*keys[i : i + 900])
    return len(stale) + len(unused)
