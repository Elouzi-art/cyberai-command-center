import time
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.models import SessionRow
from app.providers import RawResult
from tests.conftest import FakeProvider, login

ORIGIN = {"origin": "http://localhost:8080"}


def _auth(c: TestClient) -> dict[str, str]:
    return {**ORIGIN, "cookie": f"session={c.cookies.get('session')}"}


def test_ws_rejects_unauthenticated(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws/events", headers=ORIGIN):
            pass


def test_ws_rejects_foreign_origin_even_with_valid_session(
    make_client: Callable[..., TestClient],
) -> None:
    c = make_client()
    login(c, "vic")
    headers = {**_auth(c), "origin": "https://evil.example"}
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws/events", headers=headers):
            pass


def test_ws_streams_events_live(make_client: Callable[..., TestClient]) -> None:
    c = make_client({"fake": FakeProvider(RawResult("x", 1, 1))})
    login(c, "ana")
    with c.websocket_connect("/ws/events", headers=_auth(c)) as ws:
        c.post("/providers/fake/complete", json={"prompt": "p", "sensitivity": "public"})
        types = [ws.receive_json()["type"], ws.receive_json()["type"]]
    assert types == ["api.request", "token.usage"]


def test_ws_replay(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    login(c, "vic")
    for i in range(3):
        c.app.state.bus.publish(source="s", agent="a", type=f"t{i}")  # type: ignore[attr-defined]
    with c.websocket_connect("/ws/events?replay=2", headers=_auth(c)) as ws:
        assert [ws.receive_json()["type"], ws.receive_json()["type"]] == ["t1", "t2"]


def test_ws_closes_when_session_is_revoked(make_client: Callable[..., TestClient]) -> None:
    c = make_client(ws_recheck_seconds=0.2)
    login(c, "vic")
    with c.websocket_connect("/ws/events", headers=_auth(c)) as ws:
        with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
            db.query(SessionRow).delete()
            db.commit()
        time.sleep(0.5)
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
