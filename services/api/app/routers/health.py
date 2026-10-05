"""Controlli di salute per la piattaforma di hosting e il monitoraggio esterno."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz", include_in_schema=False)
async def liveness() -> dict[str, str]:
    """Il processo risponde. Non tocca dipendenze esterne."""
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readiness(session: Annotated[AsyncSession, Depends(get_session)]) -> JSONResponse:
    """Pronto a servire traffico: database e Redis raggiungibili entro 2 s."""
    checks: dict[str, str] = {}
    try:
        await asyncio.wait_for(session.execute(text("select 1")), timeout=2)
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        await asyncio.wait_for(get_redis().ping(), timeout=2)
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503
    )


# Battito dei worker: oltre questo ritardo il monitoraggio avvisa.
WORKER_STALE = {"worker": 5 * 60, "linkcheck": 10 * 60}


@router.get("/healthz/workers", include_in_schema=False)
async def workers(session: Annotated[AsyncSession, Depends(get_session)]) -> JSONResponse:
    """I worker in background sono vivi? (ultimo battito più recente di qualche minuto)"""
    rows = await session.execute(
        text(
            """select substring(name from 11) as name,
                      extract(epoch from now() - finished_at) as age
                 from app.job_runs where name like 'heartbeat:%'"""
        )
    )
    ages = {r[0]: float(r[1]) for r in rows}
    checks = {
        name: ("ok" if ages.get(name, float("inf")) <= limit else "stale")
        for name, limit in WORKER_STALE.items()
    }
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503
    )
