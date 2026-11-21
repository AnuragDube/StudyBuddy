"""Health / liveness endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    ai_provider: str
    ai_configured: bool


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    key = settings.groq_api_key if settings.ai_provider == "groq" else settings.gemini_api_key
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        ai_provider=settings.ai_provider,
        ai_configured=bool(key),
    )
