"""Authentication endpoints: register, login, and current-user profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import crud
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import AuthResponse, UserLogin, UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new student account",
)
def register_endpoint(
    payload: UserRegister,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initialize default shared-capacity settings for this user.
    crud.get_or_create_settings(db, user_id=user.id)

    token = create_access_token(user.id, user.email, settings)
    return AuthResponse(access_token=token, user=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Sign in with email and password",
)
def login_endpoint(
    payload: UserLogin,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(user.id, user.email, settings)
    return AuthResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead, summary="Get the currently signed-in student")
def me_endpoint(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
