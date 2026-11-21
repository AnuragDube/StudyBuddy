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
