"""Cerca persone e suggerimenti (seduta 31).

- `profiles.discoverable`: farsi trovare nella ricerca e nei suggerimenti. Null = scelta di base
  per età (sì per i maggiorenni, no per i 16-17); il nickname esatto trova sempre (come prima).
- Indice a trigrammi sul nickname per la ricerca "simile a".
- `suggestion_dismissals`: le persone suggerite che hai tolto con la X, per non riproportele.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-23
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.profiles add column discoverable boolean;

        create index profiles_nickname_trgm on app.profiles
          using gin ((nickname::text) gin_trgm_ops);

        create table app.suggestion_dismissals (
          user_id    uuid not null references app.profiles(id) on delete cascade,
          target_id  uuid not null references app.profiles(id) on delete cascade,
          created_at timestamptz not null default now(),
          primary key (user_id, target_id)
        );

        alter table app.suggestion_dismissals enable row level security;
        create policy api_access on app.suggestion_dismissals for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.suggestion_dismissals to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.suggestion_dismissals;
        drop index app.profiles_nickname_trgm;
        alter table app.profiles drop column discoverable;
        """
    )
