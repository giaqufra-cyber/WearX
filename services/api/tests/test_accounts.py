"""Nickname, creazione del profilo, profilo personale, limiti di frequenza."""

import uuid

import pytest

from app.config import get_settings
from tests.authkit import bearer
from tests.conftest import create_auth_user, pass_age_check

TERMS = get_settings().terms_version


def _nick() -> str:
    return f"fit_{uuid.uuid4().hex[:8]}"


def onboarding_body(nickname: str, **overrides):
    body = {
        "nickname": nickname,
        "terms_version": TERMS,
        "accept_community_rules": True,
        "styles": ["old-money", "jappo"],
    }
    body.update(overrides)
    return body


async def onboard(client, keys, db_admin, *, minor=False, nickname=None):
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id, minor=minor)
    headers = bearer(keys.token(user_id))
    r = await client.post(
        "/v1/onboarding/profile", json=onboarding_body(nickname or _nick()), headers=headers
    )
    assert r.status_code == 201, r.text
    return user_id, headers, r.json()


# ---------- nickname-check ----------


async def test_nickname_available(client):
    r = await client.post("/v1/auth/nickname-check", json={"nickname": _nick()})
    assert r.status_code == 200
    assert r.json()["available"] is True


@pytest.mark.parametrize(
    ("nickname", "reason"),
    [
        ("ab", "invalid"),
        ("con spazio", "invalid"),
        (".inizio", "invalid"),
        ("fine_", "invalid"),
        ("doppio..punto", "invalid"),
        ("admin", "reserved"),
        ("wearx_official", "reserved"),
        ("w.e.a.r.x", "reserved"),
        ("il_vero_supporto", "reserved"),
        ("support", "reserved"),
        ("privacy", "reserved"),
    ],
)
async def test_nickname_rejected(client, nickname, reason):
    r = await client.post("/v1/auth/nickname-check", json={"nickname": nickname})
    assert r.json() == {"nickname": nickname, "available": False, "reason": reason}


async def test_nickname_taken_ignores_case(client, keys, db_admin):
    nick = _nick()
    await onboard(client, keys, db_admin, nickname=nick)
    r = await client.post("/v1/auth/nickname-check", json={"nickname": nick.upper()})
    assert r.json()["reason"] == "taken"


async def test_nickname_check_is_rate_limited_per_ip(client):
    for _ in range(20):
        r = await client.post("/v1/auth/nickname-check", json={"nickname": _nick()})
        assert r.status_code == 200
    r = await client.post("/v1/auth/nickname-check", json={"nickname": _nick()})
    assert r.status_code == 429
    assert r.json()["code"] == "rate.limited"
    assert int(r.headers["retry-after"]) >= 1


# ---------- onboarding ----------


async def test_onboarding_creates_profile_with_styles(client, keys, db_admin):
    user_id, _headers, profile = await onboard(client, keys, db_admin)
    assert profile["id"] == str(user_id)
    assert profile["account_type"] == "private"
    assert profile["age_band"] == "18_plus"
    assert profile["styles"] == ["old-money", "jappo"]
    row = db_admin.execute(
        "select terms_version, terms_accepted_at is not null from app.profiles where id = %s",
        (user_id,),
    ).fetchone()
    assert row == (TERMS, True)


async def test_onboarding_requires_age_verification(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    r = await client.post(
        "/v1/onboarding/profile", json=onboarding_body(_nick()), headers=bearer(keys.token(user_id))
    )
    assert r.status_code == 409
    assert r.json()["code"] == "age.verification_required"


async def test_failed_or_pending_verification_is_not_enough(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    db_admin.execute(
        "insert into app.age_verifications (user_id, method, status, provider, failure_reason) "
        "values (%s, 'selfie_estimation', 'failed', 'test', 'not_completed'), "
        "(%s, 'id_document', 'pending', 'test', null)",
        (user_id, user_id),
    )
    r = await client.post(
        "/v1/onboarding/profile", json=onboarding_body(_nick()), headers=bearer(keys.token(user_id))
    )
    assert r.json()["code"] == "age.verification_required"


async def test_onboarding_twice_is_rejected(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    r = await client.post("/v1/onboarding/profile", json=onboarding_body(_nick()), headers=headers)
    assert r.status_code == 409
    assert r.json()["code"] == "profile.exists"


async def test_onboarding_nickname_taken(client, keys, db_admin):
    nick = _nick()
    await onboard(client, keys, db_admin, nickname=nick)
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id)
    r = await client.post(
        "/v1/onboarding/profile", json=onboarding_body(nick), headers=bearer(keys.token(user_id))
    )
    assert r.status_code == 409
    assert r.json()["code"] == "nickname.taken"


async def test_onboarding_reserved_nickname(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id)
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body("wearx.team"),
        headers=bearer(keys.token(user_id)),
    )
    assert r.status_code == 422
    assert r.json()["code"] == "nickname.reserved"


async def test_onboarding_outdated_terms(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id)
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), terms_version="2020-01"),
        headers=bearer(keys.token(user_id)),
    )
    assert r.json()["code"] == "terms.outdated"


async def test_onboarding_requires_community_rules(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id)
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), accept_community_rules=False),
        headers=bearer(keys.token(user_id)),
    )
    assert r.status_code == 422
    assert r.json()["code"] == "request.invalid"


async def test_onboarding_rejects_unknown_and_duplicate_styles(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id)
    headers = bearer(keys.token(user_id))
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), styles=["inesistente"]),
        headers=headers,
    )
    assert r.json()["code"] == "style.not_found"
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), styles=["jappo", "jappo"]),
        headers=headers,
    )
    assert r.json()["code"] == "request.invalid"


