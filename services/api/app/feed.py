"""Feed degli stili (sez. 6.8).

Punteggio R di un post = qualità x freschezza
- qualità: media dei voti "prudente" (bayesiana): con pochi voti resta vicina a 60, così un
  solo 100 non porta un post in cima; con tanti voti conta la media vera.
- freschezza: 0,35 + 0,65 * e^(-ore/36): dopo un giorno e mezzo un post pesa poco più di metà.
Quota di esplorazione: un posto ogni EXPLORE_EVERY va a un post nuovo con pochi voti, così
ogni fit appena pubblicato ha la sua occasione di essere visto (e votato).

Redis tiene per ogni stile la classifica (ZSET) e i post nuovi; ogni apertura del feed fissa
una "sessione" (l'elenco già filtrato per chi guarda), che il cursore scorre senza doppioni né
salti anche se intanto i punteggi cambiano. Se Redis non risponde, si calcola tutto da
PostgreSQL con lo stesso risultato (solo più lento): il feed non si ferma mai.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import random
import secrets
import uuid
from collections.abc import Awaitable, Iterable
from dataclasses import dataclass
from typing import Any, cast

from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError
from app.post_access import POST_VISIBLE_SQL
from app.profiles import Profile
from app.redis_client import get_redis
from app.votes import voter_key

PAGE_SIZE = 10
EXPLORE_EVERY = 5
WINDOW_DAYS = 14
FRESH_HOURS = 48
FRESH_MAX_VOTES = 10
PRIOR_MEAN = 60.0
PRIOR_WEIGHT = 5.0
DECAY_HOURS = 36.0
TOP_PER_STYLE = 300
FRESH_PER_STYLE = 100
STYLE_SET_TTL = 15 * 60
SESSION_TTL = 30 * 60
SESSION_MAX = 400


def rank_score(vote_wsum: float, vote_wcount: float, age_hours: float) -> float:
    """Gemella in Python della formula SQL (usata nei test e come documentazione)."""
    quality = (PRIOR_WEIGHT * PRIOR_MEAN + vote_wsum) / (PRIOR_WEIGHT + vote_wcount)
    return quality / 100 * (0.35 + 0.65 * math.exp(-age_hours / DECAY_HOURS))


RANK_SQL = """
select p.id, p.style_id,
       ((cast(:pw as float8) * cast(:pm as float8) + coalesce(st.vote_wsum, 0))
         / (cast(:pw as float8) + coalesce(st.vote_wcount, 0))) / 100.0
         * (0.35 + 0.65 * exp(-extract(epoch from (now() - p.published_at))::float8
                              / 3600.0 / cast(:decay as float8)))
         as r,
       coalesce(st.vote_count, 0) as votes,
       extract(epoch from p.published_at)::float8 as ts,
       p.published_at > now() - make_interval(hours => :fresh_hours) as recent
  from app.posts p
  join app.profiles a on a.id = p.author_id
  left join app.post_stats st on st.post_id = p.id
 where p.status = 'active' and a.status = 'active'
   and p.style_id = any(:styles)
   and p.published_at > now() - make_interval(days => :days)
