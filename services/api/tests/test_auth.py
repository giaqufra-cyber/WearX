"""Verifica dei token: ogni modo noto di falsificarli deve dare 401."""

import base64
import json
import time
import uuid

import jwt
import pytest

from tests.authkit import bearer


def _b64(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


async def _me(client, headers):
    return await client.get("/v1/me", headers=headers)


async def test_missing_token_is_401_with_challenge(client, keys):
    r = await _me(client, {})
    assert r.status_code == 401
    assert r.json()["code"] == "auth.required"
    assert r.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer   ", "token xyz"])
async def test_wrong_scheme_is_401(client, keys, header):
    r = await _me(client, {"Authorization": header})
    assert r.status_code == 401
    assert r.json()["code"] == "auth.required"


async def test_garbage_token_is_401(client, keys):
    r = await _me(client, bearer("not.a.jwt"))
    assert r.json()["code"] == "auth.invalid_token"


async def test_valid_es256_token_reaches_profile_check(client, keys):
    r = await _me(client, bearer(keys.token(uuid.uuid4())))
    # Token valido ma nessun profilo: tocca all'onboarding.
    assert r.status_code == 409
    assert r.json()["code"] == "onboarding.required"


async def test_valid_rs256_token_is_accepted(client, keys):
    r = await _me(client, bearer(keys.token(uuid.uuid4(), alg="RS256")))
    assert r.json()["code"] == "onboarding.required"


async def test_expired_token(client, keys):
    token = keys.token(uuid.uuid4(), iat=int(time.time()) - 7200, exp=int(time.time()) - 3600)
    r = await _me(client, bearer(token))
    assert r.status_code == 401
    assert r.json()["code"] == "auth.token_expired"


@pytest.mark.parametrize(
    "override",
    [
        {"iss": "https://altro-progetto.supabase.co/auth/v1"},
        {"aud": "service_role"},
        {"role": "service_role"},
        {"sub": "non-un-uuid"},
        {"exp": None},
        {"sub": None},
        {"aud": None},
    ],
)
async def test_bad_claims_are_rejected(client, keys, override):
    claims = {"sub": uuid.uuid4(), **override}
    r = await _me(client, bearer(keys.token(**claims)))
    assert r.status_code == 401
    assert r.json()["code"] == "auth.invalid_token"


async def test_anonymous_supabase_users_are_rejected(client, keys):
    r = await _me(client, bearer(keys.token(uuid.uuid4(), is_anonymous=True)))
    assert r.status_code == 403
    assert r.json()["code"] == "auth.anonymous_not_allowed"


async def test_alg_none_is_rejected(client, keys):
    header = {"alg": "none", "typ": "JWT", "kid": keys.ec_kid}
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": "x",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 60,
    }
    token = f"{_b64(header)}.{_b64(payload)}."
    r = await _me(client, bearer(token))
    assert r.json()["code"] == "auth.invalid_token"


async def test_hs256_with_public_key_as_secret_is_rejected(client, keys):
    """Attacco di confusione: firmare in HS256 usando la chiave pubblica come segreto."""
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": "x",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 60,
    }
    header = {"alg": "HS256", "typ": "JWT", "kid": keys.ec_kid}
    signing_input = f"{_b64(header)}.{_b64(payload)}".encode()
    import hashlib
    import hmac

    sig = hmac.new(keys.public_pem(), signing_input, hashlib.sha256).digest()
    token = signing_input.decode() + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    r = await _me(client, bearer(token))
    assert r.json()["code"] == "auth.invalid_token"


async def test_symmetric_key_in_jwks_is_never_used(client, keys):
    now = int(time.time())
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "iss": "x", "aud": "authenticated", "iat": now, "exp": now + 60},
        "segreto",
        algorithm="HS256",
        headers={"kid": "shared-secret"},
    )
    r = await _me(client, bearer(token))
    assert r.json()["code"] == "auth.invalid_token"


async def test_signature_from_another_key_is_rejected(client, keys):
    from tests.authkit import KeySet

    attacker = KeySet()
    # Stesso kid del nostro JWKS, ma firmato con una chiave diversa.
    token = attacker.token(uuid.uuid4(), kid=keys.ec_kid)
    r = await _me(client, bearer(token))
    assert r.json()["code"] == "auth.invalid_token"


async def test_tampered_payload_is_rejected(client, keys):
    token = keys.token(uuid.uuid4())
    head, _, sig = token.split(".")
    forged = _b64(
        {"sub": str(uuid.uuid4()), "iss": "x", "aud": "authenticated", "iat": 1, "exp": 9999999999}
    )
    r = await _me(client, bearer(f"{head}.{forged}.{sig}"))
    assert r.json()["code"] == "auth.invalid_token"


async def test_unknown_kid_does_not_hammer_jwks(client, keys):
    before = keys.fetches
    for _ in range(5):
        r = await _me(client, bearer(keys.token(uuid.uuid4(), kid="sconosciuto")))
        assert r.json()["code"] == "auth.invalid_token"
    # Al massimo una ricarica al minuto, anche con molti kid sconosciuti.
    assert keys.fetches - before <= 1
