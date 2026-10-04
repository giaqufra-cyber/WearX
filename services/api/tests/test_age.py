"""Verifica dell'età: decisione, firma dei webhook, sessioni, pagina del fornitore finto."""

from __future__ import annotations

import time
import uuid
from datetime import date, timedelta

import pytest

from app.age import signing
from app.age.base import WebhookRejected, WebhookResult
from app.age.decision import add_years, decide
from app.age.fake import FakeAgeProvider
from app.config import get_settings
from tests.authkit import bearer
from tests.conftest import create_auth_user

TODAY = date(2026, 10, 4)
RETURN = "wearx://age-return"


# ---------- Decisione (funzione pura) ----------


def _result(**kw) -> WebhookResult:
    return WebhookResult(provider_ref="r", outcome=kw.pop("outcome", "passed"), **kw)


class TestDecision:
    def test_documento_maggiorenne(self):
        d = decide(_result(birth_date=date(2000, 5, 1)), None, TODAY)
        assert (d.status, d.age_band, d.adult_on) == ("passed", "18_plus", None)

    def test_documento_16_17_calcola_i_18_anni(self):
        d = decide(_result(birth_date=date(2009, 12, 25)), add_years(date(2009, 12, 25), 18), TODAY)
        assert (d.status, d.age_band, d.adult_on) == ("passed", "16_17", date(2027, 12, 25))

    def test_documento_vince_sulla_data_dichiarata(self):
        # Dichiarato maggiorenne, il documento dice 17 anni: vale il documento.
        d = decide(_result(birth_date=date(2009, 1, 1)), date(2020, 1, 1), TODAY)
        assert (d.age_band, d.adult_on) == ("16_17", date(2027, 1, 1))

    def test_documento_sotto_i_16_blocca(self):
        d = decide(_result(birth_date=date(2012, 1, 1)), date(2026, 1, 1), TODAY)
        assert (d.status, d.failure_reason) == ("failed", "underage")

    def test_stima_concorde(self):
        assert decide(_result(age_band="18_plus"), date(2015, 1, 1), TODAY).age_band == "18_plus"
        d = decide(_result(age_band="16_17"), date(2027, 6, 1), TODAY)
        assert (d.age_band, d.adult_on) == ("16_17", date(2027, 6, 1))

    def test_stima_maggiorenne_ma_dichiarato_minorenne_vale_la_piu_protettiva(self):
        d = decide(_result(age_band="18_plus"), date(2027, 6, 1), TODAY)
        assert (d.status, d.age_band, d.adult_on) == ("passed", "16_17", date(2027, 6, 1))

    def test_stima_minorenne_ma_dichiarato_maggiorenne_chiede_documento(self):
        d = decide(_result(age_band="16_17"), date(2020, 1, 1), TODAY)
        assert (d.status, d.failure_reason) == ("failed", "inconsistent")

    def test_stima_sotto_i_16_non_blocca_chiede_documento(self):
        d = decide(_result(age_band="under_16"), date(2020, 1, 1), TODAY)
        assert d.failure_reason == "inconsistent"

    def test_annullata_o_fallita(self):
        assert decide(_result(outcome="cancelled"), None, TODAY).failure_reason == "not_completed"
        assert decide(_result(outcome="failed"), None, TODAY).failure_reason == "not_completed"

    def test_compie_18_anni_oggi(self):
        d = decide(_result(birth_date=date(2008, 10, 4)), None, TODAY)
        assert d.age_band == "18_plus"

    def test_29_febbraio(self):
        assert add_years(date(2008, 2, 29), 18) == date(2026, 3, 1)


# ---------- Firma ----------


