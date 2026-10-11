"""Stili proposti dagli utenti (seduta 30).

Chiunque può proporre uno stile che non c'è; gli altri lo "vogliono" anche loro. Quando le
richieste arrivano alla soglia (`WEARX_STYLE_PROPOSAL_THRESHOLD`, 25 di base) lo stile si attiva
da solo e chi l'ha chiesto ci entra. Lo staff può respingere una proposta o spegnere lo stile.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-11
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create type app.proposal_status as enum ('open', 'approved', 'rejected');

        create table app.style_proposals (
          id           uuid primary key default gen_random_uuid(),
          name         text not null check (char_length(name) between 2 and 30),
          name_key     text not null,
          tagline      text check (char_length(tagline) <= 60),
          category     text not null check (category in
                         ('stili', 'sport', 'accessori', 'beauty', 'sottoculture', 'occasioni')),
          created_by   uuid references app.profiles(id) on delete set null,
          status       app.proposal_status not null default 'open',
          style_id     smallint references app.styles(id) on delete set null,
          decided_by   uuid references app.profiles(id) on delete set null,
          decided_at   timestamptz,
          staff_note   text check (char_length(staff_note) <= 300),
          created_at   timestamptz not null default now()
        );
        -- Una sola proposta aperta per nome (senza accenti, maiuscole e spazi).
        create unique index style_proposals_open_name on app.style_proposals (name_key)
          where status = 'open';
        create index style_proposals_status on app.style_proposals (status, created_at desc);

        create table app.style_proposal_supports (
          proposal_id uuid not null references app.style_proposals(id) on delete cascade,
          user_id     uuid not null references app.profiles(id) on delete cascade,
          created_at  timestamptz not null default now(),
          primary key (proposal_id, user_id)
        );
        create index style_proposal_supports_user on app.style_proposal_supports (user_id);

        alter table app.style_proposals enable row level security;
        alter table app.style_proposal_supports enable row level security;
        create policy api_access on app.style_proposals for all to wearx_api
          using (true) with check (true);
        create policy api_access on app.style_proposal_supports for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.style_proposals to wearx_api;
        grant select, insert, update, delete on app.style_proposal_supports to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.style_proposal_supports;
        drop table app.style_proposals;
        drop type app.proposal_status;
        """
    )
