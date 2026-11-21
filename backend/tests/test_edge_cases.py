"""Comprehensive edge-case and multi-subject workflow tests."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.ai_service import (
    AIOutputValidationError,
    AIProviderNotConfiguredError,
    AIProviderRequestError,
)


def test_three_subject_shared_capacity_never_exceeds_cap_or_overlaps(
    client: TestClient,
) -> None:
    assert (
        client.put(
            "/api/settings",
            json={
                "daily_study_minutes": 180,
                "max_session_minutes": 60,
                "preferred_study_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            },
        ).status_code
        == 200
    )

    today = date.today()
    subjects = [
        ("Operating Systems", today + timedelta(days=3), 180),
        ("Computer Networks", today + timedelta(days=5), 240),
        ("Compiler Design", today + timedelta(days=7), 180),
    ]
    for name, exam, mins in subjects:
        r = client.post(
            "/api/plans",
            json={
                "subject_name": name,
                "exam_date": exam.isoformat(),
                "topics": [
                    {
                        "name": f"{name} Core",
                        "difficulty": "high",
                        "priority": 5,
                        "estimated_minutes": mins,
                    }
                ],
            },
        )
        assert r.status_code == 201

    sched = client.get("/api/schedule").json()
    assert sched["is_feasible"] is True
    assert sched["total_required_minutes"] == 600
    assert sched["total_scheduled_minutes"] == 600

    by_day = defaultdict(list)
    for s in sched["sessions"]:
        by_day[s["scheduled_date"]].append(s)

    for day, blocks in by_day.items():
        blocks.sort(key=lambda b: b["start_offset_minutes"])
        total = 0
        prev_end = 0
        for b in blocks:
            assert b["start_offset_minutes"] >= prev_end, f"Overlap on {day}"
            prev_end = b["start_offset_minutes"] + b["duration_minutes"]
            total += b["duration_minutes"]
        assert total <= 180, f"Exceeded 180m cap on {day}: {total}"


def test_archiving_overloaded_subject_restores_feasibility(client: TestClient) -> None:
    client.put(
        "/api/settings",
        json={
            "daily_study_minutes": 120,
            "max_session_minutes": 60,
            "preferred_study_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        },
    )
    exam = (date.today() + timedelta(days=2)).isoformat()  # 2 days * 120 = 240 min capacity

    p1 = client.post(
        "/api/plans",
        json={
            "subject_name": "Math",
            "exam_date": exam,
            "topics": [
                {"name": "Calculus", "difficulty": "high", "priority": 5, "estimated_minutes": 180}
            ],
        },
    ).json()
    p2 = client.post(
        "/api/plans",
        json={
            "subject_name": "Elective",
            "exam_date": exam,
            "topics": [
                {"name": "Essay", "difficulty": "low", "priority": 2, "estimated_minutes": 180}
            ],
        },
    ).json()

    overloaded = client.get("/api/schedule").json()
    assert overloaded["is_feasible"] is False
    assert overloaded["deficit_minutes"] == 120

    # Archiving Elective immediately makes Math feasible!
    arch = client.patch(f"/api/plans/{p2['id']}", json={"status": "archived"})
    assert arch.status_code == 200

    recovered = client.get("/api/schedule").json()
    assert recovered["is_feasible"] is True
    assert recovered["deficit_minutes"] == 0
    assert all(s["plan_id"] == p1["id"] for s in recovered["sessions"])


def test_completing_all_sessions_completes_topic_and_reset_reverts(client: TestClient) -> None:
    client.put("/api/settings", json={"daily_study_minutes": 120, "max_session_minutes": 60})
    exam = (date.today() + timedelta(days=4)).isoformat()

    plan = client.post(
        "/api/plans",
        json={
            "subject_name": "DBMS",
            "exam_date": exam,
            "topics": [
                {"name": "B+ Trees", "difficulty": "medium", "priority": 4, "estimated_minutes": 60}
            ],
        },
    ).json()

    sched = client.get("/api/schedule").json()
    assert len(sched["sessions"]) == 1
    sid = sched["sessions"][0]["id"]

    done = client.patch(f"/api/sessions/{sid}", json={"status": "completed"}).json()
    assert done["topic_completed"] is True

    refreshed_plan = client.get(f"/api/plans/{plan['id']}").json()
    assert refreshed_plan["progress_percent"] == 100
    assert refreshed_plan["topics"][0]["is_completed"] is True

    # Reset back to pending
    reverted = client.patch(f"/api/sessions/{sid}", json={"status": "pending"}).json()
    assert reverted["topic_completed"] is False
    assert reverted["schedule"]["total_required_minutes"] == 60


def test_missing_session_returns_404(client: TestClient) -> None:
    resp = client.patch("/api/sessions/99999", json={"status": "completed"})
    assert resp.status_code == 404


def test_syllabus_extract_error_mappings(client: TestClient) -> None:
    # Corrupt PDF -> 400
    corrupt = client.post(
        "/api/syllabus/extract",
        files={"file": ("broken.pdf", b"%PDF-1.7\ncorrupt", "application/pdf")},
    )
    assert corrupt.status_code == 400

    # Too short raw text -> 400
    short = client.post("/api/syllabus/extract", data={"raw_text": "short"})
    assert short.status_code == 400

    valid_text = "Unit 1: Graph Theory, Shortest Paths, Minimum Spanning Trees, Network Flows."

    # Provider not configured -> 503
    with patch(
        "app.api.routes.syllabus.extract_topics_from_syllabus",
        side_effect=AIProviderNotConfiguredError("No key"),
    ):
        r503 = client.post("/api/syllabus/extract", data={"raw_text": valid_text})
        assert r503.status_code == 503

    # Upstream failure -> 502
    with patch(
        "app.api.routes.syllabus.extract_topics_from_syllabus",
        side_effect=AIProviderRequestError("timeout"),
    ):
        r502 = client.post("/api/syllabus/extract", data={"raw_text": valid_text})
        assert r502.status_code == 502

    # Invalid LLM output -> 502
    with patch(
        "app.api.routes.syllabus.extract_topics_from_syllabus",
        side_effect=AIOutputValidationError("bad json"),
    ):
        r502_val = client.post("/api/syllabus/extract", data={"raw_text": valid_text})
        assert r502_val.status_code == 502
