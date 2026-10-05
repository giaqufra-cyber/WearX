"""Pannello dello staff: ruoli, numeri, fit in qualsiasi stato, persone, stili, staff, audit."""

from __future__ import annotations

import pytest

from tests.authkit import bearer
from tests.conftest import ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")


async def _staff(client, keys, db_admin, role="moderator"):
    user_id, _, profile = await onboard(client, keys, db_admin)
    db_admin.execute("insert into app.staff (user_id, role) values (%s, %s)", (user_id, role))
    return user_id, bearer(keys.token(user_id, aal="aal2")), profile["nickname"]


async def _post(client, db_admin, user_id, headers, caption="Fit"):
    media = [str(ready_upload(db_admin, user_id))]
    r = await client.post(
        "/v1/posts",
        json={
            "style": "old-money",
            "media": media,
            "caption": caption,
            "items": [{"brand": "Tod's", "name": "Mocassini", "url": "https://tods.com/x"}],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def unique_slug():
    import uuid

    return f"test-{uuid.uuid4().hex[:8]}"


async def test_chi_sono_e_ruoli(client, keys, db_admin):
    _, mod, mod_nick = await _staff(client, keys, db_admin)
    _, admin, _ = await _staff(client, keys, db_admin, role="admin")
    r = await client.get("/v1/admin/me", headers=mod)
    assert r.json() == {"role": "moderator", "nickname": mod_nick}
    for path in ("/v1/admin/styles", "/v1/admin/staff", "/v1/admin/audit"):
        r = await client.get(path, headers=mod)
        assert (r.status_code, r.json()["code"]) == (403, "staff.admin_required")
        assert (await client.get(path, headers=admin)).status_code == 200
    _, user, _ = await onboard(client, keys, db_admin)
    assert (await client.get("/v1/admin/me", headers=user)).status_code == 404


async def test_numeri(client, keys, db_admin):
    author_id, author, _ = await onboard(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    db_admin.execute(
        """insert into app.reports
             (reporter_id, target_type, target_id, reason, priority, created_at)
           values (%s, 'post', %s, 'minor_safety', 0, now() - interval '2 hours')""",
        (author_id, post),
    )
    _, mod, _ = await _staff(client, keys, db_admin)
    stats = (await client.get("/v1/admin/stats", headers=mod)).json()
    assert stats["posts_today"] >= 1
    assert stats["reports"]["p0"] >= 1
    assert stats["reports"]["overdue"] >= 1
    assert stats["users"] >= 2


async def test_fit_anche_nascosto_con_foto_capi_e_segnalazioni(client, keys, db_admin):
    author_id, author, nick = await onboard(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author, caption="Da vedere")
    db_admin.execute("update app.posts set status = 'hidden_moderation' where id = %s", (post,))
    db_admin.execute(
        """insert into app.reports (reporter_id, target_type, target_id, reason, details, priority)
           values (%s, 'post', %s, 'spam', 'link ripetuti', 2)""",
        (author_id, post),
    )
    _, mod, _ = await _staff(client, keys, db_admin)
    body = (await client.get(f"/v1/admin/posts/{post}", headers=mod)).json()
    assert (body["status"], body["author"], body["caption"]) == (
        "hidden_moderation",
        nick["nickname"],
        "Da vedere",
    )
    assert len(body["media"]) == 1 and body["media"][0]["urls"]["variants"]
    assert body["items"][0]["link"]["domain"] == "tods.com"
    assert body["reports"][0]["details"] == "link ripetuti"
    logged = db_admin.execute(
        "select count(*) from app.admin_audit_log where action = 'admin.view_post' and target = %s",
        (f"post:{post}",),
    ).fetchone()
    assert logged == (1,)
    r = await client.get("/v1/admin/posts/00000000-0000-0000-0000-000000000000", headers=mod)
    assert r.status_code == 404


async def test_ricerca_persone_e_riattivazione(client, keys, db_admin):
    user_id, _, profile = await onboard(client, keys, db_admin)
    nick = profile["nickname"]
    _, mod, _ = await _staff(client, keys, db_admin)
    found = (await client.get("/v1/admin/users", params={"q": nick[:6]}, headers=mod)).json()
    assert nick in [u["nickname"] for u in found]
    assert (await client.get("/v1/admin/users", params={"q": "%%%"}, headers=mod)).json() == []

    r = await client.post(f"/v1/admin/users/{nick}/reinstate", json={"note": "ok"}, headers=mod)
    assert (r.status_code, r.json()["code"]) == (409, "user.not_restricted")
    db_admin.execute(
        """update app.profiles set status = 'suspended',
                  posting_blocked_until = now() + interval '3 days' where id = %s""",
        (user_id,),
    )
    r = await client.post(
        f"/v1/admin/users/{nick}/reinstate", json={"note": "Errore di valutazione"}, headers=mod
    )
    assert r.status_code == 204
    row = db_admin.execute(
        "select status::text, posting_blocked_until from app.profiles where id = %s", (user_id,)
    ).fetchone()
    assert row == ("active", None)
    action = db_admin.execute(
        "select action, ground from app.moderation_actions where subject_id = %s", (user_id,)
    ).fetchone()
    assert action == ("restore", "staff_review")


async def test_stili(client, keys, db_admin, unique_slug):
    _, admin, _ = await _staff(client, keys, db_admin, role="admin")
    body = {
        "slug": unique_slug,
        "name": "  Après   Ski ",
        "tagline": "Montagna, lana e occhiali a specchio",
        "tone": "#2B3A55",
        "active_from": "2026-12-01",
        "active_until": "2027-03-31",
    }
    r = await client.post("/v1/admin/styles", json=body, headers=admin)
    assert r.status_code == 201, r.text
    created = r.json()
    assert (created["name"], created["min_age_band"], created["members"]) == (
        "Après Ski",
        "16_17",
        0,
    )
    assert (await client.post("/v1/admin/styles", json=body, headers=admin)).status_code == 409

    r = await client.patch(
        f"/v1/admin/styles/{unique_slug}",
        json={"min_age_band": "18_plus", "is_active": False},
        headers=admin,
    )
    assert (r.json()["min_age_band"], r.json()["is_active"]) == ("18_plus", False)
    r = await client.patch(
        f"/v1/admin/styles/{unique_slug}", json={"active_until": "2026-11-01"}, headers=admin
    )
    assert (r.status_code, r.json()["code"]) == (422, "style.bad_dates")
    for bad in ({"tone": "#abcdef"}, {"slug": "x"}, {"tagline": "a" * 91}):
        r = await client.post("/v1/admin/styles", json={**body, **bad}, headers=admin)
        assert r.status_code == 422
    assert (
        await client.patch("/v1/admin/styles/nessuno", json={}, headers=admin)
    ).status_code == 404
    slugs = [s["slug"] for s in (await client.get("/v1/admin/styles", headers=admin)).json()]
    assert unique_slug in slugs and "old-money" in slugs
    logged = db_admin.execute(
        "select count(*) from app.admin_audit_log where target = %s", (f"style:{unique_slug}",)
    ).fetchone()
    assert logged == (2,)
    db_admin.execute("delete from app.styles where slug = %s", (unique_slug,))


async def test_staff_e_ultimo_admin(client, keys, db_admin):
    db_admin.execute("delete from app.staff where role = 'admin'")
    _, admin, admin_nick = await _staff(client, keys, db_admin, role="admin")
    _, _, profile = await onboard(client, keys, db_admin)
    nick = profile["nickname"]
    r = await client.put(f"/v1/admin/staff/{nick}", json={"role": "moderator"}, headers=admin)
    assert (r.status_code, r.json()["role"]) == (200, "moderator")
    assert nick in [
        s["nickname"] for s in (await client.get("/v1/admin/staff", headers=admin)).json()
    ]
    r = await client.put(f"/v1/admin/staff/{admin_nick}", json={"role": "moderator"}, headers=admin)
    assert (r.status_code, r.json()["code"]) == (409, "staff.last_admin")
    r = await client.delete(f"/v1/admin/staff/{admin_nick}", headers=admin)
    assert r.json()["code"] == "staff.last_admin"
    assert (await client.delete(f"/v1/admin/staff/{nick}", headers=admin)).status_code == 204


async def test_registro_di_audit_a_pagine(client, keys, db_admin):
    _, admin, admin_nick = await _staff(client, keys, db_admin, role="admin")
    for _ in range(3):
        await client.get("/v1/admin/users/nessuno_x", headers=admin)  # 404, nessun audit
        await client.post(
            "/v1/admin/styles",
            json={"slug": "x", "name": "x", "tagline": "x"},
            headers=admin,
        )  # 422, nessun audit
    _, _, profile = await onboard(client, keys, db_admin)
    for role in ("moderator", "admin", "moderator"):
        await client.put(
            f"/v1/admin/staff/{profile['nickname']}", json={"role": role}, headers=admin
        )
    page = (await client.get("/v1/admin/audit", params={"limit": 2}, headers=admin)).json()
    assert [i["action"] for i in page["items"]] == ["admin.staff_set", "admin.staff_set"]
    assert page["items"][0]["staff"] == admin_nick
    assert page["items"][0]["details"] == {"role": "moderator"}
    nxt = (
        await client.get(
            "/v1/admin/audit", params={"limit": 2, "cursor": page["next_cursor"]}, headers=admin
        )
    ).json()
    assert nxt["items"][0]["id"] < page["items"][-1]["id"]
