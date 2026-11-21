"""Authentication and multi-user schedule isolation tests."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _register_and_headers(client: TestClient, name: str, email: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_me_flow(anon_client: TestClient) -> None:
    reg = anon_client.post(
        "/api/auth/register",
        json={"name": "Alice", "email": "Alice@Example.com", "password": "secret123"},
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["token_type"] == "bearer"

    # Duplicate registration fails with 409
    dup = anon_client.post(
        "/api/auth/register",
        json={"name": "Alice 2", "email": "alice@example.com", "password": "secret123"},
    )
    assert dup.status_code == 409

    # Wrong password fails with 401
    bad = anon_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert bad.status_code == 401

    # Valid login returns token and /me works
    ok = anon_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "secret123"},
    )
    assert ok.status_code == 200
    token = ok.json()["access_token"]

    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["name"] == "Alice"


def test_protected_endpoints_require_authentication(anon_client: TestClient) -> None:
    assert anon_client.get("/api/settings").status_code == 401
    assert anon_client.get("/api/plans").status_code == 401
    assert anon_client.get("/api/schedule").status_code == 401


def test_two_users_have_completely_isolated_plans_settings_and_schedules(
    anon_client: TestClient,
) -> None:
    alice_h = _register_and_headers(anon_client, "Alice", "alice@test.edu", "pass1234")
    bob_h = _register_and_headers(anon_client, "Bob", "bob@test.edu", "pass1234")

    exam = (date.today() + timedelta(days=5)).isoformat()

    # Alice sets 120 min/day and adds Algorithms
    assert anon_client.put("/api/settings", json={"daily_study_minutes": 120}, headers=alice_h).status_code == 200
    alice_plan = anon_client.post(
        "/api/plans",
        json={
            "subject_name": "Algorithms",
            "exam_date": exam,
            "topics": [{"name": "DP", "difficulty": "high", "priority": 5, "estimated_minutes": 120}],
        },
        headers=alice_h,
    ).json()

    # Bob sets 300 min/day and adds Biology
    assert anon_client.put("/api/settings", json={"daily_study_minutes": 300}, headers=bob_h).status_code == 200
    anon_client.post(
        "/api/plans",
        json={
            "subject_name": "Biology",
            "exam_date": exam,
            "topics": [{"name": "Genetics", "difficulty": "medium", "priority": 4, "estimated_minutes": 60}],
        },
        headers=bob_h,
    )

    # Verify strict isolation of settings, plans, and schedules
    assert anon_client.get("/api/settings", headers=alice_h).json()["daily_study_minutes"] == 120
    assert anon_client.get("/api/settings", headers=bob_h).json()["daily_study_minutes"] == 300

    alice_plans = anon_client.get("/api/plans", headers=alice_h).json()
    bob_plans = anon_client.get("/api/plans", headers=bob_h).json()
    assert [p["subject_name"] for p in alice_plans] == ["Algorithms"]
    assert [p["subject_name"] for p in bob_plans] == ["Biology"]

    # Bob cannot read or delete Alice's plan
    assert anon_client.get(f"/api/plans/{alice_plan['id']}", headers=bob_h).status_code == 404
    assert anon_client.delete(f"/api/plans/{alice_plan['id']}", headers=bob_h).status_code == 404

    alice_sched = anon_client.get("/api/schedule", headers=alice_h).json()
    bob_sched = anon_client.get("/api/schedule", headers=bob_h).json()
    assert {s["subject_name"] for s in alice_sched["sessions"]} == {"Algorithms"}
    assert {s["subject_name"] for s in bob_sched["sessions"]} == {"Biology"}
