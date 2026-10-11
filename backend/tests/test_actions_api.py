"""File d'approbation (R5, R9) : niveau décidé par la politique, l'humain approuve ce qu'il a vu."""

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from fastapi.testclient import TestClient

from app.models import Action, AuditLog, User, utcnow
from app.policy import Policy
from app.security import hash_password
from tests.conftest import PASSWORD, POLICY, login

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "schemas" / "approval_action.v1.json").read_text()
)
Make = Callable[..., TestClient]
SCAN = {"target": "198.51.100.1"}


def add_user(c: TestClient, name: str, role: str) -> None:
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        db.add(User(username=name, password_hash=hash_password(PASSWORD), role=role))
        db.commit()


def propose(c: TestClient, tool: str = "net.scan", params: dict[str, Any] | None = None, **kw: Any):  # type: ignore[no-untyped-def]
    return c.post("/actions", json={"tool": tool, "params": params or SCAN, **kw})


def approve(c: TestClient, act: dict[str, Any], dry_run: bool = False, seen: str | None = None):  # type: ignore[no-untyped-def]
    return c.post(
        f"/actions/{act['id']}/approve",
        json={"params_hash": seen or act["params_hash"], "dry_run": dry_run},
    )


def audit_names(c: TestClient) -> list[str]:
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        return [a.action for a in db.query(AuditLog).order_by(AuditLog.id)]


def event_types(c: TestClient) -> list[str]:
    return [e.type for e in c.app.state.bus.recent(500)]  # type: ignore[attr-defined]


def db_update(c: TestClient, values: dict[str, Any]) -> None:
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        db.query(Action).update(values)
        db.commit()


# ---------- accès ----------


def test_endpoints_require_auth_and_analyst_role(make_client: Make) -> None:
    c = make_client()
    assert c.get("/actions").status_code == 401
    assert propose(c).status_code == 401
    login(c, "vic")
    assert c.get("/actions").status_code == 403
    assert propose(c).status_code == 403
    assert c.get("/policy").status_code == 200  # la politique n'est pas secrète


EVIL = {"Origin": "https://evil.example"}


def test_foreign_origin_rejected_on_every_mutating_route(make_client: Make) -> None:
    c = make_client(allow_self_approval=True, demo_agent_enabled=True)
    login(c, "ana")
    a = propose(c).json()
    assert c.post("/actions", json={"tool": "net.scan"}, headers=EVIL).status_code == 403
    body = {"params_hash": a["params_hash"]}
    assert c.post(f"/actions/{a['id']}/approve", json=body, headers=EVIL).status_code == 403
    assert c.post(f"/actions/{a['id']}/reject", headers=EVIL).status_code == 403
    assert (
        c.post("/agents/demo/propose", json={"tool": "net.scan"}, headers=EVIL).status_code == 403
    )
    assert c.get(f"/actions/{a['id']}").json()["status"] == "pending"  # rien n'a bougé


# ---------- niveau décidé par la politique ----------


