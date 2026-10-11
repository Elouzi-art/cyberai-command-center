"""R5 : politique en échec fermé, non affaiblissable ; le niveau ne vient pas de la requête."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import Settings
from app.executor import ExecutionRequest, Executor, ExecutorRefused
from app.main import create_app
from app.policy import Policy, PolicyError
from tests.conftest import POLICY


def raw() -> dict[str, Any]:
    return yaml.safe_load(Path(POLICY).read_text())  # type: ignore[no-any-return]


def test_unknown_tool_is_forbidden_by_default() -> None:
    d = Policy.load(POLICY).classify("rm.everything")
    assert (d.level, d.approval, d.known, d.required_role) == ("L4", "forbidden", False, None)


@pytest.mark.parametrize(
    ("tool", "level", "role"),
    [
        ("file.parse_pe", "L0", None),
        ("intel.lookup_hash", "L1", None),
        ("net.scan", "L2", "analyst"),
        ("firewall.block_ip", "L3", "admin"),
        ("evidence.delete", "L4", None),
    ],
)
def test_real_policy_levels_and_roles(tool: str, level: str, role: str | None) -> None:
    d = Policy.load(POLICY).classify(tool)
    assert d.level == level and d.required_role == role


def test_l3_has_rollback_and_short_ttl() -> None:
    d = Policy.load(POLICY).classify("firewall.block_ip")
    assert d.rollback == "firewall.unblock_ip" and d.max_ttl_minutes == 60


def test_every_rollback_is_a_declared_tool() -> None:
    pol = Policy.load(POLICY)
    for name, t in pol.tools().items():
        if t.get("rollback"):
            assert pol.classify(t["rollback"]).known, f"{name}: rollback non déclaré"


def test_default_level_must_stay_l4() -> None:
    r = raw()
    r["default_level"] = "L0"
    with pytest.raises(PolicyError):
        Policy(r)


@pytest.mark.parametrize(
    ("level", "weak"),
    [("L2", "none"), ("L3", "analyst"), ("L3", "none"), ("L4", "senior"), ("L4", "none")],
)
def test_policy_cannot_be_weakened(level: str, weak: str) -> None:
    r = raw()
    r["levels"][level]["approval"] = weak
    with pytest.raises(PolicyError):
        Policy(r)


def test_l3_tool_requires_declared_rollback() -> None:
    r = raw()
    del r["tools"]["firewall.block_ip"]["rollback"]
    with pytest.raises(PolicyError):
        Policy(r)
    r = raw()
    r["tools"]["firewall.block_ip"]["rollback"] = "ghost.tool"
    with pytest.raises(PolicyError):
        Policy(r)


def test_missing_and_invalid_files_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        Policy.load(str(tmp_path / "absent.yaml"))
    bad = tmp_path / "bad.yaml"
    bad.write_text("levels: [unclosed")
    with pytest.raises(PolicyError):
        Policy.load(str(bad))


def test_app_refuses_to_start_without_policy(tmp_path: Path) -> None:
    app = create_app(Settings(database_url="sqlite://", policy_path=str(tmp_path / "x.yaml")), {})
    with pytest.raises(PolicyError), TestClient(app):
        pass


def _req(level: str, tool: str = "net.scan") -> ExecutionRequest:
    return ExecutionRequest("act_1", tool, {"k": [1]}, level, dry_run=False)


def test_executor_refuses_l4_even_if_called_directly() -> None:
    with pytest.raises(ExecutorRefused):
        Executor.stub_for(["evidence.delete"]).run(_req("L4", "evidence.delete"))


def test_executor_unknown_tool_and_handler_errors_leak_nothing() -> None:
    assert Executor({}).run(_req("L2")).output == {"error": "no_handler"}

    def boom(_r: ExecutionRequest) -> dict[str, Any]:
        raise RuntimeError("mot de passe=hunter2")

    res = Executor({"net.scan": boom}).run(_req("L2"))
    assert not res.ok and res.output == {"error": "RuntimeError"}


def test_executor_gets_a_copy_of_params() -> None:
    seen: list[Any] = []

    def mutate(r: ExecutionRequest) -> dict[str, Any]:
        r.params["k"].append(99)
        seen.append(r.params)
        return {}

    original = _req("L2")
    Executor({"net.scan": mutate}).run(original)
    assert original.params == {"k": [1]}
