"""Insight per chi pubblica (seduta 19).

- insight_daily: totali giornalieri per fit (giorno = data italiana). `opens` = aperture del fit;
  le visite al profilo non sono di un fit e passano in insight_profile_daily.
  Visualizzazioni, aperture e click contano PERSONE DIVERSE in quel giorno (una persona che
  guarda dieci volte lo stesso fit conta una).
- Collegamenti con profili e fit: cancellato l'account o il fit, spariscono anche i suoi totali.
- job_runs: quando un lavoro periodico ha finito l'ultima volta ("aggiornato a…").
- votes_created: indice per contare i voti di un giorno senza leggere tutta la tabella.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-05
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        delete from app.insight_daily;
        alter table app.insight_daily
          drop column profile_views,
          add column opens integer not null default 0,
          add constraint insight_daily_author_fk foreign key (author_id)
            references app.profiles(id) on delete cascade,
          add constraint insight_daily_post_fk foreign key (post_id)
            references app.posts(id) on delete cascade;
        create index insight_daily_author_day on app.insight_daily (author_id, day);

        create table app.insight_profile_daily (
          author_id     uuid not null references app.profiles(id) on delete cascade,
          day           date not null,
          profile_views integer not null default 0,
          primary key (author_id, day)
        );

        create table app.job_runs (
          name        text primary key,
          finished_at timestamptz not null,
          details     jsonb not null default '{}'
        );

        create index votes_created on app.votes (created_at);

        alter table app.insight_profile_daily enable row level security;
        alter table app.job_runs enable row level security;
        create policy api_access on app.insight_profile_daily for all to wearx_api
          using (true) with check (true);
        create policy api_access on app.job_runs for all to wearx_api using (true) with check (true);
        grant select, insert, update, delete on app.insight_profile_daily, app.job_runs
          to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop index app.votes_created;
        drop table app.job_runs;
        drop table app.insight_profile_daily;
        drop index app.insight_daily_author_day;
        alter table app.insight_daily
          drop constraint insight_daily_post_fk,
          drop constraint insight_daily_author_fk,
          drop column opens,
          add column profile_views integer not null default 0;
        """
    )