"""


def _rank_params(styles: list[int]) -> dict[str, Any]:
    return {
        "styles": styles,
        "pw": PRIOR_WEIGHT,
        "pm": PRIOR_MEAN,
        "decay": DECAY_HOURS,
        "days": WINDOW_DAYS,
        "fresh_hours": FRESH_HOURS,
    }


@dataclass(frozen=True, slots=True)
class Ranked:
    id: str
    style_id: int
    r: float
    ts: float
    fresh: bool


async def ranked_posts(session: AsyncSession, styles: list[int]) -> list[Ranked]:
    if not styles:
        return []
    rows = await session.execute(text(RANK_SQL), _rank_params(styles))
    return [
        Ranked(
            id=str(row.id),
            style_id=int(row.style_id),
            r=float(row.r),
            ts=float(row.ts),
            fresh=bool(row.recent) and int(row.votes) < FRESH_MAX_VOTES,
        )
        for row in rows
    ]


def _split(ranked: Iterable[Ranked]) -> tuple[list[str], list[str]]:
    items = list(ranked)
    exploit = [r.id for r in sorted(items, key=lambda r: (-r.r, r.id))]
    explore = [r.id for r in sorted((r for r in items if r.fresh), key=lambda r: (-r.ts, r.id))]
    return exploit, explore


def interleave(exploit: list[str], explore: list[str], seed: int) -> list[str]:
    """Classifica con un posto ogni EXPLORE_EVERY riservato ai post nuovi (in ordine casuale,
    ma ripetibile con lo stesso seme)."""
    rng = random.Random(seed)  # noqa: S311 - ordine di esplorazione, nessun uso crittografico
    pool = explore[:]
    rng.shuffle(pool)
    out: list[str] = []
    used: set[str] = set()
    e = x = 0
    while e < len(exploit) or x < len(pool):
        want_explore = (len(out) + 1) % EXPLORE_EVERY == 0
        source = pool if (want_explore and x < len(pool)) or e >= len(exploit) else exploit
        if source is pool:
            candidate = pool[x]
            x += 1
        else:
            candidate = exploit[e]
            e += 1
        if candidate not in used:
            used.add(candidate)
            out.append(candidate)
    return out


# ---------- Redis: classifiche per stile ----------


def _keys(style_id: int) -> tuple[str, str, str]:
    return f"feed:rank:{style_id}", f"feed:fresh:{style_id}", f"feed:built:{style_id}"


async def build_style_sets(session: AsyncSession, styles: list[int]) -> None:
    ranked = await ranked_posts(session, styles)
    by_style: dict[int, list[Ranked]] = {s: [] for s in styles}
    for r in ranked:
        by_style[r.style_id].append(r)
    pipe = get_redis().pipeline(transaction=True)
    for style_id, rows in by_style.items():
        rank_key, fresh_key, built_key = _keys(style_id)
        pipe.delete(rank_key, fresh_key)
        top = sorted(rows, key=lambda r: -r.r)[:TOP_PER_STYLE]
        if top:
            pipe.zadd(rank_key, {r.id: r.r for r in top})
            pipe.expire(rank_key, STYLE_SET_TTL + 60)
        fresh = sorted((r for r in rows if r.fresh), key=lambda r: -r.ts)[:FRESH_PER_STYLE]
        if fresh:
            pipe.zadd(fresh_key, {r.id: r.ts for r in fresh})
            pipe.expire(fresh_key, STYLE_SET_TTL + 60)
        pipe.set(built_key, "1", ex=STYLE_SET_TTL)
    await pipe.execute()


async def _candidates_redis(
    session: AsyncSession, styles: list[int]
) -> tuple[list[str], list[str]]:
    redis = get_redis()
    built = await redis.mget([_keys(s)[2] for s in styles])
    missing = [s for s, flag in zip(styles, built, strict=True) if flag is None]
    if missing:
        await build_style_sets(session, missing)
    pipe = redis.pipeline(transaction=False)
    for s in styles:
        rank_key, fresh_key, _ = _keys(s)
        pipe.zrevrange(rank_key, 0, TOP_PER_STYLE - 1, withscores=True)
        pipe.zrevrange(fresh_key, 0, FRESH_PER_STYLE - 1, withscores=True)
    results = await pipe.execute()
    ranked: dict[str, float] = {}
    fresh: dict[str, float] = {}
    for i in range(0, len(results), 2):
        for member, score in results[i]:
            ranked[str(member)] = max(score, ranked.get(str(member), 0.0))
        for member, score in results[i + 1]:
            fresh[str(member)] = score
    exploit = [k for k, _ in sorted(ranked.items(), key=lambda kv: (-kv[1], kv[0]))]
    explore = [k for k, _ in sorted(fresh.items(), key=lambda kv: (-kv[1], kv[0]))]
    return exploit, explore


async def on_post_published(style_id: int, post_id: uuid.UUID, published_ts: float) -> None:
    """Un post nuovo entra subito tra i "nuovi" del suo stile (se la classifica è in memoria)."""
    try:
        redis = get_redis()
        _, fresh_key, built_key = _keys(style_id)
        if await redis.exists(built_key):
            await redis.zadd(fresh_key, {str(post_id): published_ts})
    except RedisError:
        pass  # al prossimo ricalcolo comparirà comunque


# ---------- Filtro per chi guarda ----------


async def _visible_unseen(session: AsyncSession, viewer: Profile, ids: list[str]) -> set[str]:
    """Tra i candidati: visibili a chi guarda, non suoi, non già votati."""
    if not ids:
        return set()
    rows = await session.execute(
        text(
            f"""select p.id from app.posts p
                  join app.profiles a on a.id = p.author_id
                  join app.styles s on s.id = p.style_id
                 where p.id = any(:ids) and p.status = 'active' and p.author_id <> :viewer
                   and {POST_VISIBLE_SQL}
                   and not exists (select 1 from app.votes v
                                    where v.post_id = p.id and v.voter_key = :k)"""
        ),
        {
            "ids": [uuid.UUID(i) for i in ids],
            "viewer": viewer.id,
            "adult": viewer.is_adult,
            "k": voter_key(viewer.id),
        },
    )
    return {str(r[0]) for r in rows}


async def personal_order(
    session: AsyncSession, viewer: Profile, exploit: list[str], explore: list[str], seed: int
) -> list[str]:
    allowed = await _visible_unseen(session, viewer, list({*exploit, *explore}))
    ordered = interleave(
        [i for i in exploit if i in allowed], [i for i in explore if i in allowed], seed
    )
    return ordered[:SESSION_MAX]


# ---------- Cursore ----------


def _cursor_mac(viewer: Profile, payload: bytes) -> str:
    secret = get_settings().vote_pepper.get_secret_value().encode()
    mac = hmac.new(secret, b"feed:" + viewer.id.bytes + payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac[:12]).decode().rstrip("=")


def encode_cursor(viewer: Profile, data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{body}.{_cursor_mac(viewer, payload)}"


def decode_cursor(viewer: Profile, cursor: str) -> dict[str, Any]:
    try:
        body, mac = cursor.split(".", 1)
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        if not hmac.compare_digest(mac, _cursor_mac(viewer, payload)):
            raise ValueError("firma")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("forma")
        return data
    except (ValueError, UnicodeDecodeError):
        # Cursore manomesso, di un altro utente o troncato.
        raise ApiError(400, "feed.invalid_cursor", "Cursore del feed non valido") from None


# ---------- Pagina ----------


@dataclass(frozen=True, slots=True)
class Page:
    ids: list[uuid.UUID]
    next_cursor: str | None


async def feed_page(
    session: AsyncSession, viewer: Profile, styles: list[int], scope: str, cursor: str | None
) -> Page:
    state = decode_cursor(viewer, cursor) if cursor else None
    if state is not None and state.get("st") != scope:
        raise ApiError(400, "feed.invalid_cursor", "Cursore del feed non valido")
    offset = int(state["o"]) if state else 0
    try:
        return await _page_redis(session, viewer, styles, scope, state, offset)
    except RedisError:
        return await _page_database(session, viewer, styles, scope, state, offset)


async def _page_redis(
    session: AsyncSession,
    viewer: Profile,
    styles: list[int],
    scope: str,
    state: dict[str, Any] | None,
    offset: int,
) -> Page:
    redis = get_redis()
    if state is None or state.get("m") != "r":
        sid = secrets.token_urlsafe(12)
        exploit, explore = await _candidates_redis(session, styles)
        ordered = await personal_order(session, viewer, exploit, explore, seed=secrets.randbits(32))
        key = f"feed:sess:{viewer.id}:{sid}"
        pipe = redis.pipeline(transaction=True)
        if ordered:
            pipe.rpush(key, *ordered)
        else:
            pipe.rpush(key, "")  # sessione vuota ma esistente
        pipe.expire(key, SESSION_TTL)
        await pipe.execute()
    else:
        sid = str(state["s"])
        key = f"feed:sess:{viewer.id}:{sid}"
    page_raw: list[str] = await cast(
        Awaitable[list[str]], redis.lrange(key, offset, offset + PAGE_SIZE - 1)
    )
    if state is not None and not page_raw and not await redis.exists(key):
        raise ApiError(410, "feed.cursor_expired", "Il feed è scaduto: ricarica")
    ids = [uuid.UUID(i) for i in page_raw if i]
    total: int = await cast(Awaitable[int], redis.llen(key))
    next_offset = offset + PAGE_SIZE
    next_cursor = (
        encode_cursor(viewer, {"m": "r", "s": sid, "o": next_offset, "st": scope})
        if next_offset < total
        else None
    )
    return Page(ids=ids, next_cursor=next_cursor)


async def _page_database(
    session: AsyncSession,
    viewer: Profile,
    styles: list[int],
    scope: str,
    state: dict[str, Any] | None,
    offset: int,
) -> Page:
    """Senza Redis: stesso ordine ricalcolato da PostgreSQL a ogni pagina (seme nel cursore)."""
    if state is not None and state.get("m") == "r":
        # La sessione stava in Redis, che ora non risponde: si riparte da capo.
        offset = 0
        state = None
    seed = int(state["seed"]) if state else secrets.randbits(32)
    exploit, explore = _split(await ranked_posts(session, styles))
    ordered = await personal_order(session, viewer, exploit, explore, seed)
    page = ordered[offset : offset + PAGE_SIZE]
    next_offset = offset + PAGE_SIZE
    next_cursor = (
        encode_cursor(viewer, {"m": "q", "seed": seed, "o": next_offset, "st": scope})
        if next_offset < len(ordered)
        else None
    )
    return Page(ids=[uuid.UUID(i) for i in page], next_cursor=next_cursor)


# ---------- Ricalcolo periodico (worker) ----------


async def refresh_all(session: AsyncSession) -> int:
    """Ricalcola i punteggi di tutti gli stili attivi: classifiche Redis e post_stats.hot_score."""
    styles = [
        int(r[0]) for r in await session.execute(text("select id from app.styles where is_active"))
    ]
    ranked = await ranked_posts(session, styles)
    if ranked:
        await session.execute(
            text(
                """update app.post_stats st set hot_score = v.r
                     from unnest(cast(:ids as uuid[]), cast(:rs as float8[])) as v(id, r)
                    where st.post_id = v.id"""
            ),
            {"ids": [uuid.UUID(r.id) for r in ranked], "rs": [r.r for r in ranked]},
        )
        await session.commit()
    try:
        await build_style_sets(session, styles)
    except RedisError:
        pass
    return len(ranked)
