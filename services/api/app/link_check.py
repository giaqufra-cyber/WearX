"""Controllo dei link ai negozi (seduta 21).

Per ogni link, all'inserimento e poi a intervalli:
1. dominio bloccato dallo staff (o un suo dominio "padre")  -> bloccato;
2. liste di siti pericolosi (Google Safe Browsing, se configurato) -> bloccato;
3. visita del link: il nome del sito deve portare a indirizzi PUBBLICI (mai rete interna:
   protezione SSRF), si seguono al massimo 5 redirect controllando ogni passaggio (sempre https,
   porta 443, dominio non bloccato); non si scarica la pagina, basta la risposta.
   - risposta 2xx/3xx, ma anche 401/403/429 (molti negozi respingono i robot): sicuro;
   - 404/410 o sito inesistente: "non raggiungibile";
   - errori di rete o del server: si riprova; dopo 3 di fila "non raggiungibile".
Ricontrolli: sicuri ogni 7 giorni, non raggiungibili ogni giorno, in attesa dopo 1 ora.

Lo stesso "visitatore sicuro" verifica i domini dei Business (file .well-known).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError
from app.links import normalize_shop_url

log = logging.getLogger("wearx.links")

USER_AGENT = "WearXLinkCheck/1.0 (+https://wearx.app/link-check)"
MAX_REDIRECTS = 5
MAX_FAILS = 3
RECHECK_SAFE = timedelta(days=7)
RECHECK_BROKEN = timedelta(days=1)
RECHECK_RETRY = timedelta(hours=1)
VERIFY_FILE = "/.well-known/wearx-verify.txt"


def parent_domains(domain: str) -> list[str]:
    """ "a.b.shop.com" -> ["a.b.shop.com", "b.shop.com", "shop.com"] (mai il solo "com")."""
    parts = domain.lower().strip(".").split(".")
    return [".".join(parts[i:]) for i in range(len(parts) - 1)]


async def blocked_reason(session: AsyncSession, domain: str) -> str | None:
    reason = await session.scalar(
        text("select reason from app.blocked_domains where domain = any(:d) limit 1"),
        {"d": parent_domains(domain)},
    )
    return str(reason) if reason is not None else None


# ---------- Liste di siti pericolosi ----------


class ThreatChecker(Protocol):
    async def threats(self, urls: list[str]) -> dict[str, str]: ...


class NoThreats:
    """Nessun servizio configurato: valgono solo i domini bloccati dallo staff."""

    async def threats(self, urls: list[str]) -> dict[str, str]:
        return {}


class SafeBrowsing:
    """Google Safe Browsing v4 (Lookup API): restituisce url -> tipo di minaccia."""

    ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=10)

    async def threats(self, urls: list[str]) -> dict[str, str]:
        if not urls:
            return {}
        body = {
            "client": {"clientId": "wearx", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": u} for u in urls[:500]],
            },
        }
        response = await self._client.post(self.ENDPOINT, params={"key": self._key}, json=body)
        response.raise_for_status()
        return {m["threat"]["url"]: m["threatType"] for m in response.json().get("matches", [])}


def threat_checker() -> ThreatChecker:
    key = get_settings().safe_browsing_key
    return SafeBrowsing(key.get_secret_value()) if key else NoThreats()


# ---------- Visita sicura ----------

Resolver = Callable[[str], Awaitable[list[str]]]


async def system_resolver(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


class Unsafe(Exception):
    """Il link porta dove non deve (rete interna, http, dominio bloccato)."""


class NotFound(Exception):
    """Il sito non esiste (nome non risolto)."""


@dataclass(frozen=True, slots=True)
class Visit:
    final_url: str
    status: int


async def _public_host(host: str, resolve: Resolver) -> None:
    try:
        addresses = await resolve(host)
    except (socket.gaierror, UnicodeError) as exc:
        raise NotFound(host) from exc
    if not addresses:
        raise NotFound(host)
    for address in addresses:
        if not ipaddress.ip_address(address.split("%")[0]).is_global:
            raise Unsafe("indirizzo interno")


async def visit(
    session: AsyncSession,
    url: str,
    client: httpx.AsyncClient,
    resolve: Resolver = system_resolver,
    *,
    read_body: int = 0,
) -> tuple[Visit, bytes]:
    """Visita il link seguendo i redirect uno per uno, con tutti i controlli a ogni passaggio."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        try:
            current, domain = normalize_shop_url(current)
        except ApiError as exc:
            raise Unsafe("redirect verso un indirizzo non ammesso") from exc
        if await blocked_reason(session, domain):
            raise Unsafe("dominio bloccato")
        await _public_host(urlsplit(current).hostname or domain, resolve)
        async with client.stream(
            "GET", current, headers={"user-agent": USER_AGENT, "accept": "text/html,*/*"}
        ) as response:
            if response.is_redirect and "location" in response.headers:
                current = urljoin(current, response.headers["location"])
                continue
            body = b""
            if read_body:
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) >= read_body:
                        break
            return Visit(final_url=current, status=response.status_code), body[:read_body]
    raise Unsafe("troppi redirect")


