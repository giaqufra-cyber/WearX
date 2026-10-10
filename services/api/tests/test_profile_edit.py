"""Profilo (seduta 27): foto profilo, bio, stili visibili solo a sé, intervento dello staff."""

from __future__ import annotations

import io
import json
import uuid
import zipfile

import pytest

from app.db import session_scope
from app.media import jobs
from app.media.keys import variant_key
from app.privacy import build_export
from tests.conftest import ready_upload
from tests.test_media_api import _upload_and_process
from tests.test_moderation import _person, _staff

pytestmark = pytest.mark.usefixtures("store")


async def _me(client, headers, **body):
    return await client.patch("/v1/me", json=body, headers=headers)


async def _user(client, nick, headers):
    r = await client.get(f"/v1/users/{nick}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _upload_exists(db_admin, upload_id) -> bool:
    row = db_admin.execute("select 1 from app.media_uploads where id = %s", (upload_id,))
    return row.fetchone() is not None


async def test_foto_profilo_si_mette_si_cambia_si_toglie(client, keys, db_admin, store):
    uid, h, nick = await _person(client, keys, db_admin)
    first = ready_upload(db_admin, uid)
    await store.put(variant_key(first, 320), b"RIFF-prima", "image/webp")

    r = await _me(client, h, avatar=str(first))
    assert r.status_code == 200, r.text
    avatar = r.json()["avatar"]
    assert avatar["blurhash"] and set(avatar["urls"]["variants"]) == {"320", "640", "1080"}
    assert (await _user(client, nick, h))["avatar"]["blurhash"] == avatar["blurhash"]

    # Una volta usata come foto profilo non si può mettere in un post (e non scade dopo 7 giorni).
    r = await client.post(
        "/v1/posts", json={"style": "old-money", "media": [str(first)]}, headers=h
    )
    assert r.json()["code"] == "media.unavailable"
    db_admin.execute(
        "update app.media_uploads set created_at = now() - interval '30 days' where id = %s",
        (first,),
    )
    await jobs.cleanup_uploads({})
    assert _upload_exists(db_admin, first)

    # Cambiandola, la precedente si cancella (database e archivio).
    second = ready_upload(db_admin, uid)
    assert (await _me(client, h, avatar=str(second))).status_code == 200
    assert not _upload_exists(db_admin, first)
    with pytest.raises(Exception, match="NoSuchKey"):
        await store.get(variant_key(first, 320), 1000)
    # Rimandare la stessa non cambia niente.
    assert (await _me(client, h, avatar=str(second))).json()["avatar"] is not None

    r = await _me(client, h, avatar=None)
    assert r.json()["avatar"] is None
    assert not _upload_exists(db_admin, second)


async def test_foto_profilo_non_valide(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    oid, _, _ = await _person(client, keys, db_admin)
    current = ready_upload(db_admin, uid)
    assert (await _me(client, h, avatar=str(current))).status_code == 200

    of_someone_else = ready_upload(db_admin, oid)
    in_a_post = ready_upload(db_admin, uid)
    r = await client.post(
        "/v1/posts", json={"style": "old-money", "media": [str(in_a_post)]}, headers=h
    )
    assert r.status_code == 201
    to_review = ready_upload(db_admin, uid)
    db_admin.execute("update app.media_uploads set needs_review = true where id = %s", (to_review,))
    pending = ready_upload(db_admin, uid)
    db_admin.execute(
        """update app.media_uploads set status = 'pending', width = null, height = null,
                  blurhash = null, sha256 = null, variants = null where id = %s""",
        (pending,),
    )

    for bad, code in [
        (of_someone_else, "avatar.unavailable"),
        (in_a_post, "avatar.unavailable"),
        (pending, "avatar.unavailable"),
        (uuid.uuid4(), "avatar.unavailable"),
        (to_review, "avatar.not_allowed"),
    ]:
        r = await _me(client, h, avatar=str(bad), bio="non salvata")
        assert (r.status_code, r.json()["code"]) == (422, code), bad
    # Resta la foto di prima, e la bio della stessa richiesta non è stata salvata.
    me = (await client.get("/v1/me", headers=h)).json()
    assert me["avatar"] is not None and me["bio"] is None
    assert _upload_exists(db_admin, current)


async def test_bio_con_le_regole_dei_testi(client, keys, db_admin):
    _, h, nick = await _person(client, keys, db_admin)
    r = await _me(client, h, bio="  Vintage e sartoria.\nMilano  ")
    assert r.json()["bio"] == "Vintage e sartoria.\nMilano"
    assert (await _me(client, h, bio="x" * 151)).status_code == 422
    assert (await _me(client, h, bio="a\nb\nc\nd\ne")).status_code == 422
    assert (await _me(client, h, bio=None)).json()["bio"] is None
    assert (await _user(client, nick, h))["bio"] is None


async def test_gli_stili_a_cui_sei_iscritto_li_vedi_solo_tu(client, keys, db_admin):
    _, h, nick = await _person(client, keys, db_admin, business=True)
    _, other, _ = await _person(client, keys, db_admin)
    assert [s["slug"] for s in (await _user(client, nick, h))["styles"]]
    # Account Business: portfolio pubblico, ma gli stili no.
    seen = await _user(client, nick, other)
    assert seen["can_view_posts"] is True and seen["styles"] == []


async def test_negli_elenchi_compare_la_foto_profilo(client, keys, db_admin):
    # Business: il follow è subito accettato.
    uid, h, nick = await _person(client, keys, db_admin, business=True)
    _, fan, fan_nick = await _person(client, keys, db_admin)
    assert (await _me(client, h, avatar=str(ready_upload(db_admin, uid)))).status_code == 200
    assert (await client.post(f"/v1/users/{nick}/follow", headers=fan)).status_code == 200
    following = (await client.get("/v1/me/following", headers=fan)).json()["items"]
    assert following[0]["nickname"] == nick and following[0]["avatar"] is not None
    # Anche sui suoi fit, quando l'autore è mostrato.
    post = (
        await client.post(
            "/v1/posts",
            json={"style": "old-money", "media": [str(ready_upload(db_admin, uid))]},
            headers=h,
        )
    ).json()["id"]
    author = (await client.get(f"/v1/posts/{post}", headers=fan)).json()["author"]
    assert author["nickname"] == nick and author["avatar"]["blurhash"]
    # Nei bloccati no.
    assert (await client.put(f"/v1/users/{nick}/block", headers=fan)).status_code in (200, 204)
    blocked = (await client.get("/v1/me/blocks", headers=fan)).json()["items"]
    assert blocked[0]["nickname"] == nick and blocked[0]["avatar"] is None
    assert fan_nick


async def test_la_foto_profilo_finisce_nell_archivio_dei_dati(client, keys, db_admin, store):
    uid, h, _ = await _person(client, keys, db_admin)
    upload = ready_upload(db_admin, uid)
    await store.put(variant_key(upload, 1080), b"RIFF-profilo", "image/webp")
    assert (await _me(client, h, avatar=str(upload))).status_code == 200
    export_id = (await client.post("/v1/me/export", headers=h)).json()["id"]
    async with session_scope() as session:
        assert await build_export(session, store, uuid.UUID(export_id))
    key = db_admin.execute(
        "select storage_key from app.data_exports where id = %s", (export_id,)
    ).fetchone()[0]
    archive = zipfile.ZipFile(io.BytesIO(await store.get(key, 10_000_000)))
    assert archive.read("foto/profilo.webp") == b"RIFF-profilo"
    assert "foto profilo" in archive.read("LEGGIMI.txt").decode()
    assert json.loads(archive.read("profilo.json"))


async def test_lo_staff_toglie_bio_e_foto_di_un_profilo_segnalato(
    client, keys, db_admin, store, queue
):
    _, h, nick = await _person(client, keys, db_admin)
    image = _checkerboard()
    upload, outcome = await _upload_and_process(client, h, store, queue, image)
    assert outcome == "ready"
    assert (await _me(client, h, avatar=upload, bio="Bio offensiva")).status_code == 200
    _, reporter, _ = await _person(client, keys, db_admin)
    r = await client.post(
        "/v1/reports",
        json={"target_type": "profile", "nickname": nick, "reason": "harassment"},
        headers=reporter,
    )
    assert r.status_code == 201

    _, staff = await _staff(client, keys, db_admin)
    item = next(
        i
        for i in (await client.get("/v1/admin/reports/queue", headers=staff)).json()
        if i["target_type"] == "profile" and i["subject"] == nick
    )
    assert item["profile"]["bio"] == "Bio offensiva" and item["profile"]["avatar"]
    decision = {
        "target_type": "profile",
        "target_id": item["target_id"],
        "decision": "remove",
        "ground": "harassment",
    }
    r = await client.post("/v1/admin/reports/decide", json=decision, headers=staff)
    assert r.status_code == 200, r.text
    me = (await client.get("/v1/me", headers=h)).json()
    assert (me["bio"], me["avatar"]) == (None, None)
    notice = (await client.get("/v1/me/moderation", headers=h)).json()[0]
    assert (notice["action"], notice["target_type"]) == ("remove", "profile")
    assert "bio e la foto del tuo profilo" in notice["statement"]
    # La stessa foto non si può ricaricare.
    _, outcome = await _upload_and_process(client, h, store, queue, image)
    assert outcome == "rejected:blocked"
    # Su un link "rimuovi" non vale.
    r = await client.post(
        "/v1/admin/reports/decide",
        json={**decision, "target_type": "link", "target_id": str(uuid.uuid4())},
        headers=staff,
    )
    assert (r.status_code, r.json()["code"]) == (422, "moderation.bad_decision")
    # La lista delle foto bloccate resta nel database dei test: si pulisce.
    db_admin.execute(
        "delete from app.blocked_hashes where source = %s",
        (f"action:{notice['id']}",),
    )


def _checkerboard() -> bytes:
    """Foto ben diversa da quelle di `imagekit.photo` (hash percettivo lontano)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1200, 1500), (20, 120, 60))
    draw = ImageDraw.Draw(image)
    for row in range(10):
        for col in range(8):
            if (row + col) % 2:
                draw.rectangle([col * 150, row * 150, col * 150 + 149, row * 150 + 149], "white")
    out = io.BytesIO()
    image.save(out, "JPEG", quality=90)
    return out.getvalue()
