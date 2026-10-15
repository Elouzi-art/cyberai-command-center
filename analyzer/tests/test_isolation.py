"""Un fichier hostile peut boucler, planter ou mentir : seul l'enfant jetable en pâtit."""

import os
import time
from typing import Any

from cyberai_analyzer.isolation import run_with_limits


def ok(x: int) -> dict[str, Any]:
    return {"value": x}


def hang() -> dict[str, Any]:
    time.sleep(60)
    return {}


def hang_and_record(pid_file: str) -> dict[str, Any]:
    with open(pid_file, "w") as fh:
        fh.write(str(os.getpid()))
    time.sleep(60)
    return {}


def crash() -> dict[str, Any]:
    os._exit(139)  # simule un segfault du parseur


def boom() -> dict[str, Any]:
    raise RuntimeError("secret interne : /etc/passwd")


def oom() -> dict[str, Any]:
    raise MemoryError


def huge() -> dict[str, Any]:
    return {"blob": "A" * 400_000}


def test_normal_result_comes_back_as_json() -> None:
    assert run_with_limits(ok, (7,), 5) == {"ok": True, "report": {"value": 7}}


def test_infinite_loop_is_killed_at_the_deadline() -> None:
    start = time.monotonic()
    assert run_with_limits(hang, (), 0.5) == {"ok": False, "error": "timeout"}
    assert time.monotonic() - start < 5


def test_child_crash_is_contained() -> None:
    assert run_with_limits(crash, (), 5) == {"ok": False, "error": "crashed"}


def test_exception_detail_never_leaks() -> None:
    out = run_with_limits(boom, (), 5)
    assert out == {"ok": False, "error": "analysis_failed"} and "passwd" not in str(out)


def test_memory_error_is_reported() -> None:
    assert run_with_limits(oom, (), 5) == {"ok": False, "error": "out_of_memory"}


def test_oversized_result_is_refused() -> None:
    assert run_with_limits(huge, (), 5) == {"ok": False, "error": "crashed"}


def test_timed_out_child_process_is_really_dead(tmp_path: Any) -> None:
    pid_file = tmp_path / "pid"
    assert run_with_limits(hang_and_record, (str(pid_file),), 0.5)["error"] == "timeout"
    pid = int(pid_file.read_text())
    time.sleep(0.2)
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    assert not alive, "le processus enfant tourne encore après le délai"
