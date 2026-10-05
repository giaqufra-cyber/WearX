"""Privacy e sicurezza (seduta 20): dispositivi, archivio dei dati, cancellazione dell'account.

- devices: una riga per accesso (session_id del token Supabase) con nome del telefono, ultima
  attività e, se tolto dalla persona, `revoked_at`: da quel momento l'API rifiuta i token di
  quell'accesso, anche se Supabase li rinnova.
- push_tokens.session_id: i push di un dispositivo tolto smettono subito.
- data_exports: archivio ZIP dei propri dati (GDPR art. 15 e 20), pronto in pochi minuti,
  scaricabile per 7 giorni.
- profiles.deletion_requested_at / delete_after: cancellazione con 30 giorni per ripensarci.
- moderation_actions.subject_id: alla cancellazione dell'account le decisioni restano senza
  riferimento alla persona (servono ai rapporti di trasparenza DSA), invece di sparire.
- notifiche: nuovo tipo 'export_ready'.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-05
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table app.devices (
          session_id  text primary key,
          user_id     uuid not null references app.profiles(id) on delete cascade,
          label       varchar(80) not null,
          platform    text not null check (platform in ('ios', 'android', 'web')),
          app_version varchar(20),
          created_at  timestamptz not null default now(),
          last_seen   timestamptz not null default now(),
          revoked_at  timestamptz
        );
        create index devices_user on app.devices (user_id, last_seen desc);

        alter table app.push_tokens add column session_id text;

        create table app.data_exports (
          id          uuid primary key default gen_random_uuid(),
          user_id     uuid not null references app.profiles(id) on delete cascade,
          status      text not null default 'pending'
            check (status in ('pending', 'ready', 'failed', 'expired')),
          storage_key text,
          size_bytes  bigint,
          created_at  timestamptz not null default now(),
          ready_at    timestamptz,
          expires_at  timestamptz
        );
        create index data_exports_user on app.data_exports (user_id, created_at desc);

        alter table app.profiles
          add column deletion_requested_at timestamptz,
          add column delete_after timestamptz;
        create index profiles_delete_after on app.profiles (delete_after)
          where status = 'pending_deletion';

        alter table app.moderation_actions
          drop constraint moderation_actions_subject_id_fkey,
          add constraint moderation_actions_subject_id_fkey foreign key (subject_id)
            references app.profiles(id) on delete set null;

        alter table app.notifications
          drop constraint notifications_type_check,
          add constraint notifications_type_check check (type in (
            'follow_request', 'new_follower', 'follow_accepted', 'vote_milestone',
            'moderation', 'appeal_decided', 'export_ready'));

        alter table app.devices enable row level security;
        alter table app.data_exports enable row level security;
        create policy api_access on app.devices for all to wearx_api using (true) with check (true);
        create policy api_access on app.data_exports for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.devices, app.data_exports to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        delete from app.notifications where type = 'export_ready';
        alter table app.notifications
          drop constraint notifications_type_check,
          add constraint notifications_type_check check (type in (
            'follow_request', 'new_follower', 'follow_accepted', 'vote_milestone',
            'moderation', 'appeal_decided'));
        alter table app.moderation_actions
          drop constraint moderation_actions_subject_id_fkey,
          add constraint moderation_actions_subject_id_fkey foreign key (subject_id)
            references app.profiles(id) on delete cascade;
        drop index app.profiles_delete_after;
        alter table app.profiles drop column delete_after, drop column deletion_requested_at;
        drop table app.data_exports;
        alter table app.push_tokens drop column session_id;
        drop table app.devices;
        """
    )
