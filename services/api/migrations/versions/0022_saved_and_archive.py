"""Fit salvati e archivio (seduta 32).

- `saved_posts`: i fit degli altri che hai salvato. Li vedi solo tu; l'autore vede solo quante
  volte un suo fit è stato salvato, mai da chi.
- `posts.archived_at`: un tuo fit archiviato sparisce per tutti gli altri (feed, profilo, pagina
  dello stile) ma non si cancella: lo ritrovi in Archivio e lo rimetti al suo posto quando vuoi.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-23
"""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.posts add column archived_at timestamptz;
        create index posts_archived on app.posts (author_id, archived_at desc, id desc)
          where archived_at is not null;

        create table app.saved_posts (
          user_id    uuid not null references app.profiles(id) on delete cascade,
          post_id    uuid not null references app.posts(id) on delete cascade,
          created_at timestamptz not null default now(),
          primary key (user_id, post_id)
        );
        create index saved_posts_list on app.saved_posts (user_id, created_at desc, post_id desc);
        create index saved_posts_post on app.saved_posts (post_id);

        alter table app.saved_posts enable row level security;
        create policy api_access on app.saved_posts for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.saved_posts to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.saved_posts;
        drop index app.posts_archived;
        alter table app.posts drop column archived_at;
        """
    )
