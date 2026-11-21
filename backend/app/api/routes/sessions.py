"""Study session status update and dynamic rescheduling endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.routes.schedule import build_schedule_response, serialize_session
from app.db.database import get_db
from app.db.models import SessionStatus, StudySession, Topic, utcnow
from app.schemas.schedule import SessionStatusUpdate, SessionUpdateResponse
from app.services.scheduler_service import recalculate_global_schedule

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.patch(
    "/{session_id}",
    response_model=SessionUpdateResponse,
    summary="Mark a study session completed, missed, or pending and recalculate schedule",
)
def update_session_status_endpoint(
    session_id: int,
    payload: SessionStatusUpdate,
    db: Session = Depends(get_db),
) -> SessionUpdateResponse:
    session = db.scalar(
        select(StudySession)
        .where(StudySession.id == session_id)
        .options(selectinload(StudySession.plan), selectinload(StudySession.topic))
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Study session {session_id} not found.",
        )

    session.status = payload.status
    session.completed_at = utcnow() if payload.status == SessionStatus.completed else None
    db.flush()

    # Sync parent topic completion status based on total completed minutes.
    topic: Topic = session.topic
    completed_minutes = int(
        db.scalar(
            select(func.coalesce(func.sum(StudySession.duration_minutes), 0)).where(
                StudySession.topic_id == topic.id,
                StudySession.status == SessionStatus.completed,
            )
        )
        or 0
    )
    topic.is_completed = completed_minutes >= topic.estimated_minutes
    db.commit()
    db.refresh(session)

    # Snapshot serialized session before recalculation (pending sessions may be rebuilt).
    serialized = serialize_session(session)
    topic_completed = topic.is_completed

    report = recalculate_global_schedule(db)
    schedule_read = build_schedule_response(db, report)

    return SessionUpdateResponse(
        session=serialized,
        topic_completed=topic_completed,
        schedule=schedule_read,
    )
