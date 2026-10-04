"""Schema iniziale di WearX (specifica tecnica v0.1, sezione 7).

Differenze rispetto alla specifica, decise in seduta 1:
- tabelle e tipi nello schema `app` invece di `public`, così le API automatiche di
  Supabase (PostgREST) non le espongono mai;
- `profiles.adult_on` (data dei 18 anni per gli utenti 16-17, sez. 11.2);
- `styles.sort_order` per l'ordine di visualizzazione;
- `events` con chiave (id, ts) e partizione di default, le partizioni mensili le crea un job;
- `admin_audit_log` senza UPDATE/DELETE per il ruolo dell'API (log immutabile).

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP_TABLES = [
    "profiles",
    "styles",
    "style_memberships",
    "follows",
    "blocks",
    "capsules",
    "posts",
    "post_media",
    "links",
    "post_items",
    "votes",
    "post_stats",
    "saves",
    "reports",
    "moderation_actions",
    "notifications",
    "push_tokens",
    "events",
    "insight_daily",
    "admin_audit_log",
]

UPGRADE_SQL = r"""
create extension if not exists citext;
create extension if not exists pg_trgm;

-- In locale e nei test non c'è Supabase: si crea una tabella auth.users minima.
-- Su Supabase auth.users esiste già e questo blocco non fa nulla.
do $$
begin
  if to_regclass('auth.users') is null then
    create schema if not exists auth;
    create table auth.users (
      id uuid primary key default gen_random_uuid(),
      created_at timestamptz not null default now()
    );
    comment on table auth.users is 'wearx-local-stub';
  end if;
end $$;

create schema app;

create type app.account_type  as enum ('private','business');
create type app.age_band      as enum ('16_17','18_plus');
create type app.user_status   as enum ('active','suspended','pending_deletion');
create type app.post_status   as enum ('processing','active','style_rejected','hidden_moderation','deleted');
create type app.follow_status as enum ('pending','accepted');
create type app.link_status   as enum ('pending','safe','blocked');

create table app.profiles (
  id               uuid primary key references auth.users(id) on delete cascade,
  -- Cast a text: l'operatore ~ su citext ignorerebbe maiuscole/minuscole.
  nickname         citext not null unique check (nickname::text ~ '^[a-z0-9._]{3,20}$'),
  bio              varchar(150),
  avatar_media_id  uuid,
  account_type     app.account_type not null default 'private',
  age_band         app.age_band not null,
  adult_on         date,
  age_verified_at  timestamptz not null,
  age_method       text not null check (age_method in ('selfie_estimation','id_document','spid','cie')),
  hide_prices      boolean not null default false,
  hide_vote_count  boolean not null default false,
  status           app.user_status not null default 'active',
  deletion_due_at  timestamptz,
  created_at       timestamptz not null default now(),
  -- Business solo per maggiorenni (sez. 11.2); i 16-17 hanno sempre adult_on.
  constraint business_only_adults check (account_type = 'private' or age_band = '18_plus'),
  constraint minors_have_adult_on check (age_band = '18_plus' or adult_on is not null)
);

create table app.styles (
  id            smallserial primary key,
  slug          text not null unique check (slug ~ '^[a-z0-9-]{2,40}$'),
  name          text not null,
  tagline       text not null,
  tone          char(7) not null check (tone ~ '^#[0-9A-F]{6}$'),
  min_age_band  app.age_band not null default '16_17',
  active_from   date,
  active_until  date,
  sort_order    smallint not null default 100,
  is_active     boolean not null default true,
  check (active_until is null or active_from is null or active_until >= active_from)
);
create index styles_search_trgm on app.styles using gin ((name || ' ' || tagline) gin_trgm_ops);

create table app.style_memberships (
  user_id   uuid references app.profiles(id) on delete cascade,
  style_id  smallint references app.styles(id),
  joined_at timestamptz not null default now(),
  primary key (user_id, style_id)
);
create index style_memberships_style on app.style_memberships (style_id);

create table app.follows (
  follower_id uuid references app.profiles(id) on delete cascade,
  followee_id uuid references app.profiles(id) on delete cascade,
  status      app.follow_status not null,
  created_at  timestamptz not null default now(),
  primary key (follower_id, followee_id),
  check (follower_id <> followee_id)
);
create index follows_followee on app.follows (followee_id, status);

