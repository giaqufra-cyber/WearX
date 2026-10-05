"""Account privati: follow con richiesta, blocchi, tutele per i 16-17 (sez. 6.6 e 14.1)."""

from __future__ import annotations

import asyncio

import pytest

from app.config import get_settings
from tests.conftest import ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")


async def _person(client, keys, db_admin, *, business=False, minor=False):
    user_id, headers, profile = await onboard(client, keys, db_admin, minor=minor)
    if business:
        db_admin.execute(
            "update app.profiles set account_type = 'business' where id = %s", (user_id,)
        )
    return user_id, headers, profile["nickname"]


async def _post(client, db_admin, user_id, headers, style="old-money"):
    media = [str(ready_upload(db_admin, user_id))]
    r = await client.post("/v1/posts", json={"style": style, "media": media}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _follow(client, nick, headers):
    return await client.post(f"/v1/users/{nick}/follow", headers=headers)


async def _profile(client, nick, headers):
    return await client.get(f"/v1/users/{nick}", headers=headers)


async def _nicks(client, path, headers):
    r = await client.get(path, headers=headers)
    assert r.status_code == 200, r.text
    return [p["nickname"] for p in r.json()["items"]]


# ---------- Follow ----------


async def test_richiesta_accettata_apre_il_portfolio(client, keys, db_admin):
    owner_id, owner, owner_nick = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, owner_id, owner)
    _, fan, fan_nick = await _person(client, keys, db_admin)

    r = await _follow(client, owner_nick, fan)
    assert (r.status_code, r.json()) == (200, {"following": "pending"})
    assert (await _follow(client, owner_nick, fan)).json() == {"following": "pending"}  # ripetibile
    body = (await _profile(client, owner_nick, fan)).json()
    assert body["relationship"] == {"following": "pending", "follows_you": False}
    assert body["can_view_posts"] is False

    mine = (await _profile(client, owner_nick, owner)).json()
    assert (mine["pending_requests"], mine["followers"]) == (1, 0)
    assert await _nicks(client, "/v1/me/follow-requests", owner) == [fan_nick]

    r = await client.post(
        "/v1/me/follow-requests", json={"nickname": fan_nick, "decision": "accept"}, headers=owner
    )
    assert r.status_code == 204
    body = (await _profile(client, owner_nick, fan)).json()
    assert body["relationship"]["following"] == "accepted"
    assert body["can_view_posts"] is True
    grid = (await client.get(f"/v1/users/{owner_nick}/posts", headers=fan)).json()
    assert [t["id"] for t in grid["items"]] == [post]
    # Nel feed il fit ora mostra l'autore.
    assert (await client.get(f"/v1/posts/{post}", headers=fan)).json()["author"] is not None

    mine = (await _profile(client, owner_nick, owner)).json()
    assert (mine["pending_requests"], mine["followers"], mine["following"]) == (0, 1, 0)
    assert (await _profile(client, fan_nick, owner)).json()["relationship"]["follows_you"] is True
    assert await _nicks(client, "/v1/me/followers", owner) == [fan_nick]
    assert await _nicks(client, "/v1/me/following", fan) == [owner_nick]
    assert await _nicks(client, "/v1/me/follow-requests", owner) == []


async def test_rifiuto_ritiro_e_smettere_di_seguire(client, keys, db_admin):
    _, owner, owner_nick = await _person(client, keys, db_admin)
    _, fan, fan_nick = await _person(client, keys, db_admin)
    await _follow(client, owner_nick, fan)
    r = await client.post(
        "/v1/me/follow-requests", json={"nickname": fan_nick, "decision": "reject"}, headers=owner
    )
    assert r.status_code == 204
    assert (await _profile(client, owner_nick, fan)).json()["relationship"]["following"] == "none"
    # Richiesta inesistente (già decisa).
    r = await client.post(
        "/v1/me/follow-requests", json={"nickname": fan_nick, "decision": "accept"}, headers=owner
    )
    assert (r.status_code, r.json()["code"]) == (404, "follow.request_not_found")

    # Ritirare una richiesta.
    await _follow(client, owner_nick, fan)
    assert (await client.delete(f"/v1/users/{owner_nick}/follow", headers=fan)).status_code == 204
    assert await _nicks(client, "/v1/me/follow-requests", owner) == []

    # Smettere di seguire, e togliere un follower.
    await _follow(client, owner_nick, fan)
    await client.post(
        "/v1/me/follow-requests", json={"nickname": fan_nick, "decision": "accept"}, headers=owner
    )
    assert (await client.delete(f"/v1/me/followers/{fan_nick}", headers=owner)).status_code == 204
    assert (await _profile(client, owner_nick, fan)).json()["can_view_posts"] is False
    assert (await client.delete(f"/v1/users/{owner_nick}/follow", headers=fan)).status_code == 204


