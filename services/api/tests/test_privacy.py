"""Privacy e sicurezza (seduta 20): dispositivi, archivio dei dati, cancellazione."""

from __future__ import annotations

import io
import json
import uuid
import zipfile

import pytest

from app.db import session_scope
from app.media.keys import variant_key
from app.privacy import LocalAuthAdmin, build_export, expire_exports, purge_deleted_accounts
from tests.authkit import bearer
from tests.conftest import ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")


def _device(keys, user_id, sid):
    return bearer(keys.token(user_id, session_id=sid))


async def _seen(client, headers, label="iPhone 15", platform="ios"):
    r = await client.put(
        "/v1/me/devices/current",
        json={"label": label, "platform": platform, "app_version": "0.1.0"},
        headers=headers,
    )
    assert r.status_code == 204, r.text


async def _post(client, db_admin, user_id, headers, caption="Serata"):
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
    return r.json()["id"], media[0]


# ---------- Dispositivi ----------


async def test_dispositivi_collegati(client, keys, db_admin):
    user_id, _, _ = await onboard(client, keys, db_admin)
    phone, tablet, laptop = (_device(keys, user_id, f"s-{n}-{uuid.uuid4()}") for n in range(3))
    await _seen(client, phone)
    await _seen(client, tablet, "Pixel‮ 8\n", "android")
    await _seen(client, laptop, "Browser web", "web")
    listed = (await client.get("/v1/me/devices", headers=phone)).json()
    assert (listed[0]["label"], listed[0]["current"]) == ("iPhone 15", True)
    assert {d["label"] for d in listed} == {"iPhone 15", "Pixel 8", "Browser web"}
    pixel = next(d for d in listed if d["label"] == "Pixel 8")

    push = "ExponentPushToken[tablet000000000001]"
    r = await client.put(
        "/v1/me/push-tokens", json={"token": push, "platform": "android"}, headers=tablet
    )
    assert r.status_code == 204
    r = await client.delete(f"/v1/me/devices/{pixel['id']}", headers=phone)
    assert r.status_code == 204
    r = await client.get("/v1/me", headers=tablet)
    assert (r.status_code, r.json()["code"]) == (401, "auth.session_revoked")
    pushes = db_admin.execute(
        "select count(*) from app.push_tokens where token = %s", (push,)
    ).fetchone()
    assert pushes == (0,)
    assert (await client.delete(f"/v1/me/devices/{pixel['id']}", headers=phone)).status_code == 404
    mine = listed[0]["id"]
    r = await client.delete(f"/v1/me/devices/{mine}", headers=phone)
    assert r.json()["code"] == "device.current"

    # Di un altro account non si tocca nulla.
    other_id, _, _ = await onboard(client, keys, db_admin)
    other = _device(keys, other_id, f"s-o-{uuid.uuid4()}")
    await _seen(client, other)
    stranger = (await client.get("/v1/me/devices", headers=other)).json()[0]["id"]
    assert (await client.delete(f"/v1/me/devices/{stranger}", headers=phone)).status_code == 404

    r = await client.post("/v1/me/devices/revoke-others", headers=phone)
    assert r.json() == {"revoked": 1}  # il portatile
    assert (await client.get("/v1/me", headers=laptop)).status_code == 401
    assert (await client.get("/v1/me", headers=phone)).status_code == 200
    assert [d["current"] for d in (await client.get("/v1/me/devices", headers=phone)).json()] == [
        True
    ]


# ---------- Archivio dei dati ----------