create table app.blocks (
  blocker_id uuid references app.profiles(id) on delete cascade,
  blocked_id uuid references app.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker_id, blocked_id),
  check (blocker_id <> blocked_id)
);
create index blocks_blocked on app.blocks (blocked_id);

create table app.capsules (
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid not null references app.profiles(id) on delete cascade,
  name      varchar(30) not null,
  position  smallint not null,
  unique (owner_id, name)
);

create table app.posts (
  id              uuid primary key default gen_random_uuid(),
  author_id       uuid not null references app.profiles(id) on delete cascade,
  style_id        smallint not null references app.styles(id),
  caption         varchar(140),
  status          app.post_status not null default 'processing',
  capsule_id      uuid references app.capsules(id) on delete set null,
  portfolio_rank  text not null collate "C",
  restyle_used    boolean not null default false,
  created_at      timestamptz not null default now(),
  published_at    timestamptz,
  deleted_at      timestamptz,
  check (status <> 'active' or published_at is not null)
);
create index posts_feed      on app.posts (style_id, published_at desc) where status = 'active';
create index posts_portfolio on app.posts (author_id, portfolio_rank) where status <> 'deleted';

create table app.post_media (
  id           uuid primary key default gen_random_uuid(),
  post_id      uuid not null references app.posts(id) on delete cascade,
  position     smallint not null check (position between 0 and 9),
  storage_key  text not null,
  width        integer not null check (width > 0),
  height       integer not null check (height > 0),
  blurhash     text not null,
  sha256       bytea not null,
  phash        bigint,
  unique (post_id, position)
);
create index post_media_phash on app.post_media (phash);

create table app.links (
  id          uuid primary key default gen_random_uuid(),
  url         text not null check (url ~* '^https://' and length(url) <= 2048),
  domain      text not null,
  status      app.link_status not null default 'pending',
  checked_at  timestamptz
);
create index links_domain on app.links (domain);

create table app.post_items (
  id              uuid primary key default gen_random_uuid(),
  post_id         uuid not null references app.posts(id) on delete cascade,
  position        smallint not null check (position between 0 and 7),
  brand           varchar(60) not null,
  name            varchar(80) not null,
  price_cents     integer check (price_cents between 0 and 10000000),
  currency        char(3) not null default 'EUR',
  link_id         uuid references app.links(id),
  media_position  smallint check (media_position between 0 and 9),
  pin_x           numeric(5,4) check (pin_x between 0 and 1),
  pin_y           numeric(5,4) check (pin_y between 0 and 1),
  unique (post_id, position),
  check ((pin_x is null) = (pin_y is null))
);

-- voter_key = HMAC-SHA256(VOTE_PEPPER, user_id): l'id dell'utente non è mai salvato qui.
create table app.votes (
  post_id        uuid not null references app.posts(id) on delete cascade,
  voter_key      bytea not null check (octet_length(voter_key) = 32),
  score          smallint not null check (score between 1 and 100),
  style_confirm  boolean,
  weight         real not null default 1.0 check (weight between 0 and 1),
  created_at     timestamptz not null default now(),
  primary key (post_id, voter_key)
);
create index votes_by_voter on app.votes (voter_key, created_at desc);

create table app.post_stats (
  post_id      uuid primary key references app.posts(id) on delete cascade,
  vote_count   integer not null default 0 check (vote_count >= 0),
  vote_sum     bigint  not null default 0,
  vote_wsum    double precision not null default 0,
  vote_wcount  double precision not null default 0,
  hist         integer[] not null default '{0,0,0,0,0,0,0,0,0,0}' check (cardinality(hist) = 10),
  confirm_yes  integer not null default 0,
  confirm_no   integer not null default 0,
  impressions  integer not null default 0,
  saves        integer not null default 0,
  shop_clicks  integer not null default 0,
  hot_score    double precision not null default 0,
  updated_at   timestamptz not null default now()
);

create table app.saves (
  user_id    uuid references app.profiles(id) on delete cascade,
  post_id    uuid references app.posts(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, post_id)
);

