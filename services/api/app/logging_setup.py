"""Log JSON strutturati e Sentry (sedute 1 e 23). Regola: mai email, telefono, token, password,
indirizzi IP o nickname nei log e negli errori inviati.

Formato compatibile con Google Cloud Logging: `severity`, `message`, `time`, e il collegamento
alla traccia della richiesta (`logging.googleapis.com/trace`) quando c'è il progetto Google.
Ogni riga porta l'id della richiesta, così log, errore in Sentry e risposta si ritrovano.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.config import Settings

_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}

# Contesto della richiesta in corso (impostato dal middleware).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_var: ContextVar[str | None] = ContextVar("trace", default=None)

_gcp_project: str | None = None

# Chiavi che non devono mai finire nei log né in Sentry.
SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-forwarded-for",
        "cf-connecting-ip",
        "x-real-ip",
        "idempotency-key",
        "x-supabase-signature",
        "x-age-signature",
    }
)


def trace_from_headers(headers: Any) -> str | None:
    """Id della traccia da `traceparent` (W3C) o `X-Cloud-Trace-Context` (Google)."""
    parent = headers.get("traceparent")
    if parent:
        parts = parent.split("-")
        if len(parts) >= 3 and len(parts[1]) == 32:
            return str(parts[1])
    cloud = headers.get("x-cloud-trace-context")
    if cloud:
        trace = cloud.split("/", 1)[0]
        if trace and all(c in "0123456789abcdefABCDEF" for c in trace):
            return str(trace).lower()
    return None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        trace = trace_var.get()
        if trace and _gcp_project:
            payload["logging.googleapis.com/trace"] = f"projects/{_gcp_project}/traces/{trace}"
        for key, value in vars(record).items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info:
            # Google Error Reporting raggruppa gli errori che hanno lo stack trace qui.
            payload["stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(json_logs: bool, gcp_project: str | None = None) -> None:
    global _gcp_project
    _gcp_project = gcp_project
    handler = logging.StreamHandler(sys.stderr)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Le richieste le registra il middleware (senza IP né query string).
    logging.getLogger("uvicorn.access").disabled = True


def scrub_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any] | None:
    """Toglie da un evento di Sentry tutto ciò che identifica una persona."""
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                k: ("[tolto]" if k.lower() in SENSITIVE_HEADERS else v) for k, v in headers.items()
            }
        request.pop("cookies", None)
        request.pop("data", None)
        request.pop("query_string", None)
        env = request.get("env")
        if isinstance(env, dict):
            env.pop("REMOTE_ADDR", None)
    event.pop("user", None)
    event.pop("server_name", None)
    request_id = request_id_var.get()
    if request_id:
        event.setdefault("tags", {})["request_id"] = request_id
    return event


def init_sentry(settings: Settings, component: str) -> bool:
    """Sentry solo se c'è il DSN (in locale e nei test no)."""
    if settings.sentry_dsn is None:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.env,
        release=settings.release,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=scrub_event,  # type: ignore[arg-type]
        before_send_transaction=scrub_event,  # type: ignore[arg-type]
    )
    sentry_sdk.set_tag("component", component)
    return True
