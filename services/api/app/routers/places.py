"""Ricerca del luogo di un fit (seduta 35). Vedi app/places.py."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.i18n import RequestLang
from app.places import QUERY_MAX, PlaceResults, search_places, suggestion
from app.profiles import CurrentProfile
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1", tags=["places"])


@router.get(
    "/places",
    response_model=PlaceResults,
    dependencies=[Depends(rate_limit("places", 60, 60))],
)
async def find_places(
    profile: CurrentProfile,
    lang: RequestLang,
    q: Annotated[str, Query(max_length=QUERY_MAX)] = "",
) -> PlaceResults:
    """Luoghi con un nome (mai indirizzi di casa); per chi ha 16-17 anni solo città e zone."""
    found = await search_places(q, lang, minor=not profile.is_adult)
    return PlaceResults(items=[suggestion(p) for p in found])
