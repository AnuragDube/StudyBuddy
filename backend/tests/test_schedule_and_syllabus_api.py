"""API integration tests for syllabus upload, scheduling, and dynamic rescheduling."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db.models import Difficulty
from app.schemas.ai import ExtractedTopic, SyllabusExtraction
from app.services.ai_service import ExtractionResult


def _mock_ai_result() -> ExtractionResult:
    extraction = SyllabusExtraction(
        subject_title="Computer Networks",
        topics=[
            ExtractedTopic(
                name="TCP/IP Stack",
                unit="Unit 1",
                subtopics=["TCP Handshake", "Congestion Control"],
                difficulty=Difficulty.high,
                priority=5,
                estimated_minutes=120,
                rationale="Core transport layer protocol.",
            ),
            ExtractedTopic(
                name="Routing Algorithms",
                unit="Unit 2",
                subtopics=["Dijkstra", "Bellman-Ford"],
                difficulty=Difficulty.medium,
                priority=4,
                estimated_minutes=60,
                rationale="Standard shortest-path practice.",
            ),
        ],
        notes=None,
    )
    return ExtractionResult(
        extraction=extraction,
        provider="groq",
        model="openai/gpt-oss-20b",
        latency_ms=42.5,
        raw_json=extraction.model_dump_json(),
        truncated=False,
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
    )


def test_syllabus_extract_endpoint_with_raw_text_and_file(client: TestClient) -> None:
    with patch(
        "app.api.routes.syllabus.extract_topics_from_syllabus",
        return_value=_mock_ai_result(),
    ):
        resp = client.post(
            "/api/syllabus/extract",
            data={
                "raw_text": "Unit 1: TCP/IP Stack and Congestion Control. Unit 2: Routing Algorithms.",
                "subject_hint": "Computer Networks",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "groq"
        assert len(body["extraction"]["topics"]) == 2

        file_resp = client.post(
            "/api/syllabus/extract",
            files={
                "file": (
                    "syllabus.txt",
                    b"Unit 1: TCP/IP Stack and Congestion Control. Unit 2: Routing Algorithms.",
                    "text/plain",
                )
            },
        )
        assert file_resp.status_code == 200
        assert file_resp.json()["page_count"] == 1


def test_syllabus_extract_requires_file_or_text(client: TestClient) -> None:
    resp = client.post("/api/syllabus/extract", data={})
    assert resp.status_code == 400


def test_plan_extract_syllabus_populates_topics_and_schedule(client: TestClient) -> None:
    exam = (date.today() + timedelta(days=5)).isoformat()
    plan_resp = client.post(
        "/api/plans",
        json={"subject_name": "Computer Networks", "exam_date": exam},
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    with patch(
        "app.api.routes.syllabus.extract_topics_from_syllabus",
        return_value=_mock_ai_result(),
    ):
        ext_resp = client.post(
            f"/api/plans/{plan_id}/extract-syllabus",
            data={
                "raw_text": "Unit 1: TCP/IP Stack and Congestion Control. Unit 2: Routing Algorithms."
            },
        )
    assert ext_resp.status_code == 200
    assert len(ext_resp.json()["topics"]) == 2

    sched_resp = client.get("/api/schedule")
    assert sched_resp.status_code == 200
    sched = sched_resp.json()
    assert sched["is_feasible"] is True
    assert sched["total_required_minutes"] == 180
    assert sched["total_scheduled_minutes"] == 180
    assert len(sched["sessions"]) >= 3


def test_session_completion_missed_rescheduling_and_capacity_overload(
    client: TestClient,
) -> None:
    # Set shared capacity to 120 min/day, max 60 min/session
    cap_resp = client.put(
        "/api/settings",
        json={"daily_study_minutes": 120, "max_session_minutes": 60},
    )
    assert cap_resp.status_code == 200

    exam = (date.today() + timedelta(days=3)).isoformat()
    plan_resp = client.post(
        "/api/plans",
        json={
            "subject_name": "Linear Algebra",
            "exam_date": exam,
            "topics": [
                {
                    "name": "Eigenvalues",
                    "difficulty": "high",
                    "priority": 5,
                    "estimated_minutes": 120,
                }
            ],
        },
    )
    assert plan_resp.status_code == 201

    sched = client.get("/api/schedule").json()
    assert sched["is_feasible"] is True
    assert len(sched["sessions"]) == 2  # two 60-min blocks

    # Mark first session missed -> unfinished 120 min still rescheduled
    first_id = sched["sessions"][0]["id"]
    miss_resp = client.patch(f"/api/sessions/{first_id}", json={"status": "missed"})
    assert miss_resp.status_code == 200
    miss_body = miss_resp.json()
    assert miss_body["topic_completed"] is False
    assert miss_body["schedule"]["total_required_minutes"] == 120

    # Mark a pending session completed -> remaining drops to 60 min
    pending = [s for s in miss_body["schedule"]["sessions"] if s["status"] == "pending"]
    done_resp = client.patch(f"/api/sessions/{pending[0]['id']}", json={"status": "completed"})
    assert done_resp.status_code == 200
    done_body = done_resp.json()
    assert done_body["topic_completed"] is False
    assert done_body["schedule"]["total_required_minutes"] == 60

    # Reduce daily capacity to 30 min/day with only 1 remaining preferred day -> infeasible!
    low_cap = client.put(
        "/api/settings",
        json={"daily_study_minutes": 30, "max_session_minutes": 30},
    )
    assert low_cap.status_code == 200
    # Add a second heavy topic so remaining workload clearly exceeds 3 days * 30 min = 90 min
    plan_id = plan_resp.json()["id"]
    add_resp = client.post(
        f"/api/plans/{plan_id}/topics",
        json={
            "name": "Singular Value Decomposition",
            "difficulty": "high",
            "priority": 5,
            "estimated_minutes": 180,
        },
    )
    assert add_resp.status_code == 201
    overloaded = client.get("/api/schedule").json()
    assert overloaded["is_feasible"] is False
    assert overloaded["deficit_minutes"] > 0
    assert len(overloaded["warnings"]) >= 1
    assert len(overloaded["suggestions"]) >= 1
