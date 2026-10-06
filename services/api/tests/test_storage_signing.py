"""Firma veloce degli URL di lettura (seduta 24): uguale a botocore, stabile per finestra."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from botocore import auth as botocore_auth

from app.config import Settings
from app.storage import ObjectStore, _ReadSigner

MOMENT = 1_790_000_123  # un istante fisso qualunque


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://acct.r2.cloudflarestorage.com",
        "http://127.0.0.1:9000",
        "https://media.example.com:8443/base",
    ],
)
@pytest.mark.parametrize("key", ["media/ab/cd/1080.webp", "export/x y+z~é.zip"])
def test_firma_identica_a_botocore(monkeypatch, endpoint, key):
    settings = Settings(storage_endpoint_url=endpoint, storage_region="auto")
    store = ObjectStore(settings)
    fixed = datetime.fromtimestamp(MOMENT, UTC).replace(tzinfo=None)  # botocore: UTC senza fuso
    monkeypatch.setattr(botocore_auth, "get_current_datetime", lambda **_: fixed)
    theirs = urlsplit(store.signed_url(key, 3600))
    signer = _ReadSigner(
        endpoint,
        settings.storage_bucket,
        "auto",
        settings.storage_access_key,
        settings.storage_secret_key.get_secret_value(),
    )
    ours = urlsplit(signer.sign(key, 3600, MOMENT))
    assert (ours.scheme, ours.netloc, ours.path) == (theirs.scheme, theirs.netloc, theirs.path)
    assert parse_qs(ours.query) == parse_qs(theirs.query)


def test_stesso_url_nella_stessa_finestra():
    store = ObjectStore(Settings(storage_endpoint_url="https://acct.r2.cloudflarestorage.com"))
    start = MOMENT - MOMENT % 900
    a, exp_a = store.signed_read_url("k.webp", 3600, now=start + 1)
    b, exp_b = store.signed_read_url("k.webp", 3600, now=start + 899)
    c, exp_c = store.signed_read_url("k.webp", 3600, now=start + 900)
    assert a == b and exp_a == exp_b == start + 3600
    assert c != a and exp_c == start + 900 + 3600
    # Vale sempre ancora almeno 3/4 della durata.
    assert exp_b - (start + 899) >= 2700


async def test_l_archivio_accetta_la_firma(store):
    await store.put("prova/firma.txt", b"ciao", "text/plain")
    url, _ = store.signed_read_url("prova/firma.txt", 600)
    async with httpx.AsyncClient() as client:
        ok = await client.get(url)
    # (moto non controlla le firme: la correttezza la garantisce il confronto con botocore.)
    assert ok.status_code == 200 and ok.content == b"ciao"
