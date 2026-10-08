from collections.abc import Callable

from fastapi.testclient import TestClient


def test_health_and_metrics_are_public(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    assert c.get("/health").json() == {"status": "ok"}
    assert c.get("/metrics").status_code == 200


def test_protected_endpoints_require_auth(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    for path in ("/agents", "/providers", "/usage", "/auth/me"):
        assert c.get(path).status_code == 401, path
