from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models import AuditLog, RequestLog
from app.providers import RawResult
from tests.conftest import FakeProvider, login


def _client(
    make_client: Callable[..., TestClient],
    raw: RawResult | Exception,
    sens: tuple[str, ...] = ("public",),
) -> TestClient:
    return make_client({"fake": FakeProvider(raw, sens)})


def test_viewer_can_list_but_not_complete(make_client: Callable[..., TestClient]) -> None:
    c = _client(make_client, RawResult("x"))
    login(c, "vic")
    assert c.get("/providers").status_code == 200
    r = c.post("/providers/fake/complete", json={"prompt": "hi", "sensitivity": "public"})
    assert r.status_code == 403


def test_missing_tokens_are_null_not_zero_r1(make_client: Callable[..., TestClient]) -> None:
    c = _client(make_client, RawResult("réponse"))  # le fournisseur n'expose aucun token
    login(c, "ana")
    r = c.post("/providers/fake/complete", json={"prompt": "hi", "sensitivity": "public"})
    assert r.json()["input_tokens"] == {"value": None, "available": False}
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        row = db.query(RequestLog).one()
        assert row.total_tokens is None and row.status == "success"
    use = c.get("/usage").json()[0]
    assert use["tokens"] == {"value": None, "available": False}
    m = c.get("/providers").json()[0]["metrics"]
    assert m["tokens"] == {"value": None, "available": False}
    assert m["quota_remaining"] == {"value": None, "available": False}
    assert m["cost"] == {"value": None, "available": False}


def test_known_tokens_are_summed(make_client: Callable[..., TestClient]) -> None:
    c = _client(make_client, RawResult("ok", input_tokens=10, output_tokens=5))
    login(c, "ana")
    c.post("/providers/fake/complete", json={"prompt": "a", "sensitivity": "public"})
    c.post("/providers/fake/complete", json={"prompt": "b", "sensitivity": "public"})
    assert c.get("/usage").json()[0]["tokens"] == {"value": 30, "available": True}


def test_sensitivity_routing_blocks_confidential_to_public_provider(
    make_client: Callable[..., TestClient],
) -> None:
    c = _client(make_client, RawResult("x"), sens=("public",))
    login(c, "ana")
    r = c.post(
        "/providers/fake/complete", json={"prompt": "log client", "sensitivity": "confidential"}
    )
    assert r.status_code == 403
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.query(RequestLog).count() == 0
        assert db.query(AuditLog).filter_by(action="provider_refused_sensitivity").count() == 1


def test_provider_error_is_logged_without_leaking(make_client: Callable[..., TestClient]) -> None:
    c = _client(make_client, RuntimeError("clé=sk-SECRET prompt=secret-data"))
    login(c, "ana")
    r = c.post("/providers/fake/complete", json={"prompt": "secret-data", "sensitivity": "public"})
    assert r.status_code == 502 and "SECRET" not in r.text and "secret-data" not in r.text
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        row = db.query(RequestLog).one()
        assert row.status == "error" and row.error_type == "RuntimeError"
    assert c.get("/usage").json()[0]["errors"] == 1


def test_prompt_never_written_to_audit_log(make_client: Callable[..., TestClient]) -> None:
    c = _client(make_client, RawResult("x", 1, 1))
    login(c, "ana")
    c.post(
        "/providers/fake/complete", json={"prompt": "PROMPT-CONFIDENTIEL", "sensitivity": "public"}
    )
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert all("PROMPT-CONFIDENTIEL" not in a.detail for a in db.query(AuditLog))
