"""Test HTTP: salute, configurazione, formato degli errori, versione minima dell'app."""

import re

PROBLEM = "application/problem+json"


async def test_liveness(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_readiness_checks_database_and_redis(client):
    r = await client.get("/readyz")
    assert r.status_code == 200, r.text
    assert r.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_config_returns_active_styles(client):
    r = await client.get("/v1/config")
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "public, max-age=300"
    body = r.json()
    slugs = [s["slug"] for s in body["styles"]]
    assert len(slugs) == len(set(slugs))
    assert "old-money" in slugs and "techwear" in slugs
    for style in body["styles"]:
        assert re.fullmatch(r"#[0-9A-F]{6}", style["tone"])
    beach = next(s for s in body["styles"] if s["slug"] == "beach-party")
    assert beach["min_age_band"] == "18_plus"
    assert body["min_app_version"] == "0.1.0"
    assert body["legal"]["privacy"].startswith("https://")


async def test_config_hides_expired_seasonal_styles(client, db_admin):
    db_admin.execute(
        "insert into app.styles (slug, name, tagline, tone, active_from, active_until) "
        "values ('test-expired', 'Scaduto', 'x', '#000000', '2020-01-01', '2020-01-31')"
    )
    try:
        r = await client.get("/v1/config")
        assert "test-expired" not in [s["slug"] for s in r.json()["styles"]]
    finally:
        db_admin.execute("delete from app.styles where slug = 'test-expired'")


async def test_unknown_route_is_problem_json(client):
    r = await client.get("/v1/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith(PROBLEM)
    body = r.json()
    assert body["code"] == "resource.not_found"
    assert body["status"] == 404
    assert body["request_id"] == r.headers["x-request-id"]


async def test_request_id_is_echoed_when_valid(client):
    r = await client.get("/healthz", headers={"X-Request-Id": "abc12345-test"})
    assert r.headers["x-request-id"] == "abc12345-test"


async def test_request_id_is_replaced_when_invalid(client):
    r = await client.get("/healthz", headers={"X-Request-Id": "<script>"})
    assert r.headers["x-request-id"] != "<script>"
    assert re.fullmatch(r"[0-9a-f-]{36}", r.headers["x-request-id"])


async def test_old_app_version_gets_426(client):
    r = await client.get("/v1/config", headers={"X-App-Version": "0.0.9"})
    assert r.status_code == 426
    assert r.json()["code"] == "app.update_required"
    assert r.json()["min_version"] == "0.1.0"


async def test_malformed_app_version_gets_426(client):
    r = await client.get("/v1/config", headers={"X-App-Version": "banana"})
    assert r.status_code == 426


async def test_current_app_version_passes(client):
    r = await client.get("/v1/config", headers={"X-App-Version": "0.1.0"})
    assert r.status_code == 200


async def test_security_headers(client):
    r = await client.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "private, no-store"
