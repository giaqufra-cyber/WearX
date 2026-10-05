"""Link ai negozi e account Business (seduta 21).

- link_status 'broken': il negozio risponde che la pagina non esiste più (404/410) o il sito
  non esiste; il capo resta, il link si mostra come "non raggiungibile".
- links: dove porta davvero (final_url, dopo i redirect), perché è bloccato (block_reason),
  quando ricontrollarlo (next_check_at), fallimenti di fila (fail_count), click dal redirect.
- blocked_domains: domini bloccati dallo staff (phishing, truffe, siti segnalati): bloccano
  subito tutti i link verso quel dominio e i suoi sottodomini.
- business_domains: i siti di un account Business; "verificato" dopo aver pubblicato un file
  con il codice su https://<dominio>/.well-known/wearx-verify.txt. Un dominio verificato ha un
  solo proprietario.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-05
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Il nuovo valore dell'enum va aggiunto fuori dalla transazione che poi lo usa.
    with op.get_context().autocommit_block():
        op.execute("alter type app.link_status add value if not exists 'broken'")
    op.execute(
        """
        alter table app.links
          add column final_url     text check (final_url is null or length(final_url) <= 2048),
          add column block_reason  text,
          add column fail_count    integer not null default 0,
          add column next_check_at timestamptz not null default now(),
          add column clicks        bigint not null default 0;
        create index links_due on app.links (next_check_at) where status <> 'blocked';

        create table app.blocked_domains (
          domain     text primary key,
          reason     text not null,
          created_by uuid,
          created_at timestamptz not null default now()
        );

        create table app.business_domains (
          user_id         uuid not null references app.profiles(id) on delete cascade,
          domain          text not null,
          token           text not null,
          verified_at     timestamptz,
          last_checked_at timestamptz,
          created_at      timestamptz not null default now(),
          primary key (user_id, domain)
        );
        create unique index business_domains_owner on app.business_domains (domain)
          where verified_at is not null;

        alter table app.blocked_domains enable row level security;
        alter table app.business_domains enable row level security;
        create policy api_access on app.blocked_domains for all to wearx_api
          using (true) with check (true);
        create policy api_access on app.business_domains for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.blocked_domains, app.business_domains
          to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.business_domains;
        drop table app.blocked_domains;
        drop index app.links_due;
        alter table app.links
          drop column clicks, drop column next_check_at, drop column fail_count,
          drop column block_reason, drop column final_url;
        update app.links set status = 'pending' where status = 'broken';
        """
    )
    # Il valore 'broken' resta nell'enum (PostgreSQL non permette di toglierlo): non è usato.
