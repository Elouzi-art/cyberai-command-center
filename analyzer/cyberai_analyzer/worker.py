"""Boucle de travail : lit /inbox (lecture seule), écrit /outbox. Aucun réseau, aucun autre accès.

Protocole fichier :
  inbox/<id>/sample.bin   le fichier (posé par le backend)
  inbox/<id>/job.json     {"sample_id","sha256","size"} — écrit EN DERNIER (marqueur de fin)
  outbox/<id>.json        {"ok":true,"report":{...}} ou {"ok":false,"error":"<code>"}
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path
from typing import Any

from cyberai_analyzer.core import analyze
from cyberai_analyzer.isolation import run_with_limits

ID_RE = re.compile(r"^smp_[0-9a-f]{16}$")
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


def process_job(inbox: Path, outbox: Path, sample_id: str, max_bytes: int, timeout: float) -> None:
    def fail(code: str) -> None:
        _write_result(outbox, sample_id, {"ok": False, "error": code})

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
    _write_result(outbox, sample_id, run_with_limits(analyze, (data, sample_id), timeout))


def pending(inbox: Path, outbox: Path) -> list[str]:
    ids: list[tuple[float, str]] = []
    for entry in inbox.iterdir():
        if not ID_RE.match(entry.name) or entry.is_symlink() or not entry.is_dir():
            continue
        job = entry / "job.json"
        if job.is_file() and not job.is_symlink() and not (outbox / f"{entry.name}.json").exists():
            ids.append((job.stat().st_mtime, entry.name))
    return [i for _, i in sorted(ids)]


def run_once(inbox: Path, outbox: Path, max_bytes: int, timeout: float) -> int:
    done = 0
    for sample_id in pending(inbox, outbox):
        try:
            process_job(inbox, outbox, sample_id, max_bytes, timeout)
        except Exception:  # noqa: BLE001 - un échec ne doit jamais arrêter la boucle
            _write_result(outbox, sample_id, {"ok": False, "error": "worker_error"})
        done += 1
    return done


def serve_forever(
    inbox: Path, outbox: Path, max_bytes: int, timeout: float, poll: float = 2.0
) -> None:
    while True:
        run_once(inbox, outbox, max_bytes, timeout)
        time.sleep(poll)
