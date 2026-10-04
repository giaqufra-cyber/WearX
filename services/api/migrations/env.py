"""Ambiente Alembic. Le migrazioni sono SQL scritto a mano: è la fonte di verità dello schema.

Le migrazioni girano con un utente proprietario dello schema (WEARX_MIGRATION_DATABASE_URL),
diverso dal ruolo con cui gira l'API.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _url() -> str:
    url = (
        os.environ.get("WEARX_MIGRATION_DATABASE_URL")
        or os.environ.get("WEARX_DATABASE_URL")
        or "postgresql+asyncpg://postgres:postgres@localhost:5432/wearx"
    )
    # Le migrazioni usano il driver sincrono psycopg.
    return url.replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, version_table_schema="public")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, version_table_schema="public")
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
