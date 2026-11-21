"""Data-access helpers shared by the API routers.

Routers stay thin: they validate input via Pydantic and delegate persistence and
progress aggregation to these functions.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    PlanStatus,
    SessionStatus,
    StudyPlan,
    Topic,
    UserSettings,
)
from app.schemas.plan import (
    PlanCreate,
    PlanDetail,
    PlanSummary,
    PlanUpdate,
    TopicCreate,
    TopicRead,
    TopicUpdate,
)
from app.schemas.settings import SettingsUpdate

SUBJECT_PALETTE = [
    "#7c5cff", "#22c3a6", "#ff7a59", "#f5b83d", "#3da5f5",
    "#e85d9c", "#8bd450", "#b07cff", "#ff5f6d", "#2ec4b6",
]


# ---------------------------------------------------------------- Settings
def get_or_create_settings(db: Session) -> UserSettings:
    settings = db.scalar(select(UserSettings).order_by(UserSettings.id).limit(1))
    if settings is None:
        settings = UserSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, payload: SettingsUpdate) -> UserSettings:
    settings = get_or_create_settings(db)
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


# ---------------------------------------------------------------- Progress
def topic_completed_minutes(topic: Topic) -> int:
    if topic.is_completed:
        return topic.estimated_minutes
    done = sum(s.duration_minutes for s in topic.sessions if s.status == SessionStatus.completed)
    return min(done, topic.estimated_minutes)


def topic_remaining_minutes(topic: Topic) -> int:
    return max(0, topic.estimated_minutes - topic_completed_minutes(topic))


def to_topic_read(topic: Topic) -> TopicRead:
    done = topic_completed_minutes(topic)
    return TopicRead.model_validate(topic).model_copy(
        update={"completed_minutes": done, "remaining_minutes": max(0, topic.estimated_minutes - done)}
    )


def _summary_fields(plan: StudyPlan, today: date | None = None) -> dict:
    today = today or date.today()
    total = sum(t.estimated_minutes for t in plan.topics)
    done = sum(topic_completed_minutes(t) for t in plan.topics)
    return {
        "topic_count": len(plan.topics),
        "completed_topic_count": sum(1 for t in plan.topics if t.is_completed),
        "total_minutes": total,
        "completed_minutes": done,
        "progress_percent": round(100 * done / total, 1) if total else 0.0,
        "days_until_exam": (plan.exam_date - today).days,
    }


def to_plan_summary(plan: StudyPlan) -> PlanSummary:
    return PlanSummary.model_validate(plan).model_copy(update=_summary_fields(plan))


def to_plan_detail(plan: StudyPlan) -> PlanDetail:
    base = PlanSummary.model_validate(plan).model_dump()
    return PlanDetail(
        **base | _summary_fields(plan),
        syllabus_raw_text=plan.syllabus_raw_text,
        topics=[to_topic_read(t) for t in plan.topics],
    )


# ---------------------------------------------------------------- Plans
def _plan_query():
    return select(StudyPlan).options(selectinload(StudyPlan.topics).selectinload(Topic.sessions))


def list_plans(db: Session, status_filter: PlanStatus | None = None) -> list[StudyPlan]:
    query = _plan_query().order_by(StudyPlan.exam_date, StudyPlan.id)
    if status_filter is not None:
        query = query.where(StudyPlan.status == status_filter)
    return list(db.scalars(query).unique())


def get_plan_or_404(db: Session, plan_id: int) -> StudyPlan:
    plan = db.scalar(_plan_query().where(StudyPlan.id == plan_id))
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Study plan {plan_id} not found.")
    return plan


def _next_color(db: Session) -> str:
    count = db.query(StudyPlan).count()
    return SUBJECT_PALETTE[count % len(SUBJECT_PALETTE)]


def _new_topic(plan_id: int, data: TopicCreate, order_index: int) -> Topic:
    return Topic(plan_id=plan_id, order_index=order_index, **data.model_dump())


def create_plan(db: Session, payload: PlanCreate) -> StudyPlan:
    plan = StudyPlan(
        subject_name=payload.subject_name,
        exam_date=payload.exam_date,
        syllabus_raw_text=payload.syllabus_raw_text,
        color=payload.color or _next_color(db),
    )
    db.add(plan)
    db.flush()
    for i, topic in enumerate(payload.topics):
        db.add(_new_topic(plan.id, topic, i))
    db.commit()
    return get_plan_or_404(db, plan.id)


def update_plan(db: Session, plan: StudyPlan, payload: PlanUpdate) -> StudyPlan:
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(plan, field, value)
    db.commit()
    return get_plan_or_404(db, plan.id)


def delete_plan(db: Session, plan: StudyPlan) -> None:
    db.delete(plan)
    db.commit()


def replace_topics(db: Session, plan: StudyPlan, topics: list[TopicCreate]) -> StudyPlan:
    """Replace all topics of a plan (used after AI extraction review)."""
    for topic in list(plan.topics):
        db.delete(topic)
    db.flush()
    for i, topic in enumerate(topics):
        db.add(_new_topic(plan.id, topic, i))
    db.commit()
    db.expire_all()
    return get_plan_or_404(db, plan.id)


# ---------------------------------------------------------------- Topics
def get_topic_or_404(db: Session, plan: StudyPlan, topic_id: int) -> Topic:
    topic = next((t for t in plan.topics if t.id == topic_id), None)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Topic {topic_id} not found in plan {plan.id}.")
    return topic


def add_topic(db: Session, plan: StudyPlan, payload: TopicCreate) -> Topic:
    order = max((t.order_index for t in plan.topics), default=-1) + 1
    topic = _new_topic(plan.id, payload, order)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


def update_topic(db: Session, topic: Topic, payload: TopicUpdate) -> Topic:
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(topic, field, value)
    db.commit()
    db.refresh(topic)
    return topic


def delete_topic(db: Session, topic: Topic) -> None:
    db.delete(topic)
    db.commit()
