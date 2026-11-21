"""Global multi-subject schedule endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.db.models import SessionStatus, StudySession
from app.schemas.schedule import (
    PlanFeasibilityRead,
    ScheduleReportRead,
    StudySessionRead,
)
from app.services.scheduler_service import ScheduleReport, recalculate_global_schedule

router = APIRouter(prefix="/schedule", tags=["schedule"])


def serialize_session(session: StudySession) -> StudySessionRead:
    return StudySessionRead(
        id=session.id,
        plan_id=session.plan_id,
        topic_id=session.topic_id,
        subject_name=session.plan.subject_name,
        plan_color=session.plan.color,
        topic_name=session.topic.name,
        difficulty=session.topic.difficulty,
        priority=session.topic.priority,
        scheduled_date=session.scheduled_date,
        start_offset_minutes=session.start_offset_minutes,
        duration_minutes=session.duration_minutes,
        status=session.status,
        completed_at=session.completed_at,
    )


def load_sessions(
    db: Session,
    *,
    plan_id: int | None = None,
    status: SessionStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[StudySessionRead]:
    stmt = (
        select(StudySession)
        .options(selectinload(StudySession.plan), selectinload(StudySession.topic))
        .order_by(
            StudySession.scheduled_date.asc(),
            StudySession.start_offset_minutes.asc(),
            StudySession.id.asc(),
        )
    )
    if plan_id is not None:
        stmt = stmt.where(StudySession.plan_id == plan_id)
    if status is not None:
        stmt = stmt.where(StudySession.status == status)
    if from_date is not None:
        stmt = stmt.where(StudySession.scheduled_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(StudySession.scheduled_date <= to_date)

    rows = db.scalars(stmt).all()
    return [serialize_session(row) for row in rows]


def build_schedule_response(
    db: Session,
    report: ScheduleReport,
    *,
    plan_id: int | None = None,
    status: SessionStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> ScheduleReportRead:
    sessions = load_sessions(
        db,
        plan_id=plan_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    return ScheduleReportRead(
        is_feasible=report.is_feasible,
        total_required_minutes=report.total_required_minutes,
        total_scheduled_minutes=report.total_scheduled_minutes,
        total_available_minutes=report.total_available_minutes,
        deficit_minutes=report.deficit_minutes,
        warnings=report.warnings,
        suggestions=report.suggestions,
        per_plan=[
            PlanFeasibilityRead(
                plan_id=p.plan_id,
                subject_name=p.subject_name,
                exam_date=p.exam_date,
                required_minutes=p.required_minutes,
                scheduled_minutes=p.scheduled_minutes,
                deficit_minutes=p.deficit_minutes,
                is_feasible=p.is_feasible,
            )
            for p in report.per_plan
        ],
        sessions=sessions,
    )


@router.get("", response_model=ScheduleReportRead, summary="Get global study schedule and feasibility")
def get_schedule_endpoint(
    plan_id: int | None = Query(None, description="Filter sessions by study plan ID"),
    status: SessionStatus | None = Query(None, description="Filter sessions by status"),
    from_date: date | None = Query(None, description="Inclusive start date filter"),
    to_date: date | None = Query(None, description="Inclusive end date filter"),
    db: Session = Depends(get_db),
) -> ScheduleReportRead:
    report = recalculate_global_schedule(db)
    return build_schedule_response(
        db,
        report,
        plan_id=plan_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )


@router.post(
    "/recalculate",
    response_model=ScheduleReportRead,
    summary="Recalculate global multi-subject schedule",
)
def recalculate_schedule_endpoint(
    start_date: date | None = Query(None, description="Optional override for schedule start date"),
    db: Session = Depends(get_db),
) -> ScheduleReportRead:
    report = recalculate_global_schedule(db, start_date=start_date)
    return build_schedule_response(db, report)
