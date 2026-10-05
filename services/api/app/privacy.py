"""Privacy (seduta 20): archivio dei propri dati e cancellazione dell'account.

Archivio (GDPR art. 15 e 20): un file ZIP con tutto ciò che WearX tiene di una persona, in JSON
leggibile, più le foto dei suoi fit. Si prepara in background, resta scaricabile 7 giorni, poi
si cancella. I voti dati e gli eventi d'uso sono salvati con uno pseudonimo: si ritrovano
ricalcolandolo, e solo per la persona stessa.

Cancellazione: chiesta dalla persona, l'account sparisce subito per gli altri (profilo, fit,
capsule, follow) e resta recuperabile per 30 giorni. Poi un lavoro notturno cancella foto,
archivi e dati, e infine l'utente di Supabase Auth (che porta via tutto a cascata).
Restano, senza alcun riferimento alla persona: i voti dati (anonimi, dentro le medie dei fit
altrui), le decisioni di moderazione (rapporti di trasparenza DSA), le segnalazioni fatte.
"""

from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.media.keys import quarantine_key, variant_key
from app.notifications import notify
from app.routers.events import actor_key
from app.storage import ObjectStore
from app.votes import voter_key

log = logging.getLogger("wearx.privacy")

DELETION_GRACE = timedelta(days=30)
EXPORT_TTL = timedelta(days=7)
EXPORT_PHOTO_BYTES = 15 * 1024 * 1024

README = """WearX - i tuoi dati
===================

Questo archivio contiene i dati che WearX conserva su di te alla data indicata in profilo.json
(campo "archivio_creato"). Ogni file e' in formato JSON, leggibile con qualsiasi editor.

profilo.json         nickname, bio, fascia d'eta', impostazioni, consensi, verifica dell'eta'
                     (solo l'esito: nessuna immagine o data di nascita)
stili.json           gli stili a cui aderisci
fit.json             i tuoi fit con didascalia, stile, capi, prezzi e link
capsule.json         le tue capsule
persone.json         chi segui, chi ti segue, richieste, account bloccati
voti.json            i voti che hai dato (sono anonimi per gli altri)
segnalazioni.json    le segnalazioni che hai fatto
moderazione.json     le decisioni di moderazione che ti riguardano e i tuoi reclami
notifiche.json       le tue notifiche
dispositivi.json     i dispositivi con cui hai fatto l'accesso
eventi.json          le azioni registrate per gli Insight (ultimi 3 mesi circa)
foto/                le foto dei tuoi fit (la versione piu' grande)

Domande sui tuoi dati: privacy@wearx.app
"""


def _plain(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes | memoryview):
        return None
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


async def _rows(session: AsyncSession, sql: str, **params: Any) -> list[dict[str, Any]]:
    result = (await session.execute(text(sql), params)).mappings().all()
    return [{k: _plain(v) for k, v in r.items()} for r in result]