create table app.reports (
  id           uuid primary key default gen_random_uuid(),
  reporter_id  uuid references app.profiles(id) on delete set null,
  target_type  text not null check (target_type in ('post','profile','link')),
  target_id    uuid not null,
  reason       text not null check (reason in ('nudity','minor_safety','harassment','spam',
                                                 'wrong_style','dangerous_link','stolen_photo','other')),
  details      varchar(500),
  priority     smallint not null check (priority between 0 and 2),
  status       text not null default 'open' check (status in ('open','in_review','actioned','dismissed')),
  created_at   timestamptz not null default now()
);
create index reports_queue on app.reports (status, priority, created_at) where status in ('open','in_review');

create table app.moderation_actions (
  id           uuid primary key default gen_random_uuid(),
  target_type  text not null,
  target_id    uuid not null,
  action       text not null check (action in ('hide','remove','restyle','suspend','ban','restore','warn')),
  ground       text not null,
  automated    boolean not null,
  actor_id     uuid,
  statement    text not null,
  created_at   timestamptz not null default now()
);
create index moderation_actions_target on app.moderation_actions (target_type, target_id);

create table app.notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references app.profiles(id) on delete cascade,
  type       text not null,
  payload    jsonb not null,
  read_at    timestamptz,
  created_at timestamptz not null default now()
);
create index notifications_inbox on app.notifications (user_id, created_at desc);

create table app.push_tokens (
  token      text primary key,
  user_id    uuid not null references app.profiles(id) on delete cascade,
  platform   text not null check (platform in ('ios','android')),
  last_seen  timestamptz not null default now()
);

create table app.events (
  id         bigint generated always as identity,
  actor_key  bytea,
  name       text not null,
  post_id    uuid,
  props      jsonb not null default '{}',
  ts         timestamptz not null default now(),
  primary key (id, ts)
) partition by range (ts);
create table app.events_default partition of app.events default;

create table app.insight_daily (
  author_id      uuid not null,
  day            date not null,
  post_id        uuid not null,
  impressions    integer not null default 0,
  votes          integer not null default 0,
  vote_sum       bigint not null default 0,
  shop_clicks    integer not null default 0,
  profile_views  integer not null default 0,
  primary key (author_id, day, post_id)
);

create table app.admin_audit_log (
  id        bigint generated always as identity primary key,
  admin_id  uuid not null,
  action    text not null,
  target    text,
  details   jsonb,
  ts        timestamptz not null default now()
);

-- Ruolo dell'API: permessi minimi, nessun superuser. In ogni ambiente si crea un utente
-- di login membro di questo ruolo (es. CREATE ROLE wearx_api_user LOGIN IN ROLE wearx_api).
do $$
begin
  if not exists (select from pg_roles where rolname = 'wearx_api') then
    create role wearx_api nologin;
  end if;
end $$;

grant usage on schema app to wearx_api;
grant select, insert, update, delete on all tables in schema app to wearx_api;
grant usage, select on all sequences in schema app to wearx_api;
revoke update, delete on app.admin_audit_log from wearx_api;

-- I ruoli pubblici di Supabase non devono poter toccare nulla dello schema app.
do $$
declare r text;
begin
  foreach r in array array['anon','authenticated'] loop
    if exists (select from pg_roles where rolname = r) then
      execute format('revoke all on schema app from %I', r);
      execute format('revoke all on all tables in schema app from %I', r);
    end if;
  end loop;
end $$;
"""


def _rls_sql() -> str:
    # RLS attiva ovunque. Solo il ruolo dell'API ha una policy; tutti gli altri ruoli
    # non superuser vengono rifiutati anche se un permesso venisse concesso per errore.
    statements = []
    for table in APP_TABLES:
        statements.append(f"alter table app.{table} enable row level security;")
        statements.append(
            f"create policy api_access on app.{table} for all to wearx_api "
            f"using (true) with check (true);"
        )
    return "\n".join(statements)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)
    op.execute(_rls_sql())


def downgrade() -> None:
    op.execute("drop schema app cascade;")
    op.execute(
        """
        do $$
        begin
          if to_regclass('auth.users') is not null
             and obj_description('auth.users'::regclass, 'pg_class') = 'wearx-local-stub' then
            drop table auth.users;
            drop schema if exists auth;
          end if;
        end $$;
        """
    )
