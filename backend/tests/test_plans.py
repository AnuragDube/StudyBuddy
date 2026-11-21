from datetime import date, timedelta


def _future(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _plan_payload(**overrides):
    payload = {
        "subject_name": "Operating Systems",
        "exam_date": _future(),
        "syllabus_raw_text": "Unit 1: Processes. Unit 2: Memory management.",
        "topics": [
            {"name": "Processes", "difficulty": "medium", "priority": 4, "estimated_minutes": 90},
            {"name": "Memory management", "difficulty": "high", "priority": 5, "estimated_minutes": 120},
        ],
    }
    payload.update(overrides)
    return payload


def test_create_plan_with_topics(client):
    response = client.post("/api/plans", json=_plan_payload())
    assert response.status_code == 201
    plan = response.json()
    assert plan["subject_name"] == "Operating Systems"
    assert plan["status"] == "active"
    assert plan["topic_count"] == 2
    assert plan["total_minutes"] == 210
    assert plan["progress_percent"] == 0.0
    assert plan["color"].startswith("#")
    assert [t["order_index"] for t in plan["topics"]] == [0, 1]


def test_list_get_update_delete_plan(client):
    plan_id = client.post("/api/plans", json=_plan_payload()).json()["id"]
    client.post("/api/plans", json=_plan_payload(subject_name="DBMS", exam_date=_future(10)))

    plans = client.get("/api/plans").json()
    assert [p["subject_name"] for p in plans] == ["DBMS", "Operating Systems"]  # sorted by exam date

    assert client.get(f"/api/plans/{plan_id}").json()["id"] == plan_id

    updated = client.patch(f"/api/plans/{plan_id}", json={"status": "archived"}).json()
    assert updated["status"] == "archived"
    assert [p["subject_name"] for p in client.get("/api/plans?status=active").json()] == ["DBMS"]

    assert client.delete(f"/api/plans/{plan_id}").status_code == 204
    assert client.get(f"/api/plans/{plan_id}").status_code == 404


def test_plan_validation(client):
    assert client.post("/api/plans", json=_plan_payload(subject_name="   ")).status_code == 422
    past = (date.today() - timedelta(days=1)).isoformat()
    assert client.post("/api/plans", json=_plan_payload(exam_date=past)).status_code == 422
    bad_topic = _plan_payload(topics=[{"name": "X", "priority": 9}])
    assert client.post("/api/plans", json=bad_topic).status_code == 422
    assert client.post("/api/plans", json=_plan_payload(color="red")).status_code == 422


def test_missing_plan_returns_404(client):
    assert client.get("/api/plans/999").status_code == 404
    assert client.patch("/api/plans/999", json={"subject_name": "X"}).status_code == 404
    assert client.delete("/api/plans/999").status_code == 404


def test_topic_crud(client):
    plan = client.post("/api/plans", json=_plan_payload()).json()
    pid = plan["id"]

    topic = client.post(f"/api/plans/{pid}/topics", json={"name": "Deadlocks", "estimated_minutes": 45})
    assert topic.status_code == 201
    tid = topic.json()["id"]
    assert topic.json()["order_index"] == 2

    done = client.patch(f"/api/plans/{pid}/topics/{tid}", json={"is_completed": True}).json()
    assert done["is_completed"] is True
    assert done["remaining_minutes"] == 0

    detail = client.get(f"/api/plans/{pid}").json()
    assert detail["completed_topic_count"] == 1
    assert detail["progress_percent"] == round(100 * 45 / 255, 1)

    assert client.delete(f"/api/plans/{pid}/topics/{tid}").status_code == 204
    assert client.patch(f"/api/plans/{pid}/topics/{tid}", json={"name": "x"}).status_code == 404


def test_replace_topics(client):
    pid = client.post("/api/plans", json=_plan_payload()).json()["id"]
    response = client.put(f"/api/plans/{pid}/topics", json=[{"name": "Only topic", "estimated_minutes": 30}])
    assert response.status_code == 200
    assert [t["name"] for t in response.json()["topics"]] == ["Only topic"]
