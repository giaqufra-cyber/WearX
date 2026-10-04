"""Caricamenti delle foto: quarantena, elaborazione, esito (sez. 7).

Una foto passa da qui prima di diventare parte di un post:
pending (URL firmato rilasciato) -> processing (caricata, in coda al worker)
-> ready (pulita: niente EXIF/GPS, varianti WebP, blurhash, hash) oppure rejected.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-05
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create type app.upload_status as enum ('pending', 'processing', 'ready', 'rejected');

        create table app.media_uploads (
          id              uuid primary key default gen_random_uuid(),
          owner_id        uuid not null references app.profiles(id) on delete cascade,
          status          app.upload_status not null default 'pending',
          content_type    text not null
                          check (content_type in ('image/jpeg', 'image/png', 'image/webp')),
          declared_bytes  integer not null check (declared_bytes between 1 and 15728640),
          width           integer check (width > 0),
          height          integer check (height > 0),
          blurhash        text,
          sha256          bytea check (octet_length(sha256) = 32),
          phash           bigint,
          variants        smallint[],
          reject_reason   text check (reject_reason in (
                            'too_large', 'not_an_image', 'unsupported_format', 'too_many_pixels',
                            'too_small', 'bad_aspect_ratio', 'blocked', 'processing_error',
                            'expired')),
          attached_at     timestamptz,
          created_at      timestamptz not null default now(),
          uploaded_at     timestamptz,
          processed_at    timestamptz,
          constraint media_ready_complete check (
            (status = 'ready') = (width is not null and height is not null and blurhash is not null
                                  and sha256 is not null and variants is not null)),
          constraint media_rejected_has_reason check ((status = 'rejected') = (reject_reason is not null))
        );
        create index media_uploads_owner on app.media_uploads (owner_id, created_at desc);
        create index media_uploads_cleanup on app.media_uploads (status, created_at)
          where attached_at is null;
        create index media_uploads_sha on app.media_uploads (sha256) where sha256 is not null;

        alter table app.media_uploads enable row level security;
        create policy api_access on app.media_uploads for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.media_uploads to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.media_uploads;
        drop type app.upload_status;
        """
    )
