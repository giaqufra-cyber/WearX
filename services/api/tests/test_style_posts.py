"""Griglia della pagina di uno stile (seduta 26): GET /v1/styles/{slug}/posts."""

from __future__ import annotations

import pytest

from tests.test_portfolio import _person, _post
from tests.test_votes import publish

pytestmark = pytest.mark.usefixtures("store")


async def _page(client, headers, slug="gorpcore", **params):
    r = await client.get(f"/v1/styles/{slug}/posts", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _all_ids(client, headers, slug="gorpcore", **params):
    """Tutte le pagine, in ordine (controlla anche che non ci siano doppioni)."""
    ids, cursor = [], None
    while True:
        extra = {"cursor": cursor} if cursor else {}
        page = await _page(client, headers, slug, **params, **extra)
        ids += [t["id"] for t in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(ids) == len(set(ids))
    return ids


async def _old_voter(client, keys, db_admin):
    vid, vh, _ = await _person(client, keys, db_admin)
    db_admin.execute(
        "update app.profiles set created_at = now() - interval '30 days' where id = %s", (vid,)
    )
    return vh


async def test_i_propri_fit_compaiono_nella_pagina_dello_stile(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    mine = await _post(client, db_admin, uid, h, style="gorpcore", caption="Il mio")
    other_style = await _post(client, db_admin, uid, h, style="jappo")
    oid, oh, _ = await _person(client, keys, db_admin)
    theirs = await _post(client, db_admin, oid, oh, style="gorpcore")

    ids = await _all_ids(client, h, sort="new")
    assert ids.index(theirs) < ids.index(mine)  # dal più recente
    assert other_style not in ids
    tile = next(
        t for t in (await _page(client, h, sort="new", limit=60))["items"] if t["id"] == mine
    )
    # Sul proprio fit media e numero di voti si vedono sempre (anche a zero).
    assert (tile["caption"], tile["vote_count"], tile["style"]["slug"]) == ("Il mio", 0, "gorpcore")


async def test_fit_fuori_stile_nascosti_o_cancellati_non_compaiono(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    rejected = await _post(client, db_admin, uid, h, style="gorpcore")
    hidden = await _post(client, db_admin, uid, h, style="gorpcore")
    deleted = await _post(client, db_admin, uid, h, style="gorpcore")
    kept = await _post(client, db_admin, uid, h, style="gorpcore")
    db_admin.execute("update app.posts set status = 'style_rejected' where id = %s", (rejected,))
    db_admin.execute("update app.posts set status = 'hidden_moderation' where id = %s", (hidden,))
    assert (await client.delete(f"/v1/posts/{deleted}", headers=h)).status_code == 204
    ids = await _all_ids(client, h, sort="new")
    assert kept in ids
    assert not {rejected, hidden, deleted} & set(ids)


async def test_in_evidenza_con_media_prudente_e_medie_solo_dopo_il_voto(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    great = await _post(client, db_admin, uid, h, style="minimal")
    fine = await _post(client, db_admin, uid, h, style="minimal")
    lone_hundred = await _post(client, db_admin, uid, h, style="minimal")
    voters = [await _old_voter(client, keys, db_admin) for _ in range(6)]
    for vh in voters[:6]:
        await client.put(f"/v1/posts/{great}/vote", json={"score": 92}, headers=vh)
    for vh in voters[:5]:
        await client.put(f"/v1/posts/{fine}/vote", json={"score": 75}, headers=vh)
    await client.put(f"/v1/posts/{lone_hundred}/vote", json={"score": 100}, headers=voters[0])
    await publish()

    _, viewer, _ = await _person(client, keys, db_admin)
    ids = [i for i in await _all_ids(client, viewer, "minimal") if i in {great, fine, lone_hundred}]
    # Un solo 100 non scavalca sei 92: sotto i 5 voti la media non è pubblicata e conta 60.
    assert ids == [great, fine, lone_hundred]
    tiles = {t["id"]: t for t in (await _page(client, viewer, "minimal", limit=60))["items"]}
    assert tiles[great]["average"] is None  # non l'ha votato
    tiles = {t["id"]: t for t in (await _page(client, voters[0], "minimal", limit=60))["items"]}
    assert (tiles[great]["mine"], tiles[great]["average"]) == (92, 92.0)


async def test_pagine_con_cursore_senza_doppioni(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    made = {await _post(client, db_admin, uid, h, style="techwear") for _ in range(7)}
    for sort in ("new", "top"):
        ids = await _all_ids(client, h, "techwear", sort=sort, limit=3)
        assert made <= set(ids)


async def test_cursore_manomesso_o_di_un_altro_ordine(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    for _ in range(3):
        await _post(client, db_admin, uid, h, style="y2k")
    page = await _page(client, h, "y2k", sort="new", limit=1)
    assert page["next_cursor"]
    r = await client.get(
        "/v1/styles/y2k/posts", params={"sort": "top", "cursor": page["next_cursor"]}, headers=h
    )
    assert (r.status_code, r.json()["code"]) == (400, "style.invalid_cursor")
    for bad in ("x", "bmV3fG5hbnwx", "bmV3fDF8bm9uLXV1aWQ"):
        r = await client.get("/v1/styles/y2k/posts", params={"cursor": bad}, headers=h)
        assert r.status_code == 400


async def test_regole_di_eta_e_blocchi(client, keys, db_admin):
    # Stile 18+: per un 16-17enne "non esiste".
    _, minor, _ = await _person(client, keys, db_admin, minor=True)
    r = await client.get("/v1/styles/beach-party/posts", headers=minor)
    assert (r.status_code, r.json()["code"]) == (404, "style.not_found")

    # Fit di un 16-17enne: non li vede un maggiorenne.
    mid, mh, _ = await _person(client, keys, db_admin, minor=True)
    minor_post = await _post(client, db_admin, mid, mh, style="country")
    _, adult, _ = await _person(client, keys, db_admin)
    assert minor_post not in await _all_ids(client, adult, "country")
    assert minor_post in await _all_ids(client, minor, "country")

    # Blocco: chi è bloccato non vede i fit di chi lo ha bloccato, e viceversa.
    aid, ah, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, aid, ah, style="country")
    _, bh, bnick = await _person(client, keys, db_admin)
    assert post in await _all_ids(client, bh, "country")
    assert (await client.put(f"/v1/users/{bnick}/block", headers=ah)).status_code in (200, 204)
    assert post not in await _all_ids(client, bh, "country")
