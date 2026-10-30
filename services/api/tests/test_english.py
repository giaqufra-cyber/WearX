"""L'app in inglese, lato server (seduta 34): stili, errori, notifiche, push, moderazione, link."""

from __future__ import annotations

import pytest

from tests.test_admin_console import _staff as _staff_role
from tests.test_notifications import _inbox, _person, _post, _register, _send, _staff

pytestmark = pytest.mark.usefixtures("store")

EN = {"Accept-Language": "en"}


@pytest.fixture
def unique_slug():
    import uuid

    return f"test-{uuid.uuid4().hex[:8]}"


def _en(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, **EN}


async def test_stili_in_inglese(client, keys, db_admin):
    _, me, _ = await _person(client, keys, db_admin)
    items = {
        s["slug"]: s for s in (await client.get("/v1/styles", headers=_en(me))).json()["items"]
    }
    assert (items["gala"]["name"], items["gala"]["tagline"]) == (
        "Gala",
        "Black tie, long gowns, tuxedos",
    )
    # Nome uguale nelle due lingue: resta com'è, cambia solo la descrizione.
    assert items["old-money"]["name"] == "Old Money"
    assert items["old-money"]["tagline"] == "Quiet luxury, cashmere, loafers"
    it = {s["slug"]: s for s in (await client.get("/v1/styles", headers=me)).json()["items"]}
    assert (it["gala"]["name"], it["gioielli"]["name"]) == ("Galà", "Gioielli")

    card = (await client.get("/v1/styles/gioielli", headers=_en(me))).json()
    assert card["name"] == "Jewellery"
    config = (await client.get("/v1/config", params={"lang": "en"})).json()
    assert {s["slug"]: s["name"] for s in config["styles"]}["calcio"] == "Football"
    r = await client.get("/v1/config", headers=EN)
    assert r.headers["vary"] == "Accept-Language"

    # Si cerca in tutte e due le lingue, qualunque sia quella dell'app.
    async def found(q, headers):
        r = await client.get("/v1/styles", params={"q": q}, headers=headers)
        return [s["slug"] for s in r.json()["items"]]

    assert (await found("jewellery", me))[0] == "gioielli"
    assert (await found("gioielli", _en(me)))[0] == "gioielli"
    assert (await found("wedding", me))[0] == "matrimonio"


async def test_nome_dello_stile_sui_fit(client, keys, db_admin):
    author_id, author, nick = await _person(client, keys, db_admin)
    db_admin.execute(
        "update app.profiles set account_type = 'business' where id = %s", (author_id,)
    )
    post = await _post(client, db_admin, author_id, author)
    db_admin.execute(
        "update app.posts set style_id = (select id from app.styles where slug = 'gala') "
        "where id = %s",
        (post,),
    )
    r = await client.get(f"/v1/posts/{post}", headers=_en(author))
    assert r.json()["style"]["name"] == "Gala"
    r = await client.get(f"/v1/users/{nick}/posts", headers=_en(author))
    assert r.json()["items"][0]["style"]["name"] == "Gala"
    r = await client.get(f"/v1/posts/{post}", headers=author)
    assert r.json()["style"]["name"] == "Galà"


async def test_errori_tradotti_anche_con_i_valori(client, keys, db_admin):
    _, me, _ = await _person(client, keys, db_admin)
    r = await client.patch("/v1/me", json={"bio": "x" * 400}, headers=_en(me))
    assert r.status_code == 422
    assert r.json()["title"] == "The bio can be at most 150 characters"
    r = await client.patch("/v1/me", json={"bio": "x" * 400}, headers=me)
    assert r.json()["title"] == "La bio può avere al massimo 150 caratteri"
    # Il codice non cambia mai: l'app decide da quello.
    assert r.json()["code"] == "text.too_long"


async def test_notifiche_e_push_nella_lingua_di_ognuno(client, keys, db_admin):
    _, owner, owner_nick = await _person(client, keys, db_admin)
    _, fan, fan_nick = await _person(client, keys, db_admin)
    # Due telefoni dello stesso account: uno in inglese, uno in italiano.
    english = await _register(client, _en(owner))
    italian = await _register(client, owner)

    await client.post(f"/v1/users/{owner_nick}/follow", headers=fan)
    [item] = (await _inbox(client, _en(owner)))["items"]
    assert (item["title"], item["body"]) == (
        f"@{fan_nick} wants to follow you",
        "Accept to let them see your portfolio.",
    )
    [item] = (await _inbox(client, owner))["items"]
    assert item["title"] == f"@{fan_nick} vuole seguirti"

    sender = await _send()
    pushes = {m["to"]: m for m in sender.sent if m["to"] in (english, italian)}
    assert (pushes[english]["title"], pushes[english]["body"]) == (
        "New request",
        f"@{fan_nick} wants to follow you",
    )
    assert pushes[italian]["title"] == "Nuova richiesta"

    # Cambiata la lingua dell'app, il telefono si registra di nuovo: i push seguono.
    await _register(client, owner, token=english)
    lang = db_admin.execute(
        "select language from app.push_tokens where token = %s", (english,)
    ).fetchone()
    assert lang == ("it",)


