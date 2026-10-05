"""Seduta 22: attestazione del dispositivo (App Attest con una catena di prova, Play Integrity
con una risposta di Google simulata) e suo effetto sui voti."""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta

import cbor2
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.attest import apple
from app.attest.apple import AttestationError, verify_assertion, verify_attestation
from app.attest.google import check_verdict
from app.config import get_settings
from app.routers import attest as attest_router
from tests.authkit import bearer
from tests.test_accounts import onboard
from tests.test_votes import _post, _stats, _vote

pytestmark = pytest.mark.usefixtures("store")

TEAM, BUNDLE, PACKAGE = "ABCDE12345", "app.wearx.mobile", "app.wearx.mobile"


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(subject, issuer, public_key, signer, *, ca, extensions=()):
    now = datetime.now(UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(subject))
        .issuer_name(_name(issuer))
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    for ext in extensions:
        builder = builder.add_extension(ext, critical=False)
    return builder.sign(signer, hashes.SHA384() if ca else hashes.SHA256())


class FakeApple:
    """Una "Apple" di prova: radice, intermedio e un telefono con la sua chiave."""

    def __init__(self, team=TEAM, bundle=BUNDLE, aaguid=apple.AAGUID_PRODUCTION):
        self.root_key = ec.generate_private_key(ec.SECP384R1())
        self.root = _cert("Root", "Root", self.root_key.public_key(), self.root_key, ca=True)
        self.ca_key = ec.generate_private_key(ec.SECP384R1())
        self.ca = _cert("CA", "Root", self.ca_key.public_key(), self.root_key, ca=True)
        self.device_key = ec.generate_private_key(ec.SECP256R1())
        point = self.device_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.key_bytes = hashlib.sha256(point).digest()
        self.key_id = base64.b64encode(self.key_bytes).decode()
        self.rp = hashlib.sha256(f"{team}.{bundle}".encode()).digest()
        self.aaguid = aaguid
        self.counter = 0

    def attestation(self, challenge: str, *, nonce_challenge: str | None = None) -> str:
        auth = (
            self.rp
            + b"\x40"
            + (0).to_bytes(4, "big")
            + self.aaguid
            + len(self.key_bytes).to_bytes(2, "big")
            + self.key_bytes
        )
        client = hashlib.sha256((nonce_challenge or challenge).encode()).digest()
        nonce = hashlib.sha256(auth + client).digest()
        ext = x509.UnrecognizedExtension(apple.NONCE_OID, bytes.fromhex("3024a1220420") + nonce)
        leaf = _cert(
            "Device", "CA", self.device_key.public_key(), self.ca_key, ca=False, extensions=[ext]
        )
        obj = {
            "fmt": "apple-appattest",
            "attStmt": {
                "x5c": [
                    leaf.public_bytes(serialization.Encoding.DER),
                    self.ca.public_bytes(serialization.Encoding.DER),
                ],
                "receipt": b"",
            },
            "authData": auth,
        }
        return base64.b64encode(cbor2.dumps(obj)).decode()

    def assertion(self, challenge: str, *, counter: int | None = None) -> str:
        self.counter = counter if counter is not None else self.counter + 1
        auth = self.rp + b"\x00" + self.counter.to_bytes(4, "big")
        nonce = hashlib.sha256(auth + hashlib.sha256(challenge.encode()).digest()).digest()
        signature = self.device_key.sign(nonce, ec.ECDSA(hashes.SHA256()))
        return base64.b64encode(
            cbor2.dumps({"signature": signature, "authenticatorData": auth})
        ).decode()


# ---------- Verifiche pure ----------


def _verify(fake, attestation, challenge="sfida-di-prova-1234567890", **kw):
    params = {
        "attestation_b64": attestation,
        "challenge": challenge,
        "key_id": fake.key_id,
        "team_id": TEAM,
        "bundle_id": BUNDLE,
        "allow_development": False,
        "root": fake.root,
    }
    params.update(kw)
    return verify_attestation(**params)


def test_app_attest_valida_e_casi_falsi():
    fake = FakeApple()
    challenge = "sfida-di-prova-1234567890"
    key = _verify(fake, fake.attestation(challenge))
    assert (key.key_id, key.environment) == (fake.key_id, "production")

    with pytest.raises(AttestationError, match="nonce"):
        _verify(fake, fake.attestation(challenge, nonce_challenge="altra-sfida"))
    with pytest.raises(AttestationError, match="firma della catena"):
        _verify(fake, fake.attestation(challenge), root=FakeApple().root)
    other_app = FakeApple(bundle="altra.app")
    with pytest.raises(AttestationError, match="rpIdHash"):
        _verify(other_app, other_app.attestation(challenge), root=other_app.root)
    other = FakeApple()
    with pytest.raises(AttestationError):
        _verify(fake, fake.attestation(challenge), key_id=other.key_id)
    dev = FakeApple(aaguid=apple.AAGUID_DEVELOPMENT)
    with pytest.raises(AttestationError, match="ambiente"):
        _verify(dev, dev.attestation(challenge))
    assert _verify(dev, dev.attestation(challenge), allow_development=True).environment == (
        "development"
    )
    with pytest.raises(AttestationError):
        _verify(fake, base64.b64encode(b"non cbor").decode())


