"""Syllabus upload (PDF/TXT/raw text) and AI topic extraction endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import crud
from app.db.database import get_db
from app.schemas.plan import PlanDetail, TopicCreate
from app.schemas.schedule import SyllabusExtractResponse
from app.services.ai_service import (
    AIOutputValidationError,
    AIProviderNotConfiguredError,
    AIProviderRequestError,
    ProviderName,
    extract_topics_from_syllabus,
)
from app.services.pdf_service import (
    MIN_TEXT_CHARS,
    SyllabusExtractionError,
    clean_text,
    extract_syllabus_text,
)
from app.services.scheduler_service import recalculate_global_schedule

router = APIRouter(tags=["syllabus"])


async def _resolve_syllabus_text(
    file: UploadFile | None,
    raw_text: str | None,
    settings: Settings,
) -> tuple[str, int | None]:
    if file is not None and file.filename:
        content = await file.read()
        try:
            pdf_res = extract_syllabus_text(
                filename=file.filename,
                content=content,
                max_bytes=settings.max_upload_bytes,
            )
        except SyllabusExtractionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return pdf_res.text, pdf_res.page_count

    if raw_text and raw_text.strip():
        cleaned = clean_text(raw_text)
        if len(cleaned) < MIN_TEXT_CHARS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Syllabus text is too short (minimum {MIN_TEXT_CHARS} characters).",
            )
        return cleaned, None

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide either a syllabus PDF/TXT file or raw_text.",
    )


def _run_ai_extraction(
    text: str,
    *,
    subject_hint: str | None,
    provider: ProviderName | None,
    settings: Settings,
):
    try:
        return extract_topics_from_syllabus(
            text,
            subject_hint=subject_hint,
            provider=provider,
            settings=settings,
        )
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AIProviderRequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except AIOutputValidationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/syllabus/extract",
    response_model=SyllabusExtractResponse,
    summary="Extract structured study topics from an uploaded PDF/TXT or raw syllabus text",
)
async def extract_syllabus_endpoint(
    file: UploadFile | None = File(None),
    raw_text: str | None = Form(None),
    subject_hint: str | None = Form(None),
    provider: ProviderName | None = Form(None),
    settings: Settings = Depends(get_settings),
) -> SyllabusExtractResponse:
    text, page_count = await _resolve_syllabus_text(file, raw_text, settings)
    ai_res = _run_ai_extraction(
        text, subject_hint=subject_hint, provider=provider, settings=settings
    )
    return SyllabusExtractResponse(
        extracted_char_count=len(text),
        page_count=page_count,
        provider=ai_res.provider,
        model=ai_res.model,
        latency_ms=ai_res.latency_ms,
        truncated=ai_res.truncated,
        prompt_tokens=ai_res.prompt_tokens,
        completion_tokens=ai_res.completion_tokens,
        total_tokens=ai_res.total_tokens,
        extraction=ai_res.extraction,
        raw_text=text,
    )


@router.post(
    "/plans/{plan_id}/extract-syllabus",
    response_model=PlanDetail,
    summary="Extract topics from a syllabus, attach them to a plan, and recalculate schedule",
)
async def extract_syllabus_for_plan_endpoint(
    plan_id: int,
    file: UploadFile | None = File(None),
    raw_text: str | None = Form(None),
    provider: ProviderName | None = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PlanDetail:
    plan = crud.get_plan_or_404(db, plan_id)

    text, _ = await _resolve_syllabus_text(file, raw_text, settings)
    ai_res = _run_ai_extraction(
        text,
        subject_hint=plan.subject_name,
        provider=provider,
        settings=settings,
    )

    plan.syllabus_raw_text = text
    topic_creates = [
        TopicCreate(
            name=t.name,
            unit=t.unit,
            subtopics=t.subtopics,
            difficulty=t.difficulty,
            priority=t.priority,
            estimated_minutes=t.estimated_minutes,
            order_index=idx,
        )
        for idx, t in enumerate(ai_res.extraction.topics)
    ]
    crud.replace_topics(db, plan, topic_creates)
    recalculate_global_schedule(db)

    refreshed = crud.get_plan_or_404(db, plan_id)
    return crud.to_plan_detail(refreshed)
