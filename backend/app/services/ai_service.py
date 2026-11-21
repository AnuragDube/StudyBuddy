"""Provider-independent LLM service for structured syllabus topic extraction.

Separates AI reasoning (reading unstructured syllabus text and producing
structured topics, difficulties, priorities, and time estimates) from
deterministic scheduling math.

Supported providers:
* ``groq``   – Primary provider (default ``openai/gpt-oss-20b``) using strict
  JSON Schema structured output.
* ``gemini`` – Secondary/baseline provider (default ``gemini-2.5-flash-lite``)
  via the official ``google-genai`` SDK, used for automatic fallback and
  research benchmarking.
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.ai import SYLLABUS_EXTRACTION_JSON_SCHEMA, SyllabusExtraction

logger = logging.getLogger(__name__)

ProviderName = Literal["groq", "gemini"]

SYSTEM_PROMPT = """You are an expert academic curriculum analyst and study coach.
Your job is to read an unstructured course syllabus and extract a clean, structured list of study topics.

Rules:
1. Preserve the logical syllabus order (units/modules from start to finish).
2. Extract concrete, actionable study topics—not administrative items (grading policy, office hours, attendance, textbook ISBNs, exam dates).
3. For each topic, list key subtopics mentioned in the syllabus (up to 20).
4. Assign difficulty: "low" (introductory/memorization), "medium" (standard conceptual + practice), or "high" (complex proofs, algorithms, synthesis, or heavy problem-solving).
5. Assign priority from 1 (optional/enrichment) to 5 (core/foundational/heavily weighted).
6. Estimate realistic total study minutes (15 to 1200) needed for a typical student to learn, practice, and revise the topic.
7. Provide a concise one-sentence rationale justifying the difficulty and time estimate.
8. Do NOT invent a schedule, dates, or daily study limits—only extract topics and estimates.
9. Return strictly valid JSON matching the requested schema."""

_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


class AIServiceError(Exception):
    """Base error raised by the AI extraction service."""


class AIProviderNotConfiguredError(AIServiceError):
    """Raised when the requested LLM provider has no API key configured."""


class AIProviderRequestError(AIServiceError):
    """Raised when an upstream LLM API call fails."""


class AIOutputValidationError(AIServiceError):
    """Raised when the LLM returns invalid JSON or fails schema validation."""


@dataclass(frozen=True)
class ExtractionResult:
    """Validated extraction output paired with provider telemetry."""

    extraction: SyllabusExtraction
    provider: str
    model: str
    latency_ms: float
    raw_json: str
    truncated: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


def _build_user_prompt(syllabus_text: str, subject_hint: str | None = None) -> str:
    header = (
        f"Subject hint: {subject_hint.strip()}\n\n"
        if subject_hint and subject_hint.strip()
        else ""
    )
    return (
        f"{header}Extract the structured study topics from the following syllabus text:\n\n"
        f"--- SYLLABUS START ---\n{syllabus_text}\n--- SYLLABUS END ---"
    )


def _strip_code_fences(raw: str) -> str:
    match = _CODE_FENCE_RE.match(raw)
    return match.group(1).strip() if match else raw.strip()


def _parse_and_validate(raw_text: str) -> tuple[SyllabusExtraction, str]:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        raise AIOutputValidationError("LLM returned an empty response.")
    try:
        json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIOutputValidationError(f"LLM returned invalid JSON: {exc}") from exc
    try:
        extraction = SyllabusExtraction.model_validate_json(cleaned)
    except ValidationError as exc:
        raise AIOutputValidationError(f"LLM JSON failed schema validation: {exc}") from exc
    return extraction, cleaned


class BaseLLMProvider(ABC):
    """Abstract base class for syllabus-extraction LLM providers."""

    name: str

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 60.0) -> None:
        if not api_key or not api_key.strip():
            raise AIProviderNotConfiguredError(
                f"API key for provider '{self.name}' is not configured."
            )
        self.api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def extract(
        self,
        syllabus_text: str,
        *,
        subject_hint: str | None = None,
        truncated: bool = False,
    ) -> ExtractionResult:
        """Call the provider and return a validated ``ExtractionResult``."""


class GroqProvider(BaseLLMProvider):
    """Groq API provider using strict JSON Schema structured outputs."""

    name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        timeout_seconds: float = 60.0,
        client: Any | None = None,
    ) -> None:
        super().__init__(api_key=api_key, model=model, timeout_seconds=timeout_seconds)
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from groq import Groq

            self._client = Groq(api_key=self.api_key, timeout=self.timeout_seconds)
        return self._client

    def extract(
        self,
        syllabus_text: str,
        *,
        subject_hint: str | None = None,
        truncated: bool = False,
    ) -> ExtractionResult:
        client = self._get_client()
        user_prompt = _build_user_prompt(syllabus_text, subject_hint=subject_hint)

        t0 = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "syllabus_extraction",
                        "strict": True,
                        "schema": SYLLABUS_EXTRACTION_JSON_SCHEMA,
                    },
                },
            )
        except Exception as exc:
            raise AIProviderRequestError(f"Groq API request failed: {exc}") from exc

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        choices = getattr(response, "choices", None) or []
        if not choices or not getattr(choices[0], "message", None):
            raise AIOutputValidationError("Groq API returned no completion choices.")

        raw_content = choices[0].message.content or ""
        extraction, cleaned_json = _parse_and_validate(raw_content)

        usage = getattr(response, "usage", None)
        return ExtractionResult(
            extraction=extraction,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            raw_json=cleaned_json,
            truncated=truncated,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
        )


class GeminiProvider(BaseLLMProvider):
    """Google Gen AI SDK provider (``google-genai``) with structured JSON output."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-lite",
        timeout_seconds: float = 60.0,
        client: Any | None = None,
    ) -> None:
        super().__init__(api_key=api_key, model=model, timeout_seconds=timeout_seconds)
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def extract(
        self,
        syllabus_text: str,
        *,
        subject_hint: str | None = None,
        truncated: bool = False,
    ) -> ExtractionResult:
        from google.genai import types

        client = self._get_client()
        user_prompt = _build_user_prompt(syllabus_text, subject_hint=subject_hint)

        t0 = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=SyllabusExtraction,
                ),
            )
        except Exception as exc:
            raise AIProviderRequestError(f"Gemini API request failed: {exc}") from exc

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        raw_content = getattr(response, "text", None) or ""
        extraction, cleaned_json = _parse_and_validate(raw_content)

        usage = getattr(response, "usage_metadata", None)
        return ExtractionResult(
            extraction=extraction,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            raw_json=cleaned_json,
            truncated=truncated,
            prompt_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            completion_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            total_tokens=getattr(usage, "total_token_count", None) if usage else None,
        )


