"""Cerca persone e suggerimenti (seduta 31).

Regole di chi compare (oltre a quelle di `app/people.py`: blocchi, account attivi, i 16-17 mai
a un maggiorenne):
- il nickname ESATTO trova sempre, come "Trova persone" di prima;
- per il resto compare solo chi si fa trovare (`discoverable`; di base sì per i maggiorenni,
  no per i 16-17) oppure chi conosci già (lo segui, l'hai chiesto, ti segue);
- a un 16-17 la ricerca e i suggerimenti mostrano altri 16-17 e account Business, mai un
  maggiorenne privato che non conosce già.

L'ordine mette davanti chi conosci: segui già, ti segue, amici in comune, stili in comune;
poi quanto il nickname somiglia a quello che scrivi e quanto è seguito. Degli stili in comune si
dice solo che ci sono, mai quali: gli stili di una persona restano privati.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.avatars import AvatarOut, avatar_out
from app.db import get_session
from app.people import FollowState, find_person
from app.profiles import VISIBLE_STYLE_SQL, CurrentProfile, Profile
from app.ratelimit import rate_limit

router = APIRouter(prefix="/v1/people", tags=["people"])

Session = Annotated[AsyncSession, Depends(get_session)]

RESULTS = 20
# Candidati letti prima di riordinarli con le relazioni.
CANDIDATES = 60
QUERY_MAX = 30
# "Somiglia a una parte del nickname" (pg_trgm word_similarity): 0,5 prende un errore di battitura
# in un nome di 6 lettere ("giulai" -> giulia: 0,57), non lettere a caso.
WORD_SIMILARITY = 0.5
_NOT_NICK = re.compile(r"[^a-z0-9._]")

Reason = Literal["follows_you", "mutuals", "styles", "popular"]


class PersonCard(BaseModel):
    nickname: str
    account_type: Literal["private", "business"]
    avatar: AvatarOut | None = None
    bio: str | None
    followers: int
    is_self: bool
    following: FollowState
    follows_you: bool
    # Persone che segui e che seguono questa persona: quante e le prime due.
    mutual_count: int
    mutuals: list[str]
    # Quanti stili avete in comune. Solo il numero: quali stili segue una persona lo sa solo lei
    # (seduta 27), quindi qui non si dice mai quali sono.
    shared_style_count: int
    # Solo nei suggerimenti: perché te la proponiamo.
    reason: Reason | None = None


class PeopleResults(BaseModel):
    query: str
    items: list[PersonCard]


class Suggestions(BaseModel):
    items: list[PersonCard]


def normalize_query(raw: str) -> str:
    """ "@Giulia.R " -> "giulia.r": i nickname sono minuscoli, senza spazi né simboli."""
    return _NOT_NICK.sub("", raw.strip().lstrip("@").lower())[:QUERY_MAX]


def _like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Chi può comparire a chi guarda, fuori dal nickname esatto. :me, :adult.
_FINDABLE = """
    (exists (select 1 from app.follows f where f.follower_id = :me and f.followee_id = p.id)
     or exists (select 1 from app.follows f
                 where f.follower_id = p.id and f.followee_id = :me and f.status = 'accepted')
     or (coalesce(p.discoverable, p.age_band = '18_plus')
         and (cast(:adult as boolean) or p.age_band = '16_17' or p.account_type = 'business')))
"""

_VISIBLE = """
    p.status = 'active'
    and (not cast(:adult as boolean) or p.age_band = '18_plus' or p.id = :me)
    and not exists (
      select 1 from app.blocks b
       where (b.blocker_id = :me and b.blocked_id = p.id)
          or (b.blocker_id = p.id and b.blocked_id = :me))
