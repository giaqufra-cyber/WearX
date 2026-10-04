"""Middleware trasversali: id di richiesta, versione minima dell'app, intestazioni di sicurezza."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.config import get_settings
from app.errors import problem

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.match(value.strip())
    if not match:
        return None
    major, minor, patch = (int(x) for x in match.groups())
    return major, minor, patch


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id

        # Versione minima: si controlla solo se l'app manda l'header (i webhook non lo mandano).
        app_version = request.headers.get("x-app-version")
        if app_version is not None and request.url.path.startswith("/v1/"):
            current = parse_version(app_version)
            minimum = parse_version(get_settings().min_app_version)
            if current is None or (minimum is not None and current < minimum):
                response: Response = problem(
                    request,
                    426,
                    "app.update_required",
                    "Aggiorna WearX per continuare",
                    extra={"min_version": get_settings().min_app_version},
                )
                response.headers["X-Request-Id"] = request_id
                return response

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers.setdefault("Cache-Control", "private, no-store")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