async def test_moderazione_in_inglese(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author, caption="Teatro")
    token = await _register(client, _en(author))
    staff = await _staff(client, keys, db_admin)
    r = await client.post(
        "/v1/admin/reports/decide",
        json={
            "target_type": "post",
            "target_id": post,
            "decision": "hide",
            "sanction": "none",
            "ground": "nudity",
        },
        headers=staff,
    )
    assert r.status_code == 200, r.text

    [notice] = (await client.get("/v1/me/moderation", headers=_en(author))).json()
    assert notice["reason"] == "nudity or sexual content"
    assert notice["statement"].startswith(
        "Your fit “Teatro” has been hidden: others no longer see it in the feed"
    )
    assert "Reason: nudity or sexual content. Decision by a moderator." in notice["statement"]
    [notice_it] = (await client.get("/v1/me/moderation", headers=author)).json()
    assert notice_it["statement"].startswith("Il tuo fit «Teatro» è stato nascosto")
    # Lo staff legge sempre il testo di riferimento, in italiano.
    stored = db_admin.execute(
        "select statement, statement_en from app.moderation_actions where target_id = %s",
        (post,),
    ).fetchone()
    assert stored[0].startswith("Il tuo fit") and stored[1].startswith("Your fit")

    [item] = (await _inbox(client, _en(author)))["items"]
    assert item["title"] == "One of your fits has been hidden"
    sender = await _send()
    [push] = [m for m in sender.sent if m["to"] == token]
    assert (push["title"], push["body"]) == ("WearX", "You have a new moderation notice")


async def test_decisioni_vecchie_solo_in_italiano(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    db_admin.execute(
        """insert into app.moderation_actions
             (target_type, target_id, action, ground, automated, subject_id, statement)
           values ('post', %s, 'warn', 'spam', false, %s, 'Avviso di prima.')""",
        (post, author_id),
    )
    [notice] = (await client.get("/v1/me/moderation", headers=_en(author))).json()
    assert (notice["reason"], notice["statement"]) == ("spam", "Avviso di prima.")


async def test_campi_inglesi_dallo_staff(client, keys, db_admin, unique_slug):
    _, admin, _ = await _staff_role(client, keys, db_admin, role="admin")
    body = {"slug": unique_slug, "name": "Montagna", "tagline": "Lana e scarponi"}
    r = await client.post("/v1/admin/styles", json=body, headers=admin)
    assert (r.json()["name_en"], r.json()["tagline_en"]) == (None, None)
    r = await client.patch(
        f"/v1/admin/styles/{unique_slug}",
        json={"name_en": " Mountain ", "tagline_en": "Wool and boots"},
        headers=admin,
    )
    assert (r.json()["name_en"], r.json()["tagline_en"]) == ("Mountain", "Wool and boots")
    _, me, _ = await _person(client, keys, db_admin)
    card = (await client.get(f"/v1/styles/{unique_slug}", headers=_en(me))).json()
    assert (card["name"], card["tagline"]) == ("Mountain", "Wool and boots")
    # Vuoto = si torna al testo italiano.
    r = await client.patch(f"/v1/admin/styles/{unique_slug}", json={"name_en": ""}, headers=admin)
    assert r.json()["name_en"] is None
    card = (await client.get(f"/v1/styles/{unique_slug}", headers=_en(me))).json()
    assert card["name"] == "Montagna"
    db_admin.execute("delete from app.styles where slug = %s", (unique_slug,))


async def test_pagina_del_link_in_inglese(client):
    r = await client.get("/r/rotto", headers={"Accept-Language": "en-GB,en;q=0.9"})
    assert r.status_code == 404
    assert '<html lang="en">' in r.text and "Invalid link" in r.text
    r = await client.get("/r/rotto")
    assert "Link non valido" in r.text
