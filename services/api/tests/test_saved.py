"""Fit salvati e archivio (seduta 32)."""

from __future__ import annotations

import pytest

from tests.test_portfolio import _grid, _ids, _person, _post

pytestmark = pytest.mark.usefixtures("store")


async def _saved(client, headers, **params):
    r = await client.get("/v1/me/saved", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _archive(client, headers):
    r = await client.get("/v1/me/archive", headers=headers)
    assert r.status_code == 200, r.text
    return [t["id"] for t in r.json()["items"]]


async def _get(client, post_id, headers):
    return await client.get(f"/v1/posts/{post_id}", headers=headers)


async def test_salvare_e_togliere(client, keys, db_admin):
    shop_id, shop, shop_nick = await _person(client, keys, db_admin, business=True)
    priv_id, priv, _ = await _person(client, keys, db_admin)
    _, me, _ = await _person(client, keys, db_admin)
    a = await _post(client, db_admin, shop_id, shop, caption="Del negozio")
    b = await _post(client, db_admin, priv_id, priv)

    r = await client.put(f"/v1/posts/{a}/save", headers=me)
    assert (r.status_code, r.json()) == (200, {"saved": True})
    assert (await client.put(f"/v1/posts/{a}/save", headers=me)).status_code == 200  # ripetibile
    assert (await client.put(f"/v1/posts/{b}/save", headers=me)).status_code == 200

    assert (await _get(client, a, me)).json()["saved"] is True
    # L'autore vede quante volte è stato salvato, non da chi; non lo vede "salvato" lui.
    mine = (await _get(client, a, shop)).json()
    assert (mine["saved"], mine["save_count"], mine["archived"]) == (False, 1, False)
    assert (await _get(client, a, me)).json()["save_count"] is None

    page = await _saved(client, me)
    assert [t["id"] for t in page["items"]] == [b, a]  # dal più recente
    tiles = {t["id"]: t for t in page["items"]}
    assert tiles[a]["author"]["nickname"] == shop_nick
    assert tiles[a]["caption"] == "Del negozio"
    # Un profilo privato che non segui resta anonimo anche nei salvati.
    assert tiles[b]["author"] is None
    assert tiles[b]["capsule_id"] is None and tiles[b]["own"] is False

    assert (await client.delete(f"/v1/posts/{a}/save", headers=me)).status_code == 204
    assert (await client.delete(f"/v1/posts/{a}/save", headers=me)).status_code == 204
    assert [t["id"] for t in (await _saved(client, me))["items"]] == [b]
    assert (await _get(client, a, me)).json()["saved"] is False

    # I propri fit non si salvano.
    r = await client.put(f"/v1/posts/{a}/save", headers=shop)
    assert (r.status_code, r.json()["code"]) == (422, "save.own")


async def test_salvati_a_pagine(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin, business=True)
    _, me, _ = await _person(client, keys, db_admin)
    posts = [await _post(client, db_admin, author_id, author) for _ in range(5)]
    for p in posts:
        await client.put(f"/v1/posts/{p}/save", headers=me)
    seen, cursor = [], None
    while True:
        page = await _saved(client, me, limit=2, **({"cursor": cursor} if cursor else {}))
        seen += [t["id"] for t in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == list(reversed(posts))
    r = await client.get("/v1/me/saved", params={"cursor": "rotto"}, headers=me)
    assert r.status_code == 400


async def test_archivio_nasconde_a_tutti_e_rimette_al_suo_posto(client, keys, db_admin):
    author_id, author, nick = await _person(client, keys, db_admin, business=True)
    _, fan, _ = await _person(client, keys, db_admin)
    first = await _post(client, db_admin, author_id, author, style="gorpcore")
    second = await _post(client, db_admin, author_id, author, style="gorpcore")
    third = await _post(client, db_admin, author_id, author, style="gorpcore")
    r = await client.post("/v1/me/capsules", json={"name": "Estate"}, headers=author)
    capsule = r.json()["id"]
    await client.patch(f"/v1/posts/{second}", json={"capsule_id": capsule}, headers=author)
    await client.put(f"/v1/posts/{second}/save", headers=fan)
    before = await _ids(client, nick, author)
    assert before == [third, second, first]

    r = await client.post(f"/v1/posts/{second}/archive", headers=author)
    assert (r.status_code, r.json()["archived"]) == (200, True)
    assert (await client.post(f"/v1/posts/{second}/archive", headers=author)).status_code == 200

    # Per gli altri non esiste più: dettaglio, profilo, capsula, stile, salvati.
    assert (await _get(client, second, fan)).status_code == 404
    assert second not in await _ids(client, nick, fan)
    assert [t["id"] for t in (await _saved(client, fan))["items"]] == []
    assert (await client.put(f"/v1/posts/{second}/save", headers=fan)).status_code == 404
    style_page = await client.get("/v1/styles/gorpcore/posts", params={"limit": 60}, headers=fan)
    assert second not in [t["id"] for t in style_page.json()["items"]]
    profile = (await client.get(f"/v1/users/{nick}", headers=fan)).json()
    assert profile["stats"]["posts"] == 2
    # Anche per chi l'ha pubblicato è fuori dal profilo e dalle capsule, ma in Archivio.
    assert await _ids(client, nick, author) == [third, first]
    mine = (await client.get(f"/v1/users/{nick}", headers=author)).json()
    assert mine["stats"]["posts"] == 2
    assert [c["post_count"] for c in mine["capsules"] if c["id"] == capsule] == [0]
    assert await _archive(client, author) == [second]
    detail = (await _get(client, second, author)).json()
    assert (detail["archived"], detail["capsule_id"], detail["save_count"]) == (True, capsule, 1)
    # Non si può spostare in copertina mentre è in archivio.
    r = await client.put(
        "/v1/me/portfolio/order", json={"post_id": second, "after_id": None}, headers=author
    )
    assert r.status_code == 404

    # Rimesso: torna al suo posto, nella sua capsula, e ricompare nei salvati di chi l'aveva.
    r = await client.delete(f"/v1/posts/{second}/archive", headers=author)
    assert (r.status_code, r.json()["archived"]) == (200, False)
    assert await _ids(client, nick, author) == before
    assert await _ids(client, nick, fan, capsule=capsule) == [second]
    assert await _archive(client, author) == []
    assert [t["id"] for t in (await _saved(client, fan))["items"]] == [second]


async def test_archivio_solo_dei_propri_fit(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin, business=True)
    _, other, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    r = await client.post(f"/v1/posts/{post}/archive", headers=other)
    assert (r.status_code, r.json()["code"]) == (403, "post.not_owner")
    assert (await client.delete(f"/v1/posts/{post}/archive", headers=other)).status_code == 403
    assert (await client.get("/v1/me/archive", headers=other)).json()["items"] == []


async def test_eliminare_un_fit_toglie_i_salvataggi(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin, business=True)
    _, fan, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    await client.put(f"/v1/posts/{post}/save", headers=fan)
    assert (await client.delete(f"/v1/posts/{post}", headers=author)).status_code == 204
    left = db_admin.execute(
        "select count(*) from app.saved_posts where post_id = %s", (post,)
    ).fetchone()
    assert left[0] == 0
    assert (await _saved(client, fan))["items"] == []


async def test_griglia_degli_altri_non_mostra_le_capsule(client, keys, db_admin):
    author_id, author, nick = await _person(client, keys, db_admin, business=True)
    _, other, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    capsule = (await client.post("/v1/me/capsules", json={"name": "Mia"}, headers=author)).json()
    await client.patch(f"/v1/posts/{post}", json={"capsule_id": capsule["id"]}, headers=author)
    tile = (await _grid(client, nick, other))["items"][0]
    assert tile["capsule_id"] is None
    assert (await _grid(client, nick, author))["items"][0]["capsule_id"] == capsule["id"]
