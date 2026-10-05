"""Moderazione (sez. 13.2 DSA, 14.2-14.3): staff, liste di hash, reclami, sanzioni.

- staff: chi può usare la coda di moderazione (moderator) e gestire lo staff (admin).
- blocked_hashes: impronte di foto da non accettare più. 'csam' = materiale illegale noto
  (dal servizio esterno o inserito su indicazione delle autorità), 'removed' = foto rimosse dai
  moderatori (non si ricaricano uguali o quasi uguali).
- media_uploads.scan_labels / needs_review: cosa ha visto il classificatore; una foto "da
  rivedere" passa, ma il fit che la usa entra in coda.
- profiles.posting_blocked_until: sospensione della pubblicazione (7 giorni, sez. 14.3),
  azione 'limit_posting'.
- reports: una sola segnalazione aperta per persona e contenuto; chiusura con chi e quando;
  segnalazioni automatiche (reporter assente, auto = true).
- moderation_actions: chi è colpito (subject_id), fino a quando (expires_at), quale
  segnalazione l'ha generata. Motivazione sempre presente (statement), art. 17 DSA.
- appeals: un reclamo per decisione (art. 20 DSA), entro 6 mesi.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-05
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table app.staff (
          user_id    uuid primary key references auth.users(id) on delete cascade,
          role       text not null check (role in ('moderator', 'admin')),
          created_at timestamptz not null default now()
        );

        create table app.blocked_hashes (
          id         bigint generated always as identity primary key,
          sha256     bytea,
          phash      bigint,
          kind       text not null check (kind in ('csam', 'removed')),
          source     text not null,
          created_at timestamptz not null default now(),
          check (sha256 is not null or phash is not null)
        );
        create unique index blocked_hashes_sha on app.blocked_hashes (sha256)
          where sha256 is not null;
        create index blocked_hashes_phash on app.blocked_hashes (phash) where phash is not null;

        alter table app.media_uploads
          add column scan_labels jsonb,
          add column needs_review boolean not null default false;

        alter table app.profiles add column posting_blocked_until timestamptz;

        alter table app.reports
          add column auto boolean not null default false,
          add column resolved_at timestamptz,
          add column resolved_by uuid,
          add constraint reports_reporter_or_auto check (auto or reporter_id is not null);
        create unique index reports_one_open on app.reports (reporter_id, target_type, target_id)
          where status in ('open', 'in_review') and reporter_id is not null;
        create index reports_target on app.reports (target_type, target_id, status);

        alter table app.moderation_actions
          drop constraint moderation_actions_action_check,
          add constraint moderation_actions_action_check check (action in (
            'hide', 'remove', 'restyle', 'suspend', 'ban', 'restore', 'warn', 'limit_posting')),
          add column subject_id uuid references app.profiles(id) on delete cascade,
          add column expires_at timestamptz,
          add column report_reason text;
        create index moderation_actions_subject on app.moderation_actions (subject_id, created_at desc);

        create table app.appeals (
          id           uuid primary key default gen_random_uuid(),
          action_id    uuid not null unique references app.moderation_actions(id) on delete cascade,
          user_id      uuid not null references app.profiles(id) on delete cascade,
          text         varchar(1000) not null,
          status       text not null default 'open' check (status in ('open', 'upheld', 'reversed')),
          created_at   timestamptz not null default now(),
          decided_at   timestamptz,
          decided_by   uuid,
          decision_note varchar(1000)
        );
        create index appeals_queue on app.appeals (status, created_at) where status = 'open';

        alter table app.staff enable row level security;
        alter table app.blocked_hashes enable row level security;
        alter table app.appeals enable row level security;
        create policy api_access on app.staff for all to wearx_api using (true) with check (true);
        create policy api_access on app.blocked_hashes for all to wearx_api
          using (true) with check (true);
        create policy api_access on app.appeals for all to wearx_api using (true) with check (true);
        grant select, insert, update, delete on app.staff, app.blocked_hashes, app.appeals
          to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.appeals;
        drop index app.moderation_actions_subject;
        alter table app.moderation_actions
          drop column report_reason, drop column expires_at, drop column subject_id,
          drop constraint moderation_actions_action_check,
          add constraint moderation_actions_action_check check (action in (
            'hide', 'remove', 'restyle', 'suspend', 'ban', 'restore', 'warn'));
        drop index app.reports_target;
        drop index app.reports_one_open;
        alter table app.reports
          drop constraint reports_reporter_or_auto,
          drop column resolved_by, drop column resolved_at, drop column auto;
        alter table app.profiles drop column posting_blocked_until;
        alter table app.media_uploads drop column needs_review, drop column scan_labels;
        drop table app.blocked_hashes;
        drop table app.staff;
        """
    )