def test_forbidden_and_unknown_tools_are_refused_and_audited(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    for tool in ("evidence.delete", "rm.everything"):
        assert propose(c, tool).status_code == 403
    assert c.get("/actions").json() == []
    assert audit_names(c).count("action_refused") == 2
    assert event_types(c).count("action.refused") == 2


def test_request_cannot_choose_its_own_risk_level(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    for extra in (
        {"risk_level": "L0"},
        {"rollback": "x"},
        {"status": "approved"},
        {"approved_by": "ana"},
    ):
        assert propose(c, **extra).status_code == 422
    assert c.get("/actions").json() == []


def test_l0_and_l1_run_automatically_and_are_audited(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    a = propose(c, "file.parse_pe", {"path": "sample.bin"}).json()
    assert (a["status"], a["decided_by"], a["risk_level"]) == ("executed", "policy:auto", "L0")
    assert a["result"]["simulated"] is True
    b = propose(c, "intel.lookup_hash", {"sha256": "ab" * 32}).json()
    assert b["status"] == "executed" and b["risk_level"] == "L1"
    assert {"action_proposed", "action_auto_approved", "action_executed"} <= set(audit_names(c))


def test_l2_waits_for_approval_with_hash_and_ttl(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    a = propose(c).json()
    assert (a["status"], a["risk_level"], a["required_role"]) == ("pending", "L2", "analyst")
    expected = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                {"tool": "net.scan", "params": SCAN}, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )
    assert a["params_hash"] == expected
    ttl = datetime.fromisoformat(a["expires_at"]) - datetime.fromisoformat(a["created_at"])
    assert ttl == timedelta(minutes=60)
    jsonschema.validate(a, SCHEMA)


def test_l3_ttl_is_capped_by_policy_and_rollback_comes_from_policy(make_client: Make) -> None:
    c = make_client(approval_ttl_minutes=240)
    login(c, "ana")
    a = propose(c, "firewall.block_ip", {"ip": "203.0.113.9"}).json()
    ttl = datetime.fromisoformat(a["expires_at"]) - datetime.fromisoformat(a["created_at"])
    assert ttl == timedelta(minutes=60)
    assert (a["rollback"], a["required_role"]) == ("firewall.unblock_ip", "admin")


# ---------- qui peut approuver ----------


def test_analyst_cannot_approve_l3_but_admin_can(make_client: Make) -> None:
    c = make_client()
    add_user(c, "boss", "admin")
    login(c, "ana")
    a = propose(c, "firewall.block_ip", {"ip": "203.0.113.9"}).json()
    assert approve(c, a).status_code == 403
    assert c.get(f"/actions/{a['id']}").json()["status"] == "pending"
    assert "approval_denied_role" in audit_names(c)
    login(c, "boss")
    done = approve(c, a).json()
    assert (done["status"], done["decided_by"]) == ("executed", "boss")
    assert done["result"]["simulated"] is True
    chain = [n for n in audit_names(c) if n.startswith("action_") or n.startswith("approval_")]
    assert chain == [
        "action_proposed",
        "approval_denied_role",
        "action_approved",
        "action_executed",
    ]
    jsonschema.validate(done, SCHEMA)


def test_no_self_approval_for_human_requests(make_client: Make) -> None:
    c = make_client()
    add_user(c, "bob", "analyst")
    login(c, "ana")
    a = propose(c).json()
    assert approve(c, a).status_code == 403
    assert "approval_denied_self" in audit_names(c)
    login(c, "bob")
    assert approve(c, a).json()["status"] == "executed"


def test_self_approval_only_with_explicit_setting(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    assert approve(c, propose(c).json()).json()["status"] == "executed"


def test_agent_proposal_can_be_approved_by_the_human_who_triggered_it(make_client: Make) -> None:
    c = make_client(demo_agent_enabled=True)
    login(c, "root")
    a = c.post("/agents/demo/propose", json={"tool": "firewall.block_ip"}).json()
    assert (a["requested_by"], a["requester_kind"], a["status"]) == (
        "agent:demo",
        "agent",
        "pending",
    )
    assert approve(c, a).json()["status"] == "executed"
    assert c.post("/agents/demo/propose", json={"tool": "evidence.delete"}).status_code == 403
    assert "demo_proposal_triggered" in audit_names(c)


# ---------- l'humain approuve ce qu'il a vu ----------


def test_approval_must_target_the_hash_the_human_saw(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    other = "sha256:" + "f" * 64
    assert approve(c, a, seen=other).status_code == 409
    assert c.get(f"/actions/{a['id']}").json()["status"] == "pending"
    assert "approval_hash_mismatch" in audit_names(c)
    assert (
        c.post(f"/actions/{a['id']}/approve", json={"params_hash": "nimporte"}).status_code == 422
    )
    assert approve(c, a).json()["status"] == "executed"


def test_tampered_params_in_database_block_execution(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    db_update(c, {"params_json": json.dumps({"target": "10.0.0.1"})})
    assert approve(c, a).status_code == 409
    got = c.get(f"/actions/{a['id']}").json()
    assert got["status"] == "failed" and got["result"] == {"error": "integrity_violation"}
    assert "action_integrity_violation" in audit_names(c) and "action_executed" not in audit_names(
        c
    )


def test_policy_change_after_proposal_forces_resubmission(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    raw = yaml.safe_load(Path(POLICY).read_text())
    raw["tools"]["net.scan"] = {"level": "L3", "rollback": "firewall.unblock_ip"}
    c.app.state.policy = Policy(raw)  # type: ignore[attr-defined]
    assert approve(c, a).status_code == 409
    assert "approval_refused_policy_changed" in audit_names(c)


# ---------- une seule exécution, jamais après expiration ----------


def test_double_approval_executes_once(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    assert approve(c, a).status_code == 200
    assert approve(c, a).status_code == 409
    assert audit_names(c).count("action_executed") == 1


def test_expired_request_never_executes(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    db_update(c, {"expires_at": utcnow() - timedelta(minutes=1)})
    assert approve(c, a).status_code == 409
    assert c.get(f"/actions/{a['id']}").json()["status"] == "expired"
    assert "action_expired" in audit_names(c) and "action_executed" not in audit_names(c)
    assert "action.expired" in event_types(c)
    assert approve(c, a).status_code == 409


def test_listing_expires_stale_requests(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    propose(c)
    db_update(c, {"expires_at": utcnow() - timedelta(seconds=1)})
    assert [x["status"] for x in c.get("/actions").json()] == ["expired"]


def test_reject_is_final(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    assert c.post(f"/actions/{a['id']}/reject").json()["status"] == "rejected"
    assert approve(c, a).status_code == 409
    assert c.post(f"/actions/{a['id']}/reject").status_code == 409
    assert {"action_rejected"} <= set(audit_names(c)) and "action.rejected" in event_types(c)


def test_unknown_action_is_404(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    assert c.get("/actions/act_nope").status_code == 404


# ---------- dry-run ----------


def test_dry_run_simulates_without_consuming_the_request(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    dry = approve(c, a, dry_run=True).json()
    assert dry["dry_run_result"]["dry_run"] is True and dry["status"] == "pending"
    assert "action_dry_run" in audit_names(c) and "action_executed" not in audit_names(c)
    assert approve(c, a).json()["status"] == "executed"


def test_dry_run_requires_the_same_rights(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    a = propose(c, "firewall.block_ip", {"ip": "203.0.113.9"}).json()
    assert approve(c, a, dry_run=True).status_code == 403


# ---------- exécuteur en échec, validation, confidentialité ----------


def test_executor_failure_is_recorded(make_client: Make) -> None:
    from app.executor import Executor

    c = make_client(allow_self_approval=True)
    c.app.state.executor = Executor({})  # type: ignore[attr-defined]
    login(c, "ana")
    done = approve(c, propose(c).json()).json()
    assert done["status"] == "failed" and done["result"] == {"error": "no_handler"}
    assert "action.failed" in event_types(c) and "action_failed" in audit_names(c)


@pytest.mark.parametrize(
    "params",
    [
        {"k": "x" * 2000},
        {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}},
        {"l": list(range(200))},
        {"k" * 100: 1},
    ],
)
def test_oversized_or_deep_params_rejected(make_client: Make, params: dict[str, Any]) -> None:
    c = make_client()
    login(c, "ana")
    assert propose(c, params=params).status_code == 422


def test_invalid_tool_name_rejected(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    assert propose(c, "../etc/passwd").status_code == 422


def test_params_never_leak_into_audit_or_events(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c, params={"target": "SECRET-HOST-42"}).json()
    approve(c, a)
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert all("SECRET-HOST-42" not in x.detail for x in db.query(AuditLog))
    assert "SECRET-HOST-42" not in c.get("/events").text
    assert "SECRET-HOST-42" in json.dumps(
        c.get(f"/actions/{a['id']}").json()
    )  # visible à l'approbateur


def test_all_statuses_conform_to_schema(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a, b = propose(c).json(), propose(c, params={"target": "198.51.100.2"}).json()
    approve(c, a)
    c.post(f"/actions/{b['id']}/reject")
    propose(c, params={"target": "198.51.100.3"})
    seen = {x["status"] for x in c.get("/actions").json()}
    assert seen == {"executed", "rejected", "pending"}
    for x in c.get("/actions").json():
        jsonschema.validate(x, SCHEMA)


def test_action_events_validate_against_event_schema(make_client: Make) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    approve(c, propose(c).json())
    schema = json.loads(
        (Path(__file__).resolve().parents[2] / "schemas" / "event.v1.json").read_text()
    )
    evs = [e for e in c.get("/events?type=action").json()["events"]]
    assert {e["type"] for e in evs} == {"action.proposed", "action.approved", "action.executed"}
    for e in evs:
        jsonschema.validate(e, schema)


# ---------- course entre deux décisions (la prise en charge doit être atomique) ----------


def _interleave(c: TestClient, monkeypatch: pytest.MonkeyPatch, values: dict[str, Any]) -> None:
    """Simule une décision concurrente entre le contrôle de statut et la prise en charge."""
    from app import actions as svc

    real = svc._get

    def racy(db: Any, action_id: str) -> Any:
        a = real(db, action_id)
        with c.app.state.session_factory() as other:  # type: ignore[attr-defined]
            other.query(Action).filter(Action.id == action_id).update(values)
            other.commit()
        return a  # l'objet en mémoire croit encore que l'action est « pending »

    monkeypatch.setattr(svc, "_get", racy)


def test_claim_is_atomic_against_a_concurrent_rejection(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    _interleave(c, monkeypatch, {"status": "rejected"})
    assert approve(c, a).status_code == 409
    assert "action_executed" not in audit_names(c) and "action_approved" not in audit_names(c)


def test_claim_refuses_a_request_that_expires_during_approval(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = make_client(allow_self_approval=True)
    login(c, "ana")
    a = propose(c).json()
    _interleave(c, monkeypatch, {"expires_at": utcnow() - timedelta(seconds=1)})
    assert approve(c, a).status_code == 409
    assert "action_executed" not in audit_names(c)
