"""Schemas for LLM syllabus-extraction output.

Two representations are kept deliberately in sync:

* ``SYLLABUS_EXTRACTION_JSON_SCHEMA`` – a hand-written JSON Schema that satisfies
  provider "strict" structured-output rules (every object has
  ``additionalProperties: false`` and lists *all* keys in ``required``; optional
  values are expressed as ``anyOf [T, null]``).
* ``SyllabusExtraction`` – the Pydantic model every provider response is
  validated against before it reaches the database or scheduler.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.models import Difficulty

MIN_TOPIC_MINUTES = 15
MAX_TOPIC_MINUTES = 1200


class ExtractedTopic(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    unit: str | None = Field(None, max_length=200)
    subtopics: list[str] = Field(default_factory=list)
    difficulty: Difficulty
    priority: int = Field(..., ge=1, le=5)
    estimated_minutes: int = Field(..., ge=MIN_TOPIC_MINUTES, le=MAX_TOPIC_MINUTES)
    rationale: str = ""

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()[:200]
            return value or None
        return value

    @field_validator("difficulty", mode="before")
    @classmethod
    def _difficulty(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("priority", mode="before")
    @classmethod
    def _clamp_priority(cls, value: Any) -> Any:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(min(5, max(1, round(value))))
        return value

    @field_validator("estimated_minutes", mode="before")
    @classmethod
    def _clamp_minutes(cls, value: Any) -> Any:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(min(MAX_TOPIC_MINUTES, max(MIN_TOPIC_MINUTES, round(value))))
        return value

    @field_validator("subtopics", mode="before")
    @classmethod
    def _subtopics(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [str(s).strip() for s in value if str(s).strip()][:20]
        return value


class SyllabusExtraction(BaseModel):
    subject_title: str | None = None
    topics: list[ExtractedTopic] = Field(..., min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def _dedupe(self) -> SyllabusExtraction:
        seen: set[str] = set()
        unique: list[ExtractedTopic] = []
        for topic in self.topics:
            key = topic.name.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(topic)
        self.topics = unique
        return self

    @property
    def total_minutes(self) -> int:
        return sum(t.estimated_minutes for t in self.topics)


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


SYLLABUS_EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "subject_title": {
            **_nullable({"type": "string"}),
            "description": "Course/subject title if stated in the syllabus, else null.",
        },
        "topics": {
            "type": "array",
            "description": "Study topics found in the syllabus, in syllabus order.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Concise topic name from the syllabus."},
                    "unit": {
                        **_nullable({"type": "string"}),
                        "description": "Unit/module label if stated, else null.",
                    },
                    "subtopics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key subtopics mentioned for this topic.",
                    },
                    "difficulty": {"type": "string", "enum": ["low", "medium", "high"]},
                    "priority": {
                        "type": "integer",
                        "description": "1 (optional) to 5 (critical/foundational).",
                    },
                    "estimated_minutes": {
                        "type": "integer",
                        "description": "Total minutes a typical student needs (learning + practice + revision).",
                    },
                    "rationale": {"type": "string", "description": "One short sentence justifying the estimate."},
                },
                "required": [
                    "name", "unit", "subtopics", "difficulty", "priority", "estimated_minutes", "rationale",
                ],
                "additionalProperties": False,
            },
        },
        "notes": {
            **_nullable({"type": "string"}),
            "description": "Caveats, e.g. if the text is not a syllabus.",
        },
    },
    "required": ["subject_title", "topics", "notes"],
    "additionalProperties": False,
}
