"""Flusso di verifica dell'età: motivo dell'esito negativo e data dichiarata provvisoria.

- failure_reason: perché una verifica non è passata (l'app mostra il passo successivo giusto).
- declared_adult_on: data dei 18 anni ricavata dalla data di nascita dichiarata in
  registrazione. Serve SOLO finché la verifica è in corso (confronto con l'esito del
  fornitore) e il vincolo la obbliga a sparire quando la verifica si chiude.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-04
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.age_verifications
          add column failure_reason text
            check (failure_reason in ('underage', 'inconsistent', 'not_completed')),
          add column declared_adult_on date,
          add constraint age_verifications_declared_only_pending
            check (status = 'pending' or declared_adult_on is null),
          add constraint age_verifications_failure_has_reason
            check ((status = 'failed') = (failure_reason is not null));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table app.age_verifications
          drop constraint age_verifications_failure_has_reason,
          drop constraint age_verifications_declared_only_pending,
          drop column declared_adult_on,
          drop column failure_reason;
        """
    )
