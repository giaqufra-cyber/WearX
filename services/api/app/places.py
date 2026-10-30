"""Luogo del fit (seduta 35): ricerca dei luoghi su mappa e luoghi salvati.

Come funziona:
- L'app cerca con `GET /v1/places?q=…`; il server chiede a Photon (geocoder di komoot su dati
  OpenStreetMap) e restituisce al massimo 8 luoghi. La richiesta parte dal server: Photon non
  vede né l'indirizzo IP né l'account di chi cerca. Non usiamo mai la posizione del telefono.
- Solo luoghi con un nome (un locale, un negozio, una via, un quartiere, una città): gli
  indirizzi senza nome e le case private si scartano, così non si può segnare dove abita qualcuno.
- Chi ha 16-17 anni può scegliere solo la città (o il quartiere, la regione, il paese).
- Ogni risultato arriva con un codice firmato (`ref`): quando si pubblica, il server si fida dei
  dati del luogo solo se il codice è integro, e salva il luogo in `places`.
- Risultati in cache per un giorno (Redis), per non chiedere a Photon due volte la stessa cosa.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError
from app.i18n import Lang
from app.redis_client import get_redis

log = logging.getLogger("wearx.places")

Kind = Literal["venue", "street", "area", "city", "region", "country"]
# Per chi ha 16-17 anni: niente posti precisi, solo zone.
MINOR_KINDS: frozenset[str] = frozenset({"area", "city", "region", "country"})
MAX_RESULTS = 8
QUERY_MIN, QUERY_MAX = 2, 80
CACHE_SECONDS = 86400
_SIG = 12


@dataclass(frozen=True, slots=True)
class Place:
    provider: str
    ref: str
    kind: Kind
    name: str
    detail: str | None
    country_code: str | None
    lat: float
    lon: float


class PlaceSuggestion(BaseModel):
    """Un risultato della ricerca. `ref` si rimanda così com'è quando si pubblica il fit."""

    ref: str
    name: str
    detail: str | None
    kind: Kind


class PlaceResults(BaseModel):
    items: list[PlaceSuggestion]


class PlaceOut(BaseModel):
    """Il luogo di un fit. Le coordinate sono quelle del luogo, per aprirlo in Mappe."""

    name: str
    detail: str | None
    kind: Kind
    lat: float
    lon: float


# ---------- Codice firmato ----------


def _sign(payload: bytes) -> bytes:
    pepper = get_settings().vote_pepper.get_secret_value().encode()
    return hmac.new(pepper, b"place:" + payload, hashlib.sha256).digest()[:_SIG]


def place_token(place: Place) -> str:
    payload = json.dumps(asdict(place), separators=(",", ":"), ensure_ascii=False).encode()
    raw = payload + _sign(payload)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def parse_place_token(token: str) -> Place | None:
    if not token or len(token) > 1200:
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None
    payload, signature = raw[:-_SIG], raw[-_SIG:]
    if len(raw) <= _SIG or not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        return Place(**json.loads(payload))
    except (TypeError, ValueError):
        return None


def suggestion(place: Place) -> PlaceSuggestion:
    return PlaceSuggestion(
        ref=place_token(place), name=place.name, detail=place.detail, kind=place.kind
    )


# ---------- Fornitori ----------


class PlaceProvider(Protocol):
    name: str

    async def search(self, query: str, lang: Lang, *, minor: bool) -> list[Place]: ...


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# Case e abitazioni: mai, anche se hanno un nome.
_HOMES = frozenset(
    {"house", "residential", "apartments", "detached", "semidetached_house", "terrace", "bungalow"}
)
_CITY_VALUES = frozenset({"city", "town", "village", "hamlet", "municipality"})


def _kind(props: dict[str, Any]) -> Kind:
    kind = str(props.get("type") or "")
    if kind == "city" or (
        props.get("osm_key") == "place" and props.get("osm_value") in _CITY_VALUES
    ):
        return "city"
    if kind in ("district", "locality"):
        return "area"
    if kind in ("county", "state"):
        return "region"
    if kind == "country":
        return "country"
    if kind == "street":
        return "street"
    return "venue"


def _detail(kind: Kind, props: dict[str, Any], name: str) -> str | None:
    if kind == "country":
        parts: list[Any] = []
    elif kind == "region":
        parts = [props.get("country")]
    elif kind == "city":
        parts = [props.get("state"), props.get("country")]
    else:
        town = props.get("city") or props.get("locality") or props.get("county")
        parts = [props.get("district") if kind == "venue" else None, town, props.get("country")]
    out: list[str] = []
    for part in parts:
        value = str(part).strip() if part else ""
        if value and value != name and value not in out:
            out.append(value)
    return ", ".join(out)[:160] or None


