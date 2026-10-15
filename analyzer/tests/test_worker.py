"""Protocole fichier : le worker ne fait confiance ni aux liens, ni aux tailles, ni aux hashs."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from cyberai_analyzer.worker import ID_RE, pending, run_once
from tests.pe_builder import CODE, Sec, make_pe

SID = "smp_0123456789abcdef"
LIMIT = 1_000_000


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    inbox, outbox = tmp_path / "in", tmp_path / "out"
    inbox.mkdir()
    outbox.mkdir()
    return inbox, outbox


def put(inbox: Path, data: bytes, sid: str = SID, **job_over: object) -> None:
    d = inbox / sid
    d.mkdir()
    (d / "sample.bin").write_bytes(data)
    job = {
        "sample_id": sid,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        **job_over,
    }
    (d / "job.json").write_text(json.dumps(job))


def result(outbox: Path, sid: str = SID) -> dict[str, object]:
    return json.loads((outbox / f"{sid}.json").read_text())  # type: ignore[no-any-return]


def test_happy_path_produces_a_report(dirs: tuple[Path, Path]) -> None:
    inbox, outbox = dirs
    put(inbox, make_pe([Sec(b".text", b"\x90" * 600, CODE)]))
    assert run_once(inbox, outbox, LIMIT, 20) == 1
    res = result(outbox)
    assert res["ok"] is True and res["report"]["sample"]["file_type"] == "PE"  # type: ignore[index]
    assert not list(outbox.glob(".*.tmp"))  # écriture atomique : pas de reste


def test_job_is_processed_once(dirs: tuple[Path, Path]) -> None:
    inbox, outbox = dirs
    put(inbox, b"hello")
    assert run_once(inbox, outbox, LIMIT, 20) == 1
    assert run_once(inbox, outbox, LIMIT, 20) == 0


def test_tampered_sample_is_refused(dirs: tuple[Path, Path]) -> None:
    inbox, outbox = dirs
    put(inbox, b"original")
    (inbox / SID / "sample.bin").write_bytes(b"swapped!")  # même taille, autre contenu
    run_once(inbox, outbox, LIMIT, 20)
    assert result(outbox) == {"ok": False, "error": "hash_mismatch"}


def test_size_mismatch_and_too_large(dirs: tuple[Path, Path]) -> None:
    inbox, outbox = dirs
    put(inbox, b"abcdef", size=3)
    put(inbox, b"x" * 50, sid="smp_aaaaaaaaaaaaaaaa")
    run_once(inbox, outbox, 10, 20)
    assert result(outbox)["error"] == "size_mismatch"
    assert result(outbox, "smp_aaaaaaaaaaaaaaaa")["error"] == "too_large"


def test_symlinked_sample_is_never_followed(dirs: tuple[Path, Path], tmp_path: Path) -> None:
    inbox, outbox = dirs
    secret = tmp_path / "secret.txt"
    secret.write_text("contenu hors quarantaine")
    put(inbox, b"x")
    (inbox / SID / "sample.bin").unlink()
    os.symlink(secret, inbox / SID / "sample.bin")
    run_once(inbox, outbox, LIMIT, 20)
    assert result(outbox) == {"ok": False, "error": "unreadable_sample"}
    assert "secret" not in (outbox / f"{SID}.json").read_text()


def test_symlinked_job_or_directory_is_ignored(dirs: tuple[Path, Path], tmp_path: Path) -> None:
    inbox, outbox = dirs
    real = tmp_path / "elsewhere"
    real.mkdir()
    (real / "job.json").write_text("{}")
    os.symlink(real, inbox / SID)
    assert pending(inbox, outbox) == []


@pytest.mark.parametrize(
    "name", ["../etc", "smp_short", "SMP_0123456789ABCDEF", "x" * 40, "smp_0123456789abcdeg"]
)
def test_invalid_directory_names_are_ignored(dirs: tuple[Path, Path], name: str) -> None:
    inbox, outbox = dirs
    (inbox / name.replace("/", "_")).mkdir()
    ((inbox / name.replace("/", "_")) / "job.json").write_text("{}")
    assert pending(inbox, outbox) == [] and not ID_RE.match(name)


def test_garbage_job_gives_error_not_crash(dirs: tuple[Path, Path]) -> None:
    inbox, outbox = dirs
    (inbox / SID).mkdir()
    (inbox / SID / "job.json").write_text("{not json")
    run_once(inbox, outbox, LIMIT, 20)
    assert result(outbox) == {"ok": False, "error": "bad_job"}


def test_job_for_another_sample_id_is_rejected(dirs: tuple[Path, Path]) -> None:
    inbox, outbox = dirs
    put(inbox, b"x", sample_id="smp_ffffffffffffffff")
    run_once(inbox, outbox, LIMIT, 20)
    assert result(outbox)["error"] == "bad_job"


def test_job_without_marker_is_not_picked_up(dirs: tuple[Path, Path]) -> None:
    inbox, outbox = dirs
    (inbox / SID).mkdir()
    (inbox / SID / "sample.bin").write_bytes(b"upload en cours")
    assert pending(inbox, outbox) == []


def test_unexpected_exception_does_not_stop_the_loop(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    inbox, outbox = dirs
    put(inbox, b"x")
    put(inbox, b"y", sid="smp_bbbbbbbbbbbbbbbb")

    import cyberai_analyzer.worker as w

    real = w.process_job

    def flaky(i: Path, o: Path, sid: str, m: int, t: float) -> None:
        if sid == SID:
            raise OSError("disque plein")
        real(i, o, sid, m, t)

    monkeypatch.setattr(w, "process_job", flaky)
    assert run_once(inbox, outbox, LIMIT, 20) == 2
    assert (
        result(outbox)["error"] == "worker_error" and result(outbox, "smp_bbbbbbbbbbbbbbbb")["ok"]
    )
