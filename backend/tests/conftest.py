"""Shared pytest fixtures.

Every test gets a fresh, isolated in-memory SQLite database; the developer's
``study_buddy.db`` is never touched and no external AI API is ever called
unless a test is explicitly marked ``live``.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ["AUTO_MIGRATE"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"  # never touch the developer database from tests

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401  (register models)
from app.db.database import Base, build_engine, get_db
from app.main import create_app


@pytest.fixture()
def engine():
    eng = build_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app(session_factory):
    application = create_app()

    def _override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest.fixture()
def anon_client(app) -> Generator[TestClient, None, None]:
    """Unauthenticated TestClient for testing auth & 401 behavior."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def client(app) -> Generator[TestClient, None, None]:
    """Authenticated TestClient with a freshly registered test student."""
    with TestClient(app) as test_client:
        resp = test_client.post(
            "/api/auth/register",
            json={
                "name": "Test Student",
                "email": "student@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 201, resp.text
        token = resp.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client
