"""Alembic migration environment.

The database URL is taken from ``app.core.config.Settings`` (i.e. ``DATABASE_URL``)
unless one is passed explicitly via ``-x url=...`` or set on the Alembic config.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db import models  # noqa: F401  (register models on Base.metadata)
from app.db.database import Base, normalize_database_url

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

url_override = context.get_x_argument(as_dictionary=True).get("url")
if url_override:
    config.set_main_option("sqlalchemy.url", normalize_database_url(url_override))
elif not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", normalize_database_url(get_settings().database_url))
else:
    config.set_main_option(
        "sqlalchemy.url", normalize_database_url(config.get_main_option("sqlalchemy.url") or "")
    )

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite-safe ALTER TABLE
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
