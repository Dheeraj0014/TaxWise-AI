"""Alembic environment (§3, §11).

The database URL is not read from alembic.ini — it comes from the same
`Settings` object the app and the tests use, so a migration run can never point
at a different database than the code it is migrating.

`render_as_batch` is on because the dev database is SQLite, which cannot
`ALTER TABLE ... DROP COLUMN` or alter a column's type. Batch mode makes Alembic
rebuild the table instead, so a migration authored here still applies both
locally and on Postgres.
"""
from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import get_settings
from app.core.database import Base
from app.infrastructure.db import models  # noqa: F401  (registers the mappers)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """`-x db_url=...` wins, otherwise the app's configured DATABASE_URL."""
    override = context.get_x_argument(as_dictionary=True).get("db_url")
    return override or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    connectable = create_engine(
        url, connect_args=connect_args, poolclass=pool.NullPool, future=True
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
