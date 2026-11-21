"""SQLAlchemy engine, session factory and FastAPI DB dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def build_engine(database_url: str, **kwargs) -> Engine:
    """Create an engine; SQLite gets thread-safety + foreign-key enforcement."""
    connect_args = kwargs.pop("connect_args", {})
    if database_url.startswith("sqlite"):
        connect_args.setdefault("check_same_thread", False)
    engine = create_engine(database_url, connect_args=connect_args, future=True, **kwargs)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _record):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
