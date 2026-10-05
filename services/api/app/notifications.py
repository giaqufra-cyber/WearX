"""Notifiche (seduta 18): un registro per persona e i push che ne derivano.

Come funziona:
- `notify()` scrive la notifica NELLA STESSA TRANSAZIONE dell'azione che la causa (follow,
  decisione di moderazione…): se l'azione non va a buon fine, la notifica non esiste.
- Il push parte dopo, da un lavoro in background (`app.push_jobs`), solo per le righe in stato
  `pending`. Se la persona ha spento quel tipo di push, la riga nasce `none` (resta nella lista).
- 16-17 anni: niente push di notte (22-7, ora italiana); arrivano alle 7.
- Una persona bloccata non genera notifiche, e bloccare cancella quelle già arrivate.
- Stessa notizia ripetuta (es. segui, smetti, segui di nuovo): una sola riga (`dedupe_key`), e
  al massimo un push ogni 24 ore per quella notizia.
- Nei push sul telefono, che si leggono anche a schermo bloccato, la moderazione resta generica.

I testi si compongono quando si leggono: se un fit cambia didascalia o viene cancellato, la lista
resta coerente.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NotificationType = Literal[
    "follow_request",
    "new_follower",
    "follow_accepted",
    "vote_milestone",
    "moderation",
    "appeal_decided",
]
Category = Literal["follows", "votes", "moderation"]

CATEGORY: dict[str, Category] = {
    "follow_request": "follows",
    "new_follower": "follows",
    "follow_accepted": "follows",
    "vote_milestone": "votes",
    "moderation": "moderation",
    "appeal_decided": "moderation",
}

# Traguardi di voti che meritano una notifica (mai un push per ogni singolo voto: dal momento
# del push si potrebbe capire chi ha votato).
# Stessa lista nella migrazione 0012 (punto di partenza dei fit già pubblicati).
VOTE_MILESTONES = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)

ROME = ZoneInfo("Europe/Rome")
QUIET_FROM = time(22, 0)
QUIET_UNTIL = time(7, 0)
REPUSH_AFTER = timedelta(hours=24)


def quiet_until(now: datetime) -> datetime | None:
    """Per i 16-17: se ora è notte (22-7 a Roma), l'istante delle 7 successive; altrimenti None."""
    local = now.astimezone(ROME)
    if QUIET_UNTIL <= local.time() < QUIET_FROM:
        return None
    day = local.date() if local.time() < QUIET_UNTIL else local.date() + timedelta(days=1)
    return datetime.combine(day, QUIET_UNTIL, tzinfo=ROME)


