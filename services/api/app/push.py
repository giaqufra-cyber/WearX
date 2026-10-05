"""Spedizione dei push (servizio di Expo) e lavori periodici delle notifiche.

- `send_pending`: ogni minuto prende le notifiche in attesa, le raggruppa per persona (più
  notizie insieme = un solo push "Hai N nuove notifiche"), le manda a tutti i suoi telefoni.
- `check_receipts`: dopo 15 minuti Expo dice se un telefono non esiste più
  (DeviceNotRegistered): quel token si cancella.
- `vote_milestones`: ogni 10 minuti i fit che hanno superato un traguardo di voti.

Se Expo non risponde, le notifiche restano in attesa e si riprova dopo 5 minuti; dopo 24 ore
si rinuncia (restano comunque nella lista dell'app).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.notifications import VOTE_MILESTONES, notify, render

log = logging.getLogger("wearx.push")

EXPO_SEND = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS = "https://exp.host/--/api/v2/push/getReceipts"
BATCH = 100  # massimo di Expo per richiesta
RECEIPT_BATCH = 1000


@dataclass(frozen=True, slots=True)
class Ticket:
    ok: bool
    id: str | None = None
    error: str | None = None


class PushSender(Protocol):
    async def send(self, messages: list[dict[str, Any]]) -> list[Ticket]: ...

    async def receipts(self, ids: list[str]) -> dict[str, Ticket]: ...


class ExpoSender:
    def __init__(self, access_token: str | None, client: httpx.AsyncClient | None = None):
        headers = {"accept": "application/json", "content-type": "application/json"}
        if access_token:
            headers["authorization"] = f"Bearer {access_token}"
        self._client = client or httpx.AsyncClient(timeout=15, headers=headers)
        if client is not None:
            self._client.headers.update(headers)

    async def send(self, messages: list[dict[str, Any]]) -> list[Ticket]:
        tickets: list[Ticket] = []
        for start in range(0, len(messages), BATCH):
            chunk = messages[start : start + BATCH]
            response = await self._client.post(EXPO_SEND, json=chunk)
            response.raise_for_status()
            for item in response.json()["data"]:
                details = item.get("details") or {}
                tickets.append(
                    Ticket(
                        ok=item.get("status") == "ok", id=item.get("id"), error=details.get("error")
                    )
                )
        return tickets

    async def receipts(self, ids: list[str]) -> dict[str, Ticket]:
        out: dict[str, Ticket] = {}
        for start in range(0, len(ids), RECEIPT_BATCH):
            response = await self._client.post(
                EXPO_RECEIPTS, json={"ids": ids[start : start + RECEIPT_BATCH]}
            )
            response.raise_for_status()
            for ticket_id, item in response.json()["data"].items():
                details = item.get("details") or {}
                out[ticket_id] = Ticket(
                    ok=item.get("status") == "ok", id=ticket_id, error=details.get("error")
                )
        return out


@dataclass
class LogSender:
    """Sviluppo e test: niente rete, i messaggi restano qui (e nei log)."""

    sent: list[dict[str, Any]] = field(default_factory=list)
    unregistered: set[str] = field(default_factory=set)

    async def send(self, messages: list[dict[str, Any]]) -> list[Ticket]:
        tickets = []
        for message in messages:
            log.info("push (solo log): %s", json.dumps(message, ensure_ascii=False))
            self.sent.append(message)
            if message["to"] in self.unregistered:
                tickets.append(Ticket(ok=False, error="DeviceNotRegistered"))
            else:
                tickets.append(Ticket(ok=True, id=f"log-{uuid.uuid4()}"))
        return tickets

    async def receipts(self, ids: list[str]) -> dict[str, Ticket]:
        return {i: Ticket(ok=True, id=i) for i in ids}


_sender: PushSender | None = None


def get_sender() -> PushSender:
    global _sender
    if _sender is None:
        settings = get_settings()
        if settings.push_provider == "expo":
            token = settings.expo_access_token
            _sender = ExpoSender(token.get_secret_value() if token else None)
        else:
            _sender = LogSender()
    return _sender


def set_sender(sender: PushSender | None) -> None:
    global _sender
    _sender = sender


# ---------- Lavori ----------


async def send_pending(session: AsyncSession, sender: PushSender, limit: int = 500) -> int:
    """Spedisce i push in attesa. Restituisce quante notifiche ha trattato."""
    await session.execute(
        text(
            """update app.notifications set push_state = 'failed'
                where push_state = 'pending' and created_at < now() - interval '24 hours'"""
        )
    )
    rows = (
        (
            await session.execute(
                text(
                    """select n.id, n.user_id, n.type, n.payload, n.post_id,
                              a.nickname::text as actor, p.caption
                         from app.notifications n
                         left join app.profiles a on a.id = n.actor_id
                         left join app.posts p on p.id = n.post_id
                        where n.push_state = 'pending' and n.push_after <= now()
                        order by n.push_after
                        limit :limit
                        for update of n skip locked"""
                ),
                {"limit": limit},
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        await session.commit()
        return 0
    by_user: dict[uuid.UUID, list[Any]] = defaultdict(list)
    for row in rows:
        by_user[row["user_id"]].append(row)
    users = list(by_user)
    tokens: dict[uuid.UUID, list[str]] = defaultdict(list)
    for user_id, token in (
        await session.execute(
            text("select user_id, token from app.push_tokens where user_id = any(:ids)"),
            {"ids": users},
        )
    ).all():
        tokens[user_id].append(token)
    unread: dict[uuid.UUID, int] = dict(
        (
            await session.execute(
                text(
                    """select user_id, count(*) from app.notifications
                        where user_id = any(:ids) and read_at is null group by user_id"""
                ),
                {"ids": users},
            )
        ).all()
    )

    messages: list[dict[str, Any]] = []
    owners: list[uuid.UUID] = []
    for user_id, items in by_user.items():
        if not tokens[user_id]:
            continue
        if len(items) == 1:
            item = items[0]
            text_ = render(
                item["type"],
                item["payload"],
                actor=item["actor"],
                caption=item["caption"],
                post_id=item["post_id"],
            )
            title, body, url = text_.push_title, text_.push_body, text_.url
        else:
            title, body, url = "WearX", f"Hai {len(items)} nuove notifiche", "/notifications"
        for token in tokens[user_id]:
            messages.append(
                {
                    "to": token,
                    "title": title,
                    "body": body,
                    "data": {"url": url},
                    "sound": "default",
                    "badge": int(unread.get(user_id, 0)),
                    "channelId": "default",
                    "ttl": 86400,
                }
            )
            owners.append(user_id)

    try:
        tickets = await sender.send(messages) if messages else []
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("push non spediti, si riprova tra 5 minuti: %s", exc)
        await session.execute(
            text(
                """update app.notifications set push_after = now() + interval '5 minutes'
                    where id = any(:ids)"""
            ),
            {"ids": [r["id"] for r in rows]},
        )
        await session.commit()
        return 0

    delivered: set[uuid.UUID] = set()
    for message, owner, ticket in zip(messages, owners, tickets, strict=True):
        if ticket.ok and ticket.id:
            delivered.add(owner)
            await session.execute(
                text(
                    """insert into app.push_receipts (ticket_id, token) values (:id, :token)
                       on conflict do nothing"""
                ),
                {"id": ticket.id, "token": message["to"]},
            )
        elif ticket.error == "DeviceNotRegistered":
            await _forget_token(session, message["to"])
    for user_id, items in by_user.items():
        state = "sent" if user_id in delivered else "skipped" if not tokens[user_id] else "failed"
        await session.execute(
            text(
                """update app.notifications
                      set push_state = :state,
                          pushed_at = case when :state = 'sent' then now() else pushed_at end
                    where id = any(:ids)"""
            ),
            {"state": state, "ids": [i["id"] for i in items]},
        )
    await session.commit()
    return len(rows)


async def _forget_token(session: AsyncSession, token: str) -> None:
    log.info("token push non più valido, cancellato")
    await session.execute(text("delete from app.push_tokens where token = :t"), {"t": token})


async def check_receipts(session: AsyncSession, sender: PushSender) -> int:
    """Ricevute dei push di almeno 15 minuti fa: via i telefoni che non esistono più."""
    rows = (
        await session.execute(
            text(
                """select ticket_id, token from app.push_receipts
                    where created_at < now() - interval '15 minutes'
                    order by created_at limit :limit"""
            ),
            {"limit": RECEIPT_BATCH},
        )
    ).all()
    if not rows:
        return 0
    try:
        receipts = await sender.receipts([r[0] for r in rows])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("ricevute push non lette: %s", exc)
        return 0
    token_of = {r[0]: r[1] for r in rows}
    for ticket_id, ticket in receipts.items():
        if ticket.error == "DeviceNotRegistered" and ticket_id in token_of:
            await _forget_token(session, token_of[ticket_id])
        elif not ticket.ok:
            log.warning("push non consegnato: %s", ticket.error)
    # Le ricevute lette (o troppo vecchie: Expo le tiene 24 ore) non servono più.
    await session.execute(
        text(
            """delete from app.push_receipts
                where ticket_id = any(:ids) or created_at < now() - interval '24 hours'"""
        ),
        {"ids": list(receipts)},
    )
    await session.commit()
    return len(receipts)


async def vote_milestones(session: AsyncSession, limit: int = 1000) -> int:
    """Fit che hanno superato un traguardo di voti: una notifica per fit (si aggiorna salendo).

    Conta il numero PUBBLICATO (aggiornato ogni ora), non quello in tempo reale."""
    rows = (
        (
            await session.execute(
                text(
                    """select s.post_id, s.shown_count as vote_count, p.author_id,
                              p.status::text as status
                         from app.post_stats s join app.posts p on p.id = s.post_id
                        where s.shown_count >= s.vote_milestone_next
                        limit :limit
                        for update of s skip locked"""
                ),
                {"limit": limit},
            )
        )
        .mappings()
        .all()
    )
    for row in rows:
        reached = max(m for m in VOTE_MILESTONES if m <= row["vote_count"])
        following = next((m for m in VOTE_MILESTONES if m > row["vote_count"]), 2**31 - 1)
        await session.execute(
            text("update app.post_stats set vote_milestone_next = :n where post_id = :id"),
            {"n": following, "id": row["post_id"]},
        )
        if row["status"] in ("active", "style_rejected"):
            await notify(
                session,
                user_id=row["author_id"],
                type="vote_milestone",
                post_id=row["post_id"],
                payload={"count": reached},
                dedupe_key=f"votes:{row['post_id']}",
            )
    await session.commit()
    return len(rows)
