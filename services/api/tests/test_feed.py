"""Feed: punteggio, quota di esplorazione, sessione e cursore, filtri per chi guarda,
ripiego senza Redis."""

from __future__ import annotations

import pytest
from redis.exceptions import RedisError

from app import feed as feed_module
from app.feed import EXPLORE_EVERY, PAGE_SIZE, interleave, rank_score
from tests.conftest import ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")


# ---------- Formula e mescolanza ----------


def test_punteggio_prudente_e_freschezza():
    # Un solo 100 non batte venti voti da 90.
    assert rank_score(100, 1, 1) < rank_score(90 * 20, 20, 1)
    # A parità di voti, il più recente sta sopra.
    assert rank_score(80 * 10, 10, 2) > rank_score(80 * 10, 10, 48)
    # Senza voti si parte dalla media prudente (60).
    assert rank_score(0, 0, 0) == pytest.approx(0.6)
    # Molto vecchio: resta il 35% della qualità.
    assert rank_score(0, 0, 10_000) == pytest.approx(0.6 * 0.35)


def test_un_posto_su_cinque_ai_nuovi():
    exploit = [f"e{i}" for i in range(20)]
    explore = [f"x{i}" for i in range(4)]
    out = interleave(exploit, explore, seed=1)
    assert len(out) == 24 and len(set(out)) == 24
    for i, post in enumerate(out[:20]):
        assert post.startswith("x") == ((i + 1) % EXPLORE_EVERY == 0)
    assert interleave(exploit, explore, seed=1) == out  # ripetibile
    assert interleave([], explore, seed=1)[0].startswith("x")
    assert interleave(exploit, [], seed=1) == exploit
    # Un post sia in classifica sia tra i nuovi compare una volta sola.
    assert interleave(["a", "b"], ["a"], seed=3).count("a") == 1


# ---------- Supporto ----------


async def _person(client, keys, db_admin, **kw):
    user_id, headers, _ = await onboard(client, keys, db_admin, **kw)
    return user_id, headers


async def _join(client, headers, slug):
    r = await client.put(f"/v1/styles/{slug}/membership", headers=headers)
    assert r.status_code == 200, r.text


async def _post(client, db_admin, user_id, headers, style, *, votes=0, avg=0.0, hours=1.0):
    media = [str(ready_upload(db_admin, user_id))]
    r = await client.post("/v1/posts", json={"style": style, "media": media}, headers=headers)
    assert r.status_code == 201, r.text
    post_id = r.json()["id"]
    db_admin.execute(
        """update app.posts set published_at = now() - make_interval(secs => %s) where id = %s""",
        (hours * 3600, post_id),
    )
    db_admin.execute(
        """update app.post_stats set vote_count = %s, vote_wcount = %s, vote_wsum = %s,
                  vote_sum = %s where post_id = %s""",
        (votes, votes, votes * avg, int(votes * avg), post_id),
    )
    return post_id


async def _p(client, db_admin, s, **kw):
    """Post dell'autore principale nello stile del test."""
    return await _post(client, db_admin, s["author_id"], s["author"], s["slug"], **kw)


