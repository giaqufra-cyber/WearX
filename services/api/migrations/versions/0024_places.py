"""Luogo del fit (seduta 35).

- `places`: i luoghi scelti per i fit (un locale, una via, una città), presi da una ricerca su
  mappa (OpenStreetMap). Solo luoghi con un nome: mai indirizzi di casa. Le coordinate sono
  quelle pubbliche del luogo, non la posizione del telefono.
- `posts.place_id`: facoltativo. Se il luogo sparisse, il fit resta senza.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-30
"""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table app.places (
          id           uuid primary key default gen_random_uuid(),
          provider     text not null check (provider in ('photon', 'fake')),
          provider_ref text not null check (char_length(provider_ref) <= 80),
          kind         text not null
                       check (kind in ('venue', 'street', 'area', 'city', 'region', 'country')),
          name         text not null check (char_length(name) between 1 and 120),
          detail       text check (char_length(detail) <= 160),
          country_code text check (country_code ~ '^[A-Z]{2}$'),
          lat          numeric(8, 5) not null check (lat between -90 and 90),
          lon          numeric(8, 5) not null check (lon between -180 and 180),
          created_at   timestamptz not null default now(),
          unique (provider, provider_ref)
        );
        alter table app.places enable row level security;
        create policy api_access on app.places for all to wearx_api using (true) with check (true);
        grant select, insert, update on app.places to wearx_api;

        alter table app.posts add column place_id uuid references app.places(id)
          on delete set null;
        create index posts_place on app.posts (place_id) where place_id is not null;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table app.posts drop column place_id;
        drop table app.places;
        """
    )