async def test_archivio_dei_dati(client, keys, db_admin, store, queue):
    user_id, me, profile = await onboard(client, keys, db_admin)
    post_id, upload = await _post(client, db_admin, user_id, me, caption="Prima alla Scala")
    widths = db_admin.execute(
        "select variants from app.media_uploads where id = %s", (upload,)
    ).fetchone()[0]
    await store.put(variant_key(uuid.UUID(upload), max(widths)), b"RIFF-foto", "image/webp")
    author_id, author, _ = await onboard(client, keys, db_admin)
    other_post, _ = await _post(client, db_admin, author_id, author)
    r = await client.put(f"/v1/posts/{other_post}/vote", json={"score": 87}, headers=me)
    assert r.status_code in (200, 201), r.text
    await _seen(client, me)

    assert (await client.get("/v1/me/export", headers=me)).json() is None
    r = await client.post("/v1/me/export", headers=me)
    assert (r.status_code, r.json()["status"], r.json()["url"]) == (202, "pending", None)
    export_id = r.json()["id"]
    assert queue.jobs[-1] == ("export_data", (export_id,), f"export:{export_id}")
    assert (await client.post("/v1/me/export", headers=me)).json()["id"] == export_id

    async with session_scope() as session:
        assert await build_export(session, store, uuid.UUID(export_id))
    body = (await client.get("/v1/me/export", headers=me)).json()
    assert body["status"] == "ready" and body["url"] and body["size_bytes"] > 0
    key = db_admin.execute(
        "select storage_key from app.data_exports where id = %s", (export_id,)
    ).fetchone()[0]
    archive = zipfile.ZipFile(io.BytesIO(await store.get(key, 10_000_000)))
    names = set(archive.namelist())
    assert {"LEGGIMI.txt", "profilo.json", "fit.json", "voti.json", "dispositivi.json"} <= names
    assert f"foto/{post_id}-1.webp" in names
    data = {n: json.loads(archive.read(n)) for n in names if n.endswith(".json")}
    assert data["profilo.json"]["nickname"] == profile["nickname"]
    assert data["fit.json"][0]["didascalia"] == "Prima alla Scala"
    assert data["fit.json"][0]["capi"][0]["link"] == "https://tods.com/x"
    assert [(v["post_id"], v["voto"]) for v in data["voti.json"]] == [(other_post, 87)]
    assert data["dispositivi.json"][0]["dispositivo"] == "iPhone 15"
    # Nessun dato di altre persone oltre ai nickname di chi segui o ti segue.
    assert str(author_id) not in archive.read("fit.json").decode()

    inbox = (await client.get("/v1/notifications", headers=me)).json()["items"]
    assert inbox[0]["title"] == "Il tuo archivio dei dati è pronto"
    assert inbox[0]["url"] == "/data-export"
    r = await client.post("/v1/me/export", headers=me)
    assert (r.status_code, r.json()["code"]) == (429, "export.too_soon")

    db_admin.execute(
        "update app.data_exports set expires_at = now() - interval '1 minute' where id = %s",
        (export_id,),
    )
    async with session_scope() as session:
        assert await expire_exports(session, store) >= 1
    assert (await client.get("/v1/me/export", headers=me)).json()["status"] == "expired"
    assert await store.size(key) is None


# ---------- Cancellazione ----------


async def test_cancellazione_con_ripensamento(client, keys, db_admin):
    user_id, _, profile = await onboard(client, keys, db_admin)
    nick = profile["nickname"]
    me = _device(keys, user_id, f"s-me-{uuid.uuid4()}")
    tablet = _device(keys, user_id, f"s-tab-{uuid.uuid4()}")
    await _seen(client, me)
    await _seen(client, tablet)
    _, viewer, _ = await onboard(client, keys, db_admin)
    assert (await client.get(f"/v1/users/{nick}", headers=viewer)).status_code == 200

    r = await client.post("/v1/me/deletion", json={"nickname": "qualcun.altro"}, headers=me)
    assert (r.status_code, r.json()["code"]) == (422, "deletion.confirm_mismatch")
    r = await client.post("/v1/me/deletion", json={"nickname": f"@{nick.upper()}"}, headers=me)
    assert r.status_code == 200, r.text
    assert r.json()["delete_after"]
    assert (await client.get("/v1/me", headers=me)).json()["status"] == "pending_deletion"
    assert (await client.get("/v1/me/deletion", headers=me)).json()["pending"] is True
    r = await client.get("/v1/feed", headers=me)
    assert (r.status_code, r.json()["code"]) == (403, "account.pending_deletion")
    assert (await client.get(f"/v1/users/{nick}", headers=viewer)).status_code == 404
    assert (await client.get("/v1/me", headers=tablet)).status_code == 401  # altri dispositivi
    r = await client.post("/v1/me/deletion", json={"nickname": nick}, headers=me)
    assert r.json()["code"] == "deletion.already"

    assert (await client.delete("/v1/me/deletion", headers=me)).status_code == 204
    assert (await client.get("/v1/me", headers=me)).json()["status"] == "active"
    assert (await client.get(f"/v1/users/{nick}", headers=viewer)).status_code == 200
    assert (await client.delete("/v1/me/deletion", headers=me)).json()["code"] == "deletion.none"


