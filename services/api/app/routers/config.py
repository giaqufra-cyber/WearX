"""GET /v1/config: impostazioni pubbliche che l'app legge all'avvio."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session

router = APIRouter(prefix="/v1", tags=["config"])


class StyleOut(BaseModel):
    slug: str
    name: str
    tagline: str
    tone: str = Field(pattern=r"^#[0-9A-F]{6}$")
    min_age_band: str
    seasonal: bool
    active_until: date | None


class LegalLinks(BaseModel):
    terms: str
    privacy: str
    community_rules: str
    feed_explainer: str


class ConfigOut(BaseModel):
    min_app_version: str
    # Versione dei termini da inviare alla creazione del profilo.
    terms_version: str
    feature_flags: dict[str, bool]
    styles: list[StyleOut]
    legal: LegalLinks


@router.get("/config", response_model=ConfigOut)
async def get_config(
    response: Response, session: Annotated[AsyncSession, Depends(get_session)]
) -> ConfigOut:
    settings = get_settings()
    rows = await session.execute(
        text(
            """
            select slug, name, tagline, tone, min_age_band::text as min_age_band,
                   (active_until is not null) as seasonal, active_until
              from app.styles
             where is_active
               and (active_from is null or active_from <= current_date)
               and (active_until is null or active_until >= current_date)
             order by sort_order, id
            """
        )
    )
    styles = [StyleOut.model_validate(dict(r._mapping)) for r in rows]
    response.headers["Cache-Control"] = "public, max-age=300"
    return ConfigOut(
        min_app_version=settings.min_app_version,
        terms_version=settings.terms_version,
        feature_flags=settings.feature_flags,
        styles=styles,
        legal=LegalLinks(
            terms="https://wearx.app/termini",
            privacy="https://wearx.app/privacy",
            community_rules="https://wearx.app/regole",
            feed_explainer="https://wearx.app/come-funziona-il-feed",
        ),
    )