async def test_minor_cannot_join_adult_styles(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id, minor=True)
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), styles=["beach-party"]),
        headers=bearer(keys.token(user_id)),
    )
    assert r.status_code == 403
    assert r.json()["code"] == "style.age_restricted"


async def test_minor_profile_keeps_age_band(client, keys, db_admin):
    _, _, profile = await onboard(client, keys, db_admin, minor=True)
    assert profile["age_band"] == "16_17"


async def test_business_disabled_by_feature_flag(client, keys, db_admin, monkeypatch):
    # Il flag ora è acceso (seduta 21), ma spegnerlo deve ancora fermare i Business.
    monkeypatch.setitem(get_settings().feature_flags, "business_accounts", False)
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id)
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), account_type="business"),
        headers=bearer(keys.token(user_id)),
    )
    assert r.status_code == 403
    assert r.json()["code"] == "feature.disabled"


async def test_business_requires_adult_when_enabled(client, keys, db_admin, monkeypatch):
    monkeypatch.setitem(get_settings().feature_flags, "business_accounts", True)
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id, minor=True)
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), account_type="business"),
        headers=bearer(keys.token(user_id)),
    )
    assert r.json()["code"] == "account.business_requires_adult"


async def test_unknown_fields_are_rejected(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    pass_age_check(db_admin, user_id)
    r = await client.post(
        "/v1/onboarding/profile",
        json=onboarding_body(_nick(), age_band="18_plus"),
        headers=bearer(keys.token(user_id)),
    )
    assert r.status_code == 422


# ---------- /v1/me ----------


async def test_get_me(client, keys, db_admin):
    user_id, headers, _ = await onboard(client, keys, db_admin)
    r = await client.get("/v1/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == str(user_id)


async def test_update_bio_and_flags(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    r = await client.patch(
        "/v1/me", json={"bio": "  Archivio di fit.\nTrento  ", "hide_prices": True}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["bio"] == "Archivio di fit.\nTrento"
    assert r.json()["hide_prices"] is True
    assert r.json()["hide_vote_count"] is False


@pytest.mark.parametrize(
    ("bio", "code"),
    [
        ("ciao\u202emoc.xraew", "text.invalid_characters"),
        ("zero\u200bwidth", "text.invalid_characters"),
        ("x" * 151, "text.too_long"),
        ("a\nb\nc\nd\ne", "text.too_many_lines"),
    ],
)
async def test_bio_rules(client, keys, db_admin, bio, code):
    _, headers, _ = await onboard(client, keys, db_admin)
    r = await client.patch("/v1/me", json={"bio": bio}, headers=headers)
    assert r.status_code == 422
    assert r.json()["code"] == code


async def test_empty_bio_clears_it(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    await client.patch("/v1/me", json={"bio": "qualcosa"}, headers=headers)
    r = await client.patch("/v1/me", json={"bio": "   "}, headers=headers)
    assert r.json()["bio"] is None


async def test_profile_fields_cannot_be_forged(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin, minor=True)
    r = await client.patch("/v1/me", json={"age_band": "18_plus"}, headers=headers)
    assert r.status_code == 422
    r = await client.get("/v1/me", headers=headers)
    assert r.json()["age_band"] == "16_17"


async def test_suspended_account(client, keys, db_admin):
    user_id, headers, _ = await onboard(client, keys, db_admin)
    db_admin.execute("update app.profiles set status = 'suspended' where id = %s", (user_id,))
    r = await client.get("/v1/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "suspended"
    r = await client.patch("/v1/me", json={"bio": "x"}, headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "account.suspended"


async def test_users_only_ever_see_themselves(client, keys, db_admin):
    a_id, a_headers, _ = await onboard(client, keys, db_admin)
    _b_id, b_headers, _ = await onboard(client, keys, db_admin)
    await client.patch("/v1/me", json={"bio": "di B"}, headers=b_headers)
    r = await client.get("/v1/me", headers=a_headers)
    assert r.json()["id"] == str(a_id)
    assert r.json()["bio"] is None


async def test_profile_update_rate_limit(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    for i in range(30):
        r = await client.patch("/v1/me", json={"bio": f"v{i}"}, headers=headers)
        assert r.status_code == 200
    r = await client.patch("/v1/me", json={"bio": "troppo"}, headers=headers)
    assert r.status_code == 429


async def test_rate_limit_fails_open_when_redis_is_down(client, monkeypatch):
    from redis.exceptions import ConnectionError as RedisConnectionError

    import app.ratelimit as rl

    class DownRedis:
        async def eval(self, *args, **kwargs):
            raise RedisConnectionError("giù")

    monkeypatch.setattr(rl, "get_redis", lambda: DownRedis())
    for _ in range(25):
        r = await client.post("/v1/auth/nickname-check", json={"nickname": _nick()})
        assert r.status_code == 200


async def test_concurrent_onboarding_same_nickname(client, keys, db_admin):
    import asyncio

    nick = _nick()
    headers = []
    for _ in range(2):
        user_id = create_auth_user(db_admin)
        pass_age_check(db_admin, user_id)
        headers.append(bearer(keys.token(user_id)))
    results = await asyncio.gather(
        *(
            client.post("/v1/onboarding/profile", json=onboarding_body(nick), headers=h)
            for h in headers
        )
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409]
    loser = next(r for r in results if r.status_code == 409)
    assert loser.json()["code"] == "nickname.taken"
