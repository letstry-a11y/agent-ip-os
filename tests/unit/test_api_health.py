from agent_ip_api.main import app
from fastapi.testclient import TestClient


def test_health_endpoint_is_safe_by_default() -> None:
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agent-ip-api",
        "external_side_effects_enabled": False,
    }
