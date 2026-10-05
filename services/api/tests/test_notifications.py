"""Notifiche, push ed eventi (seduta 18)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.db import session_scope
from app.notifications import quiet_until
from app.push import ExpoSender, LogSender, check_receipts, send_pending, vote_milestones
from tests.authkit import bearer
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


async def _post(client, db_admin, user_id, headers, caption="Serata"):
    media = [str(ready_upload(db_admin, user_id))]
    r = await client.post(
        "/v1/posts",
        json={"style": "old-money", "media": media, "caption": caption},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _inbox(client, headers):
    r = await client.get("/v1/notifications", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _token(n: int | None = None) -> str:
    return f"ExponentPushToken[{uuid.uuid4().hex[:22] if n is None else f'tok{n:019d}'}]"


async def _register(client, headers, token=None, platform="ios"):
    token = token or _token()
    r = await client.put(
        "/v1/me/push-tokens", json={"token": token, "platform": platform}, headers=headers
    )
    assert r.status_code == 204, r.text
    return token


async def _send(sender=None):
    sender = sender or LogSender()
    async with session_scope() as session:
        await send_pending(session, sender)
    return sender


# ---------- Follow ----------


async def test_richiesta_accettata_e_notifiche_di_follow(client, keys, db_admin):
    owner_id, owner, owner_nick = await _person(client, keys, db_admin)
    fan_id, fan, fan_nick = await _person(client, keys, db_admin)

    await client.post(f"/v1/users/{owner_nick}/follow", headers=fan)
    inbox = await _inbox(client, owner)
    assert inbox["unread"] == 1
    [item] = inbox["items"]
    assert (item["type"], item["title"], item["read"]) == (
        "follow_request",
        f"@{fan_nick} vuole seguirti",
        False,
    )
    assert item["actor"] == {"nickname": fan_nick, "account_type": "private", "can_open": True}
    assert item["url"] == "/notifications"

    r = await client.post(
        "/v1/me/follow-requests", json={"nickname": fan_nick, "decision": "accept"}, headers=owner
    )
    assert r.status_code == 204
    [item] = (await _inbox(client, owner))["items"]
    assert (item["type"], item["title"]) == ("new_follower", f"@{fan_nick} ha iniziato a seguirti")
    [accepted] = (await _inbox(client, fan))["items"]
    assert accepted["title"] == f"@{owner_nick} ha accettato la tua richiesta"
    assert accepted["url"] == f"/user/{owner_nick}"

    # Letto tutto.
    r = await client.post("/v1/notifications/read", json={"all": True}, headers=owner)
    assert r.status_code == 204
    assert (await client.get("/v1/notifications/unread", headers=owner)).json() == {"unread": 0}
    # Mai le notifiche di altri.
    r = await client.post("/v1/notifications/read", json={"ids": [accepted["id"]]}, headers=owner)
    assert (await client.get("/v1/notifications/unread", headers=fan)).json() == {"unread": 1}
    for bad in ({}, {"ids": [], "all": True}, {"all": False}):
        r = await client.post("/v1/notifications/read", json=bad, headers=owner)
        assert r.status_code == 422
    assert owner_id != fan_id


async def test_richiesta_ritirata_o_rifiutata_sparisce(client, keys, db_admin):
    _, owner, owner_nick = await _person(client, keys, db_admin)
    _, fan, fan_nick = await _person(client, keys, db_admin)
    await client.post(f"/v1/users/{owner_nick}/follow", headers=fan)
    await client.delete(f"/v1/users/{owner_nick}/follow", headers=fan)
    assert (await _inbox(client, owner))["items"] == []

    await client.post(f"/v1/users/{owner_nick}/follow", headers=fan)
    await client.post(
        "/v1/me/follow-requests", json={"nickname": fan_nick, "decision": "reject"}, headers=owner
    )
    assert (await _inbox(client, owner))["items"] == []
    assert (await _inbox(client, fan))["items"] == []


async def test_business_e_follow_ripetuti_un_solo_push(client, keys, db_admin):
    brand_id, brand, brand_nick = await _person(client, keys, db_admin, business=True)
    _, fan, fan_nick = await _person(client, keys, db_admin)
    token = await _register(client, brand)

    await client.post(f"/v1/users/{brand_nick}/follow", headers=fan)
    sender = await _send()
    mine = [m for m in sender.sent if m["to"] == token]
    assert len(mine) == 1
    assert mine[0]["title"] == "Nuovo follower"
    assert mine[0]["body"] == f"@{fan_nick} ha iniziato a seguirti"
    assert mine[0]["data"] == {"url": f"/user/{fan_nick}"}
    assert mine[0]["badge"] == 1

    # Segui, smetti, segui di nuovo: una sola riga e nessun altro push entro 24 ore.
    for _ in range(3):
        await client.delete(f"/v1/users/{brand_nick}/follow", headers=fan)
        await client.post(f"/v1/users/{brand_nick}/follow", headers=fan)
    sender = await _send()
    assert [m for m in sender.sent if m["to"] == token] == []
    assert len((await _inbox(client, brand))["items"]) == 1
    rows = db_admin.execute(
        "select count(*) from app.notifications where user_id = %s", (brand_id,)
    ).fetchone()
    assert rows == (1,)


async def test_bloccare_cancella_e_blocca_le_notifiche(client, keys, db_admin):
    _, brand, brand_nick = await _person(client, keys, db_admin, business=True)
    _, fan, fan_nick = await _person(client, keys, db_admin)
    await client.post(f"/v1/users/{brand_nick}/follow", headers=fan)
    assert len((await _inbox(client, brand))["items"]) == 1
    assert (await client.put(f"/v1/users/{fan_nick}/block", headers=brand)).status_code == 204
    assert (await _inbox(client, brand))["items"] == []


async def test_maggiorenne_non_apre_il_profilo_di_un_16_17(client, keys, db_admin):
    _, adult, adult_nick = await _person(client, keys, db_admin, business=True)
    _, minor, minor_nick = await _person(client, keys, db_admin, minor=True)
    await client.post(f"/v1/users/{adult_nick}/follow", headers=minor)
    [item] = (await _inbox(client, adult))["items"]
    assert item["actor"]["can_open"] is False
    assert item["url"] == "/notifications"
    assert minor_nick in item["title"]


# ---------- Moderazione ----------


async def _staff(client, keys, db_admin):
    user_id, _, _ = await onboard(client, keys, db_admin)
    db_admin.execute("insert into app.staff (user_id, role) values (%s, 'moderator')", (user_id,))
    return bearer(keys.token(user_id, aal="aal2"))


async def test_moderazione_e_reclamo(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    token = await _register(client, author, platform="android")
    first = await _staff(client, keys, db_admin)
    r = await client.post(
        "/v1/admin/reports/decide",
        json={
            "target_type": "post",
            "target_id": post,
            "decision": "hide",
            "sanction": "auto",
            "ground": "nudity",
        },
        headers=first,
    )
    assert r.status_code == 200, r.text
    inbox = await _inbox(client, author)
    titles = sorted(i["title"] for i in inbox["items"])
    assert titles == ["Hai ricevuto un avviso", "Un tuo fit è stato nascosto"]
    hidden = next(i for i in inbox["items"] if i["title"].startswith("Un tuo fit"))
    assert hidden["url"] == "/moderation" and hidden["post"]["id"] == post

    # Due notizie insieme = un solo push, generico (si legge a schermo bloccato).
    sender = await _send()
    [push] = [m for m in sender.sent if m["to"] == token]
    assert (push["title"], push["body"]) == ("WearX", "Hai 2 nuove notifiche")
    assert push["data"] == {"url": "/notifications"}

    notices = (await client.get("/v1/me/moderation", headers=author)).json()
    hide = next(n for n in notices if n["action"] == "hide")
    await client.post(
        f"/v1/me/moderation/{hide['id']}/appeal", json={"text": "È un costume."}, headers=author
    )
    second = await _staff(client, keys, db_admin)
    appeal = next(
        a
        for a in (await client.get("/v1/admin/appeals", headers=second)).json()
        if a["action"]["id"] == hide["id"]
    )
    r = await client.post(
        f"/v1/admin/appeals/{appeal['id']}",
        json={"decision": "reverse", "note": "Ammesso."},
        headers=second,
    )
    assert r.status_code == 200, r.text
    inbox = await _inbox(client, author)
    # L'esito del reclamo racconta l'annullamento: niente notifiche "restore" in più.
    assert inbox["items"][0]["title"] == "Reclamo accolto"
    assert len(inbox["items"]) == 3
    sender = await _send()
    [push] = [m for m in sender.sent if m["to"] == token]
    assert (push["title"], push["body"]) == ("WearX", "Il tuo reclamo è stato deciso")


# ---------- Traguardi di voti ----------


async def test_traguardi_di_voti(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author, caption="Prima alla Scala")
    hidden = await _post(client, db_admin, author_id, author)
    db_admin.execute("update app.posts set status = 'hidden_moderation' where id = %s", (hidden,))
    db_admin.execute(
        "update app.post_stats set vote_count = 12 where post_id = any(%s)",
        ([uuid.UUID(post), uuid.UUID(hidden)],),
    )
    async with session_scope() as session:
        await vote_milestones(session)
    [item] = (await _inbox(client, author))["items"]
    assert item["title"] == "Il tuo fit «Prima alla Scala» ha raggiunto 10 voti"
    assert item["body"] == "Apri il fit per vedere la media."
    assert item["url"] == f"/post/{post}"
    assert item["post"]["thumb"]["variants"]

    db_admin.execute("update app.post_stats set vote_count = 61 where post_id = %s", (post,))
    async with session_scope() as session:
        await vote_milestones(session)
        await vote_milestones(session)  # ripetuto: nulla di nuovo
    [item] = (await _inbox(client, author))["items"]
    assert item["title"].endswith("ha raggiunto 50 voti")
    nxt = db_admin.execute(
        "select vote_milestone_next from app.post_stats where post_id = %s", (post,)
    ).fetchone()
    assert nxt == (100,)


# ---------- Push ----------


async def test_telefoni(client, keys, db_admin):
    user_id, me, _ = await _person(client, keys, db_admin)
    _, other, _ = await _person(client, keys, db_admin)
    for bad in ("ciao", "ExponentPushToken[]", "ExponentPushToken[a b]" + "x" * 20):
        r = await client.put(
            "/v1/me/push-tokens", json={"token": bad, "platform": "ios"}, headers=me
        )
        assert r.status_code == 422, bad
    r = await client.put(
        "/v1/me/push-tokens", json={"token": _token(), "platform": "web"}, headers=me
    )
    assert r.status_code == 422
    shared = await _register(client, me)
    # Stesso telefono, altro account: ora i push vanno solo al nuovo account.
    await _register(client, other, token=shared)
    owner = db_admin.execute(
        "select user_id from app.push_tokens where token = %s", (shared,)
    ).fetchone()
    assert owner[0] != user_id
    for n in range(12):
        await _register(client, me, token=_token(1000 + n))
    count = db_admin.execute(
        "select count(*) from app.push_tokens where user_id = %s", (user_id,)
    ).fetchone()
    assert count == (10,)
    gone = _token(1011)
    assert (await client.delete(f"/v1/me/push-tokens/{gone}", headers=me)).status_code == 204
    assert (await client.delete(f"/v1/me/push-tokens/{gone}", headers=me)).status_code == 204
    # Il token di un altro non si tocca.
    await client.delete(f"/v1/me/push-tokens/{shared}", headers=me)
    assert db_admin.execute(
        "select count(*) from app.push_tokens where token = %s", (shared,)
    ).fetchone() == (1,)


async def test_telefono_non_piu_registrato(client, keys, db_admin):
    _, brand, brand_nick = await _person(client, keys, db_admin, business=True)
    _, fan, _ = await _person(client, keys, db_admin)
    dead = await _register(client, brand)
    alive = await _register(client, brand)
    await client.post(f"/v1/users/{brand_nick}/follow", headers=fan)
    sender = LogSender(unregistered={dead})
    await _send(sender)
    assert db_admin.execute(
        "select count(*) from app.push_tokens where token = %s", (dead,)
    ).fetchone() == (0,)
    receipts = db_admin.execute(
        "select count(*) from app.push_receipts where token = %s", (alive,)
    ).fetchone()
    assert receipts == (1,)
    state = db_admin.execute(
        """select push_state, pushed_at is not null from app.notifications n
            join app.profiles p on p.id = n.user_id where p.nickname = %s""",
        (brand_nick,),
    ).fetchone()
    assert state == ("sent", True)


async def test_senza_telefoni_o_push_spenti(client, keys, db_admin):
    _, brand, brand_nick = await _person(client, keys, db_admin, business=True)
    _, fan, _ = await _person(client, keys, db_admin)
    r = await client.patch("/v1/me/notification-settings", json={"follows": False}, headers=brand)
    assert r.json() == {"follows": False, "votes": True, "moderation": True}
    current = (await client.get("/v1/me/notification-settings", headers=brand)).json()
    assert current["follows"] is False
    r = await client.patch("/v1/me/notification-settings", json={"altro": True}, headers=brand)
    assert r.status_code == 422
    await client.post(f"/v1/users/{brand_nick}/follow", headers=fan)
    state = db_admin.execute(
        """select push_state from app.notifications n
            join app.profiles p on p.id = n.user_id where p.nickname = %s""",
        (brand_nick,),
    ).fetchone()
    assert state == ("none",)  # nella lista sì, sul telefono no
    assert len((await _inbox(client, brand))["items"]) == 1

    _, _, other_nick = await _person(client, keys, db_admin, business=True)
    await client.post(f"/v1/users/{other_nick}/follow", headers=fan)
    await _send()
    state = db_admin.execute(
        """select push_state from app.notifications n
            join app.profiles p on p.id = n.user_id where p.nickname = %s""",
        (other_nick,),
    ).fetchone()
    assert state == ("skipped",)  # nessun telefono registrato


async def test_expo_fuori_servizio_si_riprova(client, keys, db_admin):
    _, brand, brand_nick = await _person(client, keys, db_admin, business=True)
    _, fan, _ = await _person(client, keys, db_admin)
    await _register(client, brand)
    await client.post(f"/v1/users/{brand_nick}/follow", headers=fan)

    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    sender = ExpoSender(None, client=httpx.AsyncClient(transport=httpx.MockTransport(down)))
    await _send(sender)
    row = db_admin.execute(
        """select push_state, push_after > now() + interval '4 minutes'
             from app.notifications n join app.profiles p on p.id = n.user_id
            where p.nickname = %s""",
        (brand_nick,),
    ).fetchone()
    assert row == ("pending", True)


async def test_expo_richieste_e_ricevute():
    seen: list[httpx.Request] = []

    def expo(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/send"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"status": "ok", "id": "t1"},
                        {
                            "status": "error",
                            "message": "not registered",
                            "details": {"error": "DeviceNotRegistered"},
                        },
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "t1": {"status": "error", "details": {"error": "DeviceNotRegistered"}},
                    "t2": {"status": "ok"},
                }
            },
        )

    sender = ExpoSender("segreto", client=httpx.AsyncClient(transport=httpx.MockTransport(expo)))
    tickets = await sender.send([{"to": "a"}, {"to": "b"}])
    assert [(t.ok, t.id, t.error) for t in tickets] == [
        (True, "t1", None),
        (False, None, "DeviceNotRegistered"),
    ]
    assert seen[0].headers["authorization"] == "Bearer segreto"
    assert str(seen[0].url) == "https://exp.host/--/api/v2/push/send"
    receipts = await sender.receipts(["t1", "t2"])
    assert receipts["t1"].error == "DeviceNotRegistered" and receipts["t2"].ok


async def test_ricevute_cancellano_i_telefoni_spariti(client, keys, db_admin):
    user_id, me, _ = await _person(client, keys, db_admin)
    token = await _register(client, me)
    db_admin.execute(
        """insert into app.push_receipts (ticket_id, token, created_at)
           values ('r-dead', %s, now() - interval '20 minutes')""",
        (token,),
    )

    class Receipts(LogSender):
        async def receipts(self, ids):
            from app.push import Ticket

            return {i: Ticket(ok=False, id=i, error="DeviceNotRegistered") for i in ids}

    async with session_scope() as session:
        await check_receipts(session, Receipts())
    assert db_admin.execute(
        "select count(*) from app.push_tokens where user_id = %s", (user_id,)
    ).fetchone() == (0,)
    assert db_admin.execute(
        "select count(*) from app.push_receipts where ticket_id = 'r-dead'"
    ).fetchone() == (0,)


def test_niente_push_di_notte_per_i_16_17():
    def at(h: int, m: int = 0) -> datetime:
        # 5 ottobre 2026: ora legale, Roma = UTC+2.
        return datetime(2026, 10, 5, h - 2, m, tzinfo=UTC)

    assert quiet_until(at(12)) is None
    assert quiet_until(at(21, 59)) is None
    assert quiet_until(at(7)) is None
    late = quiet_until(at(23, 30))
    assert late is not None and late.isoformat() == "2026-10-06T07:00:00+02:00"
    early = quiet_until(at(3))
    assert early is not None and early.isoformat() == "2026-10-05T07:00:00+02:00"


async def test_pagine_della_lista(client, keys, db_admin):
    user_id, me, _ = await _person(client, keys, db_admin)
    for n in range(35):
        db_admin.execute(
            """insert into app.notifications (user_id, type, payload, created_at)
               values (%s, 'moderation', '{"action": "warn"}',
                       now() - make_interval(secs => %s))""",
            (user_id, n),
        )
    first = await _inbox(client, me)
    assert len(first["items"]) == 30 and first["unread"] == 35
    r = await client.get("/v1/notifications", params={"cursor": first["next_cursor"]}, headers=me)
    second = r.json()
    assert len(second["items"]) == 5 and second["next_cursor"] is None
    ids = {i["id"] for i in first["items"]} | {i["id"] for i in second["items"]}
    assert len(ids) == 35
    bad = await client.get("/v1/notifications", params={"cursor": "zzz"}, headers=me)
    assert bad.status_code == 400


# ---------- Eventi ----------


async def test_eventi_solo_dalla_lista_consentita(client, keys, db_admin):
    author_id, author, author_nick = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    viewer_id, viewer, _ = await _person(client, keys, db_admin)
    old = "2026-01-01T00:00:00Z"
    r = await client.post(
        "/v1/events",
        json={
            "events": [
                {"name": "post_impression", "post_id": post, "source": "feed"},
                {"name": "post_open", "post_id": post, "source": "profile"},
                {"name": "shop_click", "post_id": post, "item": 0},
                {"name": "profile_view", "nickname": author_nick},
                {"name": "post_impression", "post_id": str(uuid.uuid4()), "source": "feed"},
                {"name": "post_impression", "post_id": post, "source": "feed", "at": old},
            ]
        },
        headers=viewer,
    )
    assert (r.status_code, r.json()) == (202, {"accepted": 4})
    # I propri fit e il proprio profilo non contano.
    r = await client.post(
        "/v1/events",
        json={
            "events": [
                {"name": "post_impression", "post_id": post, "source": "feed"},
                {"name": "profile_view", "nickname": author_nick},
            ]
        },
        headers=author,
    )
    assert r.json() == {"accepted": 0}
    rows = db_admin.execute(
        "select name, props, actor_key from app.events where post_id = %s order by id", (post,)
    ).fetchall()
    assert [(n, p) for n, p, _ in rows] == [
        ("post_impression", {"source": "feed"}),
        ("post_open", {"source": "profile"}),
        ("shop_click", {"item": 0}),
    ]
    key = bytes(rows[0][2])
    assert len(key) == 16 and viewer_id.bytes not in key
    view = db_admin.execute(
        "select props from app.events where name = 'profile_view' and actor_key = %s", (key,)
    ).fetchone()
    assert view == ({"profile_id": str(author_id)},)

    for bad in (
        {"events": [{"name": "screen_time", "seconds": 10}]},
        {"events": [{"name": "shop_click", "post_id": post, "item": 0, "email": "x@y.z"}]},
        {"events": [{"name": "post_impression", "post_id": post, "source": "push"}]},
        {"events": [{"name": "shop_click", "post_id": post, "item": 20}]},
        {"events": []},
        {"events": [{"name": "profile_view", "nickname": author_nick}] * 51},
    ):
        r = await client.post("/v1/events", json=bad, headers=viewer)
        assert r.status_code == 422, bad
    assert (await client.post("/v1/events", json={"events": []})).status_code in (401, 422)


def test_partizioni_degli_eventi(db_admin):
    db_admin.execute(
        """insert into app.events (name, ts)
           values ('post_open', date_trunc('month', now()) + interval '5 months 3 days')"""
    )
    db_admin.execute("select app.ensure_event_partitions(6)")
    part = db_admin.execute(
        """select tableoid::regclass::text from app.events
            where ts >= date_trunc('month', now()) + interval '5 months'"""
    ).fetchone()
    assert part[0].startswith("app.events_20")
    assert db_admin.execute("select count(*) from app.events_default").fetchone() == (0,)

    db_admin.execute(
        """create table if not exists app.events_2020_01 partition of app.events
             for values from ('2020-01-01 00:00+00') to ('2020-02-01 00:00+00')"""
    )
    dropped = db_admin.execute("select app.drop_old_event_partitions(3)").fetchone()
    assert dropped[0] >= 1
    assert db_admin.execute("select to_regclass('app.events_2020_01')").fetchone() == (None,)