class TestSigning:
    SECRET = "s3cret"  # noqa: S105 - segreto di test
    BODY = b'{"ref":"abc"}'

    def test_valida(self):
        header = signing.sign(self.SECRET, self.BODY, 1000)
        signing.verify(self.SECRET, header, self.BODY, now=1100, tolerance=300)

    @pytest.mark.parametrize(
        "header,body,now",
        [
            (None, BODY, 1000),
            ("t=1000", BODY, 1000),
            ("v1=abc", BODY, 1000),
            ("t=xx,v1=abc", BODY, 1000),
        ],
    )
    def test_malformata(self, header, body, now):
        with pytest.raises(WebhookRejected):
            signing.verify(self.SECRET, header, body, now=now, tolerance=300)

    def test_corpo_modificato_o_segreto_sbagliato(self):
        header = signing.sign(self.SECRET, self.BODY, 1000)
        with pytest.raises(WebhookRejected):
            signing.verify(self.SECRET, header, b'{"ref":"xyz"}', now=1000, tolerance=300)
        with pytest.raises(WebhookRejected):
            signing.verify("altro", header, self.BODY, now=1000, tolerance=300)

    def test_replay_fuori_tolleranza(self):
        header = signing.sign(self.SECRET, self.BODY, 1000)
        with pytest.raises(WebhookRejected):
            signing.verify(self.SECRET, header, self.BODY, now=1301, tolerance=300)

    def test_rotazione_del_segreto(self):
        old = signing.sign("vecchio", self.BODY, 1000).split(",")[1]
        header = signing.sign(self.SECRET, self.BODY, 1000) + "," + old
        signing.verify(self.SECRET, header, self.BODY, now=1000, tolerance=300)


# ---------- API ----------


def _birth(years: int) -> str:
    return (date.today() - timedelta(days=years * 365 + 120)).isoformat()


async def _start(client, headers, *, method="selfie_estimation", years=25, return_url=RETURN):
    return await client.post(
        "/v1/age-verification/sessions",
        json={"method": method, "declared_birth_date": _birth(years), "return_url": return_url},
        headers=headers,
    )


def _ref(db_admin, verification_id: str) -> str:
    row = db_admin.execute(
        "select provider_ref from app.age_verifications where id = %s", (verification_id,)
    ).fetchone()
    assert row is not None
    return str(row[0])


@pytest.fixture
def user(keys, db_admin):
    user_id = create_auth_user(db_admin)
    return user_id, bearer(keys.token(user_id))


async def _finish(client, db_admin, verification_id, choice, method="selfie_estimation"):
    ref = _ref(db_admin, verification_id)
    r = await client.post(
        f"/v1/dev/fake-age/{ref}?method={method}",
        data={"choice": choice, "return_url": RETURN},
    )
    assert r.status_code == 303, r.text
    return r


async def test_stato_iniziale_e_metodi(client, user):
    _, headers = user
    r = await client.get("/v1/age-verification", headers=headers)
    assert r.status_code == 200
    # SPID/CIE dietro feature flag (spento di default).
    assert r.json() == {
        "verified": False,
        "age_band": None,
        "methods": ["selfie_estimation", "id_document"],
        "latest": None,
    }


async def test_serve_l_accesso(client):
    r = await client.get("/v1/age-verification")
    assert r.status_code == 401


