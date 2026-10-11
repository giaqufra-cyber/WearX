"""Stili proposti dalla community (seduta 30)."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.routers.style_proposals import name_key, slug_for
from tests.test_moderation import _person, _staff

pytestmark = pytest.mark.usefixtures("store")


@pytest.fixture
def threshold(monkeypatch):
    monkeypatch.setattr(get_settings(), "style_proposal_threshold", 3)
    return 3


async def _propose(client, headers, name, category="stili", **extra):
    return await client.post(
        "/v1/style-proposals", json={"name": name, "category": category, **extra}, headers=headers
    )


def test_nomi_e_slug():
    assert name_key("  Avant-Garde ") == "avant garde"
    assert name_key("Àprès Ski!") == "apres ski"
    assert slug_for("Avant-Garde") == "avant-garde"
    assert slug_for("Ñ") == "n"


async def test_proposta_richieste_e_attivazione_alla_soglia(client, keys, db_admin, threshold):
    _, a, _ = await _person(client, keys, db_admin)
    _, b, _ = await _person(client, keys, db_admin)
    _, c, _ = await _person(client, keys, db_admin)
    name = f"Avant Garde {db_admin.execute('select gen_random_uuid()').fetchone()[0].hex[:5]}"

    r = await _propose(client, a, name, "stili", tagline="Silhouette estreme, nero")
    assert r.status_code == 200, r.text
    body = r.json()
    proposal = body["proposal"]
    assert body["created"] is True
    assert (
        proposal["supports"],
        proposal["threshold"],
        proposal["supported"],
        proposal["mine"],
    ) == (
        1,
        3,
        True,
        True,
    )

    # Stesso nome scritto diverso: la richiesta va sulla proposta che c'è già.
    r = await _propose(client, b, name.upper().replace(" ", "-"))
    assert (r.json()["created"], r.json()["proposal"]["id"]) == (False, proposal["id"])
    assert r.json()["proposal"]["supports"] == 2

    listed = (await client.get("/v1/style-proposals", headers=c)).json()
    mine = next(p for p in listed["items"] if p["id"] == proposal["id"])
    assert (mine["supported"], mine["mine"], listed["threshold"]) == (False, False, 3)
    found = (await client.get("/v1/style-proposals", params={"q": "avant"}, headers=c)).json()
    assert proposal["id"] in [p["id"] for p in found["items"]]

    # Ritirare e rimettere la richiesta.
    r = await client.delete(f"/v1/style-proposals/{proposal['id']}/support", headers=b)
    assert r.json()["supports"] == 1
    await client.put(f"/v1/style-proposals/{proposal['id']}/support", headers=b)

    # La terza richiesta attiva lo stile: chi l'ha chiesto ci entra.
    r = await client.put(f"/v1/style-proposals/{proposal['id']}/support", headers=c)
    done = r.json()
    assert (done["status"], done["supports"]) == ("approved", 3)
    slug = done["style"]
    style = (await client.get(f"/v1/styles/{slug}", headers=a)).json()
    assert (style["name"], style["category"], style["joined"]) == (name, "stili", True)
    assert style["tagline"] == "Silhouette estreme, nero"
    assert style["member_count"] == 3
    # Approvata: non è più nell'elenco delle proposte aperte, e il nome ora è uno stile.
    listed = (await client.get("/v1/style-proposals", headers=c)).json()
    assert proposal["id"] not in [p["id"] for p in listed["items"]]
    r = await _propose(client, c, name)
    assert (r.status_code, r.json()["code"]) == (409, "style.exists")


async def test_nome_di_uno_stile_che_c_e_gia_o_non_ammesso(client, keys, db_admin, threshold):
    _, a, _ = await _person(client, keys, db_admin)
    for existing in ("Old Money", "gala", "GALÀ"):
        r = await _propose(client, a, existing)
        assert (r.status_code, r.json()["code"]) == (409, "style.exists"), existing
    r = await _propose(client, a, "!!")
    assert (r.status_code, r.json()["code"]) == (422, "proposal.bad_name")
    r = await _propose(client, a, "x" * 31)
    assert r.status_code == 422
    r = await _propose(client, a, "Nuovo", "auto")
    assert r.status_code == 422


async def test_al_massimo_tre_proposte_aperte(client, keys, db_admin, threshold):
    _, a, _ = await _person(client, keys, db_admin)
    tag = db_admin.execute("select gen_random_uuid()").fetchone()[0].hex[:5]
    for i in range(3):
        assert (await _propose(client, a, f"Prova {tag} {i}")).status_code == 200
    r = await _propose(client, a, f"Prova {tag} altra")
    assert (r.status_code, r.json()["code"]) == (409, "proposal.limit")


async def test_lo_staff_respinge_una_proposta(client, keys, db_admin, threshold):
    _, a, _ = await _person(client, keys, db_admin)
    _, b, _ = await _person(client, keys, db_admin)
    tag = db_admin.execute("select gen_random_uuid()").fetchone()[0].hex[:5]
    proposal = (await _propose(client, a, f"Respinta {tag}", "sport")).json()["proposal"]
    _, staff = await _staff(client, keys, db_admin)
    assert (await client.get("/v1/admin/style-proposals", headers=a)).status_code in (401, 403, 404)
    queue = (await client.get("/v1/admin/style-proposals", headers=staff)).json()
    row = next(p for p in queue if p["id"] == proposal["id"])
    assert (row["supports"], row["category"], row["proposer"]) == (1, "sport", row["proposer"])
    r = await client.post(
        f"/v1/admin/style-proposals/{proposal['id']}/reject",
        json={"note": "Doppione di Sport"},
        headers=staff,
    )
    assert (r.status_code, r.json()["status"]) == (200, "rejected")
    r = await client.put(f"/v1/style-proposals/{proposal['id']}/support", headers=b)
    assert r.status_code == 404
    listed = (await client.get("/v1/style-proposals", headers=b)).json()
    assert proposal["id"] not in [p["id"] for p in listed["items"]]
    # Una proposta respinta non blocca lo stesso nome per sempre.
    assert (await _propose(client, b, f"Respinta {tag}", "sport")).json()["created"] is True


async def test_richieste_insieme_alla_soglia_creano_un_solo_stile(
    client, keys, db_admin, threshold
):
    import asyncio

    _, a, _ = await _person(client, keys, db_admin)
    others = [(await _person(client, keys, db_admin))[1] for _ in range(3)]
    tag = db_admin.execute("select gen_random_uuid()").fetchone()[0].hex[:5]
    proposal = (await _propose(client, a, f"Insieme {tag}")).json()["proposal"]
    results = await asyncio.gather(
        *(client.put(f"/v1/style-proposals/{proposal['id']}/support", headers=h) for h in others)
    )
    assert all(r.status_code == 200 for r in results)
    count = db_admin.execute(
        "select count(*) from app.styles where name = %s", (f"Insieme {tag}",)
    ).fetchone()[0]
    assert count == 1
