"""Schemas for the shared user study settings."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_ALIASES = {d.lower(): d for d in WEEKDAYS} | {
    "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu",
    "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
}


def normalize_days(days: list[str]) -> list[str]:
    """Normalise weekday names (e.g. ``"monday"`` -> ``"Mon"``) and sort Mon..Sun."""
    out: set[str] = set()
    for raw in days:
        key = str(raw).strip().lower()
        if key not in _ALIASES:
            raise ValueError(f"Invalid weekday '{raw}'. Use one of {WEEKDAYS}.")
        out.add(_ALIASES[key])
    if not out:
        raise ValueError("Select at least one preferred study day.")
    return [d for d in WEEKDAYS if d in out]


class SettingsBase(BaseModel):
    daily_study_minutes: int = Field(
        240, ge=30, le=960, description="Shared daily study capacity across ALL active subjects."
    )
    preferred_study_days: list[str] = Field(default_factory=lambda: list(WEEKDAYS))
    max_session_minutes: int = Field(60, ge=15, le=240, description="Longest single study block.")

    @field_validator("preferred_study_days")
    @classmethod
    def _days(cls, value: list[str]) -> list[str]:
        return normalize_days(value)


class SettingsUpdate(BaseModel):
    daily_study_minutes: int | None = Field(None, ge=30, le=960)
    preferred_study_days: list[str] | None = None
    max_session_minutes: int | None = Field(None, ge=15, le=240)

    @field_validator("preferred_study_days")
    @classmethod
    def _days(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalize_days(value)


class SettingsRead(SettingsBase):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime
