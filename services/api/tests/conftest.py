"""Fixture di test: database PostgreSQL vero (non mock), ricreato a ogni sessione.

- Le migrazioni girano con l'utente amministratore (come in produzione).
- L'API gira con `wearx_api_user`, membro del ruolo `wearx_api`: così i test
  verificano anche che i permessi concessi dalla migrazione bastino.

Variabili: WEARX_TEST_ADMIN_URL (default postgres:postgres@localhost:5432).
"""

from __future__ import annotations

import os
import socket
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


# ---------- Archivio S3 locale (moto) per foto e post ----------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def s3_url() -> Iterator[str]:
    from moto.server import ThreadedMotoServer

    port = _free_port()
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port, verbose=False)
    server.start()
    yield f"http://127.0.0.1:{port}"
    server.stop()


class RecordingQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[object, ...], str]] = []

    async def enqueue(self, function: str, *args: object, job_id: str) -> None:
        self.jobs.append((function, args, job_id))


@pytest.fixture
async def store(s3_url) -> AsyncIterator[object]:
    from app.config import Settings
    from app.storage import ObjectStore, set_store

    settings = Settings(
        storage_endpoint_url=s3_url,
        storage_bucket=f"test-{uuid.uuid4().hex[:8]}",
        storage_access_key="test",
    )
    store = ObjectStore(settings)
    await store.ensure_bucket()
    set_store(store)
    yield store
    set_store(None)


@pytest.fixture
def queue() -> Iterator[RecordingQueue]:
    from app.queue import set_queue

    recorder = RecordingQueue()
    previous = set_queue(recorder)
    yield recorder
    set_queue(previous)


def ready_upload(conn: psycopg.Connection, owner: uuid.UUID, *, width: int = 1080) -> uuid.UUID:
    """Foto già elaborata (senza passare dall'archivio): per i test dei post."""
    upload_id = uuid.uuid4()
    conn.execute(
        """insert into app.media_uploads
             (id, owner_id, status, content_type, declared_bytes, width, height, blurhash,
              sha256, phash, variants, processed_at)
           values (%s, %s, 'ready', 'image/jpeg', 1000, %s, %s, 'LEHV6nWB2yk8pyo0adR*.7kCMdnj',
                   %s, 42, '{320,640,1080}', now())""",
        (upload_id, owner, width, round(width * 1.25), uuid.uuid4().bytes * 2),
    )
    return upload_id


@pytest.fixture
def temp_style(db_admin) -> Iterator[object]:
    """Crea stili temporanei (es. fuori stagione) e li rimuove a fine test."""
    created: list[str] = []

    def make(slug_prefix: str = "tmp", **cols) -> str:
        slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
        values = {
            "name": cols.pop("name", "Prova"),
            "tagline": cols.pop("tagline", "Stile di prova"),
            "tone": "#123456",
            "min_age_band": cols.pop("min_age_band", "16_17"),
            "active_from": cols.pop("active_from", None),
            "active_until": cols.pop("active_until", None),
        }
        db_admin.execute(
            """insert into app.styles (slug, name, tagline, tone, min_age_band, active_from,
                                       active_until, sort_order)
               values (%s, %s, %s, %s, %s, %s, %s, 999)""",
            (slug, *values.values()),
        )
        created.append(slug)
        return slug

    yield make
    for slug in created:
        db_admin.execute(
            "delete from app.posts where style_id = (select id from app.styles where slug = %s)",
            (slug,),
        )
        db_admin.execute(
            "delete from app.style_memberships where style_id = "
            "(select id from app.styles where slug = %s)",
            (slug,),
        )
        db_admin.execute("delete from app.styles where slug = %s", (slug,))
