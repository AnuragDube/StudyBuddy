"""ORM models for the multi-subject study planner.

Data model
----------
* ``UserSettings`` – single row holding the **shared** daily study capacity and
  preferred study days used by the scheduler across *all* active subjects.
* ``StudyPlan``    – one subject plan (syllabus, exam date, status).
* ``Topic``        – syllabus topic extracted by the LLM (or entered manually).
* ``StudySession`` – a concrete, dated block of study time for one topic,
  produced by the deterministic scheduler.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

DEFAULT_STUDY_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlanStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    archived = "archived"


class Difficulty(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SessionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    missed = "missed"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    # Store enum *values* as plain strings (portable, readable in SQLite).
    return Enum(e, name=name, native_enum=False, values_callable=lambda x: [m.value for m in x])


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_study_minutes: Mapped[int] = mapped_column(Integer, default=240, nullable=False)
    preferred_study_days: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: list(DEFAULT_STUDY_DAYS), nullable=False
    )
    max_session_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_name: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    syllabus_raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[PlanStatus] = mapped_column(
        _enum(PlanStatus, "plan_status"), default=PlanStatus.active, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    topics: Mapped[list[Topic]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="Topic.order_index",
        passive_deletes=True,
    )
    sessions: Mapped[list[StudySession]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", passive_deletes=True
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subtopics: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(
        _enum(Difficulty, "difficulty"), default=Difficulty.medium, nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # 1 (low) .. 5 (high)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan: Mapped[StudyPlan] = relationship(back_populates="topics")
    sessions: Mapped[list[StudySession]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = (Index("ix_study_sessions_date_status", "scheduled_date", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Offset (minutes) from the start of that day's study block; together with
    # duration this guarantees sessions on the same day never overlap.
    start_offset_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        _enum(SessionStatus, "session_status"), default=SessionStatus.pending, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    plan: Mapped[StudyPlan] = relationship(back_populates="sessions")
    topic: Mapped[Topic] = relationship(back_populates="sessions")
