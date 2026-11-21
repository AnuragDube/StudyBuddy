"""Database initialisation: apply Alembic migrations programmatically."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR
from app.core.logging import get_logger

logger = get_logger(__name__)


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(Path(BACKEND_DIR) / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(BACKEND_DIR) / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["configure_logger"] = False
    return cfg


def run_migrations(database_url: str) -> None:
    """Upgrade the database schema to the latest Alembic revision."""
    logger.info("Applying database migrations")
    command.upgrade(alembic_config(database_url), "head")
