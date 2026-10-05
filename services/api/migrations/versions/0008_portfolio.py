"""Portfolio: copertina scelta dall'utente, capsule senza doppioni di nome, filtro per capsula.

- profiles.portfolio_cover_id: il fit che l'utente ha messo in testa al portfolio. Finché è
  vuoto la copertina è semplicemente il fit più recente; dopo il primo riordino resta quella
  scelta e i fit nuovi entrano subito sotto di lei (non la "rubano").
- capsules: nome unico per persona senza distinguere maiuscole ("Estate" = "estate"),
  data di creazione, posizione >= 0.
- indice per mostrare un portfolio filtrato per capsula nell'ordine scelto.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-05
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.profiles
          add column portfolio_cover_id uuid references app.posts(id) on delete set null;

        alter table app.capsules
          add column created_at timestamptz not null default now(),
          add constraint capsules_position_check check (position >= 0),
          add constraint capsules_name_check check (length(btrim(name)) between 1 and 30);
        create unique index capsules_owner_name_ci on app.capsules (owner_id, lower(name));
        create index capsules_owner on app.capsules (owner_id, position);

        create index posts_capsule on app.posts (capsule_id, portfolio_rank)
          where status <> 'deleted' and capsule_id is not null;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop index app.posts_capsule;
        drop index app.capsules_owner;
        drop index app.capsules_owner_name_ci;
        alter table app.capsules
          drop constraint capsules_name_check,
          drop constraint capsules_position_check,
          drop column created_at;
        alter table app.profiles drop column portfolio_cover_id;
        """
    )
