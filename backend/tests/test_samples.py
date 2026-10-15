"""Quarantaine et agent Malware : dépôt sûr, résultat de l'analyseur traité comme hostile."""

import copy
import json
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from fastapi.testclient import TestClient

from app.malware_report import Report
from app.models import AuditLog, Sample
from app.quarantine import safe_name
from tests.conftest import login

ROOT = Path(__file__).resolve().parents[2] / "schemas"
GOLDEN = json.loads((ROOT / "examples" / "analysis_report.malware.golden.json").read_text())
REPORT_SCHEMA = json.loads((ROOT / "analysis_report.v1.json").read_text())
EVENT_SCHEMA = json.loads((ROOT / "event.v1.json").read_text())
Make = Callable[..., TestClient]
DATA = b"MZ" + b"\x90" * 300
OCTET = {"Content-Type": "application/octet-stream"}


def dirs(c: TestClient) -> tuple[Path, Path]:
    s = c.app.state.settings  # type: ignore[attr-defined]
    return Path(s.inbox_dir), Path(s.outbox_dir)


def upload(c: TestClient, data: bytes = DATA, name: str = "evil.exe") -> Any:
    return c.post(f"/samples?filename={name}", content=data, headers=OCTET)


def report_for(sample: dict[str, Any]) -> dict[str, Any]:
    rep = copy.deepcopy(GOLDEN)
    rep["sample"]["sha256"], rep["sample"]["size"] = sample["sha256"], sample["size"]
    return rep  # type: ignore[no-any-return]


def deliver(c: TestClient, sample: dict[str, Any], payload: Any) -> None:
    (dirs(c)[1] / f"{sample['id']}.json").write_text(json.dumps(payload))


def ok(
    sample: dict[str, Any], mutate: Callable[[dict[str, Any]], None] | None = None
) -> dict[str, Any]:
    rep = report_for(sample)
    if mutate:
        mutate(rep)
    return {"ok": True, "report": rep}


def audit_names(c: TestClient) -> list[str]:
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        return [a.action for a in db.query(AuditLog).order_by(AuditLog.id)]


# ---------- accès ----------


def test_access_control(make_client: Make) -> None:
    c = make_client()
    assert upload(c).status_code == 401 and c.get("/samples").status_code == 401
    login(c, "vic")
    assert upload(c).status_code == 403 and c.get("/samples").status_code == 403
    login(c, "ana")
    s = upload(c).json()
    assert c.get("/samples").status_code == 200
    assert c.delete(f"/samples/{s['id']}").status_code == 403  # suppression : admin seulement