"""


@dataclass(slots=True)
class _Facts:
    card: PersonCard
    exact: bool = False
    prefix: bool = False
    similarity: float = 0.0


async def _cards(
    session: AsyncSession, viewer: Profile, ids: list[uuid.UUID]
) -> dict[uuid.UUID, PersonCard]:
    """Le schede di queste persone viste da chi guarda (relazioni, amici e stili in comune)."""
    if not ids:
        return {}
    params: dict[str, Any] = {"me": viewer.id, "ids": ids, "adult": viewer.is_adult}
    rows = (
        (
            await session.execute(
                text(
                    """select p.id, p.nickname::text as nickname, p.bio,
                              p.account_type::text as account_type, p.id = :me as is_self,
                              u.id as avatar_id, u.variants as avatar_variants,
                              u.blurhash as avatar_blurhash,
                              (select count(*) from app.follows f
                                 join app.profiles x on x.id = f.follower_id
                                where f.followee_id = p.id and f.status = 'accepted'
                                  and x.status = 'active') as followers,
                              coalesce((select f.status::text from app.follows f
                                         where f.follower_id = :me and f.followee_id = p.id),
                                       'none') as following,
                              exists (select 1 from app.follows f
                                       where f.follower_id = p.id and f.followee_id = :me
                                         and f.status = 'accepted') as follows_you
                         from app.profiles p
                         left join app.media_uploads u on u.id = p.avatar_upload_id
                        where p.id = any(:ids)"""
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    # Chi segui (accettato) e segue anche loro.
    mutual_rows = await session.execute(
        text(
            """select f2.followee_id as target, mid.nickname::text as nickname
                 from app.follows f1
                 join app.follows f2 on f2.follower_id = f1.followee_id
                                     and f2.status = 'accepted'
                 join app.profiles mid on mid.id = f1.followee_id and mid.status = 'active'
                where f1.follower_id = :me and f1.status = 'accepted'
                  and f2.followee_id = any(:ids) and f2.followee_id <> :me
                order by mid.nickname"""
        ),
        params,
    )
    mutuals: dict[uuid.UUID, list[str]] = defaultdict(list)
    for target, nickname in mutual_rows:
        mutuals[target].append(nickname)
    style_rows = await session.execute(
        text(
            "select m.user_id, count(*) from app.style_memberships m "  # noqa: S608 - costante
            "join app.style_memberships mine on mine.style_id = m.style_id "
            "and mine.user_id = :me "
            "join app.styles s on s.id = m.style_id "
            f"where m.user_id = any(:ids) and m.user_id <> :me and {VISIBLE_STYLE_SQL} "
            "group by m.user_id"
        ),
        params,
    )
    shared: dict[uuid.UUID, int] = {user_id: int(n) for user_id, n in style_rows}

    cards: dict[uuid.UUID, PersonCard] = {}
    for r in rows:
        mine = mutuals.get(r["id"], [])
        cards[r["id"]] = PersonCard(
            nickname=r["nickname"],
            account_type=r["account_type"],
            avatar=avatar_out(r["avatar_id"], r["avatar_variants"], r["avatar_blurhash"]),
            bio=r["bio"],
            followers=int(r["followers"]),
            is_self=bool(r["is_self"]),
            following=r["following"],
            follows_you=bool(r["follows_you"]),
            mutual_count=len(mine),
            mutuals=mine[:2],
            shared_style_count=shared.get(r["id"], 0),
        )
    return cards


def _closeness(card: PersonCard) -> float:
    """Quanto conosci già questa persona: pesa più del nickname, se il nickname somiglia."""
    score = 0.0
    if card.following == "accepted":
        score += 80
    elif card.following == "pending":
        score += 40
    if card.follows_you:
        score += 50
    score += min(card.mutual_count, 5) * 12
    score += min(card.shared_style_count, 5) * 4
    score += math.log1p(card.followers) * 6
    return score


def search_score(facts: _Facts) -> float:
    if facts.exact:
        return 10_000
    return (150 if facts.prefix else 0) + facts.similarity * 100 + _closeness(facts.card)


@router.get(
    "/search",
    response_model=PeopleResults,
    dependencies=[Depends(rate_limit("people_search", 600, 3600))],
)
async def search_people(
    viewer: CurrentProfile,
    session: Session,
    q: Annotated[str, Query(max_length=60)] = "",
) -> PeopleResults:
    query = normalize_query(q)
    if not query:
        return PeopleResults(query=query, items=[])
    # Sempre: il nickname o una sua parte (dopo "." o "_") inizia con quello che scrivi.
    # Da 3 lettere anche "contiene" e "somiglia" (errori di battitura: "giulai" -> giulia.rossi).
    fuzzy = len(query) >= 3
    await session.execute(
        text("select set_config('pg_trgm.word_similarity_threshold', :t, true)"),
        {"t": str(WORD_SIMILARITY)},
    )
    rows = (
        (
            await session.execute(
                text(
                    f"""select p.id, p.nickname::text = :q as exact,
                               (p.nickname::text like :prefix escape '\\'
                                or p.nickname::text like :part_dot escape '\\'
                                or p.nickname::text like :part_under escape '\\') as prefix,
                               greatest(similarity(p.nickname::text, :q),
                                        word_similarity(:q, p.nickname::text)) as similarity
                          from app.profiles p
                         where {_VISIBLE}
                           and (p.nickname::text = :q
                                or p.nickname::text like :prefix escape '\\'
                                or p.nickname::text like :part_dot escape '\\'
                                or p.nickname::text like :part_under escape '\\'
                                or (cast(:fuzzy as boolean)
                                    and (p.nickname::text like :contains escape '\\'
                                         or p.nickname::text % :q
                                         or :q <% p.nickname::text)))
                           and (p.nickname::text = :q or (p.id <> :me and {_FINDABLE}))
                         order by exact desc, prefix desc, similarity desc, p.nickname
                         limit :limit"""  # noqa: S608 - frammenti costanti, nessun input
                ),
                {
                    "me": viewer.id,
                    "adult": viewer.is_adult,
                    "q": query,
                    "prefix": _like(query) + "%",
                    "part_dot": "%." + _like(query) + "%",
                    "part_under": "%\\_" + _like(query) + "%",
                    "contains": "%" + _like(query) + "%",
                    "fuzzy": fuzzy,
                    "limit": CANDIDATES,
                },
            )
        )
        .mappings()
        .all()
    )
    cards = await _cards(session, viewer, [r["id"] for r in rows])
    facts = [
        _Facts(
            card=cards[r["id"]],
            exact=bool(r["exact"]),
            prefix=bool(r["prefix"]),
            similarity=float(r["similarity"] or 0),
        )
        for r in rows
        if r["id"] in cards
    ]
    facts.sort(key=lambda f: (-search_score(f), f.card.nickname))
    return PeopleResults(query=query, items=[f.card for f in facts[:RESULTS]])


def suggestion_reason(card: PersonCard) -> Reason:
    if card.follows_you:
        return "follows_you"
    if card.mutual_count:
        return "mutuals"
    if card.shared_style_count:
        return "styles"
    return "popular"


def suggestion_score(card: PersonCard) -> float:
    return (
        (60 if card.follows_you else 0)
        + min(card.mutual_count, 5) * 20
        + min(card.shared_style_count, 5) * 6
        + math.log1p(card.followers) * 3
    )


@router.get(
    "/suggestions",
    response_model=Suggestions,
    dependencies=[Depends(rate_limit("people_suggestions", 240, 3600))],
)
async def suggestions(viewer: CurrentProfile, session: Session) -> Suggestions:
    """Chi potresti conoscere: ti segue, amici di amici, stili in comune, i più seguiti."""
    rows = await session.execute(
        text(
            f"""with mutual as (
                  select f2.followee_id as id from app.follows f1
                    join app.follows f2 on f2.follower_id = f1.followee_id
                                        and f2.status = 'accepted'
                   where f1.follower_id = :me and f1.status = 'accepted'
                   group by f2.followee_id
                   order by count(*) desc limit 200
                ), fans as (
                  select follower_id as id from app.follows
                   where followee_id = :me and status = 'accepted'
                ), shared as (
                  select m.user_id as id from app.style_memberships m
                    join app.style_memberships mine on mine.style_id = m.style_id
                                                   and mine.user_id = :me
                   group by m.user_id
                   order by count(*) desc, max(m.joined_at) desc limit 200
                ), popular as (
                  select followee_id as id from app.follows where status = 'accepted'
                   group by followee_id order by count(*) desc limit 50
                ), candidates as (
                  select id from mutual union select id from fans
                  union select id from shared union select id from popular
                )
                select p.id from candidates c
                  join app.profiles p on p.id = c.id
                 where p.id <> :me and {_VISIBLE}
                   and not exists (select 1 from app.follows f
                                    where f.follower_id = :me and f.followee_id = p.id)
                   and not exists (select 1 from app.suggestion_dismissals d
                                    where d.user_id = :me and d.target_id = p.id)
                   and {_FINDABLE}"""  # noqa: S608 - frammenti costanti, nessun input
        ),
        {"me": viewer.id, "adult": viewer.is_adult},
    )
    ids = [r[0] for r in rows]
    cards = list((await _cards(session, viewer, ids)).values())
    cards.sort(key=lambda c: (-suggestion_score(c), c.nickname))
    picked = cards[:RESULTS]
    for card in picked:
        card.reason = suggestion_reason(card)
    return Suggestions(items=picked)


@router.post(
    "/suggestions/{nickname}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("people_dismiss", 300, 86400))],
)
async def dismiss_suggestion(nickname: str, viewer: CurrentProfile, session: Session) -> Response:
    """Non propormela più. Ripetibile; un nickname che non vedi risponde 404 come gli altri."""
    person = await find_person(session, viewer, nickname)
    if not person.is_self:
        await session.execute(
            text(
                """insert into app.suggestion_dismissals (user_id, target_id)
                   values (:me, :them) on conflict do nothing"""
            ),
            {"me": viewer.id, "them": person.id},
        )
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
