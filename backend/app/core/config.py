"""Application configuration loaded from environment variables / ``.env``.

All runtime configuration lives here so that the rest of the codebase never
reads ``os.environ`` directly. Values are validated by pydantic-settings.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "Study Buddy API"
    app_version: str = "2.0.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = False

    # --- HTTP ---
    api_prefix: str = "/api"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- Database ---
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'study_buddy.db').as_posix()}"
    auto_migrate: bool = True  # run `alembic upgrade head` on startup

    # --- AI ---
    ai_provider: Literal["groq", "gemini"] = "groq"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    ai_timeout_seconds: float = 60.0
    ai_max_syllabus_chars: int = 30_000

    # --- Uploads ---
    max_upload_mb: int = 10

    # --- Auth ---
    jwt_secret: str = "study-buddy-dev-secret-change-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow ``CORS_ORIGINS=a,b`` in addition to a JSON list."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("groq_api_key", "gemini_api_key", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (override in tests via dependency_overrides)."""
    return Settings()
