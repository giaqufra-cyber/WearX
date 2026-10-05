"""Middleware trasversali: id di richiesta, versione minima dell'app, intestazioni di sicurezza."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.config import get_settings
from app.errors import problem
from app.logging_setup import request_id_var, trace_from_headers, trace_var

access_log = logging.getLogger("wearx.access")
# Sondaggi di salute: si registrano solo quando falliscono (altrimenti sono rumore).
_QUIET_PATHS = frozenset({"/healthz", "/readyz", "/healthz/workers"})

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# Raggiungibili anche da un'app troppo vecchia: la configurazione dice dove aggiornarla.
_VERSION_EXEMPT = frozenset({"/v1/config"})


_NUL_ESCAPE = re.compile(rb"\\u0000", re.IGNORECASE)


async def _has_nul(request: Request) -> bool:
    """Il carattere 0 non è ammesso nel testo di PostgreSQL: lo si rifiuta subito (422) invece
    di arrivare a un errore del server (trovato dalla scansione ZAP, seduta 23)."""
    raw_path = request.scope.get("raw_path") or request.url.path.encode()
    if b"%00" in raw_path.lower() or b"\x00" in raw_path or "\x00" in request.url.path:
        return True
    query = request.scope.get("query_string", b"")
    if b"%00" in query.lower() or b"\x00" in query:
        return True
    if request.method in ("POST", "PUT", "PATCH") and "json" in request.headers.get(
        "content-type", ""
    ):
        body = await request.body()
        if b"\x00" in body or _NUL_ESCAPE.search(body):
            return True
    return False


def _secure(response: Response, request_id: str, path: str = "") -> Response:
    """Intestazioni di sicurezza su ogni risposta (seduta 22, risultati della scansione)."""
    headers = response.headers
    headers["X-Request-Id"] = request_id
    headers.setdefault("Cache-Control", "private, no-store")
    headers["X-Content-Type-Options"] = "nosniff"
    headers["Referrer-Policy"] = "no-referrer"
    headers["X-Frame-Options"] = "DENY"
    # L'API risponde JSON: nessuna risorsa da caricare, mai dentro un frame. Le poche pagine HTML
    # (redirect dei negozi, fornitore d'età finto) impostano la loro politica.
    if not path.startswith("/docs"):  # Swagger UI (solo fuori produzione) carica script e stili
        headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    headers["Cross-Origin-Opener-Policy"] = "same-origin"
    # Le risposte non si caricano come risorse da altri siti (le chiamate dell'app e del pannello
    # passano da CORS, che è un'altra cosa). Segnalato dalla scansione ZAP.
    headers["Cross-Origin-Resource-Policy"] = "same-origin"
    headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    if get_settings().env in ("staging", "production"):
        headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


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
        request_id_var.set(request_id)
        trace_var.set(trace_from_headers(request.headers))
        started = time.perf_counter()

        # Versione minima: si controlla solo se l'app manda l'header (i webhook non lo mandano).
        app_version = request.headers.get("x-app-version")
        path = request.url.path
        if await _has_nul(request):
            nul = problem(
                request,
                422,
                "request.invalid",
                "Dati non validi",
                extra={"errors": [{"loc": ["request"], "msg": "carattere non ammesso"}]},
            )
            return _secure(nul, request_id, path)
        if app_version is not None and path.startswith("/v1/") and path not in _VERSION_EXEMPT:
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
                return _secure(response, request_id, path)

        response = _secure(await call_next(request), request_id, path)
        _log_request(request, response.status_code, started)
        return response


def _log_request(request: Request, status: int, started: float) -> None:
    """Una riga per richiesta: metodo, percorso "modello" (senza id né nickname), esito, durata.
    Niente IP, query string o intestazioni."""
    path = request.url.path
    if path in _QUIET_PATHS and status < 500:
        return
    route = request.scope.get("route")
    template = getattr(route, "path", None) or "(nessuna rotta)"
    level = logging.ERROR if status >= 500 else logging.INFO
    access_log.log(
        level,
        "%s %s %s",
        request.method,
        template,
        status,
        extra={
            "http_method": request.method,
            "route": template,
            "status": status,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