async def test_flusso_completo_maggiorenne_poi_profilo(client, user, db_admin):
    _, headers = user
    r = await _start(client, headers)
    assert r.status_code == 201, r.text
    session = r.json()
    assert session["status"] == "pending"
    assert "/v1/dev/fake-age/" in session["redirect_url"]

    declared = db_admin.execute(
        "select declared_adult_on from app.age_verifications where id = %s", (session["id"],)
    ).fetchone()
    assert declared is not None and declared[0] is not None

    page = await client.get(session["redirect_url"].replace("http://localhost:8000", ""))
    assert page.status_code == 200
    assert "FORNITORE DI PROVA" in page.text

    done = await _finish(client, db_admin, session["id"], "adult")
    assert done.headers["location"] == f"{RETURN}?result=adult"

    r = await client.get(f"/v1/age-verification/sessions/{session['id']}", headers=headers)
    assert r.json() | {"id": None} == {
        "id": None,
        "method": "selfie_estimation",
        "status": "passed",
        "age_band": "18_plus",
        "failure_reason": None,
        "redirect_url": None,
    }
    # La data dichiarata sparisce a verifica chiusa.
    row = db_admin.execute(
        "select declared_adult_on, adult_on from app.age_verifications where id = %s",
        (session["id"],),
    ).fetchone()
    assert row == (None, None)

    status = (await client.get("/v1/age-verification", headers=headers)).json()
    assert (status["verified"], status["age_band"]) == (True, "18_plus")

    r = await client.post(
        "/v1/onboarding/profile",
        json={
            "nickname": f"fit_{uuid.uuid4().hex[:8]}",
            "terms_version": get_settings().terms_version,
            "accept_community_rules": True,
            "styles": ["old-money"],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["age_band"] == "18_plus"

    # Con il profilo creato non si riapre una verifica.
    assert (await _start(client, headers)).json()["code"] == "profile.exists"


async def test_minorenne_con_stima(client, user, db_admin):
    _, headers = user
    session = (await _start(client, headers, years=17)).json()
    await _finish(client, db_admin, session["id"], "minor")
    row = db_admin.execute(
        "select status::text, age_band::text, adult_on from app.age_verifications where id = %s",
        (session["id"],),
    ).fetchone()
    assert row is not None
    assert row[:2] == ("passed", "16_17")
    assert row[2] > date.today()


async def test_stima_sotto_i_16_chiede_un_documento_senza_bloccare(client, user, db_admin):
    _, headers = user
    session = (await _start(client, headers, years=20)).json()
    await _finish(client, db_admin, session["id"], "under16")
    r = await client.get(f"/v1/age-verification/sessions/{session['id']}", headers=headers)
    assert (r.json()["status"], r.json()["failure_reason"]) == ("failed", "inconsistent")
    assert (await _start(client, headers, method="id_document")).status_code == 201


async def test_documento_sotto_i_16_blocca_nuovi_tentativi(client, user, db_admin):
    _, headers = user
    session = (await _start(client, headers, method="id_document", years=16)).json()
    await _finish(client, db_admin, session["id"], "under16", method="id_document")
    r = await client.get(f"/v1/age-verification/sessions/{session['id']}", headers=headers)
    assert r.json()["failure_reason"] == "underage"
    r = await _start(client, headers)
    assert (r.status_code, r.json()["code"]) == (403, "age.blocked")


async def test_annullata(client, user, db_admin):
    _, headers = user
    session = (await _start(client, headers)).json()
    await _finish(client, db_admin, session["id"], "cancel")
    r = await client.get(f"/v1/age-verification/sessions/{session['id']}", headers=headers)
    assert r.json()["failure_reason"] == "not_completed"


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"years": 15}, "age.underage"),
        ({"years": 120}, "age.invalid_birth_date"),
        ({"method": "spid"}, "age.method_unavailable"),
        ({"return_url": "https://sito-malevolo.example/"}, "age.bad_return_url"),
        ({"return_url": "wearx://ok space"}, "age.bad_return_url"),
    ],
)
async def test_avvio_rifiutato(client, user, db_admin, kwargs, code):
    user_id, headers = user
    r = await _start(client, headers, **kwargs)
    assert r.status_code == 422
    assert r.json()["code"] == code
    count = db_admin.execute(
        "select count(*) from app.age_verifications where user_id = %s", (user_id,)
    ).fetchone()
    assert count == (0,)


async def test_una_sola_verifica_aperta(client, user, db_admin):
    _, headers = user
    first = (await _start(client, headers)).json()
    second = (await _start(client, headers)).json()
    r = await client.get(f"/v1/age-verification/sessions/{first['id']}", headers=headers)
    assert r.json()["status"] == "expired"
    r = await client.get(f"/v1/age-verification/sessions/{second['id']}", headers=headers)
    assert r.json()["status"] == "pending"


async def test_scadenza_dopo_un_ora(client, user, db_admin):
    _, headers = user
    session = (await _start(client, headers)).json()
    db_admin.execute(
        "update app.age_verifications set created_at = now() - interval '2 hours' where id = %s",
        (session["id"],),
    )
    r = await client.get(f"/v1/age-verification/sessions/{session['id']}", headers=headers)
    assert r.json()["status"] == "expired"
    # Il webhook che arriva tardi non riapre nulla.
    body, hdrs = FakeAgeProvider.build_webhook(_ref(db_admin, session["id"]), "passed", "18_plus")
    assert (
        await client.post("/v1/webhooks/age/fake", content=body, headers=hdrs)
    ).status_code == 204
    r = await client.get(f"/v1/age-verification/sessions/{session['id']}", headers=headers)
    assert r.json()["status"] == "expired"


