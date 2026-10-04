"""Worker dei lavori in background. Avvio:  uv run arq app.worker.WorkerSettings"""

from __future__ import annotations

from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.db import session_scope
from app.feed import refresh_all
from app.logging_setup import configure_logging
from app.media.jobs import cleanup_uploads, process_upload


async def refresh_feeds(ctx: dict[str, Any]) -> int:
    """Ogni 5 minuti: punteggi dei post e classifiche per stile."""
    async with session_scope() as session:
        return await refresh_all(session)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(json_logs=settings.env not in ("local", "test"))


class WorkerSettings:
    functions: ClassVar[list[Any]] = [process_upload]
    cron_jobs: ClassVar[list[Any]] = [
        cron(cleanup_uploads, minute={5, 35}),
        cron(refresh_feeds, minute=set(range(0, 60, 5))),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 120
    max_tries = 3
