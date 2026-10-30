"""Luogo del fit (seduta 35)."""

from __future__ import annotations

import httpx
import pytest

from app.errors import ApiError
from app.places import (
    FakeProvider,
    PhotonProvider,
    Place,
    from_photon,
    parse_place_token,
    place_token,
    search_places,
)
from tests.conftest import ready_upload
from tests.test_notifications import _person

pytestmark = pytest.mark.usefixtures("store")


async def _search(client, headers, q, **extra):
    r = await client.get("/v1/places", params={"q": q}, headers={**headers, **extra})
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def _publish(client, db_admin, user_id, headers, place=None):
    body = {"style": "old-money", "media": [str(ready_upload(db_admin, user_id))]}
    if place is not None:
        body["place"] = place
    return await client.post("/v1/posts", json=body, headers=headers)


async def test_cerca_un_luogo(client, keys, db_admin):
    _, me, _ = await _person(client, keys, db_admin)
    [scala] = await _search(client, me, "scala")
    assert (scala["name"], scala["detail"], scala["kind"]) == (
        "Teatro alla Scala",
        "Milano, Italia",
        "venue",
    )
    assert parse_place_token(scala["ref"]) is not None
    # In inglese i nomi e i paesi in inglese; senza accenti si trova lo stesso.
    [en] = await _search(client, me, "scala", **{"Accept-Language": "en"})
    assert (en["name"], en["detail"]) == ("La Scala", "Milan, Italy")
    assert [p["name"] for p in await _search(client, me, "muse")] == ["MUSE - Museo delle Scienze"]
    assert await _search(client, me, "m") == []  # troppo corto
    assert (await client.get("/v1/places", params={"q": "x" * 81}, headers=me)).status_code == 422


async def test_16_17_solo_citta_e_zone(client, keys, db_admin):
    minor_id, minor, _ = await _person(client, keys, db_admin, minor=True)
    found = await _search(client, minor, "milano")
    assert {p["kind"] for p in found} <= {"city", "area", "region", "country"}
    assert "Milano" in [p["name"] for p in found]
    assert "Teatro alla Scala" not in [p["name"] for p in found]
    # Un codice per un posto preciso (preso da un adulto) non passa.
    _, adult, _ = await _person(client, keys, db_admin)
    [scala] = await _search(client, adult, "scala")
    r = await _publish(client, db_admin, minor_id, minor, scala["ref"])
    assert (r.status_code, r.json()["code"]) == (422, "place.not_allowed")
    [city] = [p for p in found if p["name"] == "Milano"]
    r = await _publish(client, db_admin, minor_id, minor, city["ref"])
    assert r.status_code == 201, r.text
    assert r.json()["place"]["name"] == "Milano"


