"""Shared pytest fixtures."""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ["AUTO_MIGRATE"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"  # never touch the developer database from tests

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client
