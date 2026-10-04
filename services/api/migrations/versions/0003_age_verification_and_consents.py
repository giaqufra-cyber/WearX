"""Verifiche dell'età e consenso ai termini.

- app.age_verifications: esito di ogni tentativo di verifica (sez. 11.2). Nessuna immagine,
  nessun documento, nessuna data di nascita: solo esito, metodo, fascia e data dei 18 anni.
- profiles.terms_version / terms_accepted_at: prova del consenso ai termini (GDPR art. 7).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create type app.age_check_status as enum ('pending', 'passed', 'failed', 'expired');

        create table app.age_verifications (
          id            uuid primary key default gen_random_uuid(),
          user_id       uuid not null references auth.users(id) on delete cascade,
          method        text not null check (method in ('selfie_estimation','id_document','spid','cie')),
          status        app.age_check_status not null default 'pending',
          age_band      app.age_band,
          adult_on      date,
          provider      text not null,
          provider_ref  text,
          created_at    timestamptz not null default now(),
          completed_at  timestamptz,
          check (status <> 'passed' or (age_band is not null and completed_at is not null)),
          check (age_band is distinct from '16_17' or adult_on is not null)
        );
        create index age_verifications_user on app.age_verifications (user_id, created_at desc);
        create unique index age_verifications_provider_ref
          on app.age_verifications (provider, provider_ref) where provider_ref is not null;

        alter table app.age_verifications enable row level security;
        create policy api_access on app.age_verifications for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.age_verifications to wearx_api;

        alter table app.profiles
          add column terms_version text,
          add column terms_accepted_at timestamptz;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table app.profiles drop column terms_accepted_at, drop column terms_version;
        drop table app.age_verifications;
        drop type app.age_check_status;
        """
    )
