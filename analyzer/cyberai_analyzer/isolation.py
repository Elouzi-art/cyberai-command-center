"""Exécute l'analyse dans un processus enfant jetable, avec délai et mémoire bornés.

Un fichier hostile peut faire boucler ou planter un parseur : seul l'enfant en pâtit.
Résultat renvoyé en JSON (jamais en pickle) : un enfant compromis n'exécute rien dans le parent.
"""

from __future__ import annotations

import json
import multiprocessing as mp
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

try:
    import resource
except ImportError:  # Windows (développement) : pas de limite mémoire par processus
    resource = None  # type: ignore[assignment]

MAX_RESULT_BYTES = 262_144
MEMORY_LIMIT = 768 * 1024 * 1024


def _child(conn: Connection, target: Callable[..., dict[str, Any]], args: tuple[Any, ...]) -> None:
    try:
        if resource is not None:
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        payload: dict[str, Any] = {"ok": True, "report": target(*args)}
    except MemoryError:
        payload = {"ok": False, "error": "out_of_memory"}
    except Exception:  # noqa: BLE001 - le détail n'est jamais propagé
        payload = {"ok": False, "error": "analysis_failed"}
    conn.send_bytes(json.dumps(payload).encode())
    conn.close()


def run_with_limits(
    target: Callable[..., dict[str, Any]], args: tuple[Any, ...], timeout: float
) -> dict[str, Any]:
    method = "fork" if "fork" in mp.get_all_start_methods() else "spawn"
    ctx: Any = mp.get_context(method)
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, target, args), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(timeout):
            proc.kill()
            return {"ok": False, "error": "timeout"}
        try:
            raw = parent.recv_bytes(MAX_RESULT_BYTES)
        except (EOFError, OSError):
            return {"ok": False, "error": "crashed"}
        try:
            out = json.loads(raw)
        except ValueError:
            return {"ok": False, "error": "crashed"}
        return out if isinstance(out, dict) else {"ok": False, "error": "crashed"}
    finally:
        proc.join(1)
        if proc.is_alive():
            proc.kill()
            proc.join(1)
        parent.close()
