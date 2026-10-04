"""Stili: elenco, ricerca, pagina, entrare/uscire, regole d'età, passaggio ai 18 anni."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest

from app.routers import styles as styles_router
from tests.authkit import bearer
from tests.conftest import create_auth_user
from tests.test_accounts import onboard


def _slugs(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [s["slug"] for s in response.json()["items"]]


@pytest.fixture
def temp_style(db_admin) -> Iterator[object]:
    """Crea stili temporanei (es. fuori stagione) e li rimuove a fine test."""
    created: list[str] = []

    def make(slug_prefix: str = "tmp", **cols) -> str:
        slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
        values = {
            "name": cols.pop("name", "Prova"),
            "tagline": cols.pop("tagline", "Stile di prova"),
            "tone": "#123456",
            "min_age_band": cols.pop("min_age_band", "16_17"),
            "active_from": cols.pop("active_from", None),
            "active_until": cols.pop("active_until", None),
        }
        db_admin.execute(
            """insert into app.styles (slug, name, tagline, tone, min_age_band, active_from,
                                       active_until, sort_order)
               values (%s, %s, %s, %s, %s, %s, %s, 999)""",
            (slug, *values.values()),
        )
        created.append(slug)
        return slug

    yield make
    for slug in created:
        db_admin.execute(
            "delete from app.style_memberships where style_id = "
            "(select id from app.styles where slug = %s)",
            (slug,),
        )
        db_admin.execute("delete from app.styles where slug = %s", (slug,))


# ---------- Elenco e ricerca ----------


async def test_serve_un_profilo(client, keys, db_admin):
    user_id = create_auth_user(db_admin)
    r = await client.get("/v1/styles", headers=bearer(keys.token(user_id)))
    assert r.json()["code"] == "onboarding.required"


async def test_elenco_maggiorenne_e_minorenne(client, keys, db_admin):
    _, adult, _ = await onboard(client, keys, db_admin)
    _, minor, _ = await onboard(client, keys, db_admin, minor=True)

    adult_list = await client.get("/v1/styles", headers=adult)
    assert "beach-party" in _slugs(adult_list)
    assert "beach-party" not in _slugs(await client.get("/v1/styles", headers=minor))

    items = {s["slug"]: s for s in adult_list.json()["items"]}
    # onboarding_body() sceglie old-money e jappo.
    assert items["old-money"]["joined"] is True
    assert items["gala"]["joined"] is False
    assert items["old-money"]["member_count"] >= 1
    assert items["halloween"]["seasonal"] is True
    assert adult_list.json()["total"] == len(items)


@pytest.mark.parametrize(
    "query,expected_first",
    [
        ("gala", "gala"),  # senza accento
        ("GALÀ", "gala"),  # maiuscole e accento
        ("jappo", "jappo"),
        ("jppo", "jappo"),  # refuso
        ("tokyo", "jappo"),  # parola della descrizione
        ("  old   money ", "old-money"),  # spazi in più
        ("y2k", "y2k"),
    ],
)
async def test_ricerca(client, keys, db_admin, query, expected_first):
    _, headers, _ = await onboard(client, keys, db_admin)
    slugs = _slugs(await client.get("/v1/styles", params={"q": query}, headers=headers))
    assert slugs and slugs[0] == expected_first


async def test_ricerca_senza_risultati_e_caratteri_speciali(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    for query in ("zzzzqqq", "%", "_", "\\", "' or 1=1 --"):
        assert _slugs(await client.get("/v1/styles", params={"q": query}, headers=headers)) == []
    r = await client.get("/v1/styles", params={"q": "x" * 41}, headers=headers)
    assert r.status_code == 422


async def test_ricerca_rispetta_l_eta(client, keys, db_admin):
    _, minor, _ = await onboard(client, keys, db_admin, minor=True)
    assert _slugs(await client.get("/v1/styles", params={"q": "beach"}, headers=minor)) == []


async def test_fuori_stagione_e_disattivati_non_si_vedono(client, keys, db_admin, temp_style):
    _, headers, _ = await onboard(client, keys, db_admin)
    past = temp_style("past", active_from="2025-10-01", active_until="2025-11-01")
    future = temp_style("future", active_from="2099-01-01")
    off = temp_style("off")
    db_admin.execute("update app.styles set is_active = false where slug = %s", (off,))
    listed = _slugs(await client.get("/v1/styles", headers=headers))
    for slug in (past, future, off):
        assert slug not in listed
        r = await client.get(f"/v1/styles/{slug}", headers=headers)
        assert (r.status_code, r.json()["code"]) == (404, "style.not_found")


# ---------- Pagina dello stile ----------


async def test_pagina_stile(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    r = await client.get("/v1/styles/old-money", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Old Money"
    assert body["joined"] is True
    assert body["posts_last_7_days"] == 0


async def test_pagina_18_piu_invisibile_ai_minorenni(client, keys, db_admin):
    _, minor, _ = await onboard(client, keys, db_admin, minor=True)
    r = await client.get("/v1/styles/beach-party", headers=minor)
    assert (r.status_code, r.json()["code"]) == (404, "style.not_found")
    r = await client.get("/v1/styles/non-esiste", headers=minor)
    assert r.status_code == 404


# ---------- Entrare e uscire ----------


async def test_entrare_e_uscire(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    before = (await client.get("/v1/styles/gala", headers=headers)).json()["member_count"]

    r = await client.put("/v1/styles/gala/membership", headers=headers)
    assert r.status_code == 200
    assert (r.json()["joined"], r.json()["member_count"]) == (True, before + 1)
    # Ripetere non cambia nulla.
    r = await client.put("/v1/styles/gala/membership", headers=headers)
    assert r.json()["member_count"] == before + 1

    mine = _slugs(await client.get("/v1/me/styles", headers=headers))
    assert mine[-1] == "gala"  # in ordine di adesione
    assert "gala" in (await client.get("/v1/me", headers=headers)).json()["styles"]

    r = await client.delete("/v1/styles/gala/membership", headers=headers)
    assert (r.json()["joined"], r.json()["member_count"]) == (False, before)
    r = await client.delete("/v1/styles/gala/membership", headers=headers)
    assert r.status_code == 200 and r.json()["joined"] is False


async def test_minorenne_non_entra_negli_stili_18_piu(client, keys, db_admin):
    user_id, minor, _ = await onboard(client, keys, db_admin, minor=True)
    r = await client.put("/v1/styles/beach-party/membership", headers=minor)
    assert (r.status_code, r.json()["code"]) == (404, "style.not_found")
    count = db_admin.execute(
        "select count(*) from app.style_memberships m join app.styles s on s.id = m.style_id "
        "where m.user_id = %s and s.slug = 'beach-party'",
        (user_id,),
    ).fetchone()
    assert count == (0,)


async def test_non_si_esce_dall_ultimo_stile(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    assert (await client.delete("/v1/styles/jappo/membership", headers=headers)).status_code == 200
    r = await client.delete("/v1/styles/old-money/membership", headers=headers)
    assert (r.status_code, r.json()["code"]) == (409, "style.last_membership")
    assert _slugs(await client.get("/v1/me/styles", headers=headers)) == ["old-money"]


async def test_due_uscite_in_parallelo_lasciano_almeno_uno_stile(client, keys, db_admin):
    _, headers, _ = await onboard(client, keys, db_admin)
    results = await asyncio.gather(
        client.delete("/v1/styles/old-money/membership", headers=headers),
        client.delete("/v1/styles/jappo/membership", headers=headers),
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert len(_slugs(await client.get("/v1/me/styles", headers=headers))) == 1


async def test_l_uscita_conta_solo_gli_stili_ancora_visibili(client, keys, db_admin, temp_style):
    user_id, headers, _ = await onboard(client, keys, db_admin)
    # Uno stile stagionale finito non "tiene" nel feed: non conta come stile rimasto.
    past = temp_style("past", active_from="2025-10-01", active_until="2025-11-01")
    db_admin.execute(
        "insert into app.style_memberships (user_id, style_id) "
        "select %s, id from app.styles where slug = %s",
        (user_id, past),
    )
    await client.delete("/v1/styles/jappo/membership", headers=headers)
    r = await client.delete("/v1/styles/old-money/membership", headers=headers)
    assert r.json()["code"] == "style.last_membership"
    assert past not in (await client.get("/v1/me", headers=headers)).json()["styles"]


async def test_limite_di_stili(client, keys, db_admin, monkeypatch):
    monkeypatch.setattr(styles_router, "MAX_MEMBERSHIPS", 3)
    _, headers, _ = await onboard(client, keys, db_admin)
    assert (await client.put("/v1/styles/gala/membership", headers=headers)).status_code == 200
    r = await client.put("/v1/styles/elegant/membership", headers=headers)
    assert (r.status_code, r.json()["code"]) == (409, "style.limit")


async def test_stile_diventato_18_piu_sparisce_per_i_minorenni(client, keys, db_admin, temp_style):
    _, minor, _ = await onboard(client, keys, db_admin, minor=True)
    slug = temp_style("tmp")
    assert (await client.put(f"/v1/styles/{slug}/membership", headers=minor)).status_code == 200
    db_admin.execute("update app.styles set min_age_band = '18_plus' where slug = %s", (slug,))
    assert slug not in _slugs(await client.get("/v1/me/styles", headers=minor))
    assert slug not in (await client.get("/v1/me", headers=minor)).json()["styles"]


# ---------- Passaggio ai 18 anni ----------


async def test_compiuti_18_anni_si_passa_alla_fascia_adulti(client, keys, db_admin):
    user_id, minor, _ = await onboard(client, keys, db_admin, minor=True)
    assert "beach-party" not in _slugs(await client.get("/v1/styles", headers=minor))
    db_admin.execute(
        "update app.profiles set adult_on = current_date - 1 where id = %s", (user_id,)
    )
    me = (await client.get("/v1/me", headers=minor)).json()
    assert me["age_band"] == "18_plus"
    row = db_admin.execute(
        "select age_band::text, adult_on from app.profiles where id = %s", (user_id,)
    ).fetchone()
    assert row == ("18_plus", None)
    assert "beach-party" in _slugs(await client.get("/v1/styles", headers=minor))


def test_fold_toglie_accenti_e_maiuscole(db_admin):
    row = db_admin.execute("select app.fold('Galà ÉLÈGANT Ñandú Straße')").fetchone()
    assert row == ("gala elegant nandu strase",)


def test_promote_adults_in_blocco(db_admin):
    user_id = create_auth_user(db_admin)
    db_admin.execute(
        """insert into app.profiles (id, nickname, age_band, adult_on, age_verified_at, age_method)
           values (%s, %s, '16_17', current_date, now(), 'id_document')""",
        (user_id, f"t_{uuid.uuid4().hex[:8]}"),
    )
    promoted = db_admin.execute("select app.promote_adults()").fetchone()
    assert promoted is not None and promoted[0] >= 1
    row = db_admin.execute("select age_band::text from app.profiles where id = %s", (user_id,))
    assert row.fetchone() == ("18_plus",)