def test_asserzione_contatore_e_firma():
    fake = FakeApple()
    key = _verify(fake, fake.attestation("sfida-di-prova-1234567890"))
    params = {"public_key": key.public_key, "team_id": TEAM, "bundle_id": BUNDLE}
    counter = verify_assertion(
        assertion_b64=fake.assertion("s1"), challenge="s1", previous_counter=0, **params
    )
    assert counter == 1
    with pytest.raises(AttestationError, match="contatore"):
        verify_assertion(
            assertion_b64=fake.assertion("s2", counter=1),
            challenge="s2",
            previous_counter=1,
            **params,
        )
    with pytest.raises(AttestationError, match="firma"):
        verify_assertion(
            assertion_b64=fake.assertion("s3"), challenge="altro", previous_counter=1, **params
        )


def _payload(challenge, **changes):
    payload = {
        "requestDetails": {
            "requestPackageName": PACKAGE,
            "requestHash": challenge,
            "timestampMillis": str(int(time.time() * 1000)),
        },
        "appIntegrity": {"appRecognitionVerdict": "PLAY_RECOGNIZED"},
        "deviceIntegrity": {"deviceRecognitionVerdict": ["MEETS_DEVICE_INTEGRITY"]},
        "accountDetails": {"appLicensingVerdict": "LICENSED"},
    }
    for path, value in changes.items():
        section, field = path.split(".")
        payload[section][field] = value
    return payload


def test_play_integrity_verdetti():
    ok = check_verdict(_payload("c" * 30), package=PACKAGE, challenge="c" * 30)
    assert ok.device == ["MEETS_DEVICE_INTEGRITY"]
    bad = {
        "requestDetails.requestHash": "altro",
        "requestDetails.requestPackageName": "finto.pacchetto",
        "requestDetails.timestampMillis": str(int(time.time() * 1000) - 3_600_000),
        "appIntegrity.appRecognitionVerdict": "UNRECOGNIZED_VERSION",
        "deviceIntegrity.deviceRecognitionVerdict": ["MEETS_BASIC_INTEGRITY"],
    }
    for path, value in bad.items():
        with pytest.raises(AttestationError):
            check_verdict(_payload("c" * 30, **{path: value}), package=PACKAGE, challenge="c" * 30)


# ---------- Attraverso l'API ----------


@pytest.fixture
def apple_setup(monkeypatch):
    fake = FakeApple()
    monkeypatch.setattr(apple, "apple_root", lambda: fake.root)
    monkeypatch.setattr(get_settings(), "apple_team_id", TEAM)
    return fake


async def _me(client, keys, db_admin, *, aged=True):
    user_id, _, _ = await onboard(client, keys, db_admin)
    if aged:
        db_admin.execute(
            "update app.profiles set created_at = now() - interval '30 days' where id = %s",
            (user_id,),
        )
    sid = str(uuid.uuid4())
    return user_id, sid, bearer(keys.token(user_id, session_id=sid))


