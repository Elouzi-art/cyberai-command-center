"""R3 : événements conformes à schemas/event.v1.json ; le bus ne bloque jamais le producteur."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import jsonschema
from fastapi.testclient import TestClient

from app.events import EventBus
from app.providers import RawResult
from tests.conftest import FakeProvider, login

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "event.v1.json").read_text())


def test_ring_buffer_is_bounded_and_filterable() -> None:
    bus = EventBus(size=3)
    for i in range(5):
        bus.publish(source="s", agent="a", type="api.request" if i % 2 else "token.usage")
    assert len(bus.recent(100)) == 3
    assert all(e.type.startswith("api") for e in bus.recent(100, "api"))


def test_slow_subscriber_never_blocks_producer() -> None:
    async def run() -> int:
        bus = EventBus()
        q = bus.subscribe(maxsize=2)
        for _ in range(10):
            bus.publish(source="s", agent="a", type="t")
        return q.qsize()

    assert asyncio.run(run()) == 2


def test_route_events_validate_against_unified_schema(
    make_client: Callable[..., TestClient],
) -> None:
    ok = FakeProvider(RawResult("x", 3, 2))
    c = make_client({"fake": ok})
    login(c, "ana")
    c.post("/providers/fake/complete", json={"prompt": "p", "sensitivity": "public"})
    bad = FakeProvider(httpx.ConnectError("boom"))
    bad.id = "bad"
    c.app.state.providers["bad"] = bad  # type: ignore[attr-defined]
    c.post("/providers/bad/complete", json={"prompt": "p", "sensitivity": "public"})
    events = c.get("/events").json()["events"]
    assert {e["type"] for e in events} == {"api.request", "token.usage", "api.error"}
    for e in events:
        jsonschema.validate(e, SCHEMA)


def test_events_never_contain_prompt_or_secrets(make_client: Callable[..., TestClient]) -> None:
    c = make_client({"fake": FakeProvider(RuntimeError("clé=sk-SECRET"))})
    login(c, "ana")
    c.post("/providers/fake/complete", json={"prompt": "PROMPT-SECRET", "sensitivity": "public"})
    blob = c.get("/events").text
    assert "PROMPT-SECRET" not in blob and "sk-SECRET" not in blob


def test_events_require_auth_and_unknown_tokens_are_flagged(
    make_client: Callable[..., TestClient],
) -> None:
    c = make_client({"fake": FakeProvider(RawResult("x"))})
    assert c.get("/events").status_code == 401
    login(c, "vic")
    c.app.state.bus.publish(source="s", agent="a", type="t")  # type: ignore[attr-defined]
    assert len(c.get("/events?limit=1").json()["events"]) == 1