async def test_business_si_segue_subito(client, keys, db_admin):
    _, _, shop = await _person(client, keys, db_admin, business=True)
    _, fan, _ = await _person(client, keys, db_admin)
    assert (await _follow(client, shop, fan)).json() == {"following": "accepted"}


async def test_passando_a_business_le_richieste_diventano_follow(
    client, keys, db_admin, monkeypatch
):
    monkeypatch.setitem(get_settings().feature_flags, "business_accounts", True)
    _, owner, owner_nick = await _person(client, keys, db_admin)
    _, fan, _ = await _person(client, keys, db_admin)
    await _follow(client, owner_nick, fan)
    r = await client.patch("/v1/me", json={"account_type": "business"}, headers=owner)
    assert r.status_code == 200, r.text
    rel = (await _profile(client, owner_nick, fan)).json()["relationship"]
    assert rel["following"] == "accepted"


async def test_regole_del_follow(client, keys, db_admin):
    _, me, my_nick = await _person(client, keys, db_admin)
    r = await _follow(client, my_nick, me)
    assert (r.status_code, r.json()["code"]) == (422, "follow.self")
    r = await _follow(client, "non_esiste_qui", me)
    assert (r.status_code, r.json()["code"]) == (404, "user.not_found")


async def test_elenchi_a_pagine(client, keys, db_admin, monkeypatch):
    from app.routers import social

    monkeypatch.setattr(social, "PAGE", 2)
    _, owner, owner_nick = await _person(client, keys, db_admin)
    fans = []
    for _ in range(5):
        _, fan, nick = await _person(client, keys, db_admin)
        await _follow(client, owner_nick, fan)
        fans.append(nick)
    seen, cursor = [], None
    while True:
        params = {"cursor": cursor} if cursor else {}
        r = await client.get("/v1/me/follow-requests", params=params, headers=owner)
        seen += [p["nickname"] for p in r.json()["items"]]
        cursor = r.json()["next_cursor"]
        if not cursor:
            break
    assert seen == fans[::-1]  # dalla più recente
    r = await client.get("/v1/me/follow-requests", params={"cursor": "%%"}, headers=owner)
    assert (r.status_code, r.json()["code"]) == (400, "people.invalid_cursor")


async def test_richieste_in_parallelo_una_sola_riga(client, keys, db_admin):
    owner_id, _, owner_nick = await _person(client, keys, db_admin)
    fan_id, fan, _ = await _person(client, keys, db_admin)
    results = await asyncio.gather(*(_follow(client, owner_nick, fan) for _ in range(8)))
    assert all(r.status_code == 200 for r in results)
    count = db_admin.execute(
        "select count(*) from app.follows where follower_id = %s and followee_id = %s",
        (fan_id, owner_id),
    ).fetchone()
    assert count == (1,)


# ---------- Blocchi ----------


async def test_blocco_toglie_i_follow_e_nasconde_tutto(client, keys, db_admin):
    a_id, a, a_nick = await _person(client, keys, db_admin)
    b_id, b, b_nick = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, b_id, b)
    # Si seguono a vicenda.
    await _follow(client, b_nick, a)
    await _follow(client, a_nick, b)
    for owner, nick in ((b, a_nick), (a, b_nick)):
        await client.post(
            "/v1/me/follow-requests", json={"nickname": nick, "decision": "accept"}, headers=owner
        )

    assert (await client.put(f"/v1/users/{b_nick}/block", headers=a)).status_code == 204
    assert (await client.put(f"/v1/users/{b_nick}/block", headers=a)).status_code == 204
    left = db_admin.execute(
        """select count(*) from app.follows
            where follower_id in (%s, %s) and followee_id in (%s, %s)""",
        (a_id, b_id, a_id, b_id),
    ).fetchone()
    assert left == (0,)
    for viewer, nick in ((a, b_nick), (b, a_nick)):
        assert (await _profile(client, nick, viewer)).status_code == 404
        assert (await _follow(client, nick, viewer)).status_code == 404
    assert (await client.get(f"/v1/posts/{post}", headers=a)).status_code == 404
    assert await _nicks(client, "/v1/me/blocks", a) == [b_nick]
    assert await _nicks(client, "/v1/me/blocks", b) == []

    # Sbloccare: ci si rivede, ma i follow vanno richiesti di nuovo.
    assert (await client.delete(f"/v1/users/{b_nick}/block", headers=a)).status_code == 204
    body = (await _profile(client, b_nick, a)).json()
    assert body["relationship"] == {"following": "none", "follows_you": False}
    assert await _nicks(client, "/v1/me/blocks", a) == []