def http_client() -> httpx.AsyncClient:
    # Niente redirect automatici (si controllano a mano), niente cookie conservati.
    return httpx.AsyncClient(follow_redirects=False, timeout=8, trust_env=False)


# ---------- Controllo periodico ----------


async def check_link(
    session: AsyncSession,
    link: Any,
    client: httpx.AsyncClient,
    threats: dict[str, str],
    resolve: Resolver = system_resolver,
) -> str:
    """Aggiorna un link e restituisce il nuovo stato."""
    status: str = link["status"]
    reason: str | None = None
    final_url = link["final_url"]
    fails = link["fail_count"]
    domain_block = await blocked_reason(session, link["domain"])
    if domain_block:
        status, reason = "blocked", f"dominio bloccato: {domain_block}"
    elif link["url"] in threats:
        status, reason = "blocked", f"sito pericoloso ({threats[link['url']]})"
    else:
        try:
            result, _ = await visit(session, link["url"], client, resolve)
            final_url = result.final_url if result.final_url != link["url"] else None
            if result.status in (404, 410):
                status, fails = "broken", fails + 1
            elif result.status >= 500:
                fails += 1
                status = "broken" if fails >= MAX_FAILS else link["status"]
            else:
                status, fails = "safe", 0
        except Unsafe as exc:
            status, reason = "blocked", str(exc)
        except NotFound:
            status, fails = "broken", fails + 1
        except httpx.HTTPError:
            fails += 1
            status = "broken" if fails >= MAX_FAILS else link["status"]
    delay = {"safe": RECHECK_SAFE, "broken": RECHECK_BROKEN}.get(status, RECHECK_RETRY)
    await session.execute(
        text(
            """update app.links
                  set status = cast(:status as app.link_status), block_reason = :reason,
                      final_url = :final, fail_count = :fails, checked_at = now(),
                      next_check_at = now() + cast(:delay as interval)
                where id = :id"""
        ),
        {
            "id": link["id"],
            "status": status,
            "reason": reason,
            "final": final_url,
            "fails": fails,
            "delay": delay,
        },
    )
    return status


async def check_due_links(
    session: AsyncSession,
    *,
    limit: int = 50,
    client: httpx.AsyncClient | None = None,
    checker: ThreatChecker | None = None,
    resolve: Resolver = system_resolver,
) -> int:
    """Lavoro ogni 2 minuti: i link da controllare (nuovi o in scadenza)."""
    links = (
        (
            await session.execute(
                text(
                    """select id, url, domain, status::text as status, final_url, fail_count
                         from app.links
                        where status <> 'blocked' and next_check_at <= now()
                        order by next_check_at limit :limit
                        for update skip locked"""
                ),
                {"limit": limit},
            )
        )
        .mappings()
        .all()
    )
    if not links:
        return 0
    try:
        threats = await (checker or threat_checker()).threats([link["url"] for link in links])
    except httpx.HTTPError:
        log.warning("liste di siti pericolosi non raggiungibili: si riprova più tardi")
        await session.rollback()
        return 0
    own_client = client is None
    client = client or http_client()
    try:
        for link in links:
            await check_link(session, link, client, threats, resolve)
    finally:
        if own_client:
            await client.aclose()
    await session.commit()
    return len(links)


async def block_domain(
    session: AsyncSession, domain: str, reason: str, staff_id: uuid.UUID | None
) -> int:
    """Blocca un dominio (e i suoi sottodomini): tutti i link verso di lui, subito."""
    await session.execute(
        text(
            """insert into app.blocked_domains (domain, reason, created_by)
               values (:d, :reason, :by)
               on conflict (domain) do update set reason = excluded.reason"""
        ),
        {"d": domain, "reason": reason, "by": staff_id},
    )
    result = await session.execute(
        text(
            """update app.links set status = 'blocked', block_reason = :reason
                where domain = :d or domain like :sub"""
        ),
        {"d": domain, "sub": f"%.{domain}", "reason": f"dominio bloccato: {reason}"},
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def unblock_domain(session: AsyncSession, domain: str) -> None:
    """Toglie il blocco: i link tornano da ricontrollare subito."""
    await session.execute(text("delete from app.blocked_domains where domain = :d"), {"d": domain})
    await session.execute(
        text(
            """update app.links set status = 'pending', block_reason = null, next_check_at = now()
                where (domain = :d or domain like :sub) and block_reason like 'dominio bloccato%'"""
        ),
        {"d": domain, "sub": f"%.{domain}"},
    )
