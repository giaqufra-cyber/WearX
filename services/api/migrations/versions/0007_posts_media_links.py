"""Post: foto collegate ai caricamenti, link unici, indici per profilo.

- post_media.upload_id / variants: da quale caricamento viene la foto e quali larghezze
  WebP esistono (per firmare gli URL giusti).
- links.url unico: lo stesso negozio citato da mille post è una riga sola (e un solo controllo).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-05
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.post_media
          add column upload_id uuid unique references app.media_uploads(id) on delete set null,
          add column variants smallint[] not null default '{}';

        create unique index links_url on app.links (url);
        create index posts_author on app.posts (author_id, created_at desc)
          where status <> 'deleted';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop index app.posts_author;
        drop index app.links_url;
        alter table app.post_media drop column variants, drop column upload_id;
        """
    )
