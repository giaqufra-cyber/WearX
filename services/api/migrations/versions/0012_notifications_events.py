"""Notifiche, push e raccolta eventi (seduta 18).

- notifications: chi l'ha causata (actor_id), su quale fit (post_id), una chiave per non
  duplicare la stessa notizia (dedupe_key) e lo stato del push (outbox: la riga nasce nella
  stessa transazione dell'azione, un lavoro in background la spedisce).
- profiles.notify_*: quali push ricevere (la lista nell'app resta sempre completa).
- push_tokens: data di registrazione; push_receipts: ricevute Expo da controllare dopo 15 minuti
  (servono a togliere i telefoni che non esistono più).
- post_stats.vote_milestone_next: prossimo traguardo di voti da notificare (indice parziale: il
  lavoro che li cerca legge solo i fit che l'hanno appena superato).
- events: partizioni mensili create in anticipo e cancellate dopo 3 mesi (gli Insight della
  seduta 19 tengono solo i totali giornalieri). Le funzioni girano con i permessi del
  proprietario dello schema: il ruolo dell'API non può creare o cancellare tabelle.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-05
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table app.notifications
          add column actor_id    uuid references app.profiles(id) on delete cascade,
          add column post_id     uuid references app.posts(id) on delete cascade,
          add column dedupe_key  text,
          add column push_state  text not null default 'none'
            check (push_state in ('none', 'pending', 'sent', 'skipped', 'failed')),
          add column push_after  timestamptz,
          add column pushed_at   timestamptz,
          add constraint notifications_type_check check (type in (
            'follow_request', 'new_follower', 'follow_accepted', 'vote_milestone',
            'moderation', 'appeal_decided'));
        create unique index notifications_dedupe on app.notifications (user_id, dedupe_key)
          where dedupe_key is not null;
        create index notifications_unread on app.notifications (user_id)
          where read_at is null;
        create index notifications_outbox on app.notifications (push_after)
          where push_state = 'pending';
        create index notifications_actor on app.notifications (actor_id) where actor_id is not null;

        alter table app.profiles
          add column notify_follows    boolean not null default true,
          add column notify_votes      boolean not null default true,
          add column notify_moderation boolean not null default true;

        alter table app.push_tokens
          add column created_at timestamptz not null default now();
        create index push_tokens_user on app.push_tokens (user_id);

        create table app.push_receipts (
          ticket_id  text primary key,
          token      text not null,
          created_at timestamptz not null default now()
        );

        alter table app.post_stats
          add column vote_milestone_next integer not null default 10;
        create index post_stats_milestone_due on app.post_stats (post_id)
          where vote_count >= vote_milestone_next;
        -- Fit già pubblicati: contano solo i traguardi raggiunti da adesso (niente valanga
        -- di notifiche al primo avvio).
        update app.post_stats s
           set vote_milestone_next = coalesce(
             (select min(m) from unnest(array[10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]) m
               where m > s.vote_count), 2147483647);

        create index events_post on app.events (post_id, ts) where post_id is not null;

        alter table app.push_receipts enable row level security;
        create policy api_access on app.push_receipts for all to wearx_api
          using (true) with check (true);
        grant select, insert, update, delete on app.push_receipts to wearx_api;

        create function app.ensure_event_partitions(months_ahead integer default 2)
          returns integer
          language plpgsql security definer set search_path = app, pg_temp
        as $$
        declare
          i integer;
          lo timestamptz;
          hi timestamptz;
          part text;
          made integer := 0;
        begin
          for i in 0..months_ahead loop
            lo := (date_trunc('month', now() at time zone 'UTC')
                   + make_interval(months => i)) at time zone 'UTC';
            hi := (date_trunc('month', now() at time zone 'UTC')
                   + make_interval(months => i + 1)) at time zone 'UTC';
            part := 'events_' || to_char(lo at time zone 'UTC', 'YYYY_MM');
            if to_regclass('app.' || part) is null then
              -- Righe già finite nella partizione di riserva: spostate nella nuova.
              create temp table if not exists moved_events
                (like app.events) on commit drop;
              with gone as (
                delete from app.events_default where ts >= lo and ts < hi returning *
              )
              insert into moved_events select * from gone;
              execute format(
                'create table app.%I partition of app.events for values from (%L) to (%L)',
                part, lo, hi);
              -- Accesso solo dalla tabella madre (con le sue regole), mai diretto.
              execute format('alter table app.%I enable row level security', part);
              insert into app.events overriding system value select * from moved_events;
              truncate moved_events;
              made := made + 1;
            end if;
          end loop;
          return made;
        end;
        $$;

        create function app.drop_old_event_partitions(keep_months integer default 3)
          returns integer
          language plpgsql security definer set search_path = app, pg_temp
        as $$
        declare
          cutoff timestamptz := (date_trunc('month', now() at time zone 'UTC')
                                 - make_interval(months => keep_months)) at time zone 'UTC';
          r record;
          dropped integer := 0;
        begin
          for r in
            select c.relname from pg_inherits i
              join pg_class c on c.oid = i.inhrelid
             where i.inhparent = 'app.events'::regclass
               and c.relname ~ '^events_[0-9]{4}_[0-9]{2}$'
          loop
            if (to_date(substr(r.relname, 8), 'YYYY_MM') + interval '1 month')
                 <= (cutoff at time zone 'UTC')::date then
              execute format('drop table app.%I', r.relname);
              dropped := dropped + 1;
            end if;
          end loop;
          delete from app.events_default where ts < cutoff;
          return dropped;
        end;
        $$;

        revoke all on function app.ensure_event_partitions(integer) from public;
        revoke all on function app.drop_old_event_partitions(integer) from public;
        grant execute on function app.ensure_event_partitions(integer) to wearx_api;
        grant execute on function app.drop_old_event_partitions(integer) to wearx_api;

        select app.ensure_event_partitions(2);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        do $$
        declare r record;
        begin
          for r in
            select c.relname from pg_inherits i join pg_class c on c.oid = i.inhrelid
             where i.inhparent = 'app.events'::regclass and c.relname <> 'events_default'
          loop
            execute format('drop table app.%I', r.relname);
          end loop;
        end $$;
        drop function app.drop_old_event_partitions(integer);
        drop function app.ensure_event_partitions(integer);
        drop index app.events_post;
        drop index app.post_stats_milestone_due;
        alter table app.post_stats drop column vote_milestone_next;
        drop table app.push_receipts;
        drop index app.push_tokens_user;
        alter table app.push_tokens drop column created_at;
        alter table app.profiles
          drop column notify_moderation, drop column notify_votes, drop column notify_follows;
        drop index app.notifications_actor;
        drop index app.notifications_outbox;
        drop index app.notifications_unread;
        drop index app.notifications_dedupe;
        alter table app.notifications
          drop constraint notifications_type_check,
          drop column pushed_at, drop column push_after, drop column push_state,
          drop column dedupe_key, drop column post_id, drop column actor_id;
        """
    )
