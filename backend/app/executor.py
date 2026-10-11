"""Exécuteur d'actions (Sprint 4 : FACTICE, aucun effet réel).

Interface volontairement étroite pour pouvoir le déplacer plus tard dans un processus séparé avec
des identifiants éphémères : il ne reçoit qu'une requête immuable, sans accès à la base ni aux
sessions. Défense en profondeur : il refuse L4 même si l'appelant se trompe.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ExecutorRefused(Exception):
    pass


@dataclass(frozen=True)
class ExecutionRequest:
    action_id: str
    tool: str
    params: dict[str, Any]
    level: str
    dry_run: bool


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    output: dict[str, Any]


Handler = Callable[[ExecutionRequest], dict[str, Any]]


def _stub(req: ExecutionRequest) -> dict[str, Any]:
    return {
        "simulated": True,
        "dry_run": req.dry_run,
        "tool": req.tool,
        "effect": "aucun effet réel (exécuteur factice)",
    }


class Executor:
    def __init__(self, handlers: dict[str, Handler]) -> None:
        self._handlers = handlers

    @classmethod
    def stub_for(cls, tools: list[str]) -> Executor:
        return cls({t: _stub for t in tools})

    def run(self, req: ExecutionRequest) -> ExecutionResult:
        if req.level == "L4":
            raise ExecutorRefused("niveau L4 : jamais exécuté")
        handler = self._handlers.get(req.tool)
        if handler is None:
            return ExecutionResult(False, {"error": "no_handler"})
        try:
            out = handler(
                ExecutionRequest(
                    req.action_id, req.tool, copy.deepcopy(req.params), req.level, req.dry_run
                )
            )
        except Exception as exc:  # noqa: BLE001 - le détail n'est jamais exposé
            return ExecutionResult(False, {"error": type(exc).__name__})
        return ExecutionResult(True, out)
