"""Feedback dei tester (seduta 25): "Segnala un problema" dall'app, letto dallo staff.

Il messaggio è della persona: si cancella con l'account (cascade) e finisce nel suo archivio
dei dati. Oltre al testo si salvano solo versione dell'app, sistema e la schermata da cui è
partito (per riprodurre il problema): niente registri, niente dati del telefono.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-06
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create type app.feedback_kind as enum ('bug', 'idea', 'other');
        create type app.feedback_status as enum ('new', 'seen', 'done');

        create table app.feedback (
          id           uuid primary key default gen_random_uuid(),
          author_id    uuid not null references app.profiles(id) on delete cascade,
          kind         app.feedback_kind not null,
          message      text not null check (char_length(message) between 3 and 2000),
          app_version  text not null check (char_length(app_version) <= 20),
          platform     text not null check (platform in ('ios', 'android', 'web')),
          os_version   text check (char_length(os_version) <= 20),
          screen       text check (char_length(screen) <= 100),
          status       app.feedback_status not null default 'new',
          staff_note   text check (char_length(staff_note) <= 500),
          created_at   timestamptz not null default now(),
          updated_at   timestamptz not null default now()
        );
        create index feedback_open on app.feedback (created_at desc) where status <> 'done';
        create index feedback_author on app.feedback (author_id, created_at desc);

        alter table app.feedback enable row level security;
        create policy api_access on app.feedback for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.feedback to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.feedback;
        drop type app.feedback_status;
        drop type app.feedback_kind;
        """
    )
