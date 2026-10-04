"""Punto d'ingresso dell'API WearX."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import dispose_engine
from app.errors import install_error_handlers
from app.logging_setup import configure_logging
from app.middleware import install_middleware
from app.redis_client import close_redis
from app.routers import config, health


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(json_logs=settings.env not in ("local", "test"))
    app = FastAPI(
        title="WearX API",
        version="0.1.0",
        lifespan=lifespan,
        # Documentazione interattiva solo fuori dalla produzione.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    install_middleware(app)
    install_error_handlers(app)
    if settings.env == "local":
        # Solo in locale, per l'anteprima web dell'app (Expo su :8081). In ogni altro
        # ambiente CORS resta chiuso: l'app nativa non ne ha bisogno (sez. 12.2).
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:8081", "http://localhost:8082"],
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["*"],
            expose_headers=["X-Request-Id"],
        )
    app.include_router(health.router)
    app.include_router(config.router)
    logging.getLogger("wearx").info("API avviata", extra={"env": settings.env})
    return app


app = create_app()
