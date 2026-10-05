"""Hardening dei voti e dei dispositivi (seduta 22).

- post_stats: valori PUBBLICATI (shown_*), quelli che vedono le persone, separati da quelli in
  tempo reale (vote_*, usati dal feed e dallo staff). Un lavoro ogni ora copia il conteggio e,
  solo con almeno 5 voti e almeno 3 voti nuovi o cambiati dall'ultima volta, la media e le
  conferme dello stile: guardando la media nessuno ricava il voto di una singola persona.
  unpublished_writes conta i voti nuovi o cambiati non ancora nella media pubblicata.
- votes.base_weight: il peso al momento del voto (account nuovo, dispositivo verificato);
  votes.weight resta il peso usato nelle statistiche, ridotto dai segnali di abuso.
- vote_flags: votanti (pseudonimi) con i voti neutralizzati, da una regola automatica, per
  tutti i fit o per i fit di un autore; lo staff può ripristinarli.
- devices: attestazione del dispositivo (App Attest su iOS, Play Integrity su Android).
- attest_keys: chiavi App Attest dei dispositivi iOS (la chiave pubblica e il contatore).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-05
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.post_stats
          add column shown_count        integer not null default 0,
          add column shown_wsum         double precision not null default 0,
          add column shown_wcount       double precision not null default 0,
          add column shown_confirm_yes  integer not null default 0,
          add column shown_confirm_no   integer not null default 0,
          add column shown_at           timestamptz,
          add column unpublished_writes integer not null default 0;

        -- Punto di partenza: quello che si vedeva finora (nessuna informazione nuova).
        update app.post_stats set
          shown_count = vote_count,
          shown_wsum = case when vote_count >= 5 then vote_wsum else 0 end,
          shown_wcount = case when vote_count >= 5 then vote_wcount else 0 end,
          shown_confirm_yes = confirm_yes,
          shown_confirm_no = confirm_no,
          shown_at = now();
        -- Nessun indice sulle colonne che cambiano a ogni voto (resterebbero possibili gli
        -- aggiornamenti "HOT" di PostgreSQL): il lavoro orario legge la tabella intera.

        -- I traguardi di voti contano il numero pubblicato. Il vecchio indice usava vote_count,
        -- che cambia a ogni voto.
        drop index app.post_stats_milestone_due;
        create index post_stats_milestone_due on app.post_stats (post_id)
          where shown_count >= vote_milestone_next;

        alter table app.votes add column base_weight real;
        update app.votes set base_weight = weight;
        alter table app.votes
          alter column base_weight set not null,
          alter column base_weight set default 1.0,
          add constraint votes_base_weight_check check (base_weight between 0 and 1);

        create table app.vote_flags (
          id             bigint generated always as identity primary key,
          voter_key      bytea not null check (octet_length(voter_key) = 32),
          -- null: tutti i fit; altrimenti solo i fit di questo autore.
          author_id      uuid references app.profiles(id) on delete cascade,
          rule           text not null check (rule in ('same_score', 'author_burst')),
          factor         real not null default 0 check (factor between 0 and 1),
          votes_affected integer not null default 0,
          detail         jsonb not null default '{}',
          detected_at    timestamptz not null default now(),
          expires_at     timestamptz not null,
          lifted_at      timestamptz,
          lifted_by      uuid
        );
        create index vote_flags_voter on app.vote_flags (voter_key) where lifted_at is null;
        create index vote_flags_recent on app.vote_flags (detected_at desc);

        alter table app.devices
          add column attested_at     timestamptz,
          add column attest_platform text check (attest_platform in ('ios', 'android')),
          add column attest_detail   text;

        create table app.attest_keys (
          key_id       text primary key,
          user_id      uuid not null references app.profiles(id) on delete cascade,
          public_key   bytea not null,
          sign_count   bigint not null default 0,
          environment  text not null check (environment in ('production', 'development')),
          created_at   timestamptz not null default now(),
          last_used_at timestamptz
        );
        create index attest_keys_user on app.attest_keys (user_id);

        alter table app.vote_flags enable row level security;
        alter table app.attest_keys enable row level security;
        create policy api_access on app.vote_flags for all to wearx_api
          using (true) with check (true);
        create policy api_access on app.attest_keys for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.vote_flags, app.attest_keys to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table app.attest_keys;
        alter table app.devices
          drop column attest_detail, drop column attest_platform, drop column attested_at;
        drop table app.vote_flags;
        alter table app.votes drop column base_weight;
        drop index app.post_stats_milestone_due;
        create index post_stats_milestone_due on app.post_stats (post_id)
          where vote_count >= vote_milestone_next;
        alter table app.post_stats
          drop column unpublished_writes, drop column shown_at, drop column shown_confirm_no,
          drop column shown_confirm_yes, drop column shown_wcount, drop column shown_wsum,
          drop column shown_count;
        """
    )
