"""Pydantic schemas for schedule, sessions, and syllabus extraction endpoints."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import Difficulty, SessionStatus
from app.schemas.ai import SyllabusExtraction


class StudySessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    topic_id: int
    subject_name: str
    plan_color: str | None = None
    topic_name: str
    difficulty: Difficulty
    priority: int
    scheduled_date: date
    start_offset_minutes: int
    duration_minutes: int
    status: SessionStatus
    completed_at: datetime | None = None


class PlanFeasibilityRead(BaseModel):
    plan_id: int
    subject_name: str
    exam_date: date
    required_minutes: int
    scheduled_minutes: int
    deficit_minutes: int
    is_feasible: bool


class ScheduleReportRead(BaseModel):
    is_feasible: bool
    total_required_minutes: int
    total_scheduled_minutes: int
    total_available_minutes: int
    deficit_minutes: int
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    per_plan: list[PlanFeasibilityRead] = Field(default_factory=list)
    sessions: list[StudySessionRead] = Field(default_factory=list)


class SessionStatusUpdate(BaseModel):
    status: SessionStatus


class SessionUpdateResponse(BaseModel):
    session: StudySessionRead
    topic_completed: bool
    schedule: ScheduleReportRead


class SyllabusExtractResponse(BaseModel):
    extracted_char_count: int
    page_count: int | None = None
    provider: str
    model: str
    latency_ms: float
    truncated: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    extraction: SyllabusExtraction
    raw_text: str
