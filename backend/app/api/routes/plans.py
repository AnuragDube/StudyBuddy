"""Study plan (subject) and topic CRUD endpoints (scoped per authenticated user)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import crud
from app.db.database import get_db
from app.db.models import PlanStatus, User
from app.schemas.plan import (
    PlanCreate,
    PlanDetail,
    PlanSummary,
    PlanUpdate,
    TopicCreate,
    TopicRead,
    TopicUpdate,
)
from app.services.scheduler_service import recalculate_global_schedule

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanSummary], summary="List subject plans")
def list_plans(
    status_filter: PlanStatus | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlanSummary]:
    return [
        crud.to_plan_summary(p)
        for p in crud.list_plans(db, status_filter, user_id=current_user.id)
    ]


@router.post(
    "",
    response_model=PlanDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a subject plan (optionally with topics)",
)
def create_plan(
    payload: PlanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanDetail:
    plan = crud.create_plan(db, payload, user_id=current_user.id)
    recalculate_global_schedule(db, user_id=current_user.id)
    return crud.to_plan_detail(crud.get_plan_or_404(db, plan.id, user_id=current_user.id))


@router.get("/{plan_id}", response_model=PlanDetail, summary="Get a subject plan with topics")
def get_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanDetail:
    return crud.to_plan_detail(crud.get_plan_or_404(db, plan_id, user_id=current_user.id))


@router.patch(
    "/{plan_id}",
    response_model=PlanDetail,
    summary="Update a subject plan (e.g. rename, change exam date, archive)",
)
def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanDetail:
    plan = crud.get_plan_or_404(db, plan_id, user_id=current_user.id)
    updated = crud.update_plan(db, plan, payload)
    recalculate_global_schedule(db, user_id=current_user.id)
    return crud.to_plan_detail(crud.get_plan_or_404(db, updated.id, user_id=current_user.id))


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a subject plan")
def delete_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    crud.delete_plan(db, crud.get_plan_or_404(db, plan_id, user_id=current_user.id))
    recalculate_global_schedule(db, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- Topics
@router.put(
    "/{plan_id}/topics",
    response_model=PlanDetail,
    summary="Replace all topics of a plan (e.g. after reviewing AI extraction)",
)
def replace_topics(
    plan_id: int,
    payload: list[TopicCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanDetail:
    plan = crud.get_plan_or_404(db, plan_id, user_id=current_user.id)
    crud.replace_topics(db, plan, payload)
    recalculate_global_schedule(db, user_id=current_user.id)
    return crud.to_plan_detail(crud.get_plan_or_404(db, plan_id, user_id=current_user.id))


@router.post(
    "/{plan_id}/topics",
    response_model=TopicRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a topic to a plan",
)
def add_topic(
    plan_id: int,
    payload: TopicCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TopicRead:
    plan = crud.get_plan_or_404(db, plan_id, user_id=current_user.id)
    topic = crud.add_topic(db, plan, payload)
    recalculate_global_schedule(db, user_id=current_user.id)
    return crud.to_topic_read(topic)


@router.patch("/{plan_id}/topics/{topic_id}", response_model=TopicRead, summary="Update a topic")
def update_topic(
    plan_id: int,
    topic_id: int,
    payload: TopicUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TopicRead:
    plan = crud.get_plan_or_404(db, plan_id, user_id=current_user.id)
    topic = crud.get_topic_or_404(db, plan, topic_id)
    updated = crud.update_topic(db, topic, payload)
    recalculate_global_schedule(db, user_id=current_user.id)
    return crud.to_topic_read(updated)


@router.delete(
    "/{plan_id}/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a topic",
)
def delete_topic(
    plan_id: int,
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    plan = crud.get_plan_or_404(db, plan_id, user_id=current_user.id)
    crud.delete_topic(db, crud.get_topic_or_404(db, plan, topic_id))
    recalculate_global_schedule(db, user_id=current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
