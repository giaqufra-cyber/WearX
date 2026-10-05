"""Seduta 23: log per Cloud Logging, Sentry senza dati personali, IP dietro Google, battito dei
worker, worker dei link separato, token Google senza chiavi."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from starlette.requests import Request

from app.attest.google import MetadataTokens, ServiceAccountTokens
from app.config import get_settings
from app.logging_setup import (
    JsonFormatter,
    configure_logging,
    request_id_var,
    scrub_event,
    trace_from_headers,
    trace_var,
)
from app.ratelimit import client_ip
from app.worker import LinkCheckSettings, WorkerSettings


def _record(msg="ciao", level=logging.INFO, **extra):
    record = logging.makeLogRecord({"name": "wearx.test", "levelno": level, "msg": msg})
    record.levelname = logging.getLevelName(level)
    for k, v in extra.items():
        setattr(record, k, v)
    return record


def test_formato_cloud_logging_con_traccia():
    configure_logging(json_logs=True, gcp_project="wearx-staging")
    token_r = request_id_var.set("req-123")
    token_t = trace_var.set("0af7651916cd43dd8448eb211c80319c")
    try:
        line = json.loads(JsonFormatter().format(_record("fatto", route="/v1/me")))
    finally:
        request_id_var.reset(token_r)
        trace_var.reset(token_t)
        configure_logging(json_logs=False)
    assert line["severity"] == "INFO"
    assert line["message"] == "fatto"
    assert line["request_id"] == "req-123"
    assert line["route"] == "/v1/me"
    assert line["logging.googleapis.com/trace"] == (
        "projects/wearx-staging/traces/0af7651916cd43dd8448eb211c80319c"
    )


def test_tracce_dalle_intestazioni():
    assert (
        trace_from_headers(
            {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
        )
        == "0af7651916cd43dd8448eb211c80319c"
    )
    assert trace_from_headers({"x-cloud-trace-context": "ABCDEF0123/1;o=1"}) == "abcdef0123"
    assert trace_from_headers({"x-cloud-trace-context": "<script>/1"}) is None
    assert trace_from_headers({}) is None


def test_sentry_senza_dati_personali():
    event = {
        "request": {
            "url": "https://api.wearx.app/v1/users/giulia.rossi",
            "headers": {
                "Authorization": "Bearer eyJ...",
                "X-Forwarded-For": "1.2.3.4",
                "Accept": "*/*",
            },
            "cookies": {"a": "b"},
            "data": {"password": "x"},
            "query_string": "email=a@b.it",
            "env": {"REMOTE_ADDR": "1.2.3.4"},
        },
        "user": {"ip_address": "1.2.3.4", "email": "a@b.it"},
        "server_name": "macchina-1",
    }
    token = request_id_var.set("req-9")
    try:
        out = scrub_event(event)
    finally:
        request_id_var.reset(token)
    assert out is not None
    request = out["request"]
    assert request["headers"] == {
        "Authorization": "[tolto]",
        "X-Forwarded-For": "[tolto]",
        "Accept": "*/*",
    }
    assert "cookies" not in request and "data" not in request and "query_string" not in request
    assert request["env"] == {}
    assert "user" not in out and "server_name" not in out
    assert out["tags"]["request_id"] == "req-9"


def _request(headers: dict[str, str], peer="10.0.0.1"):
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 1234),
    }
    return Request(scope)


@pytest.mark.parametrize(
    ("mode", "headers", "expected"),
    [
        ("none", {"x-forwarded-for": "6.6.6.6"}, "10.0.0.1"),
        # Su Cloud Run vale l'ultimo valore: i primi li scrive chi chiama.
        ("google", {"x-forwarded-for": "6.6.6.6, 81.2.69.160"}, "81.2.69.160"),
        ("google", {}, "10.0.0.1"),
        (
            "cloudflare",
            {"cf-connecting-ip": "81.2.69.160", "x-forwarded-for": "6.6.6.6"},
            "81.2.69.160",
        ),
    ],
)
def test_ip_reale_secondo_il_proxy(monkeypatch, mode, headers, expected):
    monkeypatch.setattr(get_settings(), "proxy_mode", mode)
    assert client_ip(_request(headers)) == expected


def test_worker_dei_link_separato():
    names = {c.name for c in WorkerSettings.cron_jobs}
    assert "cron:check_links" not in names
    assert "cron:worker_heartbeat" in names
    assert [c.name for c in LinkCheckSettings.cron_jobs] == ["cron:check_links"]
    assert LinkCheckSettings.queue_name != getattr(WorkerSettings, "queue_name", "arq:queue")


async def test_battito_dei_worker(client, db_admin):
    db_admin.execute("delete from app.job_runs where name like 'heartbeat:%'")
    r = await client.get("/healthz/workers")
    assert (r.status_code, r.json()["checks"]) == (503, {"worker": "stale", "linkcheck": "stale"})
    db_admin.execute(
        """insert into app.job_runs (name, finished_at) values
             ('heartbeat:worker', now()), ('heartbeat:linkcheck', now() - interval '20 minutes')"""
    )
    r = await client.get("/healthz/workers")
    assert r.json()["checks"] == {"worker": "ok", "linkcheck": "stale"}
    db_admin.execute("update app.job_runs set finished_at = now() where name like 'heartbeat:%'")
    assert (await client.get("/healthz/workers")).status_code == 200


async def test_registro_delle_richieste_senza_dati_personali(client, keys, db_admin, caplog):
    from tests.test_accounts import onboard

    await onboard(client, keys, db_admin)
    caplog.set_level(logging.INFO, logger="wearx.access")
    r = await client.get("/v1/users/qualcuno.di.preciso?q=email@x.it")
    lines = [rec for rec in caplog.records if rec.name == "wearx.access"]
    assert lines, "manca la riga della richiesta"
    rec = lines[-1]
    assert rec.getMessage() == f"GET /v1/users/{{nickname}} {r.status_code}"
    assert "qualcuno" not in rec.getMessage() and "email" not in rec.getMessage()
    assert rec.latency_ms >= 0  # type: ignore[attr-defined]
    caplog.clear()
    await client.get("/healthz")
    assert not [rec for rec in caplog.records if rec.name == "wearx.access"]


async def test_token_google_dal_metadata_server():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"access_token": "tok-meta", "expires_in": 3599})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tokens = MetadataTokens(client)
    assert await tokens.token() == "tok-meta"
    assert await tokens.token() == "tok-meta"  # in memoria finché vale
    assert len(seen) == 1
    assert seen[0].headers["metadata-flavor"] == "Google"
    assert "playintegrity" in seen[0].url.params["scopes"]


async def test_token_google_da_account_di_servizio():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    info = json.dumps({"client_email": "sa@progetto.iam", "private_key": pem})

    def handler(request: httpx.Request) -> httpx.Response:
        assert b"jwt-bearer" in request.content
        return httpx.Response(200, json={"access_token": "tok-sa", "expires_in": 3600})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await ServiceAccountTokens(info, client).token() == "tok-sa"


def test_ogni_componente_i_suoi_segreti(monkeypatch):
    from pydantic import SecretStr

    from app.config import Settings, require_secrets

    base = Settings(
        env="production",
        proxy_mode="google",
        push_provider="expo",
        attestation_mode="soft",
        app_attest_allow_development=False,
    )
    # Il worker dei link non ha bisogno di chiavi dell'archivio, di Supabase o dei push.
    require_secrets(base, "linkcheck")
    with pytest.raises(RuntimeError, match="WEARX_VOTE_PEPPER"):
        require_secrets(base, "api")
    full = base.model_copy(
        update={
            "vote_pepper": SecretStr("p"),
            "storage_secret_key": SecretStr("s"),
            "age_webhook_secret": SecretStr("a"),
        }
    )
    require_secrets(full, "api")
    with pytest.raises(RuntimeError, match="WEARX_SUPABASE_SECRET_KEY"):
        require_secrets(full, "worker")
    require_secrets(full.model_copy(update={"supabase_secret_key": SecretStr("k")}), "worker")
    require_secrets(Settings(env="staging"), "api")  # fuori produzione nessun obbligo
