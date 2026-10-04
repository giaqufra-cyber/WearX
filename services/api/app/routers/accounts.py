"""Account: disponibilità nickname, creazione profilo (onboarding), profilo personale."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentAuth
from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.profiles import (
    CurrentProfile,
    CurrentProfileAnyStatus,
    Profile,
    joined_style_slugs,
    load_profile,
)
from app.ratelimit import rate_limit
from app.text_policy import clean_bio, nickname_problem

router = APIRouter(prefix="/v1", tags=["account"])

Session = Annotated[AsyncSession, Depends(get_session)]
NicknameStr = Annotated[str, Field(min_length=1, max_length=40)]


# ---------- Modelli ----------


class NicknameCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nickname: NicknameStr

    @field_validator("nickname")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return value.strip().lower()


class NicknameCheckOut(BaseModel):
    nickname: str
    available: bool
    reason: Literal["invalid", "reserved", "taken"] | None = None


class OnboardingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nickname: NicknameStr
    terms_version: str = Field(max_length=20)
    accept_community_rules: Literal[True]
    styles: list[str] = Field(min_length=1, max_length=12)
    account_type: Literal["private", "business"] = "private"

    @field_validator("nickname")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("styles")
    @classmethod
    def _unique_styles(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("stili ripetuti")
        return value


class ProfileOut(BaseModel):
    id: uuid.UUID
    nickname: str
    bio: str | None
    account_type: Literal["private", "business"]
    age_band: Literal["16_17", "18_plus"]
    hide_prices: bool
    hide_vote_count: bool
    status: Literal["active", "suspended", "pending_deletion"]
    styles: list[str]
    created_at: datetime


class ProfileUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bio: str | None = Field(default=None, max_length=600)
    hide_prices: bool | None = None
    hide_vote_count: bool | None = None
    account_type: Literal["private", "business"] | None = None


async def _profile_out(session: AsyncSession, profile: Profile) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        nickname=profile.nickname,
        bio=profile.bio,
        account_type=profile.account_type,
        age_band=profile.age_band,
        hide_prices=profile.hide_prices,
        hide_vote_count=profile.hide_vote_count,
        status=profile.status,
        styles=await joined_style_slugs(session, profile.id),
        created_at=profile.created_at,
    )


def _check_business_allowed(account_type: str, is_adult: bool) -> None:
    if account_type != "business":
        return
    if not get_settings().feature_flags.get("business_accounts", False):
        raise ApiError(403, "feature.disabled", "Gli account Business non sono ancora disponibili")
    if not is_adult:
        raise ApiError(
            403, "account.business_requires_adult", "Il profilo Business è solo per maggiorenni"
        )


# ---------- Endpoint ----------


@router.post(
    "/auth/nickname-check",
    response_model=NicknameCheckOut,
    dependencies=[Depends(rate_limit("nickname_check", 20, 60, by="ip"))],
)
async def nickname_check(body: NicknameCheckIn, session: Session) -> NicknameCheckOut:
    problem = nickname_problem(body.nickname)
    if problem:
        return NicknameCheckOut(nickname=body.nickname, available=False, reason=problem)
    taken = await session.scalar(
        text("select exists(select 1 from app.profiles where nickname = :n)"), {"n": body.nickname}
    )
    if taken:
        return NicknameCheckOut(nickname=body.nickname, available=False, reason="taken")
    return NicknameCheckOut(nickname=body.nickname, available=True)


@router.post(
    "/onboarding/profile",
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("onboarding", 10, 3600))],
)
async def create_profile(body: OnboardingIn, auth: CurrentAuth, session: Session) -> ProfileOut:
    settings = get_settings()
    if await load_profile(session, auth.user_id) is not None:
        raise ApiError(409, "profile.exists", "Il profilo esiste già")

    if body.terms_version != settings.terms_version:
        raise ApiError(
            409,
            "terms.outdated",
            "I termini sono cambiati: rileggili e accettali di nuovo",
            extra={"terms_version": settings.terms_version},
        )

    problem = nickname_problem(body.nickname)
    if problem == "invalid":
        raise ApiError(422, "nickname.invalid", "Nickname non valido")
    if problem == "reserved":
        raise ApiError(422, "nickname.reserved", "Questo nickname non è disponibile")

    verification = (
        (
            await session.execute(
                text(
                    """select method, age_band::text as age_band, adult_on, completed_at
                     from app.age_verifications
                    where user_id = :u and status = 'passed'
                    order by completed_at desc limit 1"""
                ),
                {"u": auth.user_id},
            )
        )
        .mappings()
        .first()
    )
    if verification is None:
        raise ApiError(409, "age.verification_required", "Prima va verificata l'età")
    is_adult = verification["age_band"] == "18_plus"

    _check_business_allowed(body.account_type, is_adult)

    styles = (
        (
            await session.execute(
                text(
                    """select id, slug, min_age_band::text as min_age_band from app.styles
                    where slug = any(:slugs) and is_active
                      and (active_from is null or active_from <= current_date)
                      and (active_until is null or active_until >= current_date)"""
                ),
                {"slugs": body.styles},
            )
        )
        .mappings()
        .all()
    )
    found = {s["slug"] for s in styles}
    missing = [slug for slug in body.styles if slug not in found]
    if missing:
        raise ApiError(422, "style.not_found", "Stile non disponibile", extra={"styles": missing})
    if not is_adult and any(s["min_age_band"] == "18_plus" for s in styles):
        raise ApiError(403, "style.age_restricted", "Uno degli stili scelti è riservato ai 18+")

    try:
        await session.execute(
            text(
                """insert into app.profiles
                     (id, nickname, account_type, age_band, adult_on, age_verified_at, age_method,
                      terms_version, terms_accepted_at)
                   values (:id, :nickname, cast(:account_type as app.account_type),
                           cast(:age_band as app.age_band), :adult_on, :verified_at, :method,
                           :terms_version, now())"""
            ),
            {
                "id": auth.user_id,
                "nickname": body.nickname,
                "account_type": body.account_type,
                "age_band": verification["age_band"],
                "adult_on": verification["adult_on"],
                "verified_at": verification["completed_at"],
                "method": verification["method"],
                "terms_version": body.terms_version,
            },
        )
        await session.execute(
            text(
                "insert into app.style_memberships (user_id, style_id) "
                "select :u, unnest(cast(:ids as smallint[]))"
            ),
            {"u": auth.user_id, "ids": [s["id"] for s in styles]},
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if "profiles_nickname_key" in str(exc.orig):
            raise ApiError(409, "nickname.taken", "Nickname già in uso") from None
        if "profiles_pkey" in str(exc.orig):
            raise ApiError(409, "profile.exists", "Il profilo esiste già") from None
        raise

    profile = await load_profile(session, auth.user_id)
    assert profile is not None
    return await _profile_out(session, profile)


@router.get("/me", response_model=ProfileOut)
async def get_me(profile: CurrentProfileAnyStatus, session: Session) -> ProfileOut:
    return await _profile_out(session, profile)


@router.patch(
    "/me",
    response_model=ProfileOut,
    dependencies=[Depends(rate_limit("profile_update", 30, 3600))],
)
async def update_me(body: ProfileUpdateIn, profile: CurrentProfile, session: Session) -> ProfileOut:
    changes: dict[str, object] = {}
    fields = body.model_fields_set
    if "bio" in fields:
        changes["bio"] = clean_bio(body.bio)
    if "hide_prices" in fields and body.hide_prices is not None:
        changes["hide_prices"] = body.hide_prices
    if "hide_vote_count" in fields and body.hide_vote_count is not None:
        changes["hide_vote_count"] = body.hide_vote_count
    if "account_type" in fields and body.account_type is not None:
        _check_business_allowed(body.account_type, profile.is_adult)
        changes["account_type"] = body.account_type

    if changes:
        # Nomi di colonna presi da una lista fissa, mai dall'input.
        allowed = {"bio", "hide_prices", "hide_vote_count", "account_type"}
        assert set(changes) <= allowed
        assignments = ", ".join(
            f"{col} = cast(:{col} as app.account_type)"
            if col == "account_type"
            else f"{col} = :{col}"
            for col in changes
        )
        await session.execute(
            text(f"update app.profiles set {assignments} where id = :id"),  # noqa: S608
            {**changes, "id": profile.id},
        )
        await session.commit()

    updated = await load_profile(session, profile.id)
    assert updated is not None
    return await _profile_out(session, updated)
