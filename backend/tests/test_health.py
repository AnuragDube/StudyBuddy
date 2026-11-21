def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ai_provider"] in {"groq", "gemini"}
    assert isinstance(body["ai_configured"], bool)
    assert "x-request-id" in response.headers


def test_openapi_docs_available(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/health" in schema["paths"]
