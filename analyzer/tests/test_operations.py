"""Exploitation : journal sans contenu, code hostile neutralisé, arrêt propre sur signal."""

import hashlib
import json
import logging
import os
import select
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import cyberai_analyzer.worker as w
from cyberai_analyzer.worker import pending, run_once
from tests.pe_builder import CODE, Sec, make_pe

LIMIT = 1_000_000


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    return inbox, outbox


def put(inbox: Path, sid: str, data: bytes) -> None:
    d = inbox / sid
    d.mkdir()
    (d / "sample.bin").write_bytes(data)
    (d / "job.json").write_text(
        json.dumps(
            {"sample_id": sid, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        )
    )


def test_log_line_has_id_and_outcome_only(
    dirs: tuple[Path, Path], caplog: pytest.LogCaptureFixture
) -> None:
    inbox, outbox = dirs
    secret = b"CONTENU-CONFIDENTIEL-DU-CLIENT"
    put(inbox, "smp_0123456789abcdef", make_pe([Sec(b".text", secret * 20, CODE)]))
    with caplog.at_level(logging.INFO, logger="cyberai_analyzer"):
        run_once(inbox, outbox, LIMIT, 20)
    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 1 and lines[0].startswith("job smp_0123456789abcdef -> ok (")
    assert "CONFIDENTIEL" not in "".join(lines) and hashlib.sha256(
        secret
    ).hexdigest() not in "".join(lines)


def test_failure_outcome_is_logged_as_a_code(
    dirs: tuple[Path, Path], caplog: pytest.LogCaptureFixture
) -> None:
    inbox, outbox = dirs
    put(inbox, "smp_0123456789abcdef", b"x" * 50)
    with caplog.at_level(logging.INFO, logger="cyberai_analyzer"):
        run_once(inbox, outbox, 10, 20)  # trop gros
    assert "-> too_large" in caplog.text


@pytest.mark.parametrize("evil", ["bon\nFAUX LOG: admin connecté", "x" * 80, "A-B", "", 5, None])
def test_hostile_child_outcome_cannot_inject_into_the_log(
    dirs: tuple[Path, Path],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    evil: Any,
) -> None:
    inbox, outbox = dirs
    put(inbox, "smp_0123456789abcdef", b"hello")
    monkeypatch.setattr(w, "run_with_limits", lambda *_a, **_k: {"ok": False, "error": evil})
    with caplog.at_level(logging.INFO, logger="cyberai_analyzer"):
        run_once(inbox, outbox, LIMIT, 20)
    assert "-> invalid_outcome" in caplog.text and "FAUX LOG" not in caplog.text
    assert "\n" not in caplog.records[0].getMessage()


def test_stop_request_leaves_remaining_jobs_for_the_next_start(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    inbox, outbox = dirs
    put(inbox, "smp_aaaaaaaaaaaaaaaa", b"un")
    time.sleep(0.02)
    put(inbox, "smp_bbbbbbbbbbbbbbbb", b"deux")
    stop = threading.Event()
    real = w.process_job

    def first_then_stop(*args: Any) -> str:
        out = real(*args)
        stop.set()  # arrêt demandé pendant le premier travail
        return out

    monkeypatch.setattr(w, "process_job", first_then_stop)
    assert run_once(inbox, outbox, LIMIT, 20, stop) == 1
    assert pending(inbox, outbox) == ["smp_bbbbbbbbbbbbbbbb"]  # sera repris, jamais perdu
    monkeypatch.setattr(w, "process_job", real)
    assert run_once(inbox, outbox, LIMIT, 20) == 1


def test_sigterm_stops_a_real_worker_quickly_and_cleanly(tmp_path: Path) -> None:
    (tmp_path / "in").mkdir()
    (tmp_path / "out").mkdir()
    code = (
        "import logging, sys\n"
        "from pathlib import Path\n"
        "from cyberai_analyzer.worker import serve_forever\n"
        "logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(message)s')\n"
        f"inbox, outbox = Path({str(tmp_path / 'in')!r}), Path({str(tmp_path / 'out')!r})\n"
        "serve_forever(inbox, outbox, 1000, 5, poll=60)\n"
    )
    proc = subprocess.Popen(  # noqa: S603 - commande fixe de test
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, cwd=os.getcwd()
    )
    assert proc.stdout is not None
    ready, _, _ = select.select([proc.stdout], [], [], 10)
    assert ready and "analyseur démarré" in proc.stdout.readline()
    time.sleep(0.7)  # laisse le worker atteindre son attente (poll=60 s) AVANT le signal
    start = time.monotonic()
    proc.send_signal(signal.SIGTERM)
    try:
        rc = proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
    rest = proc.stdout.read()
    assert rc == 0, f"code de sortie {rc}"  # sans gestionnaire : -15
    assert time.monotonic() - start < 3  # avec poll=60 s : l'attente est bien interrompue
    assert "arrêté proprement" in rest
