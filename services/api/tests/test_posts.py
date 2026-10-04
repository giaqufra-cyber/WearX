"""Post: pubblicazione, lettura, modifica, eliminazione e suite di autorizzazione (IDOR)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.links import normalize_shop_url
from app.ranking import key_between, key_now
from tests.conftest import create_auth_user, ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")

ITEM = {
    "brand": "Loro Piana",
    "name": "Maglione in cachemire",
    "price_cents": 89000,
    "url": "https://WWW.LoroPiana.com/it/uomo?ref=wearx#top",
    "media_position": 0,
    "pin_x": 0.42,
    "pin_y": 0.31,
}


def _body(media, **extra):
    body = {"style": "old-money", "caption": "Domenica in centro", "media": [str(m) for m in media]}
    body.update(extra)
    return body


async def _person(client, keys, db_admin, **kw):
    user_id, headers, _ = await onboard(client, keys, db_admin, **kw)
    return user_id, headers


async def _post(client, db_admin, user_id, headers, n=2, **extra):
    media = [ready_upload(db_admin, user_id) for _ in range(n)]
    r = await client.post("/v1/posts", json=_body(media, **extra), headers=headers)
    assert r.status_code == 201, r.text
    return r.json(), media


# ---------- Pubblicazione ----------


async def test_pubblicazione_completa(client, keys, db_admin):
    user_id, headers = await _person(client, keys, db_admin)
    post, media = await _post(
        client, db_admin, user_id, headers, items=[ITEM, {"brand": "Tod's", "name": "Mocassini"}]
    )
    assert post["status"] == "active"
    assert post["is_own"] is True
    assert post["author"]["nickname"]
    assert post["style"]["slug"] == "old-money"
    assert post["restyle_available"] is True
    assert [m["position"] for m in post["media"]] == [0, 1]
    assert set(post["media"][0]["urls"]["variants"]) == {"320", "640", "1080"}
    first = post["items"][0]
    assert (first["brand"], first["price_cents"], first["currency"]) == ("Loro Piana", 89000, "EUR")
    assert first["link"]["domain"] == "loropiana.com"
    assert first["link"]["status"] == "pending"
    assert first["link"]["url"] == "https://www.loropiana.com/it/uomo?ref=wearx"
    assert (first["pin_x"], first["pin_y"]) == (0.42, 0.31)
    assert post["items"][1]["link"] is None
    attached = db_admin.execute(
        "select count(*) from app.media_uploads where id = any(%s) and attached_at is not null",
        (media,),
    ).fetchone()
    assert attached == (2,)
    stats = db_admin.execute(
        "select count(*) from app.post_stats where post_id = %s", (post["id"],)
    )
    assert stats.fetchone() == (1,)


async def test_didascalia_ripulita_e_limitata(client, keys, db_admin):
    user_id, headers = await _person(client, keys, db_admin)
    post, _ = await _post(client, db_admin, user_id, headers, caption="  ciao  ")
    assert post["caption"] == "ciao"
    for caption, code in [
        ("x" * 141, "text.too_long"),
        ("a\nb\nc\nd", "text.too_many_lines"),
        ("ciao‮", "text.invalid_characters"),
    ]:
        media = [ready_upload(db_admin, user_id)]
        r = await client.post("/v1/posts", json=_body(media, caption=caption), headers=headers)
        assert (r.status_code, r.json()["code"]) == (422, code)


async def _assert_nothing_created(db_admin, user_id, media):
    posts = db_admin.execute("select count(*) from app.posts where author_id = %s", (user_id,))
    assert posts.fetchone() == (0,)
    free = db_admin.execute(
        "select count(*) from app.media_uploads where id = any(%s) and attached_at is null",
        ([m for m in media if m],),
    ).fetchone()
    assert free == (len([m for m in media if m]),)


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"items": [{**ITEM, "url": "http://negozio.it"}]}, "link.invalid"),
        ({"items": [{**ITEM, "media_position": 5}]}, "item.bad_media_position"),
        ({"items": [{**ITEM, "brand": "   "}]}, "item.incomplete"),
        ({"items": [{**ITEM, "brand": "B" * 61}]}, "text.too_long"),
        ({"style": "non-esiste"}, "style.not_found"),
    ],
)
async def test_errori_non_lasciano_traccia(client, keys, db_admin, extra, code):
    user_id, headers = await _person(client, keys, db_admin)
    media = [ready_upload(db_admin, user_id)]
    r = await client.post("/v1/posts", json=_body(media, **extra), headers=headers)
    assert (r.status_code, r.json()["code"]) == (422, code)
    await _assert_nothing_created(db_admin, user_id, media)


@pytest.mark.parametrize(
    "extra",
    [
        {"items": [{**ITEM, "media_position": None}]},  # punto senza foto
        {"items": [{**ITEM, "pin_y": None}]},  # x senza y
        {"items": [ITEM] * 9},  # troppi capi
        {"items": [{**ITEM, "price_cents": -1}]},
        {"items": [{**ITEM, "currency": "BTC"}]},
    ],
)
async def test_richieste_malformate(client, keys, db_admin, extra):
    user_id, headers = await _person(client, keys, db_admin)
    media = [ready_upload(db_admin, user_id)]
    r = await client.post("/v1/posts", json=_body(media, **extra), headers=headers)
    assert (r.status_code, r.json()["code"]) == (422, "request.invalid")


async def test_foto_non_utilizzabili(client, keys, db_admin):
    user_id, headers = await _person(client, keys, db_admin)
    other_id, _ = await _person(client, keys, db_admin)
    mine = ready_upload(db_admin, user_id)
    others = ready_upload(db_admin, other_id)
    processing = ready_upload(db_admin, user_id)
    db_admin.execute(
        "update app.media_uploads set status = 'processing', width = null, height = null, "
        "blurhash = null, sha256 = null, variants = null where id = %s",
        (processing,),
    )
    for media in ([mine, others], [processing], [uuid.uuid4()]):
        r = await client.post("/v1/posts", json=_body(media), headers=headers)
        assert (r.status_code, r.json()["code"]) == (422, "media.unavailable")
    # La foto buona non è rimasta "prenotata" dal tentativo fallito.
    await _assert_nothing_created(db_admin, user_id, [mine])

    r = await client.post("/v1/posts", json=_body([mine, mine]), headers=headers)
    assert r.json()["code"] == "media.duplicate"
    r = await client.post("/v1/posts", json=_body([]), headers=headers)
    assert r.json()["code"] == "request.invalid"
    r = await client.post("/v1/posts", json=_body([mine] * 11), headers=headers)
    assert r.json()["code"] == "request.invalid"


async def test_una_foto_in_un_solo_post_anche_in_parallelo(client, keys, db_admin):
    user_id, headers = await _person(client, keys, db_admin)
    media = [ready_upload(db_admin, user_id)]
    results = await asyncio.gather(
        *[client.post("/v1/posts", json=_body(media), headers=headers) for _ in range(3)]
    )
    assert sorted(r.status_code for r in results) == [201, 422, 422]


async def test_stessa_richiesta_ripetuta_un_solo_post(client, keys, db_admin):
    user_id, headers = await _person(client, keys, db_admin)
    media = [ready_upload(db_admin, user_id)]
    idem = {**headers, "Idempotency-Key": f"k-{uuid.uuid4().hex}"}
    first = await client.post("/v1/posts", json=_body(media), headers=idem)
    again = await client.post("/v1/posts", json=_body(media), headers=idem)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    count = db_admin.execute("select count(*) from app.posts where author_id = %s", (user_id,))
    assert count.fetchone() == (1,)
    bad = await client.post(
        "/v1/posts", json=_body(media), headers={**headers, "Idempotency-Key": "x"}
    )
    assert bad.status_code == 422


async def test_stile_18_piu_non_disponibile_ai_minorenni(client, keys, db_admin):
    user_id, headers = await _person(client, keys, db_admin, minor=True)
    media = [ready_upload(db_admin, user_id)]
    r = await client.post("/v1/posts", json=_body(media, style="beach-party"), headers=headers)
    assert r.json()["code"] == "style.not_found"


async def test_lo_stesso_negozio_e_un_solo_link(client, keys, db_admin):
    user_id, headers = await _person(client, keys, db_admin)
    url = f"https://shop-{uuid.uuid4().hex[:6]}.example.com/p/1"
    for _ in range(2):
        await _post(client, db_admin, user_id, headers, n=1, items=[{**ITEM, "url": url}])
    count = db_admin.execute("select count(*) from app.links where url = %s", (url,)).fetchone()
    assert count == (1,)


# ---------- Lettura e visibilità ----------


async def test_altri_vedono_il_post_ma_l_autore_privato_e_anonimo(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    viewer_id, viewer = await _person(client, keys, db_admin)
    post, _ = await _post(client, db_admin, author_id, author, items=[ITEM])
    seen = (await client.get(f"/v1/posts/{post['id']}", headers=viewer)).json()
    assert seen["is_own"] is False
    assert seen["author"] is None
    assert seen["restyle_available"] is None
    assert seen["items"][0]["price_cents"] == 89000

    db_admin.execute(
        "insert into app.follows (follower_id, followee_id, status) values (%s, %s, 'accepted')",
        (viewer_id, author_id),
    )
    seen = (await client.get(f"/v1/posts/{post['id']}", headers=viewer)).json()
    assert seen["author"]["nickname"] == post["author"]["nickname"]


async def test_business_sempre_con_autore_e_prezzi_nascosti(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, viewer = await _person(client, keys, db_admin)
    db_admin.execute(
        "update app.profiles set account_type = 'business', hide_prices = true where id = %s",
        (author_id,),
    )
    post, _ = await _post(client, db_admin, author_id, author, items=[ITEM])
    seen = (await client.get(f"/v1/posts/{post['id']}", headers=viewer)).json()
    assert seen["author"]["account_type"] == "business"
    assert seen["items"][0]["price_cents"] is None
    own = (await client.get(f"/v1/posts/{post['id']}", headers=author)).json()
    assert own["items"][0]["price_cents"] == 89000


async def test_link_bloccato_senza_indirizzo(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    url = f"https://phish-{uuid.uuid4().hex[:6]}.example.com/"
    post, _ = await _post(client, db_admin, author_id, author, items=[{**ITEM, "url": url}])
    db_admin.execute("update app.links set status = 'blocked' where url = %s", (url,))
    seen = (await client.get(f"/v1/posts/{post['id']}", headers=author)).json()
    assert seen["items"][0]["link"]["status"] == "blocked"
    assert seen["items"][0]["link"]["url"] is None


# ---------- Modifica ----------


async def test_modifica_didascalia_e_capi(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post, _ = await _post(client, db_admin, author_id, author, items=[ITEM])
    r = await client.patch(
        f"/v1/posts/{post['id']}",
        json={"caption": "Nuova", "items": [{"brand": "Barbour", "name": "Giacca cerata"}]},
        headers=author,
    )
    assert r.status_code == 200, r.text
    assert r.json()["caption"] == "Nuova"
    assert [i["brand"] for i in r.json()["items"]] == ["Barbour"]
    # Didascalia tolta con null; capi lasciati come sono se non inviati.
    r = await client.patch(f"/v1/posts/{post['id']}", json={"caption": None}, headers=author)
    assert r.json()["caption"] is None
    assert [i["brand"] for i in r.json()["items"]] == ["Barbour"]


async def test_cambio_di_stile_una_volta_sola(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post, _ = await _post(client, db_admin, author_id, author)
    r = await client.patch(f"/v1/posts/{post['id']}", json={"style": "gala"}, headers=author)
    assert (r.json()["style"]["slug"], r.json()["restyle_available"]) == ("gala", False)
    r = await client.patch(f"/v1/posts/{post['id']}", json={"style": "jappo"}, headers=author)
    assert (r.status_code, r.json()["code"]) == (409, "post.restyle_used")


async def test_minorenne_non_sposta_un_post_in_uno_stile_18_piu(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin, minor=True)
    post, _ = await _post(client, db_admin, author_id, author)
    r = await client.patch(f"/v1/posts/{post['id']}", json={"style": "beach-party"}, headers=author)
    assert r.json()["code"] == "style.not_found"
    again = (await client.get(f"/v1/posts/{post['id']}", headers=author)).json()
    assert again["restyle_available"] is True  # tentativo fallito: cambio ancora disponibile


# ---------- Eliminazione ----------


async def test_eliminazione(client, keys, db_admin, store):
    from app.media.keys import variant_key

    author_id, author = await _person(client, keys, db_admin)
    post, media = await _post(client, db_admin, author_id, author, n=1, items=[ITEM])
    for w in (320, 640, 1080):
        await store.put(variant_key(media[0], w), b"webp", "image/webp")

    assert (await client.delete(f"/v1/posts/{post['id']}", headers=author)).status_code == 204
    assert (await client.get(f"/v1/posts/{post['id']}", headers=author)).status_code == 404
    assert (await client.delete(f"/v1/posts/{post['id']}", headers=author)).status_code == 404
    for w in (320, 640, 1080):
        assert await store.size(variant_key(media[0], w)) is None
    rows = db_admin.execute(
        "select (select count(*) from app.post_media where post_id = %(p)s),"
        " (select count(*) from app.post_items where post_id = %(p)s),"
        " (select count(*) from app.media_uploads where id = %(m)s),"
        " (select caption from app.posts where id = %(p)s)",
        {"p": post["id"], "m": media[0]},
    ).fetchone()
    assert rows == (0, 0, 0, None)


# ---------- Autorizzazione (IDOR) ----------


async def _hidden_post_cases(client, keys, db_admin):
    """Post che un estraneo NON deve poter vedere, ciascuno per un motivo diverso."""
    cases = {}
    a_id, a = await _person(client, keys, db_admin)
    cases["eliminato"], _ = await _post(client, db_admin, a_id, a, n=1)
    await client.delete(f"/v1/posts/{cases['eliminato']['id']}", headers=a)

    b_id, b = await _person(client, keys, db_admin)
    cases["moderato"], _ = await _post(client, db_admin, b_id, b, n=1)
    db_admin.execute(
        "update app.posts set status = 'hidden_moderation' where id = %s",
        (cases["moderato"]["id"],),
    )
    c_id, c = await _person(client, keys, db_admin)
    cases["autore_sospeso"], _ = await _post(client, db_admin, c_id, c, n=1)
    db_admin.execute("update app.profiles set status = 'suspended' where id = %s", (c_id,))

    d_id, d = await _person(client, keys, db_admin)
    cases["stile_18_piu"], _ = await _post(client, db_admin, d_id, d, n=1, style="beach-party")
    return cases


async def test_suite_idor(client, keys, db_admin):
    """Un estraneo non legge, non modifica e non elimina ciò che non deve: sempre 404 uguale
    a un post inesistente, così non si scopre nemmeno che il post esiste."""
    cases = await _hidden_post_cases(client, keys, db_admin)
    _, minor = await _person(client, keys, db_admin, minor=True)
    cases["inesistente"] = {"id": str(uuid.uuid4())}
    for name, post in cases.items():
        for method, payload in (("GET", None), ("PATCH", {"caption": "pwned"}), ("DELETE", None)):
            r = await client.request(method, f"/v1/posts/{post['id']}", json=payload, headers=minor)
            assert (r.status_code, r.json()["code"]) == (404, "post.not_found"), (name, method)


async def test_blocco_nascondono_in_entrambe_le_direzioni(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    viewer_id, viewer = await _person(client, keys, db_admin)
    post, _ = await _post(client, db_admin, author_id, author)
    for blocker, blocked in ((author_id, viewer_id), (viewer_id, author_id)):
        db_admin.execute(
            "insert into app.blocks (blocker_id, blocked_id) values (%s, %s)", (blocker, blocked)
        )
        r = await client.get(f"/v1/posts/{post['id']}", headers=viewer)
        assert r.status_code == 404
        db_admin.execute("delete from app.blocks where blocker_id = %s", (blocker,))


async def test_post_visibile_ma_non_tuo_non_si_tocca(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, other = await _person(client, keys, db_admin)
    post, _ = await _post(client, db_admin, author_id, author, items=[ITEM])
    for method, payload in (("PATCH", {"caption": "pwned", "style": "gala"}), ("DELETE", None)):
        r = await client.request(method, f"/v1/posts/{post['id']}", json=payload, headers=other)
        assert (r.status_code, r.json()["code"]) == (403, "post.not_owner")
    still = (await client.get(f"/v1/posts/{post['id']}", headers=author)).json()
    assert (still["caption"], still["style"]["slug"]) == ("Domenica in centro", "old-money")


async def test_l_autore_vede_i_propri_post_nascosti(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post, _ = await _post(client, db_admin, author_id, author)
    db_admin.execute(
        "update app.posts set status = 'hidden_moderation' where id = %s", (post["id"],)
    )
    seen = await client.get(f"/v1/posts/{post['id']}", headers=author)
    assert seen.json()["status"] == "hidden_moderation"


async def test_serve_un_profilo(client, keys, db_admin):
    from tests.authkit import bearer

    user_id = create_auth_user(db_admin)
    r = await client.post(
        "/v1/posts", json=_body([uuid.uuid4()]), headers=bearer(keys.token(user_id))
    )
    assert r.json()["code"] == "onboarding.required"


# ---------- Link e chiavi d'ordine ----------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://WWW.Zara.com/it/", ("https://www.zara.com/it/", "zara.com")),
        ("https://shop.example.com", ("https://shop.example.com/", "shop.example.com")),
        (
            "https://negozio.example.com:443/a?b=1#x",
            ("https://negozio.example.com/a?b=1", "negozio.example.com"),
        ),
        (
            "https://bücher.example/libro",
            ("https://xn--bcher-kva.example/libro", "xn--bcher-kva.example"),
        ),
    ],
)
def test_link_normalizzati(raw, expected):
    assert normalize_shop_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "http://zara.com",
        "javascript:alert(1)",
        "https://user:pw@zara.com",
        "https://zara.com@evil.example",
        "https://192.168.1.1/admin",
        "https://[::1]/",
        "https://localhost/",
        "https://router.local/",
        "https://intranet/",
        "https://zara.com:8443/",
        "https://zara .com",
        "https://" + "a" * 2050 + ".com",
        "",
    ],
)
def test_link_rifiutati(raw):
    from app.errors import ApiError

    with pytest.raises(ApiError):
        normalize_shop_url(raw)


def test_chiavi_d_ordine():
    assert key_now(1000) < key_now(1001) < key_now(10**12)
    assert len(key_now()) == 10
    keys = [key_now(1000), key_now(5000)]
    import random

    rng = random.Random(7)  # noqa: S311 - sequenza ripetibile, nessun uso crittografico
    for _ in range(300):
        i = rng.randrange(len(keys) + 1)
        low = keys[i - 1] if i > 0 else None
        high = keys[i] if i < len(keys) else None
        new = key_between(low, high)
        assert (low is None or low < new) and (high is None or new < high)
        assert not new.endswith("0")
        keys.insert(i, new)
    assert keys == sorted(keys)
    assert max(len(k) for k in keys) < 30
    with pytest.raises(ValueError):
        key_between("b", "a")
    with pytest.raises(ValueError):
        key_between("a0", None)


async def test_la_pagina_stile_conta_i_fit_della_settimana(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    before = (await client.get("/v1/styles/jappo", headers=author)).json()["posts_last_7_days"]
    post, _ = await _post(client, db_admin, author_id, author, n=1, style="jappo")
    after = (await client.get("/v1/styles/jappo", headers=author)).json()["posts_last_7_days"]
    assert after == before + 1
    await client.delete(f"/v1/posts/{post['id']}", headers=author)
    gone = (await client.get("/v1/styles/jappo", headers=author)).json()["posts_last_7_days"]
    assert gone == before
