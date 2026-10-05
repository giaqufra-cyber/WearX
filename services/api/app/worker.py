"""Worker dei lavori in background. Avvio:  uv run arq app.worker.WorkerSettings"""

from __future__ import annotations

from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import text

from app.config import get_settings
from app.db import session_scope
from app.feed import refresh_all
from app.insights import ROME, aggregate_recent
from app.logging_setup import configure_logging
from app.media.jobs import cleanup_uploads, process_upload
from app.push import check_receipts, get_sender, send_pending, vote_milestones


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


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(json_logs=settings.env not in ("local", "test"))


class WorkerSettings:
    functions: ClassVar[list[Any]] = [process_upload]
    cron_jobs: ClassVar[list[Any]] = [
        cron(cleanup_uploads, minute={5, 35}),
        cron(refresh_feeds, minute=set(range(0, 60, 5))),
        cron(send_pushes, second=30),
        cron(milestones, minute=set(range(2, 60, 10))),
        cron(push_receipts, minute={7, 22, 37, 52}),
        cron(event_partitions, hour={3}, minute={17}),
        cron(insights_nightly, hour={3}, minute={40}),
    ]
    # Gli orari dei lavori sono in ora italiana (anche quando il server è in UTC).
    timezone = ROME
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 120
    max_tries = 3