async def notify(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: NotificationType,
    actor_id: uuid.UUID | None = None,
    post_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> uuid.UUID | None:
    """Registra una notifica per `user_id`. None se non va scritta (blocco, sé stessi, account
    non attivo)."""
    if actor_id is not None and actor_id == user_id:
        return None
    row = (
        (
            await session.execute(
                text(
                    """select p.age_band::text as age_band, p.status::text as status,
                              p.notify_follows, p.notify_votes, p.notify_moderation,
                              exists (select 1 from app.blocks b
                                       where (b.blocker_id = p.id and b.blocked_id = :actor)
                                          or (b.blocker_id = :actor and b.blocked_id = p.id))
                                as blocked
                         from app.profiles p where p.id = :uid"""
                ),
                {"uid": user_id, "actor": actor_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["blocked"] or row["status"] == "pending_deletion":
        return None
    wants_push = bool(row[f"notify_{CATEGORY[type]}"])
    now = await session.scalar(text("select now()"))
    assert isinstance(now, datetime)
    push_after = quiet_until(now) if row["age_band"] == "16_17" else None
    params = {
        "uid": user_id,
        "type": type,
        "actor": actor_id,
        "post": post_id,
        "payload": json.dumps(payload or {}),
        "key": dedupe_key,
        "state": "pending" if wants_push else "none",
        "after": push_after or now,
        "repush": REPUSH_AFTER,
    }
    if dedupe_key is None:
        created = await session.scalar(
            text(
                """insert into app.notifications
                     (user_id, type, actor_id, post_id, payload, push_state, push_after)
                   values (:uid, :type, :actor, :post, cast(:payload as jsonb), :state, :after)
                   returning id"""
            ),
            params,
        )
        return created if isinstance(created, uuid.UUID) else None
    # Stessa notizia: torna in cima e non letta; il push si ripete solo dopo 24 ore.
    upserted = await session.scalar(
        text(
            """insert into app.notifications
                 (user_id, type, actor_id, post_id, payload, dedupe_key, push_state, push_after)
               values (:uid, :type, :actor, :post, cast(:payload as jsonb), :key, :state, :after)
               on conflict (user_id, dedupe_key) where dedupe_key is not null do update
                  set type = excluded.type, payload = excluded.payload,
                      created_at = now(), read_at = null,
                      push_state = case
                        when app.notifications.pushed_at > now() - cast(:repush as interval)
                        then 'none' else excluded.push_state end,
                      push_after = excluded.push_after
               returning id"""
        ),
        params,
    )
    return upserted if isinstance(upserted, uuid.UUID) else None


async def forget_between(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> None:
    """Dopo un blocco: via le notifiche che l'uno ha causato all'altro."""
    await session.execute(
        text(
            """delete from app.notifications
                where (user_id = :a and actor_id = :b) or (user_id = :b and actor_id = :a)"""
        ),
        {"a": a, "b": b},
    )


async def follow_request_handled(
    session: AsyncSession, *, followee: uuid.UUID, follower: uuid.UUID, accepted: bool
) -> None:
    """Richiesta decisa: se accettata diventa "ha iniziato a seguirti" (senza un altro push),
    altrimenti sparisce dalla lista."""
    if accepted:
        await session.execute(
            text(
                """update app.notifications
                      set type = 'new_follower',
                          push_state = case when push_state = 'pending' then 'none'
                                            else push_state end
                    where user_id = :me and dedupe_key = :key"""
            ),
            {"me": followee, "key": f"follow:{follower}"},
        )
    else:
        await session.execute(
            text(
                """delete from app.notifications
                    where user_id = :me and dedupe_key = :key and type = 'follow_request'"""
            ),
            {"me": followee, "key": f"follow:{follower}"},
        )


# ---------- Testi ----------

ACTION_TITLES = {
    "hide": "Un tuo fit è stato nascosto",
    "remove": "Un tuo fit è stato rimosso",
    "restyle": "Abbiamo spostato un tuo fit in un altro stile",
    "suspend": "Il tuo account è sospeso",
    "ban": "Il tuo account è stato chiuso",
    "warn": "Hai ricevuto un avviso",
    "limit_posting": "Pubblicazione sospesa per 7 giorni",
    "restore": "Abbiamo annullato una decisione",
}


@dataclass(frozen=True, slots=True)
class Rendered:
    title: str
    body: str
    # Testo per il telefono (si legge anche a schermo bloccato).
    push_title: str
    push_body: str
    # Dove porta il tocco nell'app.
    url: str


def _fit(caption: str | None) -> str:
    if not caption:
        return "Il tuo fit"
    short = caption if len(caption) <= 40 else caption[:39].rstrip() + "…"
    return f"Il tuo fit «{short}»"


def render(
    type: str,
    payload: dict[str, Any],
    *,
    actor: str | None,
    caption: str | None,
    post_id: uuid.UUID | None,
) -> Rendered:
    who = f"@{actor}" if actor else "Qualcuno"
    if type == "follow_request":
        title = f"{who} vuole seguirti"
        body = "Accetta per fargli vedere il tuo portfolio."
        return Rendered(title, body, "Nuova richiesta", title, "/notifications")
    if type == "new_follower":
        title = f"{who} ha iniziato a seguirti"
        return Rendered(title, "", "Nuovo follower", title, f"/user/{actor}" if actor else "/")
    if type == "follow_accepted":
        title = f"{who} ha accettato la tua richiesta"
        body = "Ora vedi il suo portfolio."
        return Rendered(
            title, body, "Richiesta accettata", title, f"/user/{actor}" if actor else "/"
        )
    if type == "vote_milestone":
        count = int(payload.get("count", 0))
        title = f"{_fit(caption)} ha raggiunto {count} voti"
        body = "Apri il fit per vedere la media." if count == VOTE_MILESTONES[0] else ""
        url = f"/post/{post_id}" if post_id else "/"
        return Rendered(title, body, "Nuovo traguardo", title, url)
    if type == "moderation":
        title = ACTION_TITLES.get(str(payload.get("action")), "Novità dalla moderazione")
        body = "Tocca per leggere il motivo e, se vuoi, fare reclamo."
        if payload.get("action") == "restore":
            body = "Tocca per i dettagli."
        return Rendered(
            title, body, "WearX", "Hai un nuovo avviso della moderazione", "/moderation"
        )
    if type == "appeal_decided":
        accepted = payload.get("outcome") == "reversed"
        title = "Reclamo accolto" if accepted else "Reclamo respinto"
        body = (
            "Abbiamo annullato la decisione."
            if accepted
            else "La decisione resta. Tocca per leggere la risposta."
        )
        return Rendered(title, body, "WearX", "Il tuo reclamo è stato deciso", "/moderation")
    return Rendered("Novità su WearX", "", "WearX", "Novità su WearX", "/notifications")
