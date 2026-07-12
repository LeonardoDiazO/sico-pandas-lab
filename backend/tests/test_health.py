from app import create_app


def test_health_returns_success_envelope():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["status"] == 200
    assert "message" in body
    assert "data" in body
