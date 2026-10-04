"""Coda dei lavori in background (Arq su Redis)."""

from __future__ import annotations

from typing import Any, Protocol

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings


class Queue(Protocol):
    async def enqueue(self, function: str, *args: Any, job_id: str) -> None: ...


class ArqQueue:
    def __init__(self) -> None:
        self._pool: ArqRedis | None = None

    async def enqueue(self, function: str, *args: Any, job_id: str) -> None:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        # Stesso job_id = un solo lavoro anche se la richiesta viene ripetuta.
        await self._pool.enqueue_job(function, *args, _job_id=job_id)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
        self._pool = None


_queue: Queue = ArqQueue()


def get_queue() -> Queue:
    return _queue


def set_queue(queue: Queue | None) -> Queue:
    global _queue
    previous = _queue
    _queue = queue or ArqQueue()
    return previous
