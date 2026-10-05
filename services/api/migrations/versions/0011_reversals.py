"""Decisioni annullate: quando e da quale ripristino.

Finora "annullata" si ricavava dal reclamo accolto, ma una sanzione decisa insieme a un fit
cade con il fit senza un reclamo suo, e un moderatore può annullare una sospensione automatica.
Con reversed_at la scala delle sanzioni conta solo le decisioni ancora in piedi.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-05
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.moderation_actions
          add column reversed_at timestamptz,
          add column reversed_by uuid references app.moderation_actions(id) on delete set null;

        update app.moderation_actions m
           set reversed_at = a.decided_at
          from app.appeals a
         where a.action_id = m.id and a.status = 'reversed';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table app.moderation_actions
          drop column reversed_by,
          drop column reversed_at;
        """
    )