def test_foreign_origin_rejected(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    evil = {**OCTET, "Origin": "https://evil.example"}
    assert c.post("/samples", content=DATA, headers=evil).status_code == 403
    s = upload(c).json()
    login(c, "root")
    assert (
        c.delete(f"/samples/{s['id']}", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert c.get(f"/samples/{s['id']}").status_code == 200


# ---------- dépôt ----------


def test_upload_is_stored_safely_and_queued(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    r = upload(c, name="../../etc/passwd")
    s = r.json()
    assert r.status_code == 201 and s["status"] == "queued" and s["name"] == "passwd"
    inbox = dirs(c)[0] / s["id"]
    assert (inbox / "sample.bin").read_bytes() == DATA
    mode = stat.S_IMODE(os.stat(inbox / "sample.bin").st_mode)
    assert mode == 0o600 and not mode & 0o111  # jamais exécutable, illisible par les autres
    job = json.loads((inbox / "job.json").read_text())
    import hashlib

    assert job == {
        "sample_id": s["id"],
        "sha256": hashlib.sha256(DATA).hexdigest(),
        "size": len(DATA),
    }
    assert s["sha256"] == job["sha256"]
    assert not list(dirs(c)[0].glob("*passwd*")) and not (dirs(c)[0] / "etc").exists()
    assert "sample_uploaded" in audit_names(c)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../evil.exe", "evil.exe"),
        ("C:\\Users\\x\\a b.exe", "a b.exe"),
        ("a$%b.exe", "a__b.exe"),
        ("", "sample.bin"),
        ("...", "sample.bin"),
        ("é\n.exe", "__.exe"),
        ("x" * 500, "x" * 128),
    ],
)
def test_safe_name(raw: str, expected: str) -> None:
    assert safe_name(raw) == expected


def test_oversized_body_is_refused_and_leaves_nothing(make_client: Make) -> None:
    c = make_client(max_upload_bytes=1000)
    login(c, "ana")
    assert upload(c, b"A" * 5000).status_code == 413  # Content-Length annoncé
    chunks = (b"A" * 400 for _ in range(10))  # flux sans Content-Length
    assert c.post("/samples", content=chunks, headers=OCTET).status_code == 413
    assert list(dirs(c)[0].iterdir()) == []
    assert c.get("/samples").json() == []


def test_empty_upload_refused_and_cleaned(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    assert upload(c, b"").status_code == 400
    assert list(dirs(c)[0].iterdir()) == []


def test_analysis_queue_is_capped(make_client: Make) -> None:
    c = make_client(max_queued_samples=2)
    login(c, "ana")
    assert upload(c).status_code == 201 and upload(c).status_code == 201
    assert upload(c).status_code == 429
    assert len(list(dirs(c)[0].iterdir())) == 2


def test_job_marker_is_written_last(make_client: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    c = make_client()
    login(c, "ana")
    from app import quarantine

    seen: list[bool] = []
    real = quarantine.commit_job

    def spy(inbox: Path, sid: str, sha: str, size: int) -> None:
        seen.append(
            (inbox / sid / "sample.bin").exists() and not (inbox / sid / "job.json").exists()
        )
        real(inbox, sid, sha, size)

    monkeypatch.setattr(quarantine, "commit_job", spy)
    upload(c)
    assert seen == [True]


# ---------- intégration du résultat ----------


def test_valid_result_is_ingested_once(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    assert c.get(f"/samples/{s['id']}").json()["status"] == "queued"  # pas encore de résultat
    deliver(c, s, ok(s))
    got = c.get(f"/samples/{s['id']}").json()
    assert got["status"] == "analyzed" and got["report"]["needs_human_review"] is True
    assert got["file_type"] == "PE" and got["rule_hits"] == 4
    assert {i["provenance"] for i in got["report"]["items"]} == {"tool_data"}
    summary = c.get("/samples").json()[0]
    assert summary["rule_hits"] == 4 and "report" not in summary
    assert {"sample_analyzed"} <= set(audit_names(c))
    # un résultat ultérieur ne remplace jamais ce qui a été intégré
    deliver(c, s, {"ok": False, "error": "timeout"})
    assert c.get(f"/samples/{s['id']}").json()["status"] == "analyzed"


def test_golden_report_conforms_to_schema_and_model() -> None:
    jsonschema.validate(GOLDEN, REPORT_SCHEMA)
    assert Report.model_validate(GOLDEN).sample.file_type == "PE"


def test_ingestion_events_conform_to_event_schema(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    deliver(c, s, ok(s))
    c.get(f"/samples/{s['id']}")
    evs = c.get("/events?type=sample").json()["events"]
    assert [e["type"] for e in evs] == ["sample.uploaded", "sample.analyzed"]
    for e in evs:
        jsonschema.validate(e, EVENT_SCHEMA)
        assert "evil" not in json.dumps(e)  # pas de nom de fichier dans les événements


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("caractère de contrôle", lambda r: r["items"][0].update(statement="ok\x1b[31m")),
        ("retour à la ligne", lambda r: r["items"][0].update(statement="ligne1\nligne2")),
        ("inversion bidi", lambda r: r["items"][0].update(statement="abc\u202edef")),
        ("espace insécable", lambda r: r["items"][0].update(statement="a\u00a0b")),
        ("nom de section non ASCII", lambda r: r["pe"]["sections"][0].update(name="séc")),
        ("DLL avec saut de ligne", lambda r: r["pe"]["imports_dlls"].append("a\nb.dll")),
        ("observation d'IA forgée", lambda r: r["items"][0].update(provenance="ai_observation")),
        ("hypothèse forgée", lambda r: r["items"][0].update(provenance="hypothesis")),
        ("champ en trop", lambda r: r.update(risk="critique")),
        ("revue humaine désactivée", lambda r: r.update(needs_human_review=False)),
        ("verdict dans un élément", lambda r: r["items"][0].update(verdict="malveillant")),
        ("type de fichier inventé", lambda r: r["sample"].update(file_type="Trusted")),
        ("trop d'éléments", lambda r: r.update(items=r["items"] * 60)),
        ("énoncé trop long", lambda r: r["items"][0].update(statement="x" * 301)),
        ("entropie hors bornes", lambda r: r["sample"].update(entropy=9.5)),
        ("agent usurpé", lambda r: r.update(agent="soc")),
        (
            "taille exacte mais en chaîne",
            lambda r: r["sample"].update(size=str(r["sample"]["size"])),
        ),
        ("entropie en chaîne", lambda r: r["sample"].update(entropy="3.5")),
    ],
)
def test_forged_or_malformed_results_are_rejected(
    make_client: Make, label: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    deliver(c, s, ok(s, mutate))
    got = c.get(f"/samples/{s['id']}").json()
    assert (got["status"], got["error"], got["report"]) == ("failed", "result_invalid", None), label
    assert "sample_result_rejected" in audit_names(c)


def test_report_for_another_sample_is_rejected(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    a, b = upload(c).json(), upload(c, b"MZ" + b"\x00" * 50).json()
    deliver(c, b, ok(a))  # le rapport de A posé pour B
    assert c.get(f"/samples/{b['id']}").json()["error"] == "result_invalid"


def test_bad_json_oversized_or_wrong_shape_results(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    cases: list[Any] = [
        "{pas du json",
        json.dumps([1, 2]),
        json.dumps({"ok": True}),
        json.dumps({"ok": True, "report": {}, "extra": 1}),
        json.dumps({"ok": "yes", "report": {}}),
        "x" * 300_000,
    ]
    for payload in cases:
        s = upload(c, DATA + os.urandom(8)).json()
        (dirs(c)[1] / f"{s['id']}.json").write_text(
            payload if isinstance(payload, str) else json.dumps(payload)
        )
        assert c.get(f"/samples/{s['id']}").json()["error"] == "result_invalid", str(payload)[:30]


def test_symlinked_result_is_refused(make_client: Make, tmp_path: Path) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps(ok(s)))
    os.symlink(secret, dirs(c)[1] / f"{s['id']}.json")
    assert c.get(f"/samples/{s['id']}").json()["error"] == "result_invalid"


def test_analyzer_error_codes(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    deliver(c, s, {"ok": False, "error": "timeout"})
    got = c.get(f"/samples/{s['id']}").json()
    assert (got["status"], got["error"]) == ("failed", "timeout")
    assert "sample_failed" in audit_names(c) and "sample_result_rejected" not in audit_names(c)
    for bad in ("Time Out!", "x" * 40, 5, None):
        t = upload(c, DATA + os.urandom(8)).json()
        deliver(c, t, {"ok": False, "error": bad})
        assert c.get(f"/samples/{t['id']}").json()["error"] == "result_invalid"


# ---------- suppression et identifiants ----------


def test_admin_delete_removes_everything(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    deliver(c, s, ok(s))
    c.get(f"/samples/{s['id']}")
    login(c, "root")
    assert c.delete(f"/samples/{s['id']}").json() == {"status": "deleted"}
    assert not (dirs(c)[0] / s["id"]).exists() and not (dirs(c)[1] / f"{s['id']}.json").exists()
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.query(Sample).count() == 0
    assert "sample_deleted" in audit_names(c)
    assert c.get(f"/samples/{s['id']}").status_code == 404


@pytest.mark.parametrize("bad", ["..%2F..%2Fetc%2Fpasswd", "smp_ZZ", "smp_0123456789abcdef0", "x"])
def test_malformed_sample_ids_are_rejected(make_client: Make, bad: str) -> None:
    c = make_client()
    login(c, "root")
    assert c.get(f"/samples/{bad}").status_code in (404, 422)
    assert c.delete(f"/samples/{bad}").status_code in (404, 422)


def test_no_download_endpoint_and_no_disk_paths_in_responses(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    assert c.get(f"/samples/{s['id']}/download").status_code == 404
    blob = c.get(f"/samples/{s['id']}").text + c.get("/samples").text
    assert str(dirs(c)[0]) not in blob and "sample.bin" not in blob


def test_valid_report_padded_beyond_the_size_cap_is_rejected(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    # JSON valide suivi de 300 Ko d'espaces : une simple troncature le rendrait acceptable
    (dirs(c)[1] / f"{s['id']}.json").write_text(json.dumps(ok(s)) + " " * 300_000)
    assert c.get(f"/samples/{s['id']}").json()["error"] == "result_invalid"


def test_ingest_never_replaces_an_already_ingested_result(make_client: Make) -> None:
    from app import malware

    c = make_client()
    login(c, "ana")
    s = upload(c).json()
    deliver(c, s, ok(s))
    assert c.get(f"/samples/{s['id']}").json()["status"] == "analyzed"
    deliver(c, s, {"ok": False, "error": "timeout"})
    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        row = db.get(Sample, s["id"])
        malware.ingest(db, c.app.state.bus, dirs(c)[1], row)  # type: ignore[attr-defined]
        assert (row.status, row.error) == ("analyzed", None) and row.report_json
