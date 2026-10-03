"""Garde-fou statique de la politique (R5) : défaut deny, L3 avec rollback, L4 sans outil exposé."""

from pathlib import Path

import yaml

policy = yaml.safe_load((Path(__file__).resolve().parents[2] / "policy" / "tools.yaml").read_text())


def test_default_is_deny() -> None:
    assert policy["default_level"] == "L4"


def test_l3_tools_declare_rollback() -> None:
    for name, t in policy["tools"].items():
        if t["level"] == "L3":
            assert t.get("rollback"), f"{name}: L3 sans rollback"


def test_all_tool_levels_defined() -> None:
    assert {t["level"] for t in policy["tools"].values()} <= set(policy["levels"])
