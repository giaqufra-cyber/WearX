# syntax=docker/dockerfile:1.7
# Un'unica immagine per API, worker, worker dei link e migrazioni (cambia solo il comando):
#   API          (predefinito) uvicorn sulla porta $PORT
#   worker       arq app.worker.WorkerSettings
#   link         arq app.worker.LinkCheckSettings
#   migrazioni   alembic upgrade head
# Gira come utente senza privilegi (10001), senza strumenti di build nell'immagine finale.
#checkov:skip=CKV_DOCKER_2:Su Cloud Run la salute la controllano le sonde (/readyz, /healthz); la stessa immagine fa anche da worker, che non ha porte.

FROM ghcr.io/astral-sh/uv:0.11 AS uv

FROM python:3.13-slim-bookworm AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

FROM python:3.13-slim-bookworm
RUN groupadd --system --gid 10001 wearx \
 && useradd --system --uid 10001 --gid wearx --home-dir /srv --shell /usr/sbin/nologin wearx
WORKDIR /srv
COPY --from=build /srv /srv
# Versione (commit) per Sentry e per i log: la passa la pipeline di deploy.
ARG RELEASE=dev
ENV WEARX_RELEASE=${RELEASE} \
    PATH=/srv/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080
USER 10001:10001
EXPOSE 8080
# Niente intestazione "server" (seduta 22) e niente log di accesso di uvicorn (li scrive l'API,
# senza IP né query string).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --no-server-header --no-access-log --timeout-graceful-shutdown 20"]
