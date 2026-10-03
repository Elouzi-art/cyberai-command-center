from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_metrics_endpoint() -> None:
    assert client.get("/metrics").status_code == 200


def test_lists_empty_at_sprint0() -> None:
    assert client.get("/agents").json() == []
    assert client.get("/providers").json() == []