async def _challenge(client, headers):
    r = await client.post("/v1/me/attest/challenge", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["challenge"]


async def test_iphone_attestato_poi_nuovo_accesso(client, keys, db_admin, apple_setup):
    fake = apple_setup
    user_id, sid, me = await _me(client, keys, db_admin)
    assert (await client.get("/v1/me/attest", headers=me)).json()["attested"] is False

    challenge = await _challenge(client, me)
    body = {
        "key_id": fake.key_id,
        "attestation": fake.attestation(challenge),
        "challenge": challenge,
    }
    r = await client.post("/v1/me/attest/ios", json=body, headers=me)
    assert r.status_code == 204, r.text
    assert (await client.get("/v1/me/attest", headers=me)).json()["attested"] is True
    device = db_admin.execute(
        "select platform, attest_platform from app.devices where session_id = %s", (sid,)
    ).fetchone()
    assert device == ("ios", "ios")
    # La stessa sfida non vale due volte.
    r = await client.post("/v1/me/attest/ios", json=body, headers=me)
    assert (r.status_code, r.json()["code"]) == (422, "attest.failed")

    # Nuovo accesso sullo stesso iPhone: basta l'asserzione con la chiave salvata.
    sid2 = str(uuid.uuid4())
    me2 = bearer(keys.token(user_id, session_id=sid2))
    challenge = await _challenge(client, me2)
    r = await client.post(
        "/v1/me/attest/ios/assert",
        json={
            "key_id": fake.key_id,
            "assertion": fake.assertion(challenge),
            "challenge": challenge,
        },
        headers=me2,
    )
    assert r.status_code == 204, r.text
    assert (await client.get("/v1/me/attest", headers=me2)).json()["attested"] is True

    # Una sfida di un altro accesso non vale.
    challenge = await _challenge(client, me)
    r = await client.post(
        "/v1/me/attest/ios/assert",
        json={
            "key_id": fake.key_id,
            "assertion": fake.assertion(challenge),
            "challenge": challenge,
        },
        headers=me2,
    )
    assert r.status_code == 422


async def test_chiave_di_un_altro_account_rifiutata(client, keys, db_admin, apple_setup):
    fake = apple_setup
    _, _, first = await _me(client, keys, db_admin)
    _, _, second = await _me(client, keys, db_admin)
    for headers, expected in ((first, 204), (second, 422)):
        challenge = await _challenge(client, headers)
        r = await client.post(
            "/v1/me/attest/ios",
            json={
                "key_id": fake.key_id,
                "attestation": fake.attestation(challenge),
                "challenge": challenge,
            },
            headers=headers,
        )
        assert r.status_code == expected, r.text
    unknown = FakeApple()
    challenge = await _challenge(client, second)
    r = await client.post(
        "/v1/me/attest/ios/assert",
        json={
            "key_id": unknown.key_id,
            "assertion": unknown.assertion(challenge),
            "challenge": challenge,
        },
        headers=second,
    )
    assert (r.status_code, r.json()["code"]) == (404, "attest.unknown_key")


async def test_senza_team_id_non_disponibile(client, keys, db_admin):
    _, _, me = await _me(client, keys, db_admin)
    challenge = await _challenge(client, me)
    fake = FakeApple()
    r = await client.post(
        "/v1/me/attest/ios",
        json={
            "key_id": fake.key_id,
            "attestation": fake.attestation(challenge),
            "challenge": challenge,
        },
        headers=me,
    )
    assert (r.status_code, r.json()["code"]) == (503, "attest.unavailable")


class FakeGoogle:
    def __init__(self, **changes):
        self.changes = changes

    async def decode(self, package, token):
        return _payload(token.removeprefix("token-per-"), **self.changes)


async def test_android_e_peso_dei_voti(client, keys, db_admin, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "attestation_mode", "soft")
    monkeypatch.setattr(attest_router, "play_decoder_factory", lambda: FakeGoogle())
    author_id, _, author = await _me(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    _, _, verified = await _me(client, keys, db_admin)
    _, _, unverified = await _me(client, keys, db_admin)

    challenge = await _challenge(client, verified)
    r = await client.post(
        "/v1/me/attest/android",
        json={"token": f"token-per-{challenge}", "challenge": challenge},
        headers=verified,
    )
    assert r.status_code == 204, r.text
    await _vote(client, post_id, verified, 90)
    await _vote(client, post_id, unverified, 30)
    *_, wsum, wcount = _stats(db_admin, post_id)
    # (90 x 1 + 30 x 0,5) / 1,5 = 70: il telefono non verificato pesa la metà.
    assert (wsum / wcount, wcount) == (70.0, 1.5)

    # Telefono senza integrità: rifiutato.
    monkeypatch.setattr(
        attest_router,
        "play_decoder_factory",
        lambda: FakeGoogle(**{"deviceIntegrity.deviceRecognitionVerdict": []}),
    )
    challenge = await _challenge(client, unverified)
    r = await client.post(
        "/v1/me/attest/android",
        json={"token": f"token-per-{challenge}", "challenge": challenge},
        headers=unverified,
    )
    assert (r.status_code, r.json()["code"]) == (422, "attest.failed")

    # Modalità "required": senza dispositivo verificato non si vota.
    monkeypatch.setattr(settings, "attestation_mode", "required")
    r = await _vote(client, post_id, unverified, 40)
    assert (r.status_code, r.json()["code"]) == (403, "device.not_verified")
    assert (await _vote(client, post_id, verified, 95)).status_code == 200


async def test_config_espone_modalita_e_store(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "attestation_mode", "soft")
    monkeypatch.setattr(get_settings(), "play_integrity_project_number", "123456789")
    body = (await client.get("/v1/config")).json()
    assert body["attestation"] == {"mode": "soft", "android_project_number": "123456789"}
    assert set(body["store"]) == {"ios", "android"}