async def test_blocco_regole(client, keys, db_admin):
    _, me, my_nick = await _person(client, keys, db_admin)
    r = await client.put(f"/v1/users/{my_nick}/block", headers=me)
    assert (r.status_code, r.json()["code"]) == (422, "block.self")
    r = await client.put("/v1/users/nessuno_qui/block", headers=me)
    assert r.status_code == 404
    # Si può bloccare anche chi non si vede (un 16-17 per un adulto): è una protezione.
    _, _, minor_nick = await _person(client, keys, db_admin, minor=True)
    assert (await client.put(f"/v1/users/{minor_nick}/block", headers=me)).status_code == 204


# ---------- Tutele per i 16-17 ----------


async def test_adulti_e_16_17_non_si_trovano(client, keys, db_admin):
    minor_id, minor, minor_nick = await _person(client, keys, db_admin, minor=True)
    _, adult, adult_nick = await _person(client, keys, db_admin)
    # Un adulto non vede il profilo di un 16-17 e non può chiedergli il follow.
    assert (await _profile(client, minor_nick, adult)).status_code == 404
    assert (await _follow(client, minor_nick, adult)).status_code == 404
    # Un 16-17 vede il profilo di un adulto e può chiedere di seguirlo.
    assert (await _profile(client, adult_nick, minor)).status_code == 200
    assert (await _follow(client, adult_nick, minor)).json() == {"following": "pending"}
    # Tra 16-17 ci si trova.
    _, other_minor, _ = await _person(client, keys, db_admin, minor=True)
    assert (await _profile(client, minor_nick, other_minor)).status_code == 200
    del minor_id


async def test_i_fit_dei_16_17_restano_tra_16_17(client, keys, db_admin):
    minor_id, minor, minor_nick = await _person(client, keys, db_admin, minor=True)
    db_admin.execute("update app.profiles set created_at = now() - interval '30 days'")
    post = await _post(client, db_admin, minor_id, minor)
    _, adult, _ = await _person(client, keys, db_admin)
    _, other_minor, _ = await _person(client, keys, db_admin, minor=True)

    assert (await client.get(f"/v1/posts/{post}", headers=adult)).status_code == 404
    r = await client.put(f"/v1/posts/{post}/vote", json={"score": 90}, headers=adult)
    assert r.status_code == 404
    assert (await client.get(f"/v1/posts/{post}", headers=other_minor)).status_code == 200
    assert (await client.get(f"/v1/posts/{post}", headers=minor)).status_code == 200  # suo

    # Nel feed: l'adulto che segue old-money non lo riceve, l'altro 16-17 sì.
    async def feed_ids(headers):
        r = await client.get("/v1/feed", params={"style": "old-money"}, headers=headers)
        return {p["id"] for p in r.json()["items"]}

    assert post not in await feed_ids(adult)
    assert post in await feed_ids(other_minor)

    # Compiuti 18 anni: il profilo diventa trovabile, ma i fit di quando aveva 16-17 anni no.
    db_admin.execute(
        "update app.profiles set adult_on = current_date - 1 where id = %s", (minor_id,)
    )
    assert (await client.get("/v1/me", headers=minor)).json()["age_band"] == "18_plus"
    new_post = await _post(client, db_admin, minor_id, minor)
    db_admin.execute("update app.profiles set account_type = 'business' where id = %s", (minor_id,))
    assert (await _profile(client, minor_nick, adult)).status_code == 200
    grid = (await client.get(f"/v1/users/{minor_nick}/posts", headers=adult)).json()
    assert [t["id"] for t in grid["items"]] == [new_post]
    assert (await client.get(f"/v1/posts/{post}", headers=adult)).status_code == 404


async def test_richiesta_vecchia_di_chi_ha_compiuto_18_anni(client, keys, db_admin):
    minor_id, minor, minor_nick = await _person(client, keys, db_admin, minor=True)
    fan_id, fan, fan_nick = await _person(client, keys, db_admin, minor=True)
    await _follow(client, minor_nick, fan)
    # Il richiedente diventa maggiorenne prima che la richiesta sia accettata.
    db_admin.execute(
        "update app.profiles set age_band = '18_plus', adult_on = null where id = %s", (fan_id,)
    )
    r = await client.post(
        "/v1/me/follow-requests", json={"nickname": fan_nick, "decision": "accept"}, headers=minor
    )
    assert (r.status_code, r.json()["code"]) == (409, "follow.not_allowed")
    assert await _nicks(client, "/v1/me/follow-requests", minor) == []
    del minor_id
