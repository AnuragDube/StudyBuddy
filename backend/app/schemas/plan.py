"""Schemas for study plans (subjects) and their topics."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import Difficulty, PlanStatus

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


# ---------------------------------------------------------------- Topics
class TopicBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    unit: str | None = Field(None, max_length=200)
    subtopics: list[str] = Field(default_factory=list)
    difficulty: Difficulty = Difficulty.medium
    priority: int = Field(3, ge=1, le=5, description="1 = low, 5 = critical")
    estimated_minutes: int = Field(60, ge=10, le=1200)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic name cannot be blank.")
        return value


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    unit: str | None = Field(None, max_length=200)
    subtopics: list[str] | None = None
    difficulty: Difficulty | None = None
    priority: int | None = Field(None, ge=1, le=5)
    estimated_minutes: int | None = Field(None, ge=10, le=1200)
    is_completed: bool | None = None


class TopicRead(TopicBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    order_index: int
    is_completed: bool
    completed_minutes: int = 0
    remaining_minutes: int = 0


# ---------------------------------------------------------------- Plans
class PlanCreate(BaseModel):
    subject_name: str = Field(..., min_length=1, max_length=200)
    exam_date: date
    syllabus_raw_text: str = ""
    color: str | None = Field(None, pattern=HEX_COLOR)
    topics: list[TopicCreate] = Field(default_factory=list)

    @field_validator("subject_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Subject name cannot be blank.")
        return value

    @field_validator("exam_date")
    @classmethod
    def _future(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Exam date cannot be in the past.")
        return value


class PlanUpdate(BaseModel):
    subject_name: str | None = Field(None, min_length=1, max_length=200)
    exam_date: date | None = None
    syllabus_raw_text: str | None = None
    color: str | None = Field(None, pattern=HEX_COLOR)
    status: PlanStatus | None = None

    @field_validator("exam_date")
    @classmethod
    def _future(cls, value: date | None) -> date | None:
        if value is not None and value < date.today():
            raise ValueError("Exam date cannot be in the past.")
        return value


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_name: str
    exam_date: date
    color: str | None
    status: PlanStatus
    created_at: datetime
    updated_at: datetime
    topic_count: int = 0
    completed_topic_count: int = 0
    total_minutes: int = 0
    completed_minutes: int = 0
    progress_percent: float = 0.0
    days_until_exam: int = 0


class PlanDetail(PlanSummary):
    syllabus_raw_text: str
    topics: list[TopicRead] = Field(default_factory=list)
