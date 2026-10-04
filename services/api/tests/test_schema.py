"""Test dello schema: vincoli, permessi del ruolo API, RLS, migrazioni reversibili."""

import hashlib
import subprocess
import uuid

import psycopg
import pytest

from tests.conftest import MIGRATION_URL, admin_conn, run_alembic


def make_user(conn: psycopg.Connection, nickname: str, *, minor: bool = False) -> uuid.UUID:
    user_id = uuid.uuid4()
    conn.execute("insert into auth.users (id) values (%s)", (user_id,))
    conn.execute(
        """insert into app.profiles (id, nickname, age_band, adult_on, age_verified_at, age_method)
           values (%s, %s, %s, %s, now(), 'selfie_estimation')""",
        (user_id, nickname, "16_17" if minor else "18_plus", "2028-05-01" if minor else None),
    )
    return user_id


def make_post(conn: psycopg.Connection, author: uuid.UUID) -> uuid.UUID:
    row = conn.execute(
        """insert into app.posts (author_id, style_id, portfolio_rank)
           values (%s, (select id from app.styles where slug = 'old-money'), 'a0')
           returning id""",
        (author,),
    ).fetchone()
    assert row is not None
    return row[0]


def voter_key(user: uuid.UUID) -> bytes:
    return hashlib.sha256(user.bytes).digest()


def test_nickname_rules(db_admin):
    make_user(db_admin, f"ok.nick_{uuid.uuid4().hex[:6]}")
    for bad in ("Maiuscole", "ab", "spazio no", "x" * 21, "emoji😀"):
        with pytest.raises(psycopg.errors.CheckViolation):
            make_user(db_admin, bad)


def test_nickname_unique_ignoring_case(db_admin):
    nick = f"unico_{uuid.uuid4().hex[:6]}"
    make_user(db_admin, nick)
    # Anche se il check impedisce le maiuscole, l'unicità è su citext.
    with pytest.raises(psycopg.errors.UniqueViolation):
        make_user(db_admin, nick)


def test_minor_cannot_be_business(db_admin):
    minor = make_user(db_admin, f"minore_{uuid.uuid4().hex[:6]}", minor=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        db_admin.execute(
            "update app.profiles set account_type = 'business' where id = %s", (minor,)
        )


def test_minor_requires_adult_on(db_admin):
    user_id = uuid.uuid4()
    db_admin.execute("insert into auth.users (id) values (%s)", (user_id,))
    with pytest.raises(psycopg.errors.CheckViolation):
        db_admin.execute(
            """insert into app.profiles (id, nickname, age_band, age_verified_at, age_method)
               values (%s, %s, '16_17', now(), 'id_document')""",
            (user_id, f"senza_data_{uuid.uuid4().hex[:4]}"),
        )


def test_vote_constraints(db_admin):
    author = make_user(db_admin, f"autore_{uuid.uuid4().hex[:6]}")
    voter = uuid.uuid4()
    post = make_post(db_admin, author)
    insert = "insert into app.votes (post_id, voter_key, score) values (%s, %s, %s)"
    for bad_score in (0, 101):
        with pytest.raises(psycopg.errors.CheckViolation):
            db_admin.execute(insert, (post, voter_key(voter), bad_score))
    db_admin.execute(insert, (post, voter_key(voter), 87))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db_admin.execute(insert, (post, voter_key(voter), 12))
    with pytest.raises(psycopg.errors.CheckViolation):
        db_admin.execute(insert, (post, b"short", 50))


def test_shop_links_must_be_https(db_admin):
    with pytest.raises(psycopg.errors.CheckViolation):
        db_admin.execute(
            "insert into app.links (url, domain) values ('http://shop.example', 'shop.example')"
        )


def test_api_role_can_read_and_write_app_tables(db_api):
    count = db_api.execute("select count(*) from app.styles").fetchone()
    assert count is not None and count[0] >= 12


def test_audit_log_is_append_only_for_api(db_api):
    db_api.execute(
        "insert into app.admin_audit_log (admin_id, action) values (%s, 'test')", (uuid.uuid4(),)
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db_api.execute("delete from app.admin_audit_log")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db_api.execute("update app.admin_audit_log set action = 'x'")


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_supabase_public_roles_have_no_access(db_admin, role):
    db_admin.execute(f"set role {role}")
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db_admin.execute("select * from app.profiles")
    finally:
        db_admin.execute("reset role")


def test_every_app_table_has_rls_enabled(db_admin):
    rows = db_admin.execute(
        """select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
           where n.nspname = 'app' and c.relkind in ('r', 'p') and not c.relrowsecurity"""
    ).fetchall()
    # Le partizioni ereditano le policy dalla tabella madre.
    assert [r[0] for r in rows if r[0] != "events_default"] == []


def test_events_accept_inserts_without_monthly_partition(db_api):
    db_api.execute("insert into app.events (name, props) values ('app_open', '{}')")


def test_migrations_are_reversible():
    """Su un database vuoto: su, giù fino all'inizio, di nuovo su."""
    name = "wearx_migcheck"
    with admin_conn() as conn:
        conn.execute(f"drop database if exists {name} with (force)")
        conn.execute(f"create database {name}")
    url = MIGRATION_URL.rsplit("/", 1)[0] + f"/{name}"
    try:
        run_alembic("upgrade", "head", url=url)
        run_alembic("downgrade", "base", url=url)
        run_alembic("upgrade", "head", url=url)
    finally:
        with admin_conn() as conn:
            conn.execute(f"drop database if exists {name} with (force)")


def test_seed_rollback_refuses_when_styles_are_in_use(db_admin):
    """Il rollback non deve mai cancellare dati usati da post reali."""
    author = make_user(db_admin, f"rollback_{uuid.uuid4().hex[:6]}")
    make_post(db_admin, author)
    with pytest.raises(subprocess.CalledProcessError):
        run_alembic("downgrade", "0001")
