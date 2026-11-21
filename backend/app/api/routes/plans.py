"""Study plan (subject) and topic CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db import crud
from app.db.database import get_db
from app.db.models import PlanStatus
from app.schemas.plan import (
    PlanCreate,
    PlanDetail,
    PlanSummary,
    PlanUpdate,
    TopicCreate,
    TopicRead,
    TopicUpdate,
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanSummary], summary="List subject plans")
def list_plans(
    status_filter: PlanStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[PlanSummary]:
    return [crud.to_plan_summary(p) for p in crud.list_plans(db, status_filter)]


@router.post("", response_model=PlanDetail, status_code=status.HTTP_201_CREATED,
             summary="Create a subject plan (optionally with topics)")
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)) -> PlanDetail:
    return crud.to_plan_detail(crud.create_plan(db, payload))


@router.get("/{plan_id}", response_model=PlanDetail, summary="Get a subject plan with topics")
def get_plan(plan_id: int, db: Session = Depends(get_db)) -> PlanDetail:
    return crud.to_plan_detail(crud.get_plan_or_404(db, plan_id))


@router.patch("/{plan_id}", response_model=PlanDetail,
              summary="Update a subject plan (e.g. rename, change exam date, archive)")
def update_plan(plan_id: int, payload: PlanUpdate, db: Session = Depends(get_db)) -> PlanDetail:
    plan = crud.get_plan_or_404(db, plan_id)
    return crud.to_plan_detail(crud.update_plan(db, plan, payload))


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a subject plan")
def delete_plan(plan_id: int, db: Session = Depends(get_db)) -> Response:
    crud.delete_plan(db, crud.get_plan_or_404(db, plan_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- Topics
@router.put("/{plan_id}/topics", response_model=PlanDetail,
            summary="Replace all topics of a plan (e.g. after reviewing AI extraction)")
def replace_topics(plan_id: int, payload: list[TopicCreate], db: Session = Depends(get_db)) -> PlanDetail:
    plan = crud.get_plan_or_404(db, plan_id)
    return crud.to_plan_detail(crud.replace_topics(db, plan, payload))


@router.post("/{plan_id}/topics", response_model=TopicRead, status_code=status.HTTP_201_CREATED,
             summary="Add a topic to a plan")
def add_topic(plan_id: int, payload: TopicCreate, db: Session = Depends(get_db)) -> TopicRead:
    plan = crud.get_plan_or_404(db, plan_id)
    return crud.to_topic_read(crud.add_topic(db, plan, payload))


@router.patch("/{plan_id}/topics/{topic_id}", response_model=TopicRead, summary="Update a topic")
def update_topic(plan_id: int, topic_id: int, payload: TopicUpdate,
                 db: Session = Depends(get_db)) -> TopicRead:
    plan = crud.get_plan_or_404(db, plan_id)
    topic = crud.get_topic_or_404(db, plan, topic_id)
    return crud.to_topic_read(crud.update_topic(db, topic, payload))


@router.delete("/{plan_id}/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a topic")
def delete_topic(plan_id: int, topic_id: int, db: Session = Depends(get_db)) -> Response:
    plan = crud.get_plan_or_404(db, plan_id)
    crud.delete_topic(db, crud.get_topic_or_404(db, plan, topic_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
