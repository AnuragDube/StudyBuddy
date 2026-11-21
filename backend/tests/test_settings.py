def test_settings_defaults_created_on_first_read(client):
    body = client.get("/api/settings").json()
    assert body["daily_study_minutes"] == 240
    assert body["preferred_study_days"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert body["max_session_minutes"] == 60


def test_update_settings_normalizes_days(client):
    response = client.put(
        "/api/settings",
        json={"daily_study_minutes": 180, "preferred_study_days": ["friday", "mon", "Wed", "Mon"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["daily_study_minutes"] == 180
    assert body["preferred_study_days"] == ["Mon", "Wed", "Fri"]
    # persisted
    assert client.get("/api/settings").json()["daily_study_minutes"] == 180


def test_partial_update_keeps_other_fields(client):
    client.put("/api/settings", json={"preferred_study_days": ["Sat", "Sun"]})
    body = client.put("/api/settings", json={"daily_study_minutes": 120}).json()
    assert body["preferred_study_days"] == ["Sat", "Sun"]
    assert body["daily_study_minutes"] == 120


def test_settings_validation_errors(client):
    assert client.put("/api/settings", json={"daily_study_minutes": 5}).status_code == 422
    assert client.put("/api/settings", json={"daily_study_minutes": 2000}).status_code == 422
    assert client.put("/api/settings", json={"preferred_study_days": []}).status_code == 422
    assert client.put("/api/settings", json={"preferred_study_days": ["Funday"]}).status_code == 422