async def test_verifica_altrui_invisibile(client, user, keys, db_admin):
    _, headers = user
    session = (await _start(client, headers)).json()
    other = create_auth_user(db_admin)
    r = await client.get(
        f"/v1/age-verification/sessions/{session['id']}", headers=bearer(keys.token(other))
    )
    assert (r.status_code, r.json()["code"]) == (404, "age.session_not_found")


async def test_gia_verificata(client, user, db_admin):
    _, headers = user
    session = (await _start(client, headers)).json()
    await _finish(client, db_admin, session["id"], "adult")
    r = await _start(client, headers)
    assert (r.status_code, r.json()["code"]) == (409, "age.already_verified")


class TestWebhook:
    async def test_idempotente(self, client, user, db_admin):
        _, headers = user
        session = (await _start(client, headers)).json()
        ref = _ref(db_admin, session["id"])
        body, hdrs = FakeAgeProvider.build_webhook(ref, "passed", "18_plus")
        assert (
            await client.post("/v1/webhooks/age/fake", content=body, headers=hdrs)
        ).status_code == 204
        # Ripetuto (anche con esito diverso): resta il primo.
        body2, hdrs2 = FakeAgeProvider.build_webhook(ref, "cancelled")
        assert (
            await client.post("/v1/webhooks/age/fake", content=body2, headers=hdrs2)
        ).status_code == 204
        r = await client.get(f"/v1/age-verification/sessions/{session['id']}", headers=headers)
        assert r.json()["status"] == "passed"

    async def test_firma_non_valida(self, client, user, db_admin):
        _, headers = user
        session = (await _start(client, headers)).json()
        body, hdrs = FakeAgeProvider.build_webhook(
            _ref(db_admin, session["id"]), "passed", "18_plus"
        )
        tampered = body.replace(b"18_plus", b"16_17")
        r = await client.post("/v1/webhooks/age/fake", content=tampered, headers=hdrs)
        assert (r.status_code, r.json()["code"]) == (401, "webhook.rejected")
        r = await client.post("/v1/webhooks/age/fake", content=body)
        assert r.status_code == 401

    async def test_replay_vecchio(self, client, user, db_admin):
        _, headers = user
        session = (await _start(client, headers)).json()
        body, hdrs = FakeAgeProvider.build_webhook(
            _ref(db_admin, session["id"]), "passed", "18_plus", timestamp=int(time.time()) - 3600
        )
        r = await client.post("/v1/webhooks/age/fake", content=body, headers=hdrs)
        assert r.status_code == 401

    async def test_fornitore_o_riferimento_sconosciuto(self, client):
        body, hdrs = FakeAgeProvider.build_webhook("inesistente", "passed", "18_plus")
        assert (
            await client.post("/v1/webhooks/age/altro", content=body, headers=hdrs)
        ).status_code == 404
        assert (
            await client.post("/v1/webhooks/age/fake", content=body, headers=hdrs)
        ).status_code == 404


async def test_pagina_di_prova_rifiuta_ritorni_esterni(client, user, db_admin):
    _, headers = user
    session = (await _start(client, headers)).json()
    ref = _ref(db_admin, session["id"])
    r = await client.get(f"/v1/dev/fake-age/{ref}?return_url=https://sito-malevolo.example")
    assert r.status_code == 422
    r = await client.post(
        f"/v1/dev/fake-age/{ref}", data={"choice": "adult", "return_url": "https://x.example"}
    )
    assert r.status_code == 422


async def test_config_espone_la_versione_dei_termini(client):
    r = await client.get("/v1/config")
    assert r.json()["terms_version"] == get_settings().terms_version


def test_produzione_vieta_il_fornitore_finto(monkeypatch):
    from app.config import Settings
    from app.config import get_settings as cached

    monkeypatch.setenv("WEARX_ENV", "production")
    monkeypatch.setenv("WEARX_VOTE_PEPPER", "prod-pepper")
    cached.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="fornitore finto"):
            cached()
        assert Settings().age_return_schemes == ("wearx://",)
    finally:
        monkeypatch.undo()
        cached.cache_clear()
