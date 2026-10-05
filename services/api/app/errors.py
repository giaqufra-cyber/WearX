"""Errori in formato RFC 9457 (application/problem+json) con un `code` stabile.

L'app decide cosa mostrare in base a `code`, mai al testo di `title` o `detail`.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("wearx.errors")

PROBLEM_JSON = "application/problem+json"


class ApiError(Exception):
    """Errore applicativo previsto. Viene restituito al client così com'è."""

    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.headers = headers or {}
        self.extra = extra or {}


def problem(
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://wearx.app/errors/{code.replace('.', '/')}",
        "title": title,
        "status": status,
        "code": code,
        "instance": request.url.path,
    }
    if detail:
        body["detail"] = detail
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        body["request_id"] = request_id
    body.update(extra or {})
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


_STATUS_CODES = {
    400: "request.bad",
    401: "auth.required",
    403: "auth.forbidden",
    404: "resource.not_found",
    405: "request.method_not_allowed",
    409: "resource.conflict",
    429: "rate.limited",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return problem(request, exc.status, exc.code, exc.title, exc.detail, exc.headers, exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, f"http.{exc.status_code}")
        title = HTTPStatus(exc.status_code).phrase
        headers = dict(exc.headers) if exc.headers else None
        return problem(request, exc.status_code, code, title, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Restituiamo dove e perché, mai il valore inviato (potrebbe essere una password).
        errors = [
            {"loc": [str(p) for p in e.get("loc", ())], "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return problem(request, 422, "request.invalid", "Dati non validi", extra={"errors": errors})

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        route = getattr(request.scope.get("route"), "path", None)
        logger.exception("Errore non gestito", extra={"route": route})
        # Sentry (se configurato); il doppione eventuale lo scarta Sentry stesso.
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
        return problem(request, 500, "server.error", "Errore interno")
