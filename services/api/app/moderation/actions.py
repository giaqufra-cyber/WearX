"""Azioni di moderazione (sez. 14.3) e loro motivazione per la persona coinvolta (art. 17 DSA).

Ogni azione scrive una riga in `moderation_actions` con: cosa (action), perché (ground),
se è automatica, chi l'ha decisa, chi è colpito, fino a quando, e il testo che la persona legge
nell'app (statement), compreso come fare reclamo.

Scala delle sanzioni: avviso -> pubblicazione sospesa 7 giorni -> account chiuso. Si contano le
sanzioni degli ultimi 12 mesi non annullate (reclamo accolto, o annullate insieme al fit).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.post_purge import purge_post
from app.votes import CONFIRM_MIN, MATCH_THRESHOLD

Action = Literal["hide", "remove", "restyle", "suspend", "ban", "restore", "warn", "limit_posting"]
Sanction = Literal["warn", "limit_posting", "ban"]

POSTING_SUSPENSION_DAYS = 7
APPEAL_WINDOW_DAYS = 183  # 6 mesi
STRIKE_WINDOW_DAYS = 365

# Motivi (segnalazioni e decisioni), in parole semplici.
GROUNDS: dict[str, str] = {
    "nudity": "nudità o contenuti sessuali",
    "minor_safety": "sicurezza dei minori",
    "harassment": "molestie, minacce o dati personali di altre persone",
    "spam": "spam",
    "wrong_style": "stile sbagliato",
    "dangerous_link": "link pericoloso",
    "stolen_photo": "foto di qualcun altro",
    "other": "violazione delle regole della community",
    "community_reports": "più segnalazioni di persone diverse",
    "csam_hash_match": "una foto corrisponde a materiale illegale già noto",
    "image_classifier": "il controllo automatico delle foto",
    "appeal": "il tuo reclamo è stato accolto",
    "review_cleared": "un moderatore ha verificato che rispetta le regole",
    "staff_review": "una revisione dello staff",
}

_APPEAL = "Se pensi che sia un errore puoi fare reclamo da questo avviso entro 6 mesi."


def ground_label(ground: str) -> str:
    return GROUNDS.get(ground, GROUNDS["other"])


def statement_for(
    action: Action,
    ground: str,
    *,
    automated: bool,
    caption: str | None = None,
    until: datetime | None = None,
    linked: bool = False,
) -> str:
    """Testo che la persona legge: cosa è successo, perché, chi ha deciso, come reagire.
    `linked`: sanzione decisa insieme a un'azione su un fit (il reclamo si fa lì)."""
    fit = f"Il tuo fit «{caption}»" if caption else "Un tuo fit"
    appeal = (
        "Il reclamo si fa sull'avviso del fit e, se accolto, annulla anche questa decisione."
        if linked
        else _APPEAL
    )
    why = ground_label(ground)
    who = "Decisione automatica" if automated else "Decisione di un moderatore"
    if action == "hide":
        what = f"{fit} è stato nascosto: non compare più nel feed né nel tuo profilo per gli altri"
        if automated:
            return (
                f"{what}. Motivo: {why}. {who}: un moderatore lo rivede presto e, se non viola "
                f"le regole, torna visibile. {_APPEAL}"
            )
        return f"{what}. Motivo: {why}. {who}. {_APPEAL}"
    if action == "remove":
        return (
            f"{fit} è stato rimosso e le sue foto non si possono ripubblicare. Motivo: {why}. "
            f"{who}. {_APPEAL}"
        )
    if action == "warn":
        return (
            f"Avviso: un tuo contenuto ha violato le regole della community ({why}). Al prossimo "
            f"problema la pubblicazione viene sospesa per {POSTING_SUSPENSION_DAYS} giorni. "
            f"{appeal}"
        )
    if action == "limit_posting":
        day = until.strftime("%d/%m/%Y") if until else ""
        return (
            f"Non puoi pubblicare nuovi fit fino al {day}. Motivo: {why}. Puoi ancora vedere "
            f"e votare. {who}. {appeal}"
        )
    if action == "suspend":
        return (
            f"Il tuo account è sospeso in attesa di verifica. Motivo: {why}. {who}. "
            f"Un moderatore controlla il caso il prima possibile. {_APPEAL}"
        )
    if action == "ban":
        return f"Il tuo account è stato chiuso. Motivo: {why}. {who}. {appeal}"
    if action == "restore":
        if linked:
            return (
                "Annullata anche la sanzione decisa insieme al fit: non conta più per le "
                "sanzioni successive."
            )
        return f"Abbiamo annullato una decisione precedente: {why}. Ci scusiamo per il disagio."
    return f"Decisione di moderazione. Motivo: {why}. {who}. {_APPEAL}"


