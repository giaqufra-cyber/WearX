"""Feedback dei tester (seduta 25): invio dall'app, lista e stato nel pannello, archivio dati."""

from __future__ import annotations

import pytest

from tests.authkit import bearer
from tests.test_accounts import onboard

BODY = {
    "kind": "bug",
    "message": "  Il voto non parte\n\n\n\nquando tocco Vota due volte.  ",
    "app_version": "0.1.0",
    "platform": "ios",
    "os_version": "18.6",
    "screen": "/post/[id]",
}


async def _staff(client, keys, db_admin):
    user_id, _, _ = await onboard(client, keys, db_admin)
    db_admin.execute("insert into app.staff (user_id, role) values (%s, 'moderator')", (user_id,))
    return bearer(keys.token(user_id, aal="aal2"))


async def test_dall_app_al_pannello(client, keys, db_admin):
    _, me, profile = await onboard(client, keys, db_admin)
    r = await client.post("/v1/feedback", json=BODY, headers=me)
    assert r.status_code == 201, r.text
    feedback_id = r.json()["id"]

    staff = await _staff(client, keys, db_admin)
    page = (await client.get("/v1/admin/feedback", headers=staff)).json()
    item = next(i for i in page["items"] if i["id"] == feedback_id)
    assert item["author"] == profile["nickname"]
    assert item["message"] == "Il voto non parte\n\nquando tocco Vota due volte."
    assert (item["status"], item["platform"], item["screen"]) == ("new", "ios", "/post/[id]")
    assert page["counts"]["new"] >= 1

    r = await client.patch(
        f"/v1/admin/feedback/{feedback_id}",
        json={"status": "done", "staff_note": "Corretto  nella 0.1.1"},
        headers=staff,
    )
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["staff_note"]) == ("done", "Corretto nella 0.1.1")
    open_ids = [
        i["id"] for i in (await client.get("/v1/admin/feedback", headers=staff)).json()["items"]
    ]
    assert feedback_id not in open_ids
    done = await client.get("/v1/admin/feedback?status=done&kind=bug", headers=staff)
    assert feedback_id in [i["id"] for i in done.json()["items"]]
    logged = db_admin.execute(
        "select count(*) from app.admin_audit_log where target = %s", (f"feedback:{feedback_id}",)
    ).fetchone()
    assert logged == (1,)


@pytest.mark.parametrize(
    "change",
    [
        {"message": "  \n "},
        {"message": "x" * 2001},
        {"kind": "complaint"},
        {"platform": "symbian"},
        {"screen": "/user/giulia?token=abc"},
        {"app_version": "1.0 <script>"},
        {"extra": "no"},
    ],
)
async def test_richieste_non_valide(client, keys, db_admin, change):
    _, me, _ = await onboard(client, keys, db_admin)
    r = await client.post("/v1/feedback", json={**BODY, **change}, headers=me)
    assert r.status_code == 422


async def test_solo_lo_staff_vede_i_messaggi(client, keys, db_admin):
    _, me, _ = await onboard(client, keys, db_admin)
    assert (await client.get("/v1/admin/feedback", headers=me)).status_code == 404
    r = await client.patch(
        "/v1/admin/feedback/00000000-0000-0000-0000-000000000000",
        json={"status": "seen"},
        headers=await _staff(client, keys, db_admin),
    )
    assert r.status_code == 404


async def test_al_massimo_dieci_al_giorno(client, keys, db_admin):
    _, me, _ = await onboard(client, keys, db_admin)
    codes = [
        (await client.post("/v1/feedback", json=BODY, headers=me)).status_code for _ in range(11)
    ]
    assert codes[:10] == [201] * 10 and codes[10] == 429
