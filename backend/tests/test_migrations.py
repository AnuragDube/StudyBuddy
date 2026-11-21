"""Verify Alembic migrations create the expected schema and are reversible."""

from sqlalchemy import create_engine, inspect

from app.db.init_db import alembic_config, run_migrations
from alembic import command


def test_upgrade_and_downgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    run_migrations(url)

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert {"user_settings", "study_plans", "topics", "study_sessions"} <= tables
    session_cols = {c["name"] for c in inspect(engine).get_columns("study_sessions")}
    assert {"plan_id", "topic_id", "scheduled_date", "duration_minutes", "status"} <= session_cols

    command.downgrade(alembic_config(url), "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
