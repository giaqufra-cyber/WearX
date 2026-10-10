"""Foto profilo (seduta 27).

La foto profilo è un caricamento come quelli dei fit (stessi controlli: quarantena, scansione,
varianti WebP), "agganciato" al profilo invece che a un post. Si cancella con l'account (il
caricamento è della persona) e, se lo staff la toglie, il profilo torna alle iniziali.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-10
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.profiles
          add column avatar_upload_id uuid unique
            references app.media_uploads(id) on delete set null;
        """
    )


def downgrade() -> None:
    op.execute("alter table app.profiles drop column avatar_upload_id;")