async def collect(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Tutti i dati della persona, pronti per essere scritti in JSON."""
    me = {"me": user_id}
    profile = (
        await _rows(
            session,
            """select nickname::text as nickname, bio, account_type::text as tipo_account,
                      age_band::text as fascia_eta, adult_on as maggiorenne_dal,
                      hide_prices as nascondi_prezzi, hide_vote_count as nascondi_numero_voti,
                      status::text as stato, created_at as creato_il,
                      terms_version as versione_termini, terms_accepted_at as termini_accettati_il,
                      notify_follows as push_follow, notify_votes as push_voti,
                      notify_moderation as push_moderazione,
                      deletion_requested_at as cancellazione_chiesta_il,
                      delete_after as cancellazione_definitiva_dal
                 from app.profiles where id = :me""",
            **me,
        )
    )[0]
    profile["archivio_creato"] = datetime.now(UTC).isoformat()
    profile["verifica_eta"] = await _rows(
        session,
        """select method as metodo, status::text as esito, age_band::text as fascia,
                  provider as fornitore, created_at as quando
             from app.age_verifications where user_id = :me order by created_at""",
        **me,
    )
    posts = await _rows(
        session,
        """select p.id, p.caption as didascalia, s.name as stile, p.status::text as stato,
                  p.created_at as creato_il, p.published_at as pubblicato_il,
                  st.shown_count as voti_ricevuti,
                  case when st.shown_wcount > 0
                       then round((st.shown_wsum / st.shown_wcount)::numeric, 1) end as media,
                  c.name as capsula
             from app.posts p
             join app.styles s on s.id = p.style_id
             left join app.post_stats st on st.post_id = p.id
             left join app.capsules c on c.id = p.capsule_id
            where p.author_id = :me and p.status <> 'deleted'
            order by p.created_at""",
        **me,
    )
    items = await _rows(
        session,
        """select i.post_id, i.position as posizione, i.brand as marca, i.name as capo,
                  i.price_cents as prezzo_centesimi, i.currency as valuta, l.url as link
             from app.post_items i
             join app.posts p on p.id = i.post_id
             left join app.links l on l.id = i.link_id
            where p.author_id = :me and p.status <> 'deleted'
            order by i.post_id, i.position""",
        **me,
    )
    for post in posts:
        post["capi"] = [
            {k: v for k, v in i.items() if k != "post_id"}
            for i in items
            if i["post_id"] == post["id"]
        ]
    people = {
        "segui": await _rows(
            session,
            """select p.nickname::text as nickname, f.status::text as stato, f.created_at as dal
                 from app.follows f join app.profiles p on p.id = f.followee_id
                where f.follower_id = :me order by f.created_at""",
            **me,
        ),
        "ti_seguono": await _rows(
            session,
            """select p.nickname::text as nickname, f.status::text as stato, f.created_at as dal
                 from app.follows f join app.profiles p on p.id = f.follower_id
                where f.followee_id = :me order by f.created_at""",
            **me,
        ),
        "bloccati": await _rows(
            session,
            """select p.nickname::text as nickname, b.created_at as dal
                 from app.blocks b join app.profiles p on p.id = b.blocked_id
                where b.blocker_id = :me order by b.created_at""",
            **me,
        ),
    }
    return {
        "profilo.json": profile,
        "stili.json": await _rows(
            session,
            """select s.name as stile, m.joined_at as dal
                 from app.style_memberships m join app.styles s on s.id = m.style_id
                where m.user_id = :me order by m.joined_at""",
            **me,
        ),
        "fit.json": posts,
        "capsule.json": await _rows(
            session,
            "select name as nome, created_at as creata_il from app.capsules where owner_id = :me",
            **me,
        ),
        "persone.json": people,
        "voti.json": await _rows(
            session,
            """select v.post_id, v.score as voto, v.style_confirm as conferma_stile,
                      v.created_at as quando
                 from app.votes v where v.voter_key = :k order by v.created_at""",
            k=voter_key(user_id),
        ),
        "segnalazioni.json": await _rows(
            session,
            """select target_type as tipo, target_id as contenuto, reason as motivo,
                      details as dettagli, status as stato, created_at as quando
                 from app.reports where reporter_id = :me order by created_at""",
            **me,
        ),
        "moderazione.json": await _rows(
            session,
            """select m.action as decisione, m.ground as motivo, m.automated as automatica,
                      m.statement as testo, m.created_at as quando, m.expires_at as fino_al,
                      m.reversed_at as annullata_il, a.text as reclamo,
                      a.status as esito_reclamo, a.decision_note as risposta
                 from app.moderation_actions m
                 left join app.appeals a on a.action_id = m.id
                where m.subject_id = :me order by m.created_at""",
            **me,
        ),
        "notifiche.json": await _rows(
            session,
            """select type as tipo, payload as dettagli, created_at as quando, read_at as letta_il
                 from app.notifications where user_id = :me order by created_at""",
            **me,
        ),
        "dispositivi.json": await _rows(
            session,
            """select label as dispositivo, platform as sistema, app_version as versione_app,
                      created_at as primo_accesso, last_seen as ultima_attivita,
                      revoked_at as disconnesso_il
                 from app.devices where user_id = :me order by created_at""",
            **me,
        ),
        "eventi.json": await _rows(
            session,
            """select name as evento, post_id, props as dettagli, ts as quando
                 from app.events where actor_key = :k order by ts""",
            k=actor_key(user_id),
        ),
    }


async def _photos(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, str]]:
    """(nome nell'archivio, chiave nell'archivio delle foto) della variante più grande."""
    rows = (
        await session.execute(
            text(
                """select m.post_id, m.position, m.upload_id, m.variants
                     from app.post_media m join app.posts p on p.id = m.post_id
                    where p.author_id = :me and p.status <> 'deleted' and m.upload_id is not null
                    order by m.post_id, m.position"""
            ),
            {"me": user_id},
        )
    ).all()
    return [
        (f"foto/{post_id}-{position + 1}.webp", variant_key(upload_id, max(variants)))
        for post_id, position, upload_id, variants in rows
        if variants
    ]


async def build_export(session: AsyncSession, store: ObjectStore, export_id: uuid.UUID) -> bool:
    """Prepara l'archivio ZIP e avvisa la persona. False se l'archivio non esiste più."""
    row = (
        await session.execute(
            text("select user_id, status from app.data_exports where id = :id"), {"id": export_id}
        )
    ).first()
    if row is None or row[1] != "pending":
        return False
    user_id = row[0]
    try:
        data = await collect(session, user_id)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("LEGGIMI.txt", README)
            for name, content in data.items():
                archive.writestr(name, json.dumps(content, ensure_ascii=False, indent=2))
            for name, key in await _photos(session, user_id):
                try:
                    archive.writestr(name, await store.get(key, EXPORT_PHOTO_BYTES))
                except Exception:  # una foto mancante non blocca l'archivio
                    log.warning("foto non trovata per l'archivio: %s", key)
        key = f"exports/{user_id}/{export_id}.zip"
        payload = buffer.getvalue()
        await store.put(key, payload, "application/zip")
    except Exception:
        log.exception("archivio dei dati non riuscito")
        await session.rollback()
        await session.execute(
            text("update app.data_exports set status = 'failed' where id = :id"), {"id": export_id}
        )
        await session.commit()
        return True
    await session.execute(
        text(
            """update app.data_exports
                  set status = 'ready', storage_key = :key, size_bytes = :size,
                      ready_at = now(), expires_at = now() + cast(:ttl as interval)
                where id = :id"""
        ),
        {"id": export_id, "key": key, "size": len(payload), "ttl": EXPORT_TTL},
    )
    await notify(session, user_id=user_id, type="export_ready", dedupe_key=f"export:{export_id}")
    await session.commit()
    return True


async def expire_exports(session: AsyncSession, store: ObjectStore) -> int:
    """Archivi scaduti (7 giorni): via il file."""
    rows = (
        await session.execute(
            text(
                """update app.data_exports set status = 'expired'
                    where status = 'ready' and expires_at < now()
                   returning storage_key"""
            )
        )
    ).all()
    keys = [r[0] for r in rows if r[0]]
    await session.commit()
    if keys:
        await store.delete(*keys)
    return len(rows)


# ---------- Cancellazione definitiva ----------


class AuthAdmin(Protocol):
    async def delete_user(self, user_id: uuid.UUID) -> None: ...


class SupabaseAuthAdmin:
    """Cancella l'utente da Supabase Auth con la chiave segreta (solo sul server)."""

    def __init__(self, url: str, secret: str, client: httpx.AsyncClient | None = None):
        self._url = url.rstrip("/")
        self._headers = {"apikey": secret, "authorization": f"Bearer {secret}"}
        self._client = client or httpx.AsyncClient(timeout=15)

    async def delete_user(self, user_id: uuid.UUID) -> None:
        response = await self._client.delete(
            f"{self._url}/auth/v1/admin/users/{user_id}", headers=self._headers
        )
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()


class LocalAuthAdmin:
    """Sviluppo e test: non c'è Supabase. Il ruolo dell'API non può toccare auth.users (come in
    produzione), quindi qui si registra solo la richiesta; profilo e dati spariscono comunque."""

    def __init__(self) -> None:
        self.deleted: list[uuid.UUID] = []

    async def delete_user(self, user_id: uuid.UUID) -> None:
        self.deleted.append(user_id)


def auth_admin() -> AuthAdmin | None:
    settings = get_settings()
    if settings.supabase_secret_key is not None:
        return SupabaseAuthAdmin(
            settings.supabase_url, settings.supabase_secret_key.get_secret_value()
        )
    if settings.env in ("local", "test"):
        return LocalAuthAdmin()
    return None


async def _storage_keys(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    uploads = (
        await session.execute(
            text("select id, variants from app.media_uploads where owner_id = :me"),
            {"me": user_id},
        )
    ).all()
    keys = [quarantine_key(u) for u, _ in uploads]
    keys += [variant_key(u, w) for u, variants in uploads for w in (variants or [])]
    exports = (
        await session.execute(
            text(
                """select storage_key from app.data_exports
                    where user_id = :me and storage_key is not null"""
            ),
            {"me": user_id},
        )
    ).all()
    keys += [r[0] for r in exports]
    return keys


async def purge_deleted_accounts(
    session: AsyncSession, store: ObjectStore, admin: AuthAdmin | None = None
) -> int:
    """Account oltre i 30 giorni: foto, archivi, dati, e infine l'utente di Supabase Auth."""
    due = (
        (
            await session.execute(
                text(
                    """select id from app.profiles
                    where status = 'pending_deletion' and delete_after <= now()
                    order by delete_after limit 50"""
                )
            )
        )
        .scalars()
        .all()
    )
    admin = admin or auth_admin()
    done = 0
    for user_id in due:
        if admin is None:
            log.error("cancellazione account rimandata: manca WEARX_SUPABASE_SECRET_KEY")
            break
        keys = await _storage_keys(session, user_id)
        try:
            await admin.delete_user(user_id)
        except httpx.HTTPError:
            log.exception("utente Supabase non cancellato, si riprova domani")
            await session.rollback()
            continue
        # Se auth.users è altrove (Supabase), il profilo va tolto anche qui.
        await session.execute(text("delete from app.profiles where id = :id"), {"id": user_id})
        await session.commit()
        if keys:
            await store.delete(*keys)
        done += 1
        log.info("account cancellato definitivamente")
    return done
