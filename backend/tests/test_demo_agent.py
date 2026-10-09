import time
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models import RequestLog
from tests.conftest import login


def _wait_for(c: TestClient, event_type: str) -> list[dict[str, object]]:
    for _ in range(40):
        evs = c.get("/events?limit=50").json()["events"]
        if any(e["type"] == event_type for e in evs):
            return evs  # type: ignore[no-any-return]
        time.sleep(0.05)
    raise AssertionError(f"{event_type} jamais émis")


def test_disabled_by_default(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    login(c, "ana")
    assert c.post("/agents/demo/run", json={}).status_code == 404
    assert c.get("/agents").json() == []


def test_viewer_cannot_run_agent(make_client: Callable[..., TestClient]) -> None:
    c = make_client(demo_agent_enabled=True)
    login(c, "vic")
    assert c.post("/agents/demo/run", json={}).status_code == 403


def test_successful_run_emits_lifecycle_and_is_flagged_simulated(
    make_client: Callable[..., TestClient],
) -> None:
    c = make_client(demo_agent_enabled=True, demo_step_delay=0.0)
    login(c, "ana")
    assert c.post("/agents/demo/run", json={}).status_code == 202
    evs = _wait_for(c, "agent.completed")
    assert [e["type"] for e in evs][0] == "agent.started"
    assert all(e["data"]["simulated"] is True and e["source"] == "demo_agent" for e in evs)  # type: ignore[index]
    agent = c.get("/agents").json()[0]
    assert agent["simulated"] is True and agent["tasks_completed"] == 1
    assert agent["status"] == "idle"


def test_failed_run_emits_agent_failed(make_client: Callable[..., TestClient]) -> None:
    c = make_client(demo_agent_enabled=True, demo_step_delay=0.0)
    login(c, "ana")
    c.post("/agents/demo/run", json={"fail": True})
    evs = _wait_for(c, "agent.failed")
    failed = next(e for e in evs if e["type"] == "agent.failed")
    assert failed["severity"] == "medium" and failed["data"]["error_type"] == "RuntimeError"  # type: ignore[index]
    assert c.get("/agents").json()[0]["tasks_failed"] == 1


def test_simulated_tokens_never_reach_usage_stats(make_client: Callable[..., TestClient]) -> None:
    c = make_client(demo_agent_enabled=True, demo_step_delay=0.0)
    login(c, "ana")
    c.post("/agents/demo/run", json={})
    _wait_for(c, "agent.completed")
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.query(RequestLog).count() == 0
    w = c.get("/usage/tokens").json()["windows"]["24h"]
    assert w["requests"] == 0 and w["tokens"] == {"value": 0, "available": True}
