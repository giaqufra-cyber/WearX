"""Portfolio: griglia, ordine con indice frazionario, copertina, capsule, chi vede cosa."""

from __future__ import annotations

import asyncio
import random
import uuid
from itertools import pairwise

import pytest

from app.ranking import MAX_KEY_LEN, key_now
from tests.conftest import ready_upload
from tests.test_accounts import onboard
from tests.test_votes import publish

pytestmark = pytest.mark.usefixtures("store")


async def _person(client, keys, db_admin, *, business=False, **kw):
    user_id, headers, profile = await onboard(client, keys, db_admin, **kw)
    if business:
        db_admin.execute(
            "update app.profiles set account_type = 'business' where id = %s", (user_id,)
        )
    return user_id, headers, profile["nickname"]


async def _post(client, db_admin, user_id, headers, style="old-money", caption=None, n=1):
    media = [str(ready_upload(db_admin, user_id)) for _ in range(n)]
    body = {"style": style, "media": media, "caption": caption}
    r = await client.post("/v1/posts", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _grid(client, nick, headers, **params):
    r = await client.get(f"/v1/users/{nick}/posts", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _ids(client, nick, headers, **params):
    return [t["id"] for t in (await _grid(client, nick, headers, limit=60, **params))["items"]]


async def _move(client, headers, post_id, after_id):
    return await client.put(
        "/v1/me/portfolio/order", json={"post_id": post_id, "after_id": after_id}, headers=headers
    )


# ---------- Griglia e ordine ----------


async def test_griglia_dal_piu_recente_con_foto_e_media(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    first = await _post(client, db_admin, uid, h, caption="Primo", n=3)
    second = await _post(client, db_admin, uid, h, style="jappo", caption="Secondo")
    page = await _grid(client, nick, h)
    assert [t["id"] for t in page["items"]] == [second, first]
    assert page["cover_id"] == second
    assert page["next_cursor"] is None
    tile = page["items"][1]
    assert (tile["caption"], tile["media_count"], tile["style"]["slug"]) == (
        "Primo",
        3,
        "old-money",
    )
    assert set(tile["photo"]["urls"]["variants"]) == {"320", "640", "1080"}
    # Il proprio portfolio mostra sempre media e numero di voti (anche a zero).
    assert (tile["average"], tile["vote_count"], tile["mine"]) == (None, 0, None)


async def test_in_testa_diventa_copertina_e_i_nuovi_entrano_sotto(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    a = await _post(client, db_admin, uid, h)
    b = await _post(client, db_admin, uid, h)
    c = await _post(client, db_admin, uid, h)
    assert await _ids(client, nick, h) == [c, b, a]

    assert (await _move(client, h, a, None)).status_code == 204
    assert await _ids(client, nick, h) == [a, c, b]
    cover = db_admin.execute("select portfolio_cover_id from app.profiles where id = %s", (uid,))
    assert cover.fetchone() == (uuid.UUID(a),)

    # Un fit nuovo non "ruba" la copertina scelta: entra subito sotto.
    d = await _post(client, db_admin, uid, h)
    e = await _post(client, db_admin, uid, h)
    assert await _ids(client, nick, h) == [a, e, d, c, b]
    assert (await _grid(client, nick, h))["cover_id"] == a

    # Eliminata la copertina, la copertina diventa il fit che ora è primo (e resta scelta).
    assert (await client.delete(f"/v1/posts/{a}", headers=h)).status_code == 204
    assert await _ids(client, nick, h) == [e, d, c, b]
    f = await _post(client, db_admin, uid, h)
    assert await _ids(client, nick, h) == [e, f, d, c, b]


async def test_spostamenti_casuali_come_il_modello(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    for _ in range(6):
        await _post(client, db_admin, uid, h)
    order = await _ids(client, nick, h)
    rng = random.Random(14)  # noqa: S311 - ordine casuale ripetibile, non crittografia
    for _ in range(60):
        post = rng.choice(order)
        rest = [p for p in order if p != post]
        slot = rng.randrange(len(rest) + 1)  # 0 = in testa
        after = None if slot == 0 else rest[slot - 1]
        r = await _move(client, h, post, after)
        assert r.status_code == 204, r.text
        order = [*rest[:slot], post, *rest[slot:]]
        assert await _ids(client, nick, h) == order


async def test_le_chiavi_restano_corte(client, keys, db_admin):
    """Spostare sempre nello stesso punto allunga le chiavi: oltre la soglia si riscrivono."""
    uid, h, nick = await _person(client, keys, db_admin)
    a, b, c = [await _post(client, db_admin, uid, h) for _ in range(3)][::-1]
    assert await _ids(client, nick, h) == [a, b, c]
    lengths = []
    for i in range(250):
        moving = c if i % 2 == 0 else b
        assert (await _move(client, h, moving, a)).status_code == 204
        lengths.append(
            db_admin.execute(
                """select max(length(portfolio_rank)) from app.posts
                    where author_id = %s and status <> 'deleted'""",
                (uid,),
            ).fetchone()[0]
        )
    assert max(lengths) <= MAX_KEY_LEN
    assert any(y < x for x, y in pairwise(lengths))  # almeno un ribilanciamento
    assert await _ids(client, nick, h) == [a, b, c]  # l'ultimo spostato (b) è subito dopo a
    # Dopo il ribilanciamento i fit nuovi vanno ancora sotto la copertina (a).
    d = await _post(client, db_admin, uid, h)
    assert await _ids(client, nick, h) == [a, d, b, c]


async def test_chiavi_vecchie_uguali_si_sistemano(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    a, b, c = [await _post(client, db_admin, uid, h) for _ in range(3)]
    same = key_now()
    db_admin.execute("update app.posts set portfolio_rank = %s where author_id = %s", (same, uid))
    assert (await _move(client, h, a, c)).status_code == 204
    order = await _ids(client, nick, h)
    assert order.index(a) == order.index(c) + 1
    ranks = db_admin.execute(
        "select count(distinct portfolio_rank) from app.posts where author_id = %s", (uid,)
    ).fetchone()
    assert ranks == (3,)
    del b


async def test_riordini_in_parallelo_restano_coerenti(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    posts = [await _post(client, db_admin, uid, h) for _ in range(5)]
    rng = random.Random(7)  # noqa: S311
    moves = [(rng.choice(posts), rng.choice([None, *posts])) for _ in range(20)]
    results = await asyncio.gather(
        *(_move(client, h, p, a) for p, a in moves if p != a),
    )
    assert all(r.status_code == 204 for r in results)
    order = await _ids(client, nick, h)
    assert sorted(order) == sorted(posts)
    distinct = db_admin.execute(
        """select count(distinct portfolio_rank) from app.posts
            where author_id = %s and status <> 'deleted'""",
        (uid,),
    ).fetchone()
    assert distinct == (5,)


async def test_riordino_solo_dei_propri_fit(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    other_id, other_h, _ = await _person(client, keys, db_admin)
    mine = await _post(client, db_admin, uid, h)
    mine2 = await _post(client, db_admin, uid, h)
    theirs = await _post(client, db_admin, other_id, other_h)

    r = await _move(client, h, theirs, None)
    assert (r.status_code, r.json()["code"]) == (404, "post.not_found")
    r = await _move(client, h, mine, theirs)
    assert (r.status_code, r.json()["code"]) == (422, "portfolio.bad_position")
    r = await _move(client, h, mine, mine)
    assert (r.status_code, r.json()["code"]) == (422, "portfolio.bad_position")
    r = await _move(client, h, str(uuid.uuid4()), None)
    assert r.status_code == 404
    await client.delete(f"/v1/posts/{mine2}", headers=h)
    r = await _move(client, h, mine, mine2)
    assert r.json()["code"] == "portfolio.bad_position"
    r = await _move(client, h, mine2, None)
    assert r.status_code == 404


async def test_pagine_con_cursore(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    posts = [await _post(client, db_admin, uid, h) for _ in range(5)][::-1]
    seen, cursor = [], None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = await _grid(client, nick, h, **params)
        seen += [t["id"] for t in page["items"]]
        assert page["cover_id"] == posts[0]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == posts
    for bad in ("x", "%%%", "YWJjfG5vbi11dWlk", "Ki0qfDEyMw"):
        r = await client.get(f"/v1/users/{nick}/posts", params={"cursor": bad}, headers=h)
        assert (r.status_code, r.json()["code"]) == (400, "portfolio.invalid_cursor")


# ---------- Chi vede cosa ----------


async def test_profilo_proprio(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    db_admin.execute("update app.profiles set bio = 'Trento, presto Monaco' where id = %s", (uid,))
    await _post(client, db_admin, uid, h)
    r = await client.get(f"/v1/users/{nick.upper()}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert (body["nickname"], body["is_self"], body["can_view_posts"]) == (nick, True, True)
    assert body["bio"] == "Trento, presto Monaco"
    assert [s["slug"] for s in body["styles"]] == ["old-money", "jappo"]
    assert body["stats"] == {"posts": 1, "average": None, "votes": 0}


async def test_account_privato_non_seguito(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    await _post(client, db_admin, uid, h)
    _, viewer, _ = await _person(client, keys, db_admin)
    r = await client.get(f"/v1/users/{nick}", headers=viewer)
    body = r.json()
    assert (body["can_view_posts"], body["is_self"], body["account_type"]) == (
        False,
        False,
        "private",
    )
    assert body["stats"] == {"posts": 1, "average": None, "votes": None}
    assert (body["styles"], body["capsules"]) == ([], [])
    r = await client.get(f"/v1/users/{nick}/posts", headers=viewer)
    assert (r.status_code, r.json()["code"]) == (403, "profile.private")


async def test_seguito_accettato_o_business_si_vede(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, uid, h)
    viewer_id, viewer, _ = await _person(client, keys, db_admin)
    db_admin.execute(
        "insert into app.follows (follower_id, followee_id, status) values (%s, %s, 'pending')",
        (viewer_id, uid),
    )
    r = await client.get(f"/v1/users/{nick}/posts", headers=viewer)
    assert r.status_code == 403  # richiesta non ancora accettata
    db_admin.execute(
        "update app.follows set status = 'accepted' where follower_id = %s", (viewer_id,)
    )
    assert await _ids(client, nick, viewer) == [post]

    biz_id, biz_h, biz = await _person(client, keys, db_admin, business=True)
    biz_post = await _post(client, db_admin, biz_id, biz_h)
    assert await _ids(client, biz, viewer) == [biz_post]


@pytest.mark.parametrize("direction", ["io_blocco", "mi_blocca"])
async def test_blocco_fa_sparire_il_profilo(client, keys, db_admin, direction):
    uid, _, nick = await _person(client, keys, db_admin, business=True)
    viewer_id, viewer, _ = await _person(client, keys, db_admin)
    pair = (viewer_id, uid) if direction == "io_blocco" else (uid, viewer_id)
    db_admin.execute("insert into app.blocks (blocker_id, blocked_id) values (%s, %s)", pair)
    for path in (f"/v1/users/{nick}", f"/v1/users/{nick}/posts"):
        r = await client.get(path, headers=viewer)
        assert (r.status_code, r.json()["code"]) == (404, "user.not_found")


async def test_profili_inesistenti_o_sospesi(client, keys, db_admin):
    uid, _, nick = await _person(client, keys, db_admin, business=True)
    _, viewer, _ = await _person(client, keys, db_admin)
    for name in ("nessuno_qui", "x", "a%25b", "a b", "z" * 21):
        r = await client.get(f"/v1/users/{name}", headers=viewer)
        assert r.status_code == 404
    db_admin.execute("update app.profiles set status = 'suspended' where id = %s", (uid,))
    r = await client.get(f"/v1/users/{nick}", headers=viewer)
    assert r.status_code == 404


async def test_medie_degli_altri_solo_dopo_il_voto(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin, business=True)
    posts = [await _post(client, db_admin, uid, h) for _ in range(3)]
    voters = []
    for _ in range(6):
        vid, vh, _ = await _person(client, keys, db_admin)
        db_admin.execute(
            "update app.profiles set created_at = now() - interval '30 days' where id = %s",
            (vid,),
        )
        voters.append(vh)
    # Due fit con 5 voti ciascuno (la media si mostra da 5 voti); voters[5] non vota.
    for p in posts[:2]:
        for vh in voters[:5]:
            r = await client.put(f"/v1/posts/{p}/vote", json={"score": 80}, headers=vh)
            assert r.status_code == 200, r.text
    await publish()

    tiles = {t["id"]: t for t in (await _grid(client, nick, voters[5]))["items"]}
    assert all(t["average"] is None and t["vote_count"] is None for t in tiles.values())
    tiles = {t["id"]: t for t in (await _grid(client, nick, voters[0]))["items"]}
    assert (tiles[posts[0]]["mine"], tiles[posts[0]]["average"]) == (80, 80.0)
    assert tiles[posts[0]]["vote_count"] == 5
    assert tiles[posts[2]]["average"] is None

    # Media complessiva: per gli altri solo con almeno 3 fit con la media.
    stats = (await client.get(f"/v1/users/{nick}", headers=voters[5])).json()["stats"]
    assert stats == {"posts": 3, "average": None, "votes": 10}
    for vh in voters[:5]:
        await client.put(f"/v1/posts/{posts[2]}/vote", json={"score": 50}, headers=vh)
    # Prima dell'aggiornamento orario non cambia nulla.
    stats = (await client.get(f"/v1/users/{nick}", headers=voters[5])).json()["stats"]
    assert stats == {"posts": 3, "average": None, "votes": 10}
    await publish()
    stats = (await client.get(f"/v1/users/{nick}", headers=voters[5])).json()["stats"]
    assert stats == {"posts": 3, "average": 70.0, "votes": 15}
    own = (await client.get(f"/v1/users/{nick}", headers=h)).json()["stats"]
    assert own == {"posts": 3, "average": 70.0, "votes": 15}

    # Numero di voti nascosto dall'autore: gli altri non lo vedono, lui sì.
    db_admin.execute("update app.profiles set hide_vote_count = true where id = %s", (uid,))
    stats = (await client.get(f"/v1/users/{nick}", headers=voters[5])).json()["stats"]
    assert stats["votes"] is None
    tile = next(t for t in (await _grid(client, nick, voters[0]))["items"] if t["id"] == posts[0])
    assert (tile["average"], tile["vote_count"]) == (80.0, None)
    assert (await client.get(f"/v1/users/{nick}", headers=h)).json()["stats"]["votes"] == 15


async def test_fit_nascosti_e_stili_18_piu(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin, business=True)
    hidden = await _post(client, db_admin, uid, h)
    adult = await _post(client, db_admin, uid, h, style="beach-party")
    visible = await _post(client, db_admin, uid, h)
    db_admin.execute("update app.posts set status = 'hidden_moderation' where id = %s", (hidden,))
    # L'autore vede tutto (con lo stato), gli altri no.
    own = {t["id"]: t["status"] for t in (await _grid(client, nick, h))["items"]}
    assert own == {hidden: "hidden_moderation", adult: "active", visible: "active"}
    _, adult_viewer, _ = await _person(client, keys, db_admin)
    assert await _ids(client, nick, adult_viewer) == [visible, adult]
    _, minor, _ = await _person(client, keys, db_admin, minor=True)
    assert await _ids(client, nick, minor) == [visible]
    assert (await client.get(f"/v1/users/{nick}", headers=minor)).json()["stats"]["posts"] == 1


# ---------- Capsule ----------


async def _capsule(client, headers, name):
    return await client.post("/v1/me/capsules", json={"name": name}, headers=headers)


async def test_capsule_crea_assegna_filtra_elimina(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin)
    a = await _post(client, db_admin, uid, h)
    b = await _post(client, db_admin, uid, h)
    r = await _capsule(client, h, "  Estate  ")
    assert r.status_code == 201
    estate = r.json()
    assert (estate["name"], estate["post_count"]) == ("Estate", 0)
    serate = (await _capsule(client, h, "Serate")).json()

    r = await client.patch(f"/v1/posts/{a}", json={"capsule_id": estate["id"]}, headers=h)
    assert (r.status_code, r.json()["capsule_id"]) == (200, estate["id"])
    listed = (await client.get("/v1/me/capsules", headers=h)).json()
    assert [(c["name"], c["post_count"]) for c in listed] == [("Estate", 1), ("Serate", 0)]
    assert await _ids(client, nick, h, capsule=estate["id"]) == [a]
    page = await _grid(client, nick, h, capsule=estate["id"])
    assert page["cover_id"] == b  # la copertina è quella del portfolio intero
    assert await _ids(client, nick, h, capsule=serate["id"]) == []

    # Togliere dalla capsula; rinominare; eliminare la capsula non tocca i fit.
    r = await client.patch(f"/v1/posts/{a}", json={"capsule_id": None}, headers=h)
    assert r.json()["capsule_id"] is None
    await client.patch(f"/v1/posts/{b}", json={"capsule_id": serate["id"]}, headers=h)
    r = await client.patch(f"/v1/me/capsules/{serate['id']}", json={"name": "Sere"}, headers=h)
    assert (r.status_code, r.json()["name"], r.json()["post_count"]) == (200, "Sere", 1)
    assert (await client.delete(f"/v1/me/capsules/{serate['id']}", headers=h)).status_code == 204
    assert await _ids(client, nick, h) == [b, a]
    left = db_admin.execute("select capsule_id from app.posts where id = %s", (b,)).fetchone()
    assert left == (None,)


async def test_capsule_nomi_e_limite(client, keys, db_admin):
    _, h, _ = await _person(client, keys, db_admin)
    assert (await _capsule(client, h, "Ufficio")).status_code == 201
    for name, code in [
        ("ufficio", "capsule.name_taken"),
        ("UFFICIO ", "capsule.name_taken"),
    ]:
        r = await _capsule(client, h, name)
        assert (r.status_code, r.json()["code"]) == (409, code)
    for name, code in [
        ("   ", "capsule.name_required"),
        ("x" * 31, "text.too_long"),
        ("ciao‮", "text.invalid_characters"),
    ]:
        r = await _capsule(client, h, name)
        assert (r.status_code, r.json()["code"]) == (422, code)
    other = (await _capsule(client, h, "Estate")).json()
    r = await client.patch(f"/v1/me/capsules/{other['id']}", json={"name": "ufficio"}, headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "capsule.name_taken")
    # Rinominare cambiando solo le maiuscole è permesso.
    r = await client.patch(f"/v1/me/capsules/{other['id']}", json={"name": "ESTATE"}, headers=h)
    assert r.status_code == 200
    for i in range(10):
        assert (await _capsule(client, h, f"C{i}")).status_code == 201
    r = await _capsule(client, h, "Tredicesima")
    assert (r.status_code, r.json()["code"]) == (409, "capsule.limit")


async def test_capsule_in_parallelo_rispettano_il_limite(client, keys, db_admin):
    _, h, _ = await _person(client, keys, db_admin)
    results = await asyncio.gather(*(_capsule(client, h, f"Cap {i}") for i in range(20)))
    assert sorted(r.status_code for r in results).count(201) == 12
    assert len((await client.get("/v1/me/capsules", headers=h)).json()) == 12


async def test_capsule_altrui(client, keys, db_admin):
    uid, h, nick = await _person(client, keys, db_admin, business=True)
    mine = (await _capsule(client, h, "Mia")).json()
    post = await _post(client, db_admin, uid, h)
    other_id, other_h, _ = await _person(client, keys, db_admin)
    their_post = await _post(client, db_admin, other_id, other_h)

    r = await client.patch(f"/v1/me/capsules/{mine['id']}", json={"name": "X"}, headers=other_h)
    assert (r.status_code, r.json()["code"]) == (404, "capsule.not_found")
    r = await client.delete(f"/v1/me/capsules/{mine['id']}", headers=other_h)
    assert r.status_code == 404
    r = await client.patch(
        f"/v1/posts/{their_post}", json={"capsule_id": mine["id"]}, headers=other_h
    )
    assert (r.status_code, r.json()["code"]) == (422, "capsule.not_found")
    other_cap = (await _capsule(client, other_h, "Sua")).json()
    r = await client.get(
        f"/v1/users/{nick}/posts", params={"capsule": other_cap["id"]}, headers=other_h
    )
    assert (r.status_code, r.json()["code"]) == (404, "capsule.not_found")

    # Gli altri vedono solo le capsule con dentro fit che possono vedere.
    empty = (await _capsule(client, h, "Vuota")).json()
    await client.patch(f"/v1/posts/{post}", json={"capsule_id": mine["id"]}, headers=h)
    seen = (await client.get(f"/v1/users/{nick}", headers=other_h)).json()["capsules"]
    assert [(c["name"], c["post_count"]) for c in seen] == [("Mia", 1)]
    own = (await client.get(f"/v1/users/{nick}", headers=h)).json()["capsules"]
    assert [c["id"] for c in own] == [mine["id"], empty["id"]]
    # Il campo capsula del post è solo per l'autore.
    assert (await client.get(f"/v1/posts/{post}", headers=other_h)).json()["capsule_id"] is None
