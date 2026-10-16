"""Boucle de travail : lit /inbox (lecture seule), écrit /outbox. Aucun réseau, aucun autre accès.

Protocole fichier :
  inbox/<id>/sample.bin   le fichier (posé par le backend)
  inbox/<id>/job.json     {"sample_id","sha256","size"} — écrit EN DERNIER (marqueur de fin)
  outbox/<id>.json        {"ok":true,"report":{...}} ou {"ok":false,"error":"<code>"}
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
import stat
import threading
import time
from pathlib import Path
from types import FrameType
from typing import Any

from cyberai_analyzer.core import analyze
from cyberai_analyzer.isolation import run_with_limits

log = logging.getLogger("cyberai_analyzer")
ID_RE = re.compile(r"^smp_[0-9a-f]{16}$")
OUTCOME_RE = re.compile(r"^[a-z_]{1,32}$")
MAX_JOB_BYTES = 4096
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _read_regular(path: Path, limit: int) -> bytes | None:
    """Lit un fichier ordinaire sans suivre de lien symbolique ; None si ce n'en est pas un."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
            return None
        with os.fdopen(fd, "rb", closefd=False) as fh:
            return fh.read(limit + 1)
    finally:
        os.close(fd)


def _write_result(outbox: Path, sample_id: str, payload: dict[str, Any]) -> None:
    tmp = outbox / f".{sample_id}.tmp"
    tmp.write_text(json.dumps(payload))
    os.replace(
        tmp, outbox / f"{sample_id}.json"
    )  # atomique : le backend ne voit jamais un demi-fichier


def process_job(inbox: Path, outbox: Path, sample_id: str, max_bytes: int, timeout: float) -> str:
    """Traite un échantillon et renvoie un code court (\"ok\" ou le code d'erreur)."""

    def fail(code: str) -> str:
        _write_result(outbox, sample_id, {"ok": False, "error": code})
        return code

    raw_job = _read_regular(inbox / sample_id / "job.json", MAX_JOB_BYTES)
    try:
        job = json.loads(raw_job) if raw_job is not None else None
    except ValueError:
        job = None
    if (
        not isinstance(job, dict)
        or job.get("sample_id") != sample_id
        or not HEX64.match(str(job.get("sha256", "")))
        or not isinstance(job.get("size"), int)
    ):
        return fail("bad_job")
    if job["size"] > max_bytes:
        return fail("too_large")
    data = _read_regular(inbox / sample_id / "sample.bin", max_bytes)
    if data is None:
        return fail("unreadable_sample")
    if len(data) != job["size"]:
        return fail("size_mismatch")
    if hashlib.sha256(data).hexdigest() != job["sha256"]:
        return fail("hash_mismatch")
    result = run_with_limits(analyze, (data, sample_id), timeout)
    _write_result(outbox, sample_id, result)
    outcome = "ok" if result.get("ok") is True else str(result.get("error", "unknown"))
    # Ce code vient d'un processus qui a lu un fichier hostile : journalisé seulement s'il est sûr.
    return outcome if OUTCOME_RE.match(outcome) else "invalid_outcome"


def pending(inbox: Path, outbox: Path) -> list[str]:
    ids: list[tuple[float, str]] = []
    for entry in inbox.iterdir():
        if not ID_RE.match(entry.name) or entry.is_symlink() or not entry.is_dir():
            continue
        job = entry / "job.json"
        if job.is_file() and not job.is_symlink() and not (outbox / f"{entry.name}.json").exists():
            ids.append((job.stat().st_mtime, entry.name))
    return [i for _, i in sorted(ids)]


def run_once(
    inbox: Path, outbox: Path, max_bytes: int, timeout: float, stop: threading.Event | None = None
) -> int:
    done = 0
    for sample_id in pending(inbox, outbox):
        if stop is not None and stop.is_set():
            break  # arrêt demandé : les travaux restants seront repris au prochain démarrage
        start = time.monotonic()
        try:
            outcome = process_job(inbox, outbox, sample_id, max_bytes, timeout)
        except Exception:  # noqa: BLE001 - un échec ne doit jamais arrêter la boucle
            _write_result(outbox, sample_id, {"ok": False, "error": "worker_error"})
            outcome = "worker_error"
        # Journal : identifiant et code seulement, jamais de contenu ni de nom de fichier.
        log.info("job %s -> %s (%d ms)", sample_id, outcome, (time.monotonic() - start) * 1000)
        done += 1
    return done


def serve_forever(
    inbox: Path,
    outbox: Path,
    max_bytes: int,
    timeout: float,
    poll: float = 2.0,
    stop: threading.Event | None = None,
) -> None:
    """Boucle principale. SIGTERM/SIGINT : termine le travail en cours puis s'arrête proprement.

    Sans gestionnaire, le processus principal d'un conteneur ignore SIGTERM et Docker attend 10 s
    avant de le tuer. Un travail interrompu n'a pas de résultat : il est repris au redémarrage.
    """
    stop = stop or threading.Event()

    def _on_signal(signum: int, _frame: FrameType | None) -> None:
        log.info("signal %d reçu : arrêt après le travail en cours", signum)
        stop.set()

    try:
        signal.signal(signal.SIGTERM, _on_signal)
        signal.signal(signal.SIGINT, _on_signal)
    except ValueError:  # pas le thread principal (tests) : l'appelant gère `stop`
        pass
    log.info("analyseur démarré (délai %.0f s, taille max %d octets)", timeout, max_bytes)
    while not stop.is_set():
        run_once(inbox, outbox, max_bytes, timeout, stop)
        stop.wait(poll)  # interrompu immédiatement par un signal
    log.info("analyseur arrêté proprement")