async def _feed(client, headers, **params):
    r = await client.get("/v1/feed", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _all_pages(client, headers, **params):
    ids, cursor, pages = [], None, 0
    while True:
        page = await _feed(client, headers, **({**params, "cursor": cursor} if cursor else params))
        ids += [p["id"] for p in page["items"]]
        pages += 1
        cursor = page["next_cursor"]
        if not cursor:
            return ids, pages


@pytest.fixture
async def scene(client, keys, db_admin, temp_style):
    """Uno stile tutto per il test, un lettore iscritto e un autore."""
    slug = temp_style("feed")
    reader_id, reader = await _person(client, keys, db_admin)
    author_id, author = await _person(client, keys, db_admin)
    other_id, other = await _person(client, keys, db_admin)
    for headers in (reader, author, other):
        await _join(client, headers, slug)
    return {
        "slug": slug,
        "reader": reader,
        "reader_id": reader_id,
        "author": author,
        "author_id": author_id,
        # Secondo autore: i limiti (20 post l'ora) valgono anche nei test.
        "authors": [(author_id, author), (other_id, other)],
    }


# ---------- Feed ----------


async def test_ordine_per_punteggio_e_filtri(client, keys, db_admin, scene):
    s = scene
    top = await _post(
        client, db_admin, s["author_id"], s["author"], s["slug"], votes=30, avg=88, hours=20
    )
    mid = await _post(
        client, db_admin, s["author_id"], s["author"], s["slug"], votes=30, avg=70, hours=20
    )
    low = await _post(
        client, db_admin, s["author_id"], s["author"], s["slug"], votes=30, avg=40, hours=20
    )
    own = await _post(client, db_admin, s["reader_id"], s["reader"], s["slug"], votes=30, avg=99)
    voted = await _p(client, db_admin, s, votes=30, avg=95)
    await client.put(f"/v1/posts/{voted}/vote", json={"score": 90}, headers=s["reader"])

    page = await _feed(client, s["reader"], style=s["slug"])
    ids = [p["id"] for p in page["items"]]
    assert ids == [top, mid, low]  # niente post propri, niente post già votati
    assert own not in ids and voted not in ids
    assert page["next_cursor"] is None
    assert page["items"][0]["style"]["slug"] == s["slug"]
    assert page["items"][0]["vote"]["ask_style_confirm"] is True


async def test_i_nuovi_hanno_il_loro_posto(client, keys, db_admin, scene):
    s = scene
    old = [
        await _post(
            client, db_admin, s["author_id"], s["author"], s["slug"], votes=40, avg=90 - i, hours=10
        )
        for i in range(8)
    ]
    fresh = await _p(client, db_admin, s, votes=0, hours=2)
    ids = [p["id"] for p in (await _feed(client, s["reader"], style=s["slug"]))["items"]]
    assert ids[EXPLORE_EVERY - 1] == fresh
    assert [i for i in ids if i != fresh] == old


async def test_pagine_senza_doppioni_anche_se_i_voti_cambiano(client, keys, db_admin, scene):
    s = scene
    posts = [
        await _post(
            client, db_admin, *s["authors"][i % 2], s["slug"], votes=20, avg=50 + i, hours=30
        )
        for i in range(25)
    ]
    first = await _feed(client, s["reader"], style=s["slug"])
    assert len(first["items"]) == PAGE_SIZE
    # Intanto l'ultimo in classifica diventa il primo: la sessione aperta non cambia.
    db_admin.execute(
        "update app.post_stats set vote_wsum = 99 * 500, vote_wcount = 500 where post_id = %s",
        (posts[0],),
    )
    seen = [p["id"] for p in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        page = await _feed(client, s["reader"], style=s["slug"], cursor=cursor)
        seen += [p["id"] for p in page["items"]]
        cursor = page["next_cursor"]
    assert len(seen) == 25 and set(seen) == set(posts)
    # Dopo il ricalcolo periodico (ogni 5 minuti) un feed nuovo lo vede in cima.
    from app.db import session_scope
    from app.feed import refresh_all

    async with session_scope() as session:
        await refresh_all(session)
    fresh = await _feed(client, s["reader"], style=s["slug"])
    assert fresh["items"][0]["id"] == posts[0]


async def test_feed_dei_propri_stili(client, keys, db_admin, scene, temp_style):
    s = scene
    other_slug = temp_style("other")
    await _join(client, s["author"], other_slug)
    mine = await _p(client, db_admin, s)
    elsewhere = await _post(client, db_admin, s["author_id"], s["author"], other_slug)
    # Il lettore segue anche old-money e jappo (onboarding): restano solo lo stile del test.
    await client.delete("/v1/styles/old-money/membership", headers=s["reader"])
    await client.delete("/v1/styles/jappo/membership", headers=s["reader"])
    ids, _ = await _all_pages(client, s["reader"])
    assert mine in ids and elsewhere not in ids


async def test_post_spariti_tra_una_pagina_e_l_altra(client, keys, db_admin, scene):
    s = scene
    posts = [await _p(client, db_admin, s, votes=10, avg=90 - i) for i in range(12)]
    first = await _feed(client, s["reader"], style=s["slug"])
    last_two = posts[-2:]
    await client.delete(f"/v1/posts/{last_two[0]}", headers=s["author"])
    db_admin.execute(
        "insert into app.blocks (blocker_id, blocked_id) values (%s, %s)",
        (s["reader_id"], s["author_id"]),
    )
    second = await _feed(client, s["reader"], style=s["slug"], cursor=first["next_cursor"])
    assert second["items"] == []  # cancellato e bloccato: non arrivano


async def test_minorenni_e_stili_18_piu(client, keys, db_admin):
    _, minor = await _person(client, keys, db_admin, minor=True)
    r = await client.get("/v1/feed", params={"style": "beach-party"}, headers=minor)
    assert (r.status_code, r.json()["code"]) == (404, "style.not_found")


async def test_post_appena_pubblicato_entra_subito(client, keys, db_admin, scene):
    s = scene
    await _p(client, db_admin, s, votes=5, avg=70)
    await _feed(client, s["reader"], style=s["slug"])  # classifiche costruite in Redis
    new = await _p(client, db_admin, s)
    ids, _ = await _all_pages(client, s["reader"], style=s["slug"])
    assert new in ids


async def test_feed_vuoto_con_il_motivo(client, keys, db_admin, scene):
    s = scene
    page = await _feed(client, s["reader"], style=s["slug"])
    assert (page["items"], page["empty_reason"]) == ([], "no_posts")
    db_admin.execute("delete from app.style_memberships where user_id = %s", (s["reader_id"],))
    page = await _feed(client, s["reader"])
    assert page["empty_reason"] == "no_styles"


# ---------- Cursore ----------


async def test_cursori_manomessi_altrui_o_scaduti(client, keys, db_admin, scene):
    from app.redis_client import get_redis

    s = scene
    for i in range(12):
        await _p(client, db_admin, s, votes=3, avg=60 + i)
    cursor = (await _feed(client, s["reader"], style=s["slug"]))["next_cursor"]
    body, mac = cursor.split(".")
    for bad in (f"{body}.AAAA{mac[4:]}", f"x{body}.{mac}", "rotto", body):
        r = await client.get(
            "/v1/feed", params={"style": s["slug"], "cursor": bad}, headers=s["reader"]
        )
        assert (r.status_code, r.json()["code"]) == (400, "feed.invalid_cursor")
    # Il cursore di un altro non vale.
    r = await client.get(
        "/v1/feed", params={"style": s["slug"], "cursor": cursor}, headers=s["author"]
    )
    assert r.json()["code"] == "feed.invalid_cursor"
    # Stesso cursore con un altro stile: no.
    r = await client.get("/v1/feed", params={"cursor": cursor}, headers=s["reader"])
    assert r.json()["code"] == "feed.invalid_cursor"
    # Sessione scaduta.
    redis = get_redis()
    for key in await redis.keys(f"feed:sess:{s['reader_id']}:*"):
        await redis.delete(key)
    r = await client.get(
        "/v1/feed", params={"style": s["slug"], "cursor": cursor}, headers=s["reader"]
    )
    assert (r.status_code, r.json()["code"]) == (410, "feed.cursor_expired")


# ---------- Senza Redis ----------


class BrokenRedis:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise RedisError("giù")

        return fail


async def test_senza_redis_il_feed_funziona_uguale(client, keys, db_admin, scene, monkeypatch):
    s = scene
    posts = [
        await _post(
            client, db_admin, *s["authors"][i % 2], s["slug"], votes=20, avg=40 + i, hours=30
        )
        for i in range(23)
    ]
    with_redis, _ = await _all_pages(client, s["reader"], style=s["slug"])
    monkeypatch.setattr(feed_module, "get_redis", lambda: BrokenRedis())
    without, pages = await _all_pages(client, s["reader"], style=s["slug"])
    assert pages == 3
    assert len(without) == 23 and set(without) == set(posts)
    # Stessa classifica (i posti dei nuovi sono gli stessi: nessun post è "nuovo" qui).
    assert without == with_redis


async def test_ricalcolo_periodico(client, keys, db_admin, scene):
    from app.db import session_scope
    from app.feed import refresh_all

    s = scene
    post_id = await _post(
        client, db_admin, s["author_id"], s["author"], s["slug"], votes=10, avg=80, hours=5
    )
    async with session_scope() as session:
        assert await refresh_all(session) >= 1
    hot = db_admin.execute("select hot_score from app.post_stats where post_id = %s", (post_id,))
    expected = rank_score(800, 10, 5)
    assert hot.fetchone()[0] == pytest.approx(expected, rel=1e-3)