def from_photon(feature: dict[str, Any]) -> Place | None:
    """Un risultato di Photon (GeoJSON) -> luogo, oppure None se non lo mostriamo."""
    props = feature.get("properties") or {}
    name = str(props.get("name") or "").strip()
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if not name or len(coords) != 2:
        return None  # senza nome = un indirizzo: non si segna
    if props.get("osm_key") in ("building", "place") and props.get("osm_value") in _HOMES:
        return None
    osm_id, osm_type = props.get("osm_id"), str(props.get("osm_type") or "")
    if osm_id is None or osm_type not in ("N", "W", "R"):
        return None
    kind = _kind(props)
    code = str(props.get("countrycode") or "").upper()
    return Place(
        provider="photon",
        ref=f"{osm_type}{osm_id}",
        kind=kind,
        name=name[:120],
        detail=_detail(kind, props, name),
        country_code=code if len(code) == 2 and code.isalpha() else None,
        lat=round(float(coords[1]), 5),
        lon=round(float(coords[0]), 5),
    )


class PhotonProvider:
    """Photon (https://photon.komoot.io, o un'istanza propria)."""

    name = "photon"

    def __init__(self, base_url: str, client: Callable[[], httpx.AsyncClient] | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client or (
            lambda: httpx.AsyncClient(
                timeout=4.0, headers={"User-Agent": "WearX/1.0 (+https://wearx.app)"}
            )
        )

    async def search(self, query: str, lang: Lang, *, minor: bool) -> list[Place]:
        params: list[tuple[str, str | int | float | bool | None]] = [("q", query), ("limit", 15)]
        # Photon ha i nomi in inglese; senza `lang` usa quelli locali (in Italia, l'italiano).
        if lang == "en":
            params.append(("lang", "en"))
        if minor:
            params += [
                ("layer", layer)
                for layer in ("city", "district", "locality", "county", "state", "country")
            ]
        async with self._client() as client:
            response = await client.get(f"{self.base_url}/api", params=params)
            response.raise_for_status()
            features = response.json().get("features") or []
        return [p for f in features if (p := from_photon(f)) is not None]


# (nome, nome in inglese, tipo, dettaglio, dettaglio in inglese, paese, lat, lon)
_FAKE: list[tuple[str, str, Kind, str | None, str | None, str, float, float]] = [
    ("Milano", "Milan", "city", "Lombardia, Italia", "Lombardy, Italy", "IT", 45.46419, 9.18963),
    (
        "Teatro alla Scala",
        "La Scala",
        "venue",
        "Milano, Italia",
        "Milan, Italy",
        "IT",
        45.46744,
        9.18951,
    ),
    (
        "Galleria Vittorio Emanuele II",
        "Galleria Vittorio Emanuele II",
        "venue",
        "Milano, Italia",
        "Milan, Italy",
        "IT",
        45.46566,
        9.19003,
    ),
    (
        "Via Monte Napoleone",
        "Via Monte Napoleone",
        "street",
        "Milano, Italia",
        "Milan, Italy",
        "IT",
        45.46846,
        9.19582,
    ),
    ("Brera", "Brera", "area", "Milano, Italia", "Milan, Italy", "IT", 45.47206, 9.18752),
    ("Navigli", "Navigli", "area", "Milano, Italia", "Milan, Italy", "IT", 45.45128, 9.17588),
    (
        "Trento",
        "Trento",
        "city",
        "Trentino-Alto Adige, Italia",
        "Trentino-South Tyrol, Italy",
        "IT",
        46.06787,
        11.12108,
    ),
    (
        "Piazza Duomo",
        "Piazza Duomo",
        "street",
        "Trento, Italia",
        "Trento, Italy",
        "IT",
        46.06718,
        11.12148,
    ),
    (
        "MUSE - Museo delle Scienze",
        "MUSE - Science Museum",
        "venue",
        "Trento, Italia",
        "Trento, Italy",
        "IT",
        46.06276,
        11.11328,
    ),
    (
        "Teatro Sociale",
        "Teatro Sociale",
        "venue",
        "Trento, Italia",
        "Trento, Italy",
        "IT",
        46.06912,
        11.12462,
    ),
    (
        "Bolzano",
        "Bolzano",
        "city",
        "Trentino-Alto Adige, Italia",
        "Trentino-South Tyrol, Italy",
        "IT",
        46.49067,
        11.33982,
    ),
    (
        "Madonna di Campiglio",
        "Madonna di Campiglio",
        "city",
        "Trentino-Alto Adige, Italia",
        "Trentino-South Tyrol, Italy",
        "IT",
        46.22975,
        10.82676,
    ),
    ("Roma", "Rome", "city", "Lazio, Italia", "Lazio, Italy", "IT", 41.89332, 12.48293),
    ("Colosseo", "Colosseum", "venue", "Roma, Italia", "Rome, Italy", "IT", 41.89021, 12.49223),
    ("Firenze", "Florence", "city", "Toscana, Italia", "Tuscany, Italy", "IT", 43.76956, 11.25581),
    (
        "Ponte Vecchio",
        "Ponte Vecchio",
        "venue",
        "Firenze, Italia",
        "Florence, Italy",
        "IT",
        43.76792,
        11.25314,
    ),
    (
        "Monaco di Baviera",
        "Munich",
        "city",
        "Baviera, Germania",
        "Bavaria, Germany",
        "DE",
        48.13719,
        11.57549,
    ),
    (
        "Englischer Garten",
        "English Garden",
        "venue",
        "Monaco di Baviera, Germania",
        "Munich, Germany",
        "DE",
        48.16419,
        11.60539,
    ),
    (
        "Oktoberfest - Theresienwiese",
        "Oktoberfest - Theresienwiese",
        "venue",
        "Monaco di Baviera, Germania",
        "Munich, Germany",
        "DE",
        48.13151,
        11.54957,
    ),
]


class FakeProvider:
    """Elenco fisso, per sviluppo, test, E2E e demo (si cerca anche senza accenti)."""

    name = "fake"

    async def search(self, query: str, lang: Lang, *, minor: bool) -> list[Place]:
        needle = _fold(query)
        out = []
        for it, en, kind, detail_it, detail_en, code, lat, lon in _FAKE:
            if minor and kind not in MINOR_KINDS:
                continue
            haystack = _fold(" ".join(filter(None, (it, en, detail_it, detail_en))))
            if needle not in haystack:
                continue
            name, detail = (en, detail_en) if lang == "en" else (it, detail_it)
            ref = "F" + hashlib.sha1(it.encode()).hexdigest()[:10]  # noqa: S324 - non crittografico
            out.append(Place("fake", ref, kind, name, detail, code, lat, lon))
        return out


def get_provider() -> PlaceProvider | None:
    settings = get_settings()
    if settings.places_provider == "photon":
        return PhotonProvider(settings.places_url)
    if settings.places_provider == "fake":
        return FakeProvider()
    return None


# ---------- Ricerca ----------


async def search_places(
    query: str, lang: Lang, *, minor: bool, provider: PlaceProvider | None = None
) -> list[Place]:
    provider = provider or get_provider()
    if provider is None:
        raise ApiError(503, "places.unavailable", "Ricerca dei luoghi non disponibile")
    clean = " ".join(query.split())[:QUERY_MAX]
    if len(clean) < QUERY_MIN:
        return []
    digest = hashlib.sha256(_fold(clean).encode()).hexdigest()[:32]
    key = f"places:{provider.name}:{lang}:{'m' if minor else 'a'}:{digest}"
    redis = get_redis()
    try:
        cached = await redis.get(key)
    except Exception:  # senza cache si cerca lo stesso
        log.warning("cache dei luoghi non raggiungibile")
        cached = None
    if cached is not None:
        return [Place(**p) for p in json.loads(cached)]
    try:
        found = await provider.search(clean, lang, minor=minor)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("ricerca luoghi non riuscita: %s", type(exc).__name__)
        raise ApiError(
            503, "places.unavailable", "Ricerca dei luoghi non disponibile, riprova"
        ) from exc
    seen: set[str] = set()
    places: list[Place] = []
    for place in found:
        if minor and place.kind not in MINOR_KINDS:
            continue
        if place.ref in seen:
            continue
        seen.add(place.ref)
        places.append(place)
        if len(places) == MAX_RESULTS:
            break
    try:
        await redis.set(key, json.dumps([asdict(p) for p in places]), ex=CACHE_SECONDS)
    except Exception:
        log.warning("cache dei luoghi non raggiungibile")
    return places


# ---------- Luogo di un fit ----------


async def save_place(session: AsyncSession, token: str, *, minor: bool) -> uuid.UUID:
    """Dal codice firmato al luogo salvato (lo stesso luogo una sola volta)."""
    place = parse_place_token(token)
    if place is None:
        raise ApiError(422, "place.invalid", "Luogo non valido: cercalo di nuovo")
    if minor and place.kind not in MINOR_KINDS:
        raise ApiError(422, "place.not_allowed", "Puoi indicare solo la città")
    place_id = await session.scalar(
        text(
            """insert into app.places
                 (provider, provider_ref, kind, name, detail, country_code, lat, lon)
               values (:provider, :ref, :kind, :name, :detail, :cc, :lat, :lon)
               on conflict (provider, provider_ref) do update
                  set kind = excluded.kind, name = excluded.name, detail = excluded.detail,
                      country_code = excluded.country_code, lat = excluded.lat, lon = excluded.lon
               returning id"""
        ),
        {
            "provider": place.provider,
            "ref": place.ref,
            "kind": place.kind,
            "name": place.name,
            "detail": place.detail,
            "cc": place.country_code,
            "lat": place.lat,
            "lon": place.lon,
        },
    )
    assert isinstance(place_id, uuid.UUID)
    return place_id