async def record(
    session: AsyncSession,
    *,
    target_type: str,
    target_id: uuid.UUID,
    action: Action,
    ground: str,
    automated: bool,
    actor_id: uuid.UUID | None,
    subject_id: uuid.UUID | None,
    statement: str,
    expires_at: datetime | None = None,
) -> uuid.UUID:
    action_id = await session.scalar(
        text(
            """insert into app.moderation_actions
                 (target_type, target_id, action, ground, automated, actor_id, subject_id,
                  statement, expires_at)
               values (:tt, :tid, :action, :ground, :auto, :actor, :subject, :statement, :exp)
               returning id"""
        ),
        {
            "tt": target_type,
            "tid": target_id,
            "action": action,
            "ground": ground,
            "auto": automated,
            "actor": actor_id,
            "subject": subject_id,
            "statement": statement,
            "exp": expires_at,
        },
    )
    assert isinstance(action_id, uuid.UUID)
    return action_id


async def _post(session: AsyncSession, post_id: uuid.UUID) -> tuple[uuid.UUID, str, str | None]:
    row = (
        await session.execute(
            text(
                """select author_id, status::text, caption from app.posts
                    where id = :id for update"""
            ),
            {"id": post_id},
        )
    ).one()
    return row[0], row[1], row[2]


async def hide_post(
    session: AsyncSession,
    post_id: uuid.UUID,
    *,
    ground: str,
    automated: bool,
    actor_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Nasconde un fit visibile. None se era già nascosto o eliminato."""
    author, status, caption = await _post(session, post_id)
    if status not in ("active", "style_rejected", "processing"):
        return None
    await session.execute(
        text("update app.posts set status = 'hidden_moderation' where id = :id"), {"id": post_id}
    )
    return await record(
        session,
        target_type="post",
        target_id=post_id,
        action="hide",
        ground=ground,
        automated=automated,
        actor_id=actor_id,
        subject_id=author,
        statement=statement_for("hide", ground, automated=automated, caption=caption),
    )


async def restore_post(
    session: AsyncSession, post_id: uuid.UUID, *, ground: str, actor_id: uuid.UUID | None
) -> uuid.UUID | None:
    """Rende di nuovo visibile un fit nascosto (torna "fuori stile" se lo era per i voti)."""
    author, status, _ = await _post(session, post_id)
    if status != "hidden_moderation":
        return None
    await session.execute(
        text(
            """update app.posts p set status = case
                   when st.confirm_yes + st.confirm_no >= :min
                    and st.confirm_yes::float8 / (st.confirm_yes + st.confirm_no) < :threshold
                   then 'style_rejected'::app.post_status else 'active'::app.post_status end
                 from app.post_stats st
                where p.id = :id and st.post_id = p.id"""
        ),
        {"id": post_id, "min": CONFIRM_MIN, "threshold": MATCH_THRESHOLD},
    )
    return await record(
        session,
        target_type="post",
        target_id=post_id,
        action="restore",
        ground=ground,
        automated=False,
        actor_id=actor_id,
        subject_id=author,
        statement=statement_for("restore", ground, automated=False),
    )


async def remove_post(
    session: AsyncSession, post_id: uuid.UUID, *, ground: str, actor_id: uuid.UUID
) -> tuple[uuid.UUID | None, list[str]]:
    """Rimuove un fit; le sue foto entrano nella lista locale (non si ricaricano uguali).
    Restituisce l'azione e le chiavi da cancellare dall'archivio dopo il commit."""
    author, status, caption = await _post(session, post_id)
    if status == "deleted":
        return None, []
    action_id = await record(
        session,
        target_type="post",
        target_id=post_id,
        action="remove",
        ground=ground,
        automated=False,
        actor_id=actor_id,
        subject_id=author,
        statement=statement_for("remove", ground, automated=False, caption=caption),
    )
    purged = await purge_post(session, post_id, author)
    for sha, phash in purged.hashes:
        if sha is None and phash is None:
            continue
        await session.execute(
            text(
                """insert into app.blocked_hashes (sha256, phash, kind, source)
                   values (:sha, :ph, 'removed', :source)
                   on conflict (sha256) where sha256 is not null do nothing"""
            ),
            {"sha": sha, "ph": phash, "source": f"action:{action_id}"},
        )
    return action_id, purged.storage_keys


async def strikes(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Sanzioni ricevute negli ultimi 12 mesi (avvisi e sospensioni della pubblicazione),
    escluse quelle annullate da un reclamo. Ogni violazione confermata ne aggiunge una."""
    count = await session.scalar(
        text(
            """select count(*) from app.moderation_actions m
                where m.subject_id = :uid
                  and m.action in ('warn', 'limit_posting')
                  and not m.automated
                  and m.created_at > now() - make_interval(days => :days)
                  and m.reversed_at is null"""
        ),
        {"uid": user_id, "days": STRIKE_WINDOW_DAYS},
    )
    return int(count or 0)


def next_sanction(previous_strikes: int) -> Sanction:
    """Avviso alla prima, sospensione della pubblicazione alla seconda, chiusura alla terza."""
    if previous_strikes <= 0:
        return "warn"
    if previous_strikes == 1:
        return "limit_posting"
    return "ban"


async def sanction_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    sanction: Sanction,
    *,
    ground: str,
    actor_id: uuid.UUID,
    linked: bool = False,
) -> uuid.UUID:
    until = None
    if sanction == "limit_posting":
        until = await session.scalar(
            text(
                """update app.profiles
                      set posting_blocked_until = greatest(
                            coalesce(posting_blocked_until, now()),
                            now() + make_interval(days => :days))
                    where id = :uid returning posting_blocked_until"""
            ),
            {"uid": user_id, "days": POSTING_SUSPENSION_DAYS},
        )
    elif sanction == "ban":
        await session.execute(
            text("update app.profiles set status = 'suspended' where id = :uid"), {"uid": user_id}
        )
    return await record(
        session,
        target_type="profile",
        target_id=user_id,
        action=sanction,
        ground=ground,
        automated=False,
        actor_id=actor_id,
        subject_id=user_id,
        statement=statement_for(sanction, ground, automated=False, until=until, linked=linked),
        expires_at=until,
    )


