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
from app.routers import (
    accounts,
    admin_console,
    admin_moderation,
    age,
    config,
    events,
    feed,
    health,
    insights,
    media,
    notifications,
    portfolio,
    posts,
    privacy,
    reports,
    social,
    styles,
    votes,
)


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
    # CORS: l'app nativa non ne ha bisogno (sez. 12.2). Si apre solo per l'anteprima web in
    # locale e per le origini del pannello dello staff indicate nella configurazione.
    origins = list(settings.admin_origins)
    if settings.env == "local":
        origins += ["http://localhost:8081", "http://localhost:8082", "http://localhost:3000"]
    if origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["*"],
            expose_headers=["X-Request-Id"],
        )
    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(accounts.router)
    app.include_router(age.router)
    app.include_router(styles.router)
    app.include_router(media.router)
    app.include_router(posts.router)
    app.include_router(votes.router)
    app.include_router(feed.router)
    app.include_router(portfolio.router)
    app.include_router(social.router)
    app.include_router(reports.router)
    app.include_router(notifications.router)
    app.include_router(events.router)
    app.include_router(insights.router)
    app.include_router(privacy.router)
    app.include_router(admin_moderation.router)
    app.include_router(admin_console.router)
    if settings.age_provider == "fake" and not settings.is_production:
        # Pagina del fornitore finto: solo sviluppo e test.
        from app.routers import dev_age

        app.include_router(dev_age.router)
    logging.getLogger("wearx").info("API avviata", extra={"env": settings.env})
    return app


app = create_app()
