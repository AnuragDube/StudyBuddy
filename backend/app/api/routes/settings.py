"""Shared study-capacity settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import crud
from app.db.database import get_db
from app.schemas.settings import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead, summary="Get shared study capacity settings")
def get_settings_endpoint(db: Session = Depends(get_db)) -> SettingsRead:
    return SettingsRead.model_validate(crud.get_or_create_settings(db))


@router.put("", response_model=SettingsRead, summary="Update shared study capacity settings")
def update_settings_endpoint(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsRead:
    return SettingsRead.model_validate(crud.update_settings(db, payload))
