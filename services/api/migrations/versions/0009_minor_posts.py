"""Tutele 16-17 (sez. 14.1): i fit pubblicati da un 16-17enne li vedono solo i 16-17.

- posts.minor_author: l'autore aveva 16-17 anni quando ha pubblicato. Resta vero anche dopo
  i 18 anni: le foto di quando era minorenne non diventano visibili agli adulti.
- indice per le richieste di follow in arrivo, dalla più recente.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-05
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.posts add column minor_author boolean not null default false;
        update app.posts p set minor_author = true
          from app.profiles a
         where a.id = p.author_id and a.age_band = '16_17';

        create index follows_followee_recent on app.follows (followee_id, status, created_at desc);
        create index follows_follower_recent on app.follows (follower_id, status, created_at desc);
        create index blocks_blocker_recent on app.blocks (blocker_id, created_at desc);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop index app.blocks_blocker_recent;
        drop index app.follows_follower_recent;
        drop index app.follows_followee_recent;
        alter table app.posts drop column minor_author;
        """
    )
