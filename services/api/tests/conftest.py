"""Fixture di test: database PostgreSQL vero (non mock), ricreato a ogni sessione.

- Le migrazioni girano con l'utente amministratore (come in produzione).
- L'API gira con `wearx_api_user`, membro del ruolo `wearx_api`: così i test
  verificano anche che i permessi concessi dalla migrazione bastino.

Variabili: WEARX_TEST_ADMIN_URL (default postgres:postgres@localhost:5432).
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import psycopg
import pytest

ADMIN_URL = os.environ.get(
    "WEARX_TEST_ADMIN_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
TEST_DB = "wearx_test"
API_USER = "wearx_api_user"
API_PASSWORD = "test-only-password"  # noqa: S105 - solo database di test locale

_base = ADMIN_URL.rsplit("/", 1)[0]
MIGRATION_URL = f"{_base}/{TEST_DB}".replace("postgresql://", "postgresql+psycopg://")
_host = _base.split("@", 1)[1]
API_URL = f"postgresql+asyncpg://{API_USER}:{API_PASSWORD}@{_host}/{TEST_DB}"
API_DIR = Path(__file__).resolve().parents[1]

os.environ["WEARX_ENV"] = "test"
os.environ["WEARX_DATABASE_URL"] = API_URL
os.environ.setdefault("WEARX_REDIS_URL", "redis://localhost:6379/15")


def admin_conn(dbname: str = "postgres") -> psycopg.Connection:
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{dbname}"
    return psycopg.connect(url, autocommit=True)


def run_alembic(*args: str, url: str = MIGRATION_URL) -> None:
    env = {**os.environ, "WEARX_MIGRATION_DATABASE_URL": url}
    subprocess.run(  # noqa: S603 - comando fisso
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    with admin_conn() as conn:
        conn.execute(f"drop database if exists {TEST_DB} with (force)")
        conn.execute(f"create database {TEST_DB}")
        # Ruoli che su Supabase esistono già: li simuliamo per testare le revoche.
        for role in ("anon", "authenticated"):
            exists = conn.execute("select 1 from pg_roles where rolname = %s", (role,)).fetchone()
            if not exists:
                conn.execute(f"create role {role} nologin")
    run_alembic("upgrade", "head")
    with admin_conn() as conn:
        exists = conn.execute("select 1 from pg_roles where rolname = %s", (API_USER,)).fetchone()
        if not exists:
            conn.execute(
                f"create role {API_USER} login password '{API_PASSWORD}' in role wearx_api"
            )
    yield


@pytest.fixture
def db_admin() -> Iterator[psycopg.Connection]:
    """Connessione amministratore al database di test, per preparare dati e verifiche."""
    with admin_conn(TEST_DB) as conn:
        yield conn


@pytest.fixture
def db_api() -> Iterator[psycopg.Connection]:
    """Connessione con il ruolo dell'API, per verificare i permessi."""
    url = f"postgresql://{API_USER}:{API_PASSWORD}@{_host}/{TEST_DB}"
    with psycopg.connect(url, autocommit=True) as conn:
        yield conn


@pytest.fixture
async def client() -> AsyncIterator[object]:
    import httpx

    from app.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
def keys():
    """Chiavi di firma di test e JWKS simulato, installati al posto di quelli di Supabase."""
    from app.auth import set_jwks
    from tests.authkit import KeySet

    keyset = KeySet()
    set_jwks(keyset.cache())
    yield keyset
    set_jwks(None)


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> Iterator[None]:
    """Ogni test parte con i contatori dei limiti azzerati (Redis db 15, solo test)."""
    import redis

    r = redis.Redis.from_url(os.environ["WEARX_REDIS_URL"])
    r.flushdb()
    yield
    r.close()


def create_auth_user(conn: psycopg.Connection) -> uuid.UUID:
    """Simula la registrazione su Supabase Auth (riga in auth.users)."""
    user_id = uuid.uuid4()
    conn.execute("insert into auth.users (id) values (%s)", (user_id,))
    return user_id


def pass_age_check(conn: psycopg.Connection, user_id: uuid.UUID, *, minor: bool = False) -> None:
    conn.execute(
        """insert into app.age_verifications
             (user_id, method, status, age_band, adult_on, provider, completed_at)
           values (%s, 'selfie_estimation', 'passed', %s, %s, 'test', now())""",
        (user_id, "16_17" if minor else "18_plus", "2028-03-01" if minor else None),
    )