async def suspend_pending_review(
    session: AsyncSession, user_id: uuid.UUID, *, ground: str
) -> uuid.UUID | None:
    """Sospensione automatica in attesa di un moderatore (casi P0). None se già sospeso."""
    changed = await session.scalar(
        text(
            """update app.profiles set status = 'suspended'
                where id = :uid and status = 'active' returning id"""
        ),
        {"uid": user_id},
    )
    if changed is None:
        return None
    return await record(
        session,
        target_type="profile",
        target_id=user_id,
        action="suspend",
        ground=ground,
        automated=True,
        actor_id=None,
        subject_id=user_id,
        statement=statement_for("suspend", ground, automated=True),
    )


async def reverse(
    session: AsyncSession,
    action_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    ground: str = "appeal",
    linked: bool = False,
) -> uuid.UUID | None:
    """Annulla gli effetti di una decisione (reclamo accolto o errore del moderatore).
    La decisione resta nello storico, segnata come annullata (non conta più nella scala).
    None se era già annullata."""
    row = (
        await session.execute(
            text(
                """select action, target_type, target_id, subject_id, reversed_at
                     from app.moderation_actions where id = :id for update"""
            ),
            {"id": action_id},
        )
    ).one()
    action, target_type, target_id, subject, reversed_at = row
    if reversed_at is not None:
        return None
    restored = await _undo(
        session, action_id, action, target_type, target_id, subject, actor_id, ground, linked
    )
    await session.execute(
        text(
            """update app.moderation_actions set reversed_at = now(), reversed_by = :by
                where id = :id"""
        ),
        {"id": action_id, "by": restored},
    )
    return restored


async def _undo(
    session: AsyncSession,
    action_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    subject: uuid.UUID | None,
    actor_id: uuid.UUID,
    ground: str,
    linked: bool,
) -> uuid.UUID | None:
    if action in ("hide", "remove"):
        # La sanzione decisa insieme (stessa decisione = stessa transazione) cade con il fit.
        siblings = (
            await session.execute(
                text(
                    """select s.id from app.moderation_actions s, app.moderation_actions m
                        where m.id = :id and s.subject_id = m.subject_id
                          and s.created_at = m.created_at and s.id <> m.id
                          and s.action in ('warn', 'limit_posting', 'ban')"""
                ),
                {"id": action_id},
            )
        ).scalars()
        for sibling in list(siblings):
            await reverse(session, sibling, actor_id=actor_id, ground=ground, linked=True)
    if action == "hide" and target_type == "post":
        return await restore_post(session, target_id, ground=ground, actor_id=actor_id)
    if action == "remove":
        # Il fit non torna (foto cancellate), ma le sue foto si possono ripubblicare.
        await session.execute(
            text("delete from app.blocked_hashes where source = :s"), {"s": f"action:{action_id}"}
        )
    elif action in ("suspend", "ban"):
        await session.execute(
            text(
                "update app.profiles set status = 'active' where id = :uid and status = 'suspended'"
            ),
            {"uid": subject},
        )
    elif action == "limit_posting":
        await session.execute(
            text("update app.profiles set posting_blocked_until = null where id = :uid"),
            {"uid": subject},
        )
    return await record(
        session,
        target_type=target_type,
        target_id=target_id,
        action="restore",
        ground=ground,
        automated=False,
        actor_id=actor_id,
        subject_id=subject,
        statement=statement_for("restore", ground, automated=False, linked=linked),
    )


def appeal_deadline(created_at: datetime) -> datetime:
    return created_at + timedelta(days=APPEAL_WINDOW_DAYS)
