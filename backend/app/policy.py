"""Moteur de politique (R5) : le niveau de risque vient de ce fichier, pas du LLM ni de la requête.

Échec fermé : une politique invalide ou affaiblie bloque le démarrage. Outil inconnu => L4.
Sprint 4 : le niveau dépend du seul outil (pas encore des paramètres).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LEVELS = ("L0", "L1", "L2", "L3", "L4")
_STRENGTH = {"none": 0, "analyst": 1, "senior": 2, "forbidden": 3}
_FLOOR = {"L0": "none", "L1": "none", "L2": "analyst", "L3": "senior", "L4": "forbidden"}
_ROLE = {"analyst": "analyst", "senior": "admin"}


class PolicyError(Exception):
    pass


@dataclass(frozen=True)
class Decision:
    tool: str
    level: str
    approval: str  # none | analyst | senior | forbidden
    known: bool
    rollback: str | None = None
    max_ttl_minutes: int | None = None

    @property
    def required_role(self) -> str | None:
        return _ROLE.get(self.approval)


class Policy:
    def __init__(self, raw: dict[str, Any]) -> None:
        try:
            self._levels: dict[str, dict[str, Any]] = raw["levels"]
            self._tools: dict[str, dict[str, Any]] = raw["tools"]
            default = raw["default_level"]
        except (KeyError, TypeError) as exc:
            raise PolicyError("politique incomplète (levels, tools, default_level)") from exc
        if default != "L4":
            raise PolicyError("default_level doit être L4 (outil inconnu = interdit)")
        for lvl in LEVELS:
            approval = (self._levels.get(lvl) or {}).get("approval")
            if approval not in _STRENGTH:
                raise PolicyError(f"{lvl}: approval invalide")
            if _STRENGTH[approval] < _STRENGTH[_FLOOR[lvl]]:
                raise PolicyError(
                    f"{lvl}: la validation ne peut pas être plus faible que '{_FLOOR[lvl]}'"
                )
        for name, t in self._tools.items():
            if t.get("level") not in LEVELS:
                raise PolicyError(f"{name}: niveau inconnu")
            if t["level"] == "L3" and not t.get("rollback"):
                raise PolicyError(f"{name}: un outil L3 exige un rollback")
            rb = t.get("rollback")
            if rb and rb not in self._tools:
                raise PolicyError(f"{name}: rollback '{rb}' non déclaré dans la politique")

    @classmethod
    def load(cls, path: str) -> Policy:
        p = Path(path)
        if not p.exists():
            raise PolicyError(f"fichier de politique introuvable : {path}")
        try:
            raw = yaml.safe_load(p.read_text())
        except yaml.YAMLError as exc:
            raise PolicyError("YAML de politique invalide") from exc
        return cls(raw if isinstance(raw, dict) else {})

    def tools(self) -> dict[str, dict[str, Any]]:
        return self._tools

    def classify(self, tool: str) -> Decision:
        t = self._tools.get(tool)
        if t is None:
            return Decision(tool, "L4", "forbidden", known=False)
        lvl = t["level"]
        cfg = self._levels[lvl]
        return Decision(
            tool,
            lvl,
            cfg["approval"],
            known=True,
            rollback=t.get("rollback"),
            max_ttl_minutes=cfg.get("max_ttl_minutes"),
        )
