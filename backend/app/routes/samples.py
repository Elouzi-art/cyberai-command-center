from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import Path as PathParam

from app import malware, quarantine
from app.audit import audit
from app.deps import DbDep, csrf_guard, require_role
from app.models import Sample, User

router = APIRouter(prefix="/samples", tags=["samples"])
Analyst = Annotated[User, Depends(require_role("analyst"))]
Admin = Annotated[User, Depends(require_role("admin"))]
SampleId = Annotated[str, PathParam(pattern=r"^smp_[0-9a-f]{16}$")]


def _dirs(request: Request) -> tuple[Path, Path]:
    s = request.app.state.settings
    return Path(s.inbox_dir), Path(s.outbox_dir)


def _get(db: DbDep, sample_id: str) -> Sample:
    s = db.get(Sample, sample_id)
    if s is None:
        raise HTTPException(status_code=404, detail="échantillon inconnu")
    return s


@router.post("", status_code=201, dependencies=[Depends(csrf_guard)])
async def upload(
    request: Request,
    db: DbDep,
    user: Analyst,
    filename: Annotated[str, Query(min_length=1, max_length=256)] = "sample.bin",
) -> dict[str, Any]:
    """Corps brut (application/octet-stream) lu en flux : jamais chargé entièrement en mémoire."""
    cfg = request.app.state.settings
    inbox, outbox = _dirs(request)
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > cfg.max_upload_bytes:
        raise HTTPException(status_code=413, detail="fichier trop volumineux")
    queued = db.query(Sample).filter(Sample.status == "queued").count()
    if queued >= cfg.max_queued_samples:
        raise HTTPException(status_code=429, detail="file d'analyse pleine, réessayez plus tard")
    sample_id = quarantine.new_id()
    try:
        sha, size = await quarantine.store_stream(
            request.stream(), inbox, sample_id, cfg.max_upload_bytes
        )
    except quarantine.UploadError as e:
        raise HTTPException(status_code=e.status, detail=e.detail) from None
    s = Sample(
        id=sample_id,
        uploaded_by=user.username,
        name=quarantine.safe_name(filename),
        sha256=sha,
        size=size,
        status="queued",
    )
    db.add(s)
    db.commit()
    quarantine.commit_job(
        inbox, sample_id, sha, size
    )  # marqueur de fin : l'analyseur peut démarrer
    audit(db, user.username, "sample_uploaded", sample_id=s.id, sha256=sha, size=size, name=s.name)
    request.app.state.bus.publish(
        source="malware",
        agent="malware",
        type="sample.uploaded",
        data={"sample_id": s.id, "sha256": sha, "size": size},
    )
    return malware.serialize(s)


@router.get("")
async def list_samples(
    request: Request,
    db: DbDep,
    _user: Analyst,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, Any]]:
    rows = db.query(Sample).order_by(Sample.created_at.desc()).limit(limit).all()
    malware.refresh(db, request.app.state.bus, _dirs(request)[1], rows)
    return [malware.serialize(s) for s in rows]


@router.get("/{sample_id}")
async def get_sample(
    sample_id: SampleId, request: Request, db: DbDep, _user: Analyst
) -> dict[str, Any]:
    s = _get(db, sample_id)
    malware.refresh(db, request.app.state.bus, _dirs(request)[1], [s])
    return malware.serialize(s, full=True)


@router.delete("/{sample_id}", dependencies=[Depends(csrf_guard)])
async def delete_sample(
    sample_id: SampleId, request: Request, db: DbDep, user: Admin
) -> dict[str, str]:
    s = _get(db, sample_id)
    inbox, outbox = _dirs(request)
    quarantine.delete_sample(inbox, outbox, s.id)
    audit(db, user.username, "sample_deleted", sample_id=s.id, sha256=s.sha256)
    db.delete(s)
    db.commit()
    return {"status": "deleted"}
