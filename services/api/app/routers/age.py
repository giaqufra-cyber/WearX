"""Verifica dell'età: avvio, stato, webhook del fornitore (sez. 11.2).

Flusso: l'app apre una sessione (metodo + data di nascita dichiarata), manda l'utente
alla pagina del fornitore, il fornitore notifica l'esito con un webhook firmato, l'app
legge lo stato. Nessuna immagine, documento o data di nascita viene salvata.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.age.base import ALL_METHODS, AgeProvider, Method, WebhookRejected
from app.age.decision import add_years, age_on, decide
from app.age.registry import get_provider
from app.auth import CurrentAuth
from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1", tags=["age"])

Session = Annotated[AsyncSession, Depends(get_session)]
Provider = Annotated[AgeProvider, Depends(get_provider)]

# Un "sotto i 16" da documento blocca nuovi tentativi per un anno.
UNDERAGE_BLOCK = timedelta(days=365)


# ---------- Modelli ----------


class AgeSessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Method
    # Data di nascita dichiarata in registrazione: usata solo per il confronto con l'esito
    # del fornitore, salvata come "data dei 18 anni" finché la verifica è aperta.
    declared_birth_date: date
    # Dove il fornitore riporta l'utente a fine verifica (wearx://…).
    return_url: str


class AgeSessionOut(BaseModel):
    id: uuid.UUID
    method: Method
    status: Literal["pending", "passed", "failed", "expired"]
    age_band: Literal["16_17", "18_plus"] | None = None
    failure_reason: Literal["underage", "inconsistent", "not_completed"] | None = None
    # Solo alla creazione: la pagina del fornitore.
    redirect_url: str | None = None


class AgeStatusOut(BaseModel):
    verified: bool
    age_band: Literal["16_17", "18_plus"] | None = None
    methods: list[Method]
    latest: AgeSessionOut | None = None


# ---------- Supporto ----------


def available_methods(provider: AgeProvider) -> list[Method]:
    flags = get_settings().feature_flags
    allowed = [m for m in ALL_METHODS if m in provider.methods]
    if not flags.get("spid_cie", False):
        allowed = [m for m in allowed if m not in ("spid", "cie")]
    return allowed


def _session_out(row: Any) -> AgeSessionOut:
    return AgeSessionOut(
        id=row["id"],
        method=row["method"],
        status=row["status"],
        age_band=row["age_band"],
        failure_reason=row["failure_reason"],
    )


_SELECT = """select id, method, status::text as status, age_band::text as age_band,
                    failure_reason, created_at
               from app.age_verifications"""


async def _expire_stale(session: AsyncSession, user_id: uuid.UUID) -> None:
    ttl = get_settings().age_session_ttl_seconds
    await session.execute(
        text(
            """update app.age_verifications
                  set status = 'expired', declared_adult_on = null, completed_at = now()
                where user_id = :u and status = 'pending'
                  and created_at < now() - make_interval(secs => :ttl)"""
        ),
        {"u": user_id, "ttl": ttl},
    )


async def _has_profile(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            text("select exists(select 1 from app.profiles where id = :u)"), {"u": user_id}
        )
    )


def _valid_return_url(url: str) -> bool:
    schemes = get_settings().age_return_schemes
    return len(url) <= 300 and url.startswith(schemes) and not any(c.isspace() for c in url)


# ---------- Endpoint per l'app ----------


@router.get("/age-verification", response_model=AgeStatusOut)
async def age_status(auth: CurrentAuth, session: Session, provider: Provider) -> AgeStatusOut:
    await _expire_stale(session, auth.user_id)
    await session.commit()
    passed = (
        (
            await session.execute(
                text(
                    _SELECT + " where user_id = :u and status = 'passed' "
                    "order by completed_at desc limit 1"
                ),
                {"u": auth.user_id},
            )
        )
        .mappings()
        .first()
    )
    latest = (
        (
            await session.execute(
                text(_SELECT + " where user_id = :u order by created_at desc limit 1"),
                {"u": auth.user_id},
            )
        )
        .mappings()
        .first()
    )
    return AgeStatusOut(
        verified=passed is not None,
        age_band=passed["age_band"] if passed else None,
        methods=available_methods(provider),
        latest=_session_out(latest) if latest else None,
    )


@router.post(
    "/age-verification/sessions",
    response_model=AgeSessionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("age_session", 5, 3600))],
)
async def start_age_session(
    body: AgeSessionIn, auth: CurrentAuth, session: Session, provider: Provider
) -> AgeSessionOut:
    today = datetime.now(UTC).date()
    if await _has_profile(session, auth.user_id):
        raise ApiError(409, "profile.exists", "Il profilo esiste già")
    if body.method not in available_methods(provider):
        raise ApiError(422, "age.method_unavailable", "Metodo di verifica non disponibile")
    if not _valid_return_url(body.return_url):
        raise ApiError(422, "age.bad_return_url", "Indirizzo di ritorno non ammesso")
    declared_age = age_on(body.declared_birth_date, today)
    if declared_age < 16:
        # Niente viene salvato: la registrazione si ferma qui (lo fa già anche l'app).
        raise ApiError(422, "age.underage", "WearX è riservata a chi ha almeno 16 anni")
    if declared_age > 110:
        raise ApiError(422, "age.invalid_birth_date", "Data di nascita non valida")

    await _expire_stale(session, auth.user_id)
    state = (
        (
            await session.execute(
                text(
                    """select
                         exists(select 1 from app.age_verifications
                                 where user_id = :u and status = 'passed') as passed,
                         exists(select 1 from app.age_verifications
                                 where user_id = :u and failure_reason = 'underage'
                                   and completed_at > now() - make_interval(days => :days))
                           as blocked"""
                ),
                {"u": auth.user_id, "days": UNDERAGE_BLOCK.days},
            )
        )
        .mappings()
        .one()
    )
    if state["passed"]:
        raise ApiError(409, "age.already_verified", "L'età è già verificata")
    if state["blocked"]:
        raise ApiError(403, "age.blocked", "WearX è riservata a chi ha almeno 16 anni")

    # Una sola verifica aperta per volta: le precedenti si chiudono.
    await session.execute(
        text(
            """update app.age_verifications
                  set status = 'expired', declared_adult_on = null, completed_at = now()
                where user_id = :u and status = 'pending'"""
        ),
        {"u": auth.user_id},
    )
    verification_id = uuid.uuid4()
    try:
        started = await provider.start(verification_id, body.method, body.return_url)
    except Exception:
        await session.rollback()
        raise ApiError(
            502, "age.provider_unavailable", "Il servizio di verifica non risponde, riprova"
        ) from None
    await session.execute(
        text(
            """insert into app.age_verifications
                 (id, user_id, method, status, provider, provider_ref, declared_adult_on)
               values (:id, :u, :method, 'pending', :provider, :ref, :declared)"""
        ),
        {
            "id": verification_id,
            "u": auth.user_id,
            "method": body.method,
            "provider": provider.name,
            "ref": started.provider_ref,
            "declared": add_years(body.declared_birth_date, 18),
        },
    )
    await session.commit()
    return AgeSessionOut(
        id=verification_id, method=body.method, status="pending", redirect_url=started.redirect_url
    )


@router.get("/age-verification/sessions/{verification_id}", response_model=AgeSessionOut)
async def get_age_session(
    verification_id: uuid.UUID, auth: CurrentAuth, session: Session
) -> AgeSessionOut:
    await _expire_stale(session, auth.user_id)
    await session.commit()
    row = (
        (
            await session.execute(
                text(_SELECT + " where id = :id and user_id = :u"),
                {"id": verification_id, "u": auth.user_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        # Stessa risposta per "non esiste" e "non è tua": niente indizi sugli ID altrui.
        raise ApiError(404, "age.session_not_found", "Verifica non trovata")
    return _session_out(row)


# ---------- Webhook del fornitore ----------


async def apply_webhook(
    session: AsyncSession, provider: AgeProvider, headers: dict[str, str], body: bytes
) -> None:
    try:
        result = provider.parse_webhook(headers, body)
    except WebhookRejected:
        raise ApiError(401, "webhook.rejected", "Webhook non valido") from None

    row = (
        (
            await session.execute(
                text(
                    """select id, status::text as status, declared_adult_on
                         from app.age_verifications
                        where provider = :p and provider_ref = :ref
                        for update"""
                ),
                {"p": provider.name, "ref": result.provider_ref},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "age.session_not_found", "Verifica non trovata")
    if row["status"] != "pending":
        # Il fornitore può ripetere lo stesso webhook: la prima risposta vale.
        await session.rollback()
        return

    decision = decide(result, row["declared_adult_on"], datetime.now(UTC).date())
    await session.execute(
        text(
            """update app.age_verifications
                  set status = cast(:status as app.age_check_status),
                      age_band = cast(:band as app.age_band),
                      adult_on = :adult_on,
                      failure_reason = :reason,
                      declared_adult_on = null,
                      completed_at = now()
                where id = :id"""
        ),
        {
            "status": decision.status,
            "band": decision.age_band,
            "adult_on": decision.adult_on,
            "reason": decision.failure_reason,
            "id": row["id"],
        },
    )
    await session.commit()


@router.post(
    "/webhooks/age/{provider_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("age_webhook", 120, 60, by="ip"))],
)
async def age_webhook(
    provider_name: str, request: Request, session: Session, provider: Provider
) -> Response:
    if provider_name != provider.name:
        raise ApiError(404, "webhook.unknown_provider", "Fornitore sconosciuto")
    body = await request.body()
    await apply_webhook(session, provider, dict(request.headers), body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
