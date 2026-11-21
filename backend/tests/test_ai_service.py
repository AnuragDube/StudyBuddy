"""Unit tests for the provider-independent AI syllabus extraction service."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.db.models import Difficulty
from app.schemas.ai import SYLLABUS_EXTRACTION_JSON_SCHEMA, SyllabusExtraction
from app.services.ai_service import (
    AIOutputValidationError,
    AIProviderNotConfiguredError,
    AIProviderRequestError,
    GeminiProvider,
    GroqProvider,
    extract_topics_from_syllabus,
)


def _sample_payload() -> dict:
    return {
        "subject_title": "Data Structures and Algorithms",
        "topics": [
            {
                "name": "Asymptotic Analysis",
                "unit": "Unit 1",
                "subtopics": ["Big-O", "Recurrence Relations"],
                "difficulty": "medium",
                "priority": 5,
                "estimated_minutes": 120,
                "rationale": "Foundational for analyzing all subsequent algorithms.",
            },
            {
                "name": "Dynamic Programming",
                "unit": "Unit 4",
                "subtopics": ["Memoization", "Tabulation", "Knapsack"],
                "difficulty": "high",
                "priority": 5,
                "estimated_minutes": 240,
                "rationale": "Requires extensive practice with state transitions.",
            },
        ],
        "notes": None,
    }


def _assert_strict_json_schema(node: dict) -> None:
    """Verify OpenAI/Groq strict-mode JSON schema invariants recursively."""
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False
        props = set(node.get("properties", {}).keys())
        required = set(node.get("required", []))
        assert props == required, f"Missing required keys: {props - required}"
        for child in node.get("properties", {}).values():
            _assert_strict_json_schema(child)
    elif node.get("type") == "array" and "items" in node:
        _assert_strict_json_schema(node["items"])
    for branch in node.get("anyOf", []):
        _assert_strict_json_schema(branch)


def test_json_schema_satisfies_strict_mode_rules() -> None:
    _assert_strict_json_schema(SYLLABUS_EXTRACTION_JSON_SCHEMA)


def test_syllabus_extraction_normalizes_clamps_and_deduplicates() -> None:
    raw = {
        "subject_title": "Operating Systems",
        "topics": [
            {
                "name": "  Processes & Threads  ",
                "unit": "  ",
                "subtopics": ["PCB", "", "Context Switch"],
                "difficulty": "HIGH",
                "priority": 9,
                "estimated_minutes": 5,
                "rationale": "Core OS concept.",
            },
            {
                "name": "processes & threads",
                "unit": "Unit 1",
                "subtopics": [],
                "difficulty": "low",
                "priority": 0,
                "estimated_minutes": 9999,
                "rationale": "Duplicate should be removed.",
            },
        ],
        "notes": None,
    }
    parsed = SyllabusExtraction.model_validate(raw)
    assert len(parsed.topics) == 1
    topic = parsed.topics[0]
    assert topic.name == "Processes & Threads"
    assert topic.unit is None
    assert topic.subtopics == ["PCB", "Context Switch"]
    assert topic.difficulty == Difficulty.high
    assert topic.priority == 5
    assert topic.estimated_minutes == 15
    assert parsed.total_minutes == 15


def test_groq_provider_extracts_strict_json_and_telemetry() -> None:
    payload_str = json.dumps(_sample_payload())
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload_str))],
        usage=SimpleNamespace(prompt_tokens=300, completion_tokens=180, total_tokens=480),
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    provider = GroqProvider(api_key="gsk_test", model="openai/gpt-oss-20b", client=fake_client)
    result = provider.extract("Unit 1: Asymptotic Analysis...", subject_hint="DSA")

    assert result.provider == "groq"
    assert result.model == "openai/gpt-oss-20b"
    assert len(result.extraction.topics) == 2
    assert result.extraction.total_minutes == 360
    assert result.prompt_tokens == 300
    assert result.completion_tokens == 180
    assert result.total_tokens == 480
    assert result.latency_ms >= 0

    call_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"]["type"] == "json_schema"
    assert call_kwargs["response_format"]["json_schema"]["strict"] is True


def test_groq_provider_strips_markdown_code_fences() -> None:
    wrapped = f"```json\n{json.dumps(_sample_payload())}\n```"
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=wrapped))],
        usage=None,
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    provider = GroqProvider(api_key="gsk_test", client=fake_client)
    result = provider.extract("Syllabus content")
    assert len(result.extraction.topics) == 2


def test_groq_provider_raises_on_invalid_json() -> None:
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))],
        usage=None,
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    provider = GroqProvider(api_key="gsk_test", client=fake_client)
    with pytest.raises(AIOutputValidationError):
        provider.extract("Syllabus content")


def test_groq_provider_raises_on_sdk_failure() -> None:
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("rate limit")

    provider = GroqProvider(api_key="gsk_test", client=fake_client)
    with pytest.raises(AIProviderRequestError):
        provider.extract("Syllabus content")


def test_gemini_provider_extracts_structured_json() -> None:
    payload_str = json.dumps(_sample_payload())
    fake_response = SimpleNamespace(
        text=payload_str,
        usage_metadata=SimpleNamespace(
            prompt_token_count=250,
            candidates_token_count=150,
            total_token_count=400,
        ),
    )
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    provider = GeminiProvider(
        api_key="gem_test", model="gemini-2.5-flash-lite", client=fake_client
    )
    result = provider.extract("Unit 1: Asymptotic Analysis...")

    assert result.provider == "gemini"
    assert result.model == "gemini-2.5-flash-lite"
    assert len(result.extraction.topics) == 2
    assert result.total_tokens == 400


def test_missing_api_key_raises_not_configured() -> None:
    with pytest.raises(AIProviderNotConfiguredError):
        GroqProvider(api_key="")


def test_extract_topics_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="empty"):
        extract_topics_from_syllabus("   ")


def test_extract_topics_truncates_and_falls_back_to_gemini() -> None:
    cfg = Settings(
        ai_provider="groq",
        groq_api_key="gsk_test",
        gemini_api_key="gem_test",
        ai_max_syllabus_chars=50,
    )
    fake_gemini_response = SimpleNamespace(
        text=json.dumps(_sample_payload()),
        usage_metadata=None,
    )
    fake_gemini_client = MagicMock()
    fake_gemini_client.models.generate_content.return_value = fake_gemini_response

    with (
        patch.object(GroqProvider, "extract", side_effect=AIProviderRequestError("503")),
        patch("app.services.ai_service.GeminiProvider._get_client", return_value=fake_gemini_client),
    ):
        result = extract_topics_from_syllabus("A" * 100, settings=cfg, allow_fallback=True)

    assert result.provider == "gemini"
    assert result.truncated is True
    assert len(result.extraction.topics) == 2


def test_extract_topics_no_fallback_propagates_primary_error() -> None:
    cfg = Settings(
        ai_provider="groq",
        groq_api_key="gsk_test",
        gemini_api_key="gem_test",
    )
    with patch.object(GroqProvider, "extract", side_effect=AIProviderRequestError("503")):
        with pytest.raises(AIProviderRequestError):
            extract_topics_from_syllabus("Syllabus text", settings=cfg, allow_fallback=False)
