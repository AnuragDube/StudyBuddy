"""Shared study-capacity settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import crud
from app.db.database import get_db
from app.db.models import User
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.services.scheduler_service import recalculate_global_schedule

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead, summary="Get shared study capacity settings")
def get_settings_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsRead:
    return SettingsRead.model_validate(crud.get_or_create_settings(db, user_id=current_user.id))


@router.put("", response_model=SettingsRead, summary="Update shared study capacity settings")
def update_settings_endpoint(
    payload: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SettingsRead:
    updated = crud.update_settings(db, payload, user_id=current_user.id)
    recalculate_global_schedule(db, user_id=current_user.id)
    return SettingsRead.model_validate(updated)
