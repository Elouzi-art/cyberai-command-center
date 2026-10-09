"""Fenêtres de tokens : R1 (jamais de somme partielle présentée comme complète)."""

from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from app.models import RequestLog, utcnow
from tests.conftest import login


def _add(c: TestClient, **kw: object) -> None:
    base: dict[str, object] = {
        "provider": "p",
        "model": "m",
        "agent": "a",
        "latency_ms": 10,
        "status": "success",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        db.add(RequestLog(**{**base, **kw}))
        db.commit()


def test_empty_windows_are_measured_zero(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    login(c, "vic")
    w = c.get("/usage/tokens").json()["windows"]
    assert w["1m"]["tokens"] == {"value": 0, "available": True} and w["1m"]["requests"] == 0
    assert w["1m"]["avg_tokens_per_request"] == {"value": None, "available": False}


def test_windows_respect_time_boundaries(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    login(c, "vic")
    now = utcnow()
    _add(c, timestamp=now - timedelta(seconds=10))
    _add(c, timestamp=now - timedelta(minutes=30))
    _add(c, timestamp=now - timedelta(hours=5))
    _add(c, timestamp=now - timedelta(days=3))  # hors fenêtre 24 h
    w = c.get("/usage/tokens").json()["windows"]
    assert w["1m"]["tokens"]["value"] == 15
    assert w["1h"]["tokens"]["value"] == 30
    assert w["24h"]["tokens"]["value"] == 45
    assert w["24h"]["avg_tokens_per_request"]["value"] == 15.0


def test_unknown_tokens_make_the_window_unavailable(
    make_client: Callable[..., TestClient],
) -> None:
    c = make_client()
    login(c, "vic")
    _add(c)
    _add(c, input_tokens=None, output_tokens=None, total_tokens=None)  # fournisseur muet
    w = c.get("/usage/tokens").json()["windows"]["24h"]
    assert w["tokens"] == {"value": None, "available": False}
    assert w["requests"] == 2


def test_errors_counted_and_do_not_poison_token_sum(
    make_client: Callable[..., TestClient],
) -> None:
    c = make_client()
    login(c, "vic")
    _add(c)
    _add(c, status="error", input_tokens=None, output_tokens=None, total_tokens=None)
    w = c.get("/usage/tokens").json()["windows"]["24h"]
    assert w["errors"] == 1 and w["tokens"] == {"value": 15, "available": True}


def test_breakdown_by_dimension(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    login(c, "vic")
    _add(c, agent="malware")
    _add(c, agent="malware")
    _add(c, agent="soc", input_tokens=None, output_tokens=None, total_tokens=None)
    rows = {r["agent"]: r for r in c.get("/usage/tokens?by=agent").json()["breakdown"]}
    assert rows["malware"]["tokens"] == {"value": 30, "available": True}
    assert rows["soc"]["tokens"] == {"value": None, "available": False}
    assert c.get("/usage/tokens?by=nimporte").status_code == 422


def test_requires_auth(make_client: Callable[..., TestClient]) -> None:
    assert make_client().get("/usage/tokens").status_code == 401
