"""Attestazione del dispositivo (seduta 22).

1. L'app chiede una sfida (valida 5 minuti, una volta sola, legata a persona e accesso).
2. iOS: la prima volta "attesta" una chiave App Attest; ai nuovi accessi firma la sfida con la
   stessa chiave (asserzione). Android: chiede a Google Play un token per la sfida.
3. Se la verifica riesce, l'accesso (dispositivo collegato) risulta "verificato": i suoi voti
   pesano pieno (modalità "soft") o sono ammessi (modalità "required").
Il motivo di un rifiuto finisce nei log, mai nella risposta (non aiuta chi prova a ingannarla).
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.attest.apple import AttestationError, verify_assertion, verify_attestation
from app.attest.google import (
    GooglePlayDecoder,
    MetadataTokens,
    ServiceAccountTokens,
    TokenDecoder,
    check_verdict,
)
from app.auth import CurrentAuth
from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.profiles import CurrentProfile, Profile
from app.ratelimit import rate_limit
from app.redis_client import get_redis

log = logging.getLogger("wearx.attest")
router = APIRouter(
    prefix="/v1/me/attest",
    tags=["attest"],
    dependencies=[Depends(rate_limit("attest", 30, 3600))],
)

Session = Annotated[AsyncSession, Depends(get_session)]
CHALLENGE_TTL = 300


_http: httpx.AsyncClient | None = None


def _play_decoder() -> TokenDecoder:
    global _http
    settings = get_settings()
    _http = _http or httpx.AsyncClient(timeout=10)
    secret = settings.google_service_account_json
    if secret is not None:
        return GooglePlayDecoder(ServiceAccountTokens(secret.get_secret_value(), _http), _http)
    if settings.google_metadata_auth:
        return GooglePlayDecoder(MetadataTokens(_http), _http)
    raise ApiError(503, "attest.unavailable", "Verifica del dispositivo non disponibile")


# Sostituibile nei test (niente rete).
play_decoder_factory: Callable[[], TokenDecoder] = _play_decoder


class ChallengeOut(BaseModel):
    challenge: str
    expires_in: int


class AttestStatus(BaseModel):
    mode: Literal["off", "soft", "required"]
    attested: bool


class IosAttestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key_id: str = Field(min_length=40, max_length=64)
    attestation: str = Field(min_length=100, max_length=20_000)
    challenge: str = Field(min_length=20, max_length=100)


class IosAssertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key_id: str = Field(min_length=40, max_length=64)
    assertion: str = Field(min_length=20, max_length=4_000)
    challenge: str = Field(min_length=20, max_length=100)


class AndroidIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=20_000)
    challenge: str = Field(min_length=20, max_length=100)


def _session_id(auth: CurrentAuth) -> str:
    if not auth.session_id:
        raise ApiError(409, "attest.no_session", "Accesso senza sessione: rientra nell'app")
    return auth.session_id


async def _consume(challenge: str, profile: Profile, session_id: str) -> None:
    owner = await get_redis().getdel(f"attest:ch:{challenge}")
    if isinstance(owner, bytes):
        owner = owner.decode()
    if owner != f"{profile.id}:{session_id}":
        raise ApiError(422, "attest.failed", "Verifica del dispositivo non riuscita")


async def _mark(
    session: AsyncSession,
    profile: Profile,
    session_id: str,
    platform: Literal["ios", "android"],
    detail: str,
) -> None:
    result = await session.execute(
        text(
            """update app.devices
                  set attested_at = now(), attest_platform = :platform, attest_detail = :detail,
                      last_seen = now()
                where session_id = :sid and user_id = :me and revoked_at is null"""
        ),
        {"sid": session_id, "me": profile.id, "platform": platform, "detail": detail},
    )
    if not getattr(result, "rowcount", 0):
        await session.execute(
            text(
                """insert into app.devices
                     (session_id, user_id, label, platform, attested_at, attest_platform,
                      attest_detail)
                   values (:sid, :me, :label, :platform, now(), :platform, :detail)
                   on conflict (session_id) do nothing"""
            ),
            {
                "sid": session_id,
                "me": profile.id,
                "label": "iPhone" if platform == "ios" else "Android",
                "platform": platform,
                "detail": detail,
            },
        )
    await session.commit()


def _apple_ids() -> tuple[str, str]:
    settings = get_settings()
    if not settings.apple_team_id:
        raise ApiError(503, "attest.unavailable", "Verifica del dispositivo non disponibile")
    return settings.apple_team_id, settings.ios_bundle_id


def _failed(platform: str, profile: Profile, exc: Exception) -> ApiError:
    log.warning("attestazione %s rifiutata per %s: %s", platform, profile.id, exc)
    return ApiError(422, "attest.failed", "Verifica del dispositivo non riuscita")


@router.get("", response_model=AttestStatus)
async def attest_status(profile: CurrentProfile) -> AttestStatus:
    return AttestStatus(mode=get_settings().attestation_mode, attested=profile.session_attested)


@router.post("/challenge", response_model=ChallengeOut)
async def challenge(profile: CurrentProfile, auth: CurrentAuth) -> ChallengeOut:
    sid = _session_id(auth)
    value = secrets.token_urlsafe(32)
    await get_redis().set(f"attest:ch:{value}", f"{profile.id}:{sid}", ex=CHALLENGE_TTL)
    return ChallengeOut(challenge=value, expires_in=CHALLENGE_TTL)


@router.post("/ios", status_code=status.HTTP_204_NO_CONTENT)
async def ios_attest(
    body: IosAttestIn, profile: CurrentProfile, auth: CurrentAuth, session: Session
) -> Response:
    """Prima volta su questo iPhone: attestazione della chiave App Attest."""
    sid = _session_id(auth)
    team_id, bundle_id = _apple_ids()
    await _consume(body.challenge, profile, sid)
    try:
        key = verify_attestation(
            attestation_b64=body.attestation,
            challenge=body.challenge,
            key_id=body.key_id,
            team_id=team_id,
            bundle_id=bundle_id,
            allow_development=get_settings().app_attest_allow_development,
        )
    except AttestationError as exc:
        raise _failed("ios", profile, exc) from exc
    owner = await session.scalar(
        text(
            """insert into app.attest_keys (key_id, user_id, public_key, environment)
               values (:id, :me, :pk, :env)
               on conflict (key_id) do update set last_used_at = now()
               returning user_id"""
        ),
        {"id": key.key_id, "me": profile.id, "pk": key.public_key, "env": key.environment},
    )
    if owner != profile.id:
        # Una chiave è di un solo telefono e di una sola persona.
        await session.rollback()
        raise _failed("ios", profile, AttestationError("chiave già di un altro account"))
    await _mark(session, profile, sid, "ios", f"app_attest:{key.environment}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ios/assert", status_code=status.HTTP_204_NO_CONTENT)
async def ios_assert(
    body: IosAssertIn, profile: CurrentProfile, auth: CurrentAuth, session: Session
) -> Response:
    """Nuovo accesso su un iPhone già attestato: firma della sfida con la stessa chiave."""
    sid = _session_id(auth)
    team_id, bundle_id = _apple_ids()
    await _consume(body.challenge, profile, sid)
    row = (
        (
            await session.execute(
                text(
                    """select public_key, sign_count from app.attest_keys
                        where key_id = :id and user_id = :me for update"""
                ),
                {"id": body.key_id, "me": profile.id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        # Chiave sconosciuta (es. app reinstallata): l'app ripete l'attestazione.
        raise ApiError(404, "attest.unknown_key", "Chiave del dispositivo sconosciuta")
    try:
        counter = verify_assertion(
            assertion_b64=body.assertion,
            challenge=body.challenge,
            public_key=bytes(row["public_key"]),
            previous_counter=int(row["sign_count"]),
            team_id=team_id,
            bundle_id=bundle_id,
        )
    except AttestationError as exc:
        raise _failed("ios", profile, exc) from exc
    await session.execute(
        text(
            """update app.attest_keys set sign_count = :n, last_used_at = now()
                where key_id = :id"""
        ),
        {"n": counter, "id": body.key_id},
    )
    await _mark(session, profile, sid, "ios", "app_attest:assertion")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/android", status_code=status.HTTP_204_NO_CONTENT)
async def android_attest(
    body: AndroidIn, profile: CurrentProfile, auth: CurrentAuth, session: Session
) -> Response:
    sid = _session_id(auth)
    decoder = play_decoder_factory()
    await _consume(body.challenge, profile, sid)
    package = get_settings().android_package
    try:
        payload = await decoder.decode(package, body.token)
        verdict = check_verdict(payload, package=package, challenge=body.challenge)
    except AttestationError as exc:
        raise _failed("android", profile, exc) from exc
    await _mark(session, profile, sid, "android", "play_integrity:" + ",".join(verdict.device))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
