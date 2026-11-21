import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "cors_origins",
    [
        "http://localhost:5173,http://127.0.0.1:5173",
        '["http://localhost:5173","http://127.0.0.1:5173"]',
    ],
)
def test_settings_parse_cors_origins(tmp_path, cors_origins):
    env_file = tmp_path / ".env"
    env_file.write_text(f"CORS_ORIGINS={cors_origins}\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.cors_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_normalize_database_url_for_postgres_and_sqlite():
    from app.db.database import normalize_database_url

    assert normalize_database_url("postgres://u:p@ep-abc.neon.tech/db?sslmode=require") == (
        "postgresql+psycopg://u:p@ep-abc.neon.tech/db?sslmode=require"
    )
    assert normalize_database_url("postgresql://u:p@ep-abc.neon.tech/db") == (
        "postgresql+psycopg://u:p@ep-abc.neon.tech/db"
    )
    assert normalize_database_url("sqlite:///./study_buddy.db") == "sqlite:///./study_buddy.db"
