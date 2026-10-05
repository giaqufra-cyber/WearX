"""Account Business: siti del negozio verificati (seduta 21).

Un Business aggiunge il dominio del suo negozio e pubblica un file con un codice su
https://<dominio>/.well-known/wearx-verify.txt; WearX lo legge (con il visitatore sicuro dei
link) e da quel momento i capi che puntano a quel sito mostrano "negozio verificato".
Un dominio verificato appartiene a un solo account.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ApiError
from app.link_check import VERIFY_FILE, NotFound, Unsafe, http_client, system_resolver, visit
from app.links import normalize_shop_url
from app.profiles import CurrentProfile, Profile
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1/me/shop-domains", tags=["business"])

Session = Annotated[AsyncSession, Depends(get_session)]
MAX_DOMAINS = 5

# Sostituibile nei test (niente rete).
resolver = system_resolver
client_factory = http_client


class ShopDomainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "zara.com", "www.zara.com" o anche "https://www.zara.com/it/".
    domain: str = Field(min_length=3, max_length=255)


class ShopDomainOut(BaseModel):
    domain: str
    verified: bool
    verified_at: datetime | None
    # Cosa pubblicare per la verifica.
    file_url: str
    file_content: str


def _require_business(profile: Profile) -> None:
    if profile.account_type != "business":
        raise ApiError(403, "business.required", "Serve un account Business")


def _domain(raw: str) -> str:
    value = raw.strip()
    if "://" not in value:
        value = f"https://{value}"
    _, domain = normalize_shop_url(value)
    return domain


def _out(row: dict[str, object]) -> ShopDomainOut:
    domain = str(row["domain"])
    verified_at = row["verified_at"]
    return ShopDomainOut(
        domain=domain,
        verified=verified_at is not None,
        verified_at=verified_at if isinstance(verified_at, datetime) else None,
        file_url=f"https://{domain}{VERIFY_FILE}",
        file_content=str(row["token"]),
    )


async def _rows(session: AsyncSession, me: object) -> list[ShopDomainOut]:
    rows = (
        (
            await session.execute(
                text(
                    """select domain, token, verified_at from app.business_domains
                        where user_id = :me order by created_at"""
                ),
                {"me": me},
            )
        )
        .mappings()
        .all()
    )
    return [_out(dict(r)) for r in rows]


@router.get("", response_model=list[ShopDomainOut])
async def list_domains(viewer: CurrentProfile, session: Session) -> list[ShopDomainOut]:
    return await _rows(session, viewer.id)


@router.post("", response_model=ShopDomainOut, status_code=status.HTTP_201_CREATED)
async def add_domain(body: ShopDomainIn, viewer: CurrentProfile, session: Session) -> ShopDomainOut:
    _require_business(viewer)
    domain = _domain(body.domain)
    taken = await session.scalar(
        text(
            """select 1 from app.business_domains
                where domain = :d and verified_at is not null and user_id <> :me"""
        ),
        {"d": domain, "me": viewer.id},
    )
    if taken:
        raise ApiError(409, "shop.taken", "Questo sito è già verificato da un altro account")
    count = await session.scalar(
        text("select count(*) from app.business_domains where user_id = :me"), {"me": viewer.id}
    )
    exists = await session.scalar(
        text("select 1 from app.business_domains where user_id = :me and domain = :d"),
        {"me": viewer.id, "d": domain},
    )
    if not exists and int(count or 0) >= MAX_DOMAINS:
        raise ApiError(409, "shop.limit", "Puoi aggiungere al massimo 5 siti")
    await session.execute(
        text(
            """insert into app.business_domains (user_id, domain, token)
               values (:me, :d, :token) on conflict (user_id, domain) do nothing"""
        ),
        {"me": viewer.id, "d": domain, "token": f"wearx-verify={secrets.token_urlsafe(18)}"},
    )
    await session.commit()
    return next(r for r in await _rows(session, viewer.id) if r.domain == domain)


@router.post(
    "/{domain}/verify",
    response_model=ShopDomainOut,
    dependencies=[Depends(rate_limit("shop_verify", 20, 3600))],
)
async def verify_domain(domain: str, viewer: CurrentProfile, session: Session) -> ShopDomainOut:
    _require_business(viewer)
    domain = _domain(domain)
    row = (
        (
            await session.execute(
                text(
                    """select domain, token, verified_at from app.business_domains
                        where user_id = :me and domain = :d for update"""
                ),
                {"me": viewer.id, "d": domain},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(404, "shop.not_found", "Sito non trovato")
    token = str(row["token"])
    found, problem = False, "Il file non c'è o non contiene il codice."
    async with client_factory() as client:
        for host in (domain, f"www.{domain}"):
            try:
                result, body = await visit(
                    session, f"https://{host}{VERIFY_FILE}", client, resolver, read_body=1024
                )
            except (Unsafe, NotFound, httpx.HTTPError):
                problem = "Non riusciamo a raggiungere il sito in https."
                continue
            if result.status == 200 and token in body.decode("utf-8", "replace"):
                found = True
                break
    await session.execute(
        text(
            """update app.business_domains
                  set last_checked_at = now(),
                      verified_at = case when :ok then coalesce(verified_at, now())
                                         else verified_at end
                where user_id = :me and domain = :d"""
        ),
        {"ok": found, "me": viewer.id, "d": domain},
    )
    if found:
        # Un solo proprietario per dominio: le richieste in sospeso di altri decadono.
        await session.execute(
            text(
                """delete from app.business_domains
                    where domain = :d and user_id <> :me and verified_at is null"""
            ),
            {"d": domain, "me": viewer.id},
        )
    await session.commit()
    if not found:
        raise ApiError(422, "shop.verify_failed", "Verifica non riuscita", detail=problem)
    return next(r for r in await _rows(session, viewer.id) if r.domain == domain)


@router.delete("/{domain}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_domain(domain: str, viewer: CurrentProfile, session: Session) -> Response:
    await session.execute(
        text("delete from app.business_domains where user_id = :me and domain = :d"),
        {"me": viewer.id, "d": _domain(domain)},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
