"""Caricamento delle foto end-to-end: firma, upload HTTP vero su un archivio S3 locale
(moto), completamento, worker, URL firmati, pulizia."""

from __future__ import annotations

import io
import uuid

import httpx
import pytest
from PIL import Image

from app.media import jobs
from app.media.keys import quarantine_key, variant_key
from app.moderation.scanning import set_classifier
from tests.authkit import bearer
from tests.imagekit import has_metadata, photo
from tests.test_accounts import onboard


async def _create(client, headers, *, content_type="image/jpeg", size=100_000):
    return await client.post(
        "/v1/media/uploads",
        json={"content_type": content_type, "size_bytes": size},
        headers=headers,
    )


async def _upload(target: dict, data: bytes, content_type="image/jpeg") -> httpx.Response:
    async with httpx.AsyncClient(trust_env=False) as http:
        return await http.post(
            target["url"],
            data=target["fields"],
            files={"file": ("foto.jpg", data, content_type)},
        )


async def _upload_and_process(client, headers, store, queue, data: bytes):
    created = (await _create(client, headers, size=len(data))).json()
    assert (await _upload(created["upload"], data)).status_code in (200, 204)
    r = await client.post(f"/v1/media/uploads/{created['id']}/complete", headers=headers)
    assert r.status_code == 202, r.text
    assert queue.jobs[-1] == ("process_upload", (created["id"],), f"upload:{created['id']}")
    outcome = await jobs.process_upload({}, created["id"])
    return created["id"], outcome


async def test_percorso_completo(client, keys, db_admin, store, queue):
    _, headers, _ = await onboard(client, keys, db_admin)
    data = photo(1600, 2000, gps=True)

    created = await _create(client, headers, size=len(data))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["max_bytes"] == 15 * 1024 * 1024
    assert body["upload"]["fields"]["Content-Type"] == "image/jpeg"
    assert body["upload"]["fields"]["key"] == f"quarantine/{body['id']}"
    assert "policy" in body["upload"]["fields"]

    # Prima del caricamento: niente da completare.
    r = await client.post(f"/v1/media/uploads/{body['id']}/complete", headers=headers)
    assert (r.status_code, r.json()["code"]) == (409, "media.not_uploaded")

    assert (await _upload(body["upload"], data)).status_code in (200, 204)
    r = await client.post(f"/v1/media/uploads/{body['id']}/complete", headers=headers)
    assert (r.status_code, r.json()["status"]) == (202, "processing")
    # Ripetuto: stessa risposta, nessun lavoro doppio.
    r = await client.post(f"/v1/media/uploads/{body['id']}/complete", headers=headers)
    assert r.json()["status"] == "processing"
    assert len(queue.jobs) == 1

    assert await jobs.process_upload({}, body["id"]) == "ready"
    assert await jobs.process_upload({}, body["id"]) == "skip:ready"  # lavoro ripetuto

    ready = (await client.get(f"/v1/media/uploads/{body['id']}", headers=headers)).json()
    assert ready["status"] == "ready"
    assert (ready["width"], ready["height"]) == (1600, 2000)
    assert ready["blurhash"]
    assert set(ready["urls"]["variants"]) == {"320", "640", "1080"}

    # Le varianti si leggono con l'URL firmato, sono WebP e senza metadati.
    async with httpx.AsyncClient(trust_env=False) as http:
        got = await http.get(ready["urls"]["variants"]["1080"])
        assert got.status_code == 200
        assert not has_metadata(got.content)
        with Image.open(io.BytesIO(got.content)) as image:
            assert (image.format, image.width) == ("WEBP", 1080)
        # Senza firma l'archivio non le dà a nessuno.
        unsigned = ready["urls"]["variants"]["1080"].split("?")[0]
        assert (await http.get(unsigned)).status_code == 403

    # L'originale con il GPS non esiste più.
    assert await store.size(quarantine_key(uuid.UUID(body["id"]))) is None
    row = db_admin.execute(
        "select sha256 is not null, phash is not null, variants from app.media_uploads "
        "where id = %s",
        (body["id"],),
    ).fetchone()
    assert row == (True, True, [320, 640, 1080])


async def test_file_non_immagine_rifiutato_e_cancellato(client, keys, db_admin, store, queue):
    _, headers, _ = await onboard(client, keys, db_admin)
    upload_id, outcome = await _upload_and_process(
        client, headers, store, queue, b"<?php echo 'non sono una foto'; ?>" * 10
    )
    assert outcome == "rejected:not_an_image"
    r = (await client.get(f"/v1/media/uploads/{upload_id}", headers=headers)).json()
    assert (r["status"], r["reject_reason"], r["urls"]) == ("rejected", "not_an_image", None)
    assert await store.size(quarantine_key(uuid.UUID(upload_id))) is None


async def test_foto_bloccata_dalla_moderazione(client, keys, db_admin, store, queue):
    class Explicit:
        async def classify(self, image):
            return {"sexual": 0.99}

    set_classifier(Explicit())
    try:
        _, headers, _ = await onboard(client, keys, db_admin)
        upload_id, outcome = await _upload_and_process(client, headers, store, queue, photo())
    finally:
        set_classifier(None)
    assert outcome == "rejected:blocked"
    assert await store.size(variant_key(uuid.UUID(upload_id), 1080)) is None