async def test_pubblicare_cambiare_e_togliere_il_luogo(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    db_admin.execute(
        "update app.profiles set account_type = 'business' where id = %s", (author_id,)
    )
    [scala] = await _search(client, author, "scala")
    r = await _publish(client, db_admin, author_id, author, scala["ref"])
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["place"] == {
        "name": "Teatro alla Scala",
        "detail": "Milano, Italia",
        "kind": "venue",
        "lat": 45.46744,
        "lon": 9.18951,
    }
    # Lo vede anche chi guarda il fit.
    _, viewer, _ = await _person(client, keys, db_admin)
    seen = (await client.get(f"/v1/posts/{post['id']}", headers=viewer)).json()
    assert seen["place"]["name"] == "Teatro alla Scala"

    # Lo stesso luogo, su due fit, si salva una volta sola.
    r = await _publish(client, db_admin, author_id, author, scala["ref"])
    assert r.status_code == 201
    count = db_admin.execute(
        "select count(*) from app.places where name = 'Teatro alla Scala'"
    ).fetchone()
    assert count == (1,)

    [brera] = await _search(client, author, "brera")
    r = await client.patch(f"/v1/posts/{post['id']}", json={"place": brera["ref"]}, headers=author)
    assert r.json()["place"]["name"] == "Brera"
    # Cambiare la didascalia non tocca il luogo; null lo toglie.
    r = await client.patch(f"/v1/posts/{post['id']}", json={"caption": "Prima"}, headers=author)
    assert r.json()["place"]["name"] == "Brera"
    r = await client.patch(f"/v1/posts/{post['id']}", json={"place": None}, headers=author)
    assert r.json()["place"] is None

    # Su un fit anonimo (profilo privato che non segui) il luogo non si vede.
    private_id, private, _ = await _person(client, keys, db_admin)
    r = await _publish(client, db_admin, private_id, private, scala["ref"])
    hidden = (await client.get(f"/v1/posts/{r.json()['id']}", headers=viewer)).json()
    assert (hidden["author"], hidden["place"]) == (None, None)
    assert r.json()["place"]["name"] == "Teatro alla Scala"  # chi l'ha pubblicato lo vede

    # Senza luogo si pubblica come sempre.
    r = await _publish(client, db_admin, author_id, author)
    assert r.json()["place"] is None


async def test_codice_del_luogo_non_valido(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    [scala] = await _search(client, author, "scala")
    forged = Place("fake", "Fx", "venue", "Casa di Mario", "Via Roma 1", "IT", 45.0, 9.0)
    tampered = place_token(forged)[:-4] + "AAAA"
    for ref in ("rotto", tampered, scala["ref"][:-2]):
        r = await _publish(client, db_admin, author_id, author, ref)
        assert (r.status_code, r.json()["code"]) == (422, "place.invalid"), ref


async def test_luogo_nell_archivio_dei_dati(client, keys, db_admin):
    from app.db import session_scope
    from app.privacy import collect

    author_id, author, _ = await _person(client, keys, db_admin)
    trento = next(p for p in await _search(client, author, "trento") if p["name"] == "Trento")
    assert (await _publish(client, db_admin, author_id, author, trento["ref"])).status_code == 201
    async with session_scope() as session:
        members = await collect(session, author_id)
    fits = members["fit.json"]
    assert fits[0]["luogo"] == "Trento, Trentino-Alto Adige, Italia"


# ---------- Photon ----------

FEATURES = [
    {  # un locale con nome: sì
        "geometry": {"type": "Point", "coordinates": [9.18951, 45.46744]},
        "properties": {
            "osm_id": 1,
            "osm_type": "W",
            "osm_key": "amenity",
            "osm_value": "theatre",
            "type": "house",
            "name": "Teatro alla Scala",
            "street": "Via Filodrammatici",
            "housenumber": "2",
            "city": "Milano",
            "district": "Municipio 1",
            "country": "Italia",
            "countrycode": "it",
        },
    },
    {  # un indirizzo senza nome: no
        "geometry": {"type": "Point", "coordinates": [9.1, 45.4]},
        "properties": {
            "osm_id": 2,
            "osm_type": "N",
            "osm_key": "place",
            "osm_value": "house",
            "type": "house",
            "street": "Via Roma",
            "housenumber": "10",
            "city": "Milano",
            "country": "Italia",
        },
    },
    {  # una casa con nome: no
        "geometry": {"type": "Point", "coordinates": [9.2, 45.5]},
        "properties": {
            "osm_id": 3,
            "osm_type": "W",
            "osm_key": "building",
            "osm_value": "detached",
            "type": "house",
            "name": "Villa Rossi",
            "city": "Milano",
        },
    },
    {  # una città
        "geometry": {"type": "Point", "coordinates": [9.18963, 45.46419]},
        "properties": {
            "osm_id": 4,
            "osm_type": "R",
            "osm_key": "place",
            "osm_value": "city",
            "type": "city",
            "name": "Milano",
            "state": "Lombardia",
            "country": "Italia",
            "countrycode": "IT",
        },
    },
    {  # una via
        "geometry": {"type": "Point", "coordinates": [9.19582, 45.46846]},
        "properties": {
            "osm_id": 5,
            "osm_type": "W",
            "osm_key": "highway",
            "osm_value": "pedestrian",
            "type": "street",
            "name": "Via Monte Napoleone",
            "city": "Milano",
            "country": "Italia",
        },
    },
]


def test_risultati_di_photon():
    places = [p for f in FEATURES if (p := from_photon(f)) is not None]
    assert [(p.name, p.kind, p.detail) for p in places] == [
        ("Teatro alla Scala", "venue", "Municipio 1, Milano, Italia"),
        ("Milano", "city", "Lombardia, Italia"),
        ("Via Monte Napoleone", "street", "Milano, Italia"),
    ]
    assert places[0].ref == "W1" and places[0].country_code == "IT"
    assert (places[0].lat, places[0].lon) == (45.46744, 9.18951)


async def test_richiesta_a_photon():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"type": "FeatureCollection", "features": FEATURES})

    provider = PhotonProvider(
        "https://photon.test/",
        client=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    found = await provider.search("milano", "en", minor=True)
    assert seen[0].url.path == "/api"
    params = seen[0].url.params
    assert params["q"] == "milano" and params["lang"] == "en"
    assert "city" in params.get_list("layer") and "house" not in params.get_list("layer")
    assert len(found) == 3
    # Il filtro sull'età vale anche se Photon restituisse altro.
    filtered = await search_places("milano photon", "it", minor=True, provider=provider)
    assert [p.kind for p in filtered] == ["city"]
    seen.clear()
    await provider.search("milano", "it", minor=False)
    assert "lang" not in seen[0].url.params and "layer" not in seen[0].url.params


async def test_photon_non_risponde():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502)

    provider = PhotonProvider(
        "https://photon.test",
        client=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ApiError) as caught:
        await search_places("qualcosa di nuovo", "it", minor=False, provider=provider)
    assert (caught.value.status, caught.value.code) == (503, "places.unavailable")


async def test_elenco_finto_senza_accenti():
    found = await FakeProvider().search("monaco", "it", minor=False)
    assert found[0].name == "Monaco di Baviera"
    found = await FakeProvider().search("munich", "en", minor=False)
    assert found[0].name == "Munich"
