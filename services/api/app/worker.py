"""Worker dei lavori in background. Avvio:  uv run arq app.worker.WorkerSettings"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import text

from app.config import Component, get_settings, require_secrets
from app.db import session_scope
from app.feed import refresh_all
from app.insights import ROME, aggregate_recent
from app.link_check import check_due_links
from app.logging_setup import configure_logging, init_sentry
from app.media.jobs import cleanup_uploads, process_upload
from app.privacy import build_export, expire_exports, purge_deleted_accounts
from app.push import check_receipts, get_sender, send_pending, vote_milestones
from app.storage import get_store
from app.votes import detect_vote_abuse, publish_stats


async def refresh_feeds(ctx: dict[str, Any]) -> int:
    """Ogni 5 minuti: punteggi dei post e classifiche per stile."""
    async with session_scope() as session:
        return await refresh_all(session)


async def send_pushes(ctx: dict[str, Any]) -> int:
    """Ogni minuto: i push delle notifiche in attesa."""
    async with session_scope() as session:
        return await send_pending(session, get_sender())


async def push_receipts(ctx: dict[str, Any]) -> int:
    """Ogni 15 minuti: ricevute dei push (telefoni che non esistono più)."""
    async with session_scope() as session:
        return await check_receipts(session, get_sender())


async def milestones(ctx: dict[str, Any]) -> int:
    """Ogni 10 minuti: fit che hanno raggiunto un traguardo di voti."""
    async with session_scope() as session:
        return await vote_milestones(session)


async def votes_hourly(ctx: dict[str, Any]) -> tuple[int, int]:
    """Ogni ora: prima i voti sospetti (neutralizzati), poi media e numero pubblicati."""
    async with session_scope() as session:
        flagged = await detect_vote_abuse(session)
        published = await publish_stats(session)
        return flagged, published


async def event_partitions(ctx: dict[str, Any]) -> tuple[int, int]:
    """Ogni notte: partizioni degli eventi dei prossimi mesi; via quelle più vecchie di 3 mesi."""
    async with session_scope() as session:
        made = await session.scalar(text("select app.ensure_event_partitions(2)"))
        dropped = await session.scalar(text("select app.drop_old_event_partitions(3)"))
        await session.commit()
        return int(made or 0), int(dropped or 0)


async def insights_nightly(ctx: dict[str, Any]) -> int:
    """Ogni notte: totali degli Insight di ieri e dell'altro ieri."""
    async with session_scope() as session:
        return await aggregate_recent(session)


async def export_data(ctx: dict[str, Any], export_id: str) -> bool:
    """Archivio dei dati chiesto da una persona (GDPR)."""
    async with session_scope() as session:
        return await build_export(session, get_store(), uuid.UUID(export_id))


async def privacy_nightly(ctx: dict[str, Any]) -> tuple[int, int]:
    """Ogni notte: archivi scaduti e account oltre i 30 giorni di cancellazione."""
    async with session_scope() as session:
        expired = await expire_exports(session, get_store())
        purged = await purge_deleted_accounts(session, get_store())
        return expired, purged


async def check_links(ctx: dict[str, Any]) -> int:
    """Ogni 2 minuti: link ai negozi nuovi o da ricontrollare (worker separato)."""
    async with session_scope() as session:
        checked = await check_due_links(session)
        await heartbeat(session, "linkcheck")
        return checked


async def worker_heartbeat(ctx: dict[str, Any]) -> None:
    """Ogni minuto: "sono vivo" (lo controlla /healthz/workers, e quindi il monitoraggio)."""
    async with session_scope() as session:
        await heartbeat(session, "worker")


async def heartbeat(session: Any, name: str) -> None:
    await session.execute(
        text(
            """insert into app.job_runs (name, finished_at) values (:n, now())
               on conflict (name) do update set finished_at = excluded.finished_at"""
        ),
        {"n": f"heartbeat:{name}"},
    )
    await session.commit()


def _startup(component: Component) -> Any:
    async def startup(ctx: dict[str, Any]) -> None:
        settings = get_settings()
        require_secrets(settings, component)
        configure_logging(
            json_logs=settings.env not in ("local", "test"), gcp_project=settings.gcp_project
        )
        init_sentry(settings, component)

    return startup


class WorkerSettings:
    functions: ClassVar[list[Any]] = [process_upload, export_data]
    cron_jobs: ClassVar[list[Any]] = [
        cron(cleanup_uploads, minute={5, 35}),
        cron(refresh_feeds, minute=set(range(0, 60, 5))),
        cron(send_pushes, second=30),
        cron(milestones, minute=set(range(2, 60, 10))),
        cron(votes_hourly, minute={5}),
        cron(push_receipts, minute={7, 22, 37, 52}),
        cron(event_partitions, hour={3}, minute={17}),
        cron(insights_nightly, hour={3}, minute={40}),
        cron(privacy_nightly, hour={4}, minute={10}),
        cron(worker_heartbeat, second=0),
    ]
    # Gli orari dei lavori sono in ora italiana (anche quando il server è in UTC).
    timezone = ROME
    on_startup = _startup("worker")
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 120
    max_tries = 3


class LinkCheckSettings:
    """Worker separato che visita i siti esterni (controllo dei link ai negozi).

    Gira in un servizio a parte, con un'identità senza permessi e solo i segreti che gli
    servono (database, Redis, Safe Browsing): se un sito malevolo riuscisse a ingannare i
    controlli degli indirizzi, qui non troverebbe chiavi dell'archivio, di Supabase o dei push.
    Avvio:  uv run arq app.worker.LinkCheckSettings
    """

    functions: ClassVar[list[Any]] = []
    cron_jobs: ClassVar[list[Any]] = [cron(check_links, minute=set(range(1, 60, 2)))]
    timezone = ROME
    on_startup = _startup("linkcheck")
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    queue_name = "arq:links"
    max_jobs = 2
    job_timeout = 300
    max_tries = 1