async def test_l_archivio_rifiuta_file_oltre_il_limite_firmato(
    client, keys, db_admin, store, queue
):
    _, headers, _ = await onboard(client, keys, db_admin)
    body = (await _create(client, headers, size=1000)).json()
    # Tipo diverso da quello firmato: rifiutato dall'archivio.
    r = await _upload(body["upload"], photo(), content_type="image/png")
    assert r.status_code in (200, 204, 403)
    big = b"\xff" * (15 * 1024 * 1024 + 10)
    await store.put(quarantine_key(uuid.UUID(body["id"])), big, "image/jpeg")
    r = await client.post(f"/v1/media/uploads/{body['id']}/complete", headers=headers)
    assert (r.status_code, r.json()["code"]) == (422, "media.too_large")
    assert await store.size(quarantine_key(uuid.UUID(body["id"]))) is None
    status = (await client.get(f"/v1/media/uploads/{body['id']}", headers=headers)).json()
    assert status["reject_reason"] == "too_large"


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"content_type": "image/gif", "size_bytes": 10}, "request.invalid"),
        ({"content_type": "image/heic", "size_bytes": 10}, "request.invalid"),
        ({"content_type": "image/jpeg", "size_bytes": 0}, "request.invalid"),
        ({"content_type": "image/jpeg", "size_bytes": 16 * 1024 * 1024}, "media.too_large"),
    ],
)
async def test_richieste_non_valide(client, keys, db_admin, store, payload, code):
    _, headers, _ = await onboard(client, keys, db_admin)
    r = await client.post("/v1/media/uploads", json=payload, headers=headers)
    assert r.status_code == 422
    assert r.json()["code"] == code


async def test_foto_altrui_invisibile(client, keys, db_admin, store, queue):
    _, headers, _ = await onboard(client, keys, db_admin)
    _, other, _ = await onboard(client, keys, db_admin)
    body = (await _create(client, headers)).json()
    for method, path in [
        ("GET", f"/v1/media/uploads/{body['id']}"),
        ("POST", f"/v1/media/uploads/{body['id']}/complete"),
        ("DELETE", f"/v1/media/uploads/{body['id']}"),
    ]:
        r = await client.request(method, path, headers=other)
        assert (r.status_code, r.json()["code"]) == (404, "media.not_found")


async def test_troppi_caricamenti_in_sospeso(client, keys, db_admin, store, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_pending_uploads", 2)
    _, headers, _ = await onboard(client, keys, db_admin)
    assert (await _create(client, headers)).status_code == 201
    assert (await _create(client, headers)).status_code == 201
    r = await _create(client, headers)
    assert (r.status_code, r.json()["code"]) == (429, "media.too_many_pending")


async def test_serve_un_profilo(client, keys, db_admin, store):
    from tests.conftest import create_auth_user

    user_id = create_auth_user(db_admin)
    r = await _create(client, bearer(keys.token(user_id)))
    assert r.json()["code"] == "onboarding.required"


async def test_eliminare_una_foto_non_pubblicata(client, keys, db_admin, store, queue):
    _, headers, _ = await onboard(client, keys, db_admin)
    upload_id, outcome = await _upload_and_process(client, headers, store, queue, photo(900, 900))
    assert outcome == "ready"
    r = await client.delete(f"/v1/media/uploads/{upload_id}", headers=headers)
    assert r.status_code == 204
    for width in (320, 640, 900):
        assert await store.size(variant_key(uuid.UUID(upload_id), width)) is None
    assert (await client.get(f"/v1/media/uploads/{upload_id}", headers=headers)).status_code == 404


async def test_pulizia_periodica(client, keys, db_admin, store, queue):
    _, headers, _ = await onboard(client, keys, db_admin)
    stale = (await _create(client, headers)).json()
    await _upload(stale["upload"], photo(800, 800))
    old_ready, _ = await _upload_and_process(client, headers, store, queue, photo(800, 800))
    fresh, _ = await _upload_and_process(client, headers, store, queue, photo(800, 800))
    db_admin.execute(
        "update app.media_uploads set created_at = now() - interval '2 days' where id = %s",
        (stale["id"],),
    )
    db_admin.execute(
        "update app.media_uploads set created_at = now() - interval '8 days' where id = %s",
        (old_ready,),
    )
    assert await jobs.cleanup_uploads({}) >= 2

    r = (await client.get(f"/v1/media/uploads/{stale['id']}", headers=headers)).json()
    assert (r["status"], r["reject_reason"]) == ("rejected", "expired")
    assert await store.size(quarantine_key(uuid.UUID(stale["id"]))) is None
    assert (await client.get(f"/v1/media/uploads/{old_ready}", headers=headers)).status_code == 404
    assert await store.size(variant_key(uuid.UUID(old_ready), 640)) is None
    # Quella recente resta.
    assert await store.size(variant_key(uuid.UUID(fresh), 640)) is not None