def build_provider(
    provider_name: ProviderName,
    *,
    settings: Settings | None = None,
    model_override: str | None = None,
) -> BaseLLMProvider:
    """Instantiate a configured LLM provider from application settings."""
    cfg = settings or get_settings()
    if provider_name == "groq":
        return GroqProvider(
            api_key=cfg.groq_api_key or "",
            model=model_override or cfg.groq_model,
            timeout_seconds=cfg.ai_timeout_seconds,
        )
    if provider_name == "gemini":
        return GeminiProvider(
            api_key=cfg.gemini_api_key or "",
            model=model_override or cfg.gemini_model,
            timeout_seconds=cfg.ai_timeout_seconds,
        )
    raise ValueError(f"Unsupported AI provider: {provider_name!r}")


def extract_topics_from_syllabus(
    syllabus_text: str,
    *,
    subject_hint: str | None = None,
    provider: ProviderName | None = None,
    model: str | None = None,
    settings: Settings | None = None,
    allow_fallback: bool = True,
) -> ExtractionResult:
    """Extract structured study topics from raw syllabus text.

    Uses the configured primary provider (default ``groq``) and optionally
    falls back to the secondary provider if the primary fails and a fallback
    API key is available.
    """
    cleaned_text = (syllabus_text or "").strip()
    if not cleaned_text:
        raise ValueError("Syllabus text cannot be empty.")

    cfg = settings or get_settings()
    truncated = False
    if len(cleaned_text) > cfg.ai_max_syllabus_chars:
        cleaned_text = cleaned_text[: cfg.ai_max_syllabus_chars]
        truncated = True
        logger.warning(
            "Truncated syllabus text to %d characters for AI extraction",
            cfg.ai_max_syllabus_chars,
        )

    primary_name: ProviderName = provider or cfg.ai_provider
    fallback_name: ProviderName = "gemini" if primary_name == "groq" else "groq"

    try:
        primary_provider = build_provider(primary_name, settings=cfg, model_override=model)
        result = primary_provider.extract(
            cleaned_text, subject_hint=subject_hint, truncated=truncated
        )
        logger.info(
            "Syllabus extraction succeeded",
            extra={
                "provider": result.provider,
                "model": result.model,
                "topic_count": len(result.extraction.topics),
                "latency_ms": result.latency_ms,
            },
        )
        return result
    except AIServiceError as primary_exc:
        if not allow_fallback:
            raise

        fallback_has_key = (
            bool(cfg.gemini_api_key) if fallback_name == "gemini" else bool(cfg.groq_api_key)
        )
        if not fallback_has_key:
            raise

        logger.warning(
            "Primary AI provider '%s' failed (%s); falling back to '%s'",
            primary_name,
            primary_exc,
            fallback_name,
        )
        fallback_provider = build_provider(fallback_name, settings=cfg)
        return fallback_provider.extract(
            cleaned_text, subject_hint=subject_hint, truncated=truncated
        )