async def test_sospesi_non_si_cancellano(client, keys, db_admin):
    user_id, me, profile = await onboard(client, keys, db_admin)
    db_admin.execute("update app.profiles set status = 'suspended' where id = %s", (user_id,))
    r = await client.post("/v1/me/deletion", json={"nickname": profile["nickname"]}, headers=me)
    assert (r.status_code, r.json()["code"]) == (409, "deletion.suspended")


async def test_cancellazione_definitiva_dopo_30_giorni(client, keys, db_admin, store):
    user_id, me, profile = await onboard(client, keys, db_admin)
    post_id, upload = await _post(client, db_admin, user_id, me)
    photo = variant_key(uuid.UUID(upload), 1080)
    await store.put(photo, b"foto", "image/webp")
    author_id, author, _ = await onboard(client, keys, db_admin)
    other_post, _ = await _post(client, db_admin, author_id, author)
    await client.put(f"/v1/posts/{other_post}/vote", json={"score": 64}, headers=me)
    db_admin.execute(
        """insert into app.moderation_actions
             (target_type, target_id, action, ground, automated, subject_id, statement)
           values ('post', %s, 'warn', 'spam', false, %s, 'Avviso')""",
        (post_id, user_id),
    )
    r = await client.post("/v1/me/deletion", json={"nickname": profile["nickname"]}, headers=me)
    assert r.status_code == 200
    async with session_scope() as session:
        assert await purge_deleted_accounts(session, store) == 0  # non ancora
    db_admin.execute(
        "update app.profiles set delete_after = now() - interval '1 minute' where id = %s",
        (user_id,),
    )
    admin = LocalAuthAdmin()
    async with session_scope() as session:
        assert await purge_deleted_accounts(session, store, admin) == 1
    assert admin.deleted == [user_id]  # in produzione: utente cancellato da Supabase Auth
    for table, column in (("app.profiles", "id"), ("app.posts", "author_id")):
        row = db_admin.execute(
            f"select count(*) from {table} where {column} = %s",  # noqa: S608
            (user_id,),
        ).fetchone()
        assert row == (0,), table
    assert await store.size(photo) is None
    # Restano, senza la persona: il voto dentro la media e la decisione di moderazione.
    votes = db_admin.execute(
        "select count(*) from app.votes where post_id = %s", (other_post,)
    ).fetchone()
    assert votes == (1,)
    # ... ma non più collegabile alla persona, nemmeno con il segreto dei voti.
    from app.routers.events import actor_key
    from app.votes import voter_key

    linked = db_admin.execute(
        "select count(*) from app.votes where voter_key = %s", (voter_key(user_id),)
    ).fetchone()
    assert linked == (0,)
    events = db_admin.execute(
        "select count(*) from app.events where actor_key = %s", (actor_key(user_id),)
    ).fetchone()
    assert events == (0,)
    action = db_admin.execute(
        "select subject_id from app.moderation_actions where target_id = %s", (post_id,)
    ).fetchone()
    assert action == (None,)
