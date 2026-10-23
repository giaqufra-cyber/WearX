"""Cerca persone e suggerimenti (seduta 31)."""

from __future__ import annotations

import secrets
import string

import pytest

from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")


def _base() -> str:
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(7))


async def _person(client, keys, db_admin, nickname, *, business=False, minor=False):
    user_id, headers, profile = await onboard(
        client, keys, db_admin, minor=minor, nickname=nickname
    )
    if business:
        db_admin.execute(
            "update app.profiles set account_type = 'business' where id = %s", (user_id,)
        )
    return user_id, headers, profile["nickname"]


async def _search(client, q, headers):
    r = await client.get("/v1/people/search", params={"q": q}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _nicks(client, q, headers):
    return [p["nickname"] for p in (await _search(client, q, headers))["items"]]


async def _suggested(client, headers):
    r = await client.get("/v1/people/suggestions", headers=headers)
    assert r.status_code == 200, r.text
    return {p["nickname"]: p for p in r.json()["items"]}


async def _follow(client, nick, headers):
    r = await client.post(f"/v1/users/{nick}/follow", headers=headers)
    assert r.status_code == 200, r.text


async def _accept(client, nick, headers):
    r = await client.post(
        "/v1/me/follow-requests", json={"nickname": nick, "decision": "accept"}, headers=headers
    )
    assert r.status_code == 204, r.text


async def test_cerca_per_inizio_contiene_e_somiglianza(client, keys, db_admin):
    base = _base()
    _, me, _ = await _person(client, keys, db_admin, f"{base}.io")
    _, _, anna = await _person(client, keys, db_admin, f"{base}.anna")
    _, friend_h, friend = await _person(client, keys, db_admin, f"{base}.zeta")
    _, _, lorenzo = await _person(client, keys, db_admin, f"{base}lorenzo")
    await _follow(client, friend, me)
    await _accept(client, f"{base}.io", friend_h)

    # Chi segui viene prima, anche se in ordine alfabetico verrebbe dopo; tu non compari.
    found = await _nicks(client, base, me)
    assert found[0] == friend
    assert set(found) == {friend, anna, lorenzo}
    # Maiuscole, @ e spazi non contano; il nickname esatto è sempre il primo.
    assert (await _nicks(client, f" @{base.upper()}.ANNA ", me))[0] == anna
    # Da 3 lettere anche "contiene" e un errore di battitura.
    assert anna in await _nicks(client, f"{base[2:]}.ann", me)
    assert lorenzo in await _nicks(client, f"{base}lorenzi", me)
    # Anche due lettere bastano, se è l'inizio di una parte del nickname (dopo il punto).
    assert anna in await _nicks(client, "an", me)
    # Errore di battitura su una parte del nickname.
    assert anna in await _nicks(client, f"{base}.ana", me)

    body = await _search(client, base, me)
    card = next(p for p in body["items"] if p["nickname"] == friend)
    assert card["following"] == "accepted"
    assert card["follows_you"] is False
    assert card["is_self"] is False
    # Il nickname esatto trova anche te stesso.
    assert (await _nicks(client, f"{base}.io", me))[0] == f"{base}.io"
    # Niente da cercare: nessun risultato, nessun errore (anche con caratteri strani).
    assert (await _search(client, "  @ ", me))["items"] == []
    assert (await _search(client, "' or 1=1 --", me))["query"] == "or11"


async def test_chi_non_si_fa_trovare_compare_solo_col_nickname_esatto(client, keys, db_admin):
    base = _base()
    _, me, _ = await _person(client, keys, db_admin, f"{base}.io")
    _, hidden_h, hidden = await _person(client, keys, db_admin, f"{base}.nascosto")
    r = await client.patch("/v1/me", json={"discoverable": False}, headers=hidden_h)
    assert (r.status_code, r.json()["discoverable"]) == (200, False)

    assert hidden not in await _nicks(client, base, me)
    assert await _nicks(client, hidden, me) == [hidden]
    # Chi già conosci (lo segui o l'hai chiesto) lo trovi anche se non si fa trovare.
    await _follow(client, hidden, me)
    assert hidden in await _nicks(client, base, me)


async def test_sedicenni_e_blocchi(client, keys, db_admin):
    base = _base()
    _, adult_h, adult = await _person(client, keys, db_admin, f"{base}.adulto")
    _, shop_h, shop = await _person(client, keys, db_admin, f"{base}.shop", business=True)
    _, teen_h, teen = await _person(client, keys, db_admin, f"{base}.teen", minor=True)
    _, teen2_h, _ = await _person(client, keys, db_admin, f"{base}.teen2", minor=True)

    # Un 16-17 di base non si fa trovare.
    me = (await client.get("/v1/me", headers=teen_h)).json()
    assert me["discoverable"] is False
    assert await _nicks(client, base, teen2_h) == [shop]
    assert (await _nicks(client, teen, teen2_h))[0] == teen  # col nickname esatto sì
    await client.patch("/v1/me", json={"discoverable": True}, headers=teen_h)
    assert set(await _nicks(client, base, teen2_h)) == {shop, teen}
    # Un maggiorenne privato non lo trova chi ha 16-17 anni, se non col nickname esatto.
    assert (await _nicks(client, adult, teen2_h))[0] == adult
    # Un maggiorenne non trova mai un 16-17, nemmeno col nickname esatto.
    assert teen not in await _nicks(client, base, adult_h)
    assert teen not in await _nicks(client, teen, adult_h)

    # Bloccati: spariscono nei due sensi, anche col nickname esatto.
    r = await client.put(f"/v1/users/{adult}/block", headers=shop_h)
    assert r.status_code in (200, 204), r.text
    assert await _nicks(client, adult, shop_h) == []
    assert await _nicks(client, shop, adult_h) == []


async def test_suggerimenti_con_motivo_e_x(client, keys, db_admin):
    base = _base()
    me_id, me, me_nick = await _person(client, keys, db_admin, f"{base}.io")
    _, _, shop = await _person(client, keys, db_admin, f"{base}.shop", business=True)
    _, friend_h, friend = await _person(client, keys, db_admin, f"{base}.amico", business=True)
    _, other_h, other = await _person(client, keys, db_admin, f"{base}.altro")
    _, fan_h, fan = await _person(client, keys, db_admin, f"{base}.fan")
    _, blocked_h, blocked = await _person(client, keys, db_admin, f"{base}.bloccato")

    await _follow(client, friend, me)  # Business: seguito subito
    await _follow(client, other, friend_h)
    await _accept(client, friend, other_h)
    await _follow(client, shop, friend_h)
    await _follow(client, me_nick, fan_h)
    await _accept(client, fan, me)
    await _follow(client, blocked, friend_h)
    await _accept(client, friend, blocked_h)
    assert (await client.put(f"/v1/users/{blocked}/block", headers=me)).status_code in (200, 204)

    got = await _suggested(client, me)
    assert friend not in got  # lo segui già
    assert me_nick not in got
    assert blocked not in got
    assert got[other]["reason"] == "mutuals"
    assert (got[other]["mutual_count"], got[other]["mutuals"]) == (1, [friend])
    assert got[fan]["reason"] == "follows_you"
    assert got[shop]["reason"] == "mutuals"

    r = await client.post(f"/v1/people/suggestions/{other}/dismiss", headers=me)
    assert r.status_code == 204
    again = await client.post(f"/v1/people/suggestions/{other}/dismiss", headers=me)
    assert again.status_code == 204
    got = await _suggested(client, me)
    assert other not in got
    # Chi segui non viene più proposto.
    await _follow(client, shop, me)
    assert shop not in await _suggested(client, me)
    assert (
        await client.post("/v1/people/suggestions/nessuno.qui/dismiss", headers=me)
    ).status_code == 404

    # Nei dati scaricabili c'è chi hai tolto dai suggerimenti.
    rows = db_admin.execute(
        "select count(*) from app.suggestion_dismissals where user_id = %s", (me_id,)
    ).fetchone()
    assert rows[0] == 1


async def test_ai_sedicenni_niente_maggiorenni_privati_suggeriti(client, keys, db_admin):
    base = _base()
    _, teen_h, teen = await _person(client, keys, db_admin, f"{base}.teen", minor=True)
    _, shop_h, shop = await _person(client, keys, db_admin, f"{base}.shop", business=True)
    _, adult_h, adult = await _person(client, keys, db_admin, f"{base}.adulto")
    _, teen2_h, teen2 = await _person(client, keys, db_admin, f"{base}.teen2", minor=True)
    await client.patch("/v1/me", json={"discoverable": True}, headers=teen2_h)
    # Il teen segue lo shop e lo shop segue un adulto privato: amico di amico, ma non per un
    # 16-17. L'altro teen ha gli stessi stili e si fa trovare.
    await _follow(client, shop, teen_h)
    await _follow(client, adult, shop_h)
    await _accept(client, shop, adult_h)

    got = await _suggested(client, teen_h)
    assert adult not in got
    assert teen2 in got
    assert got[teen2]["reason"] == "styles"
    # A un maggiorenne non si propone mai un 16-17.
    assert teen not in await _suggested(client, adult_h)
    assert teen2 not in await _suggested(client, shop_h)
