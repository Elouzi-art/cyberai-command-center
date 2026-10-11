"""File d'approbation humaine (R5, R9).

Règles : le niveau vient de la politique ; les paramètres sont immuables et liés par hash ;
une approbation vise le hash que l'humain a vu ; une demande expirée ne s'exécute jamais ;
la prise en charge (pending -> approved) est atomique ; chaque décision est auditée.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.audit import audit
from app.config import Settings
from app.events import EventBus, Severity
from app.executor import ExecutionRequest, ExecutionResult, Executor
from app.models import Action, User, utcnow
from app.policy import Policy
from app.security import ROLE_RANK

MAX_PARAMS_BYTES = 4096
MAX_DEPTH = 4
_SEVERITY: dict[str, Severity] = {"L2": "medium", "L3": "high"}


class ActionError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


# ---------- paramètres et hash ----------


def _check(value: Any, depth: int) -> None:
    if depth > MAX_DEPTH:
        raise ActionError(422, "paramètres trop imbriqués")
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 64:
                raise ActionError(422, "clé de paramètre invalide")
            _check(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > 100:
            raise ActionError(422, "liste trop longue")
        for v in value:
            _check(v, depth + 1)
    elif isinstance(value, str):
        if len(value) > 1024:
            raise ActionError(422, "valeur trop longue")
    elif value is not None and not isinstance(value, bool | int | float):
        raise ActionError(422, "type de paramètre non supporté")


def canonical(tool: str, params: dict[str, Any]) -> str:
    try:
        return json.dumps(
            {"tool": tool, "params": params},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (ValueError, TypeError) as exc:
        raise ActionError(422, "paramètres non sérialisables") from exc


def params_hash(tool: str, params: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical(tool, params).encode()).hexdigest()


def validate_params(tool: str, params: dict[str, Any]) -> None:
    _check(params, 0)
    if len(canonical(tool, params).encode()) > MAX_PARAMS_BYTES:
        raise ActionError(422, "paramètres trop volumineux")


# ---------- sérialisation ----------


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def serialize(a: Action) -> dict[str, Any]:
    """Conforme à schemas/approval_action.v1.json."""
    return {
        "id": a.id,
        "agent": a.agent,
        "tool": a.tool,
        "params": json.loads(a.params_json),
        "params_hash": a.params_hash,
        "risk_level": a.risk_level,
        "required_role": a.required_role,
        "justification_ai": a.justification_ai,
        "evidence": json.loads(a.evidence_json),
        "blast_radius": a.blast_radius,
        "rollback": a.rollback,
        "status": a.status,
        "created_at": _iso(a.created_at),
        "expires_at": _iso(a.expires_at),
        "requested_by": a.requested_by,
        "requester_kind": a.requester_kind,
        "decided_by": a.decided_by,
        "decided_at": _iso(a.decided_at),
        "executed_at": _iso(a.executed_at),
        "result": json.loads(a.result_json) if a.result_json else None,
    }


def _event(bus: EventBus, a: Action, type_: str, severity: Severity | None = None) -> None:
    bus.publish(
        source="actions",
        agent=a.agent,
        type=type_,
        severity=severity or _SEVERITY.get(a.risk_level, "info"),
        data={
            "action_id": a.id,
            "tool": a.tool,
            "risk_level": a.risk_level,
            "required_role": a.required_role,
        },
    )


def _get(db: Session, action_id: str) -> Action:
    a = db.get(Action, action_id)
    if a is None:
        raise ActionError(404, "action inconnue")
    return a


# ---------- expiration ----------


def expire_stale(db: Session, bus: EventBus, now: datetime | None = None) -> None:
    now = now or utcnow()
    stale = db.query(Action).filter(Action.status == "pending", Action.expires_at <= now).all()
    for a in stale:
        n = (
            db.query(Action)
            .filter(Action.id == a.id, Action.status == "pending")
            .update({"status": "expired"}, synchronize_session=False)
        )
        db.commit()
        if n:
            db.refresh(a)
            audit(
                db,
                "system",
                "action_expired",
                action_id=a.id,
                tool=a.tool,
                level=a.risk_level,
                params_hash=a.params_hash,
            )
            _event(bus, a, "action.expired", "low")


# ---------- exécution ----------


def _execute(db: Session, bus: EventBus, executor: Executor, a: Action, actor: str) -> None:
    res: ExecutionResult = executor.run(
        ExecutionRequest(a.id, a.tool, json.loads(a.params_json), a.risk_level, dry_run=False)
    )
    a.status = "executed" if res.ok else "failed"
    a.executed_at = utcnow()
    a.result_json = json.dumps(res.output)
    db.commit()
    audit(
        db,
        actor,
        "action_executed" if res.ok else "action_failed",
        action_id=a.id,
        tool=a.tool,
        level=a.risk_level,
        params_hash=a.params_hash,
    )
    _event(bus, a, "action.executed" if res.ok else "action.failed", "info" if res.ok else "medium")


# ---------- proposition ----------


def propose(
    db: Session,
    bus: EventBus,
    policy: Policy,
    executor: Executor,
    settings: Settings,
    *,
    requested_by: str,
    requester_kind: str,
    agent: str,
    tool: str,
    params: dict[str, Any],
    justification: str | None,
    evidence: list[str],
    blast_radius: str | None,
) -> Action:
    validate_params(tool, params)
    d = policy.classify(tool)  # le niveau n'est JAMAIS lu dans la requête
    h = params_hash(tool, params)
    if d.approval == "forbidden":
        audit(
            db,
            requested_by,
            "action_refused",
            tool=tool,
            level=d.level,
            known=d.known,
            params_hash=h,
        )
        bus.publish(
            source="actions",
            agent=agent,
            type="action.refused",
            severity="medium",
            data={"tool": tool, "risk_level": d.level, "known": d.known},
        )
        raise ActionError(403, "action interdite par la politique")
    ttl = settings.approval_ttl_minutes
    if d.max_ttl_minutes is not None:
        ttl = min(ttl, d.max_ttl_minutes)
    now = utcnow()
    a = Action(
        id=f"act_{uuid.uuid4().hex[:16]}",
        created_at=now,
        requested_by=requested_by,
        requester_kind=requester_kind,
        agent=agent,
        tool=tool,
        params_json=json.dumps(params, sort_keys=True),
        params_hash=h,
        risk_level=d.level,
        required_role=d.required_role,
        justification_ai=(justification or None) and justification[:2000],
        evidence_json=json.dumps(evidence),
        blast_radius=blast_radius,
        rollback=d.rollback,
        status="pending",
        expires_at=now + timedelta(minutes=ttl),
    )
    db.add(a)
    db.commit()
    audit(
        db,
        requested_by,
        "action_proposed",
        action_id=a.id,
        tool=tool,
        level=d.level,
        params_hash=h,
        agent=agent,
    )
    _event(bus, a, "action.proposed")
    if d.approval == "none":  # L0/L1 : lecture seule ou enrichissement en liste blanche
        a.status, a.decided_by, a.decided_at = "approved", "policy:auto", utcnow()
        db.commit()
        audit(db, "policy:auto", "action_auto_approved", action_id=a.id, tool=tool, level=d.level)
        _execute(db, bus, executor, a, "policy:auto")
    return a


# ---------- décision humaine ----------


def approve(
    db: Session,
    bus: EventBus,
    policy: Policy,
    executor: Executor,
    settings: Settings,
    *,
    user: User,
    action_id: str,
    seen_hash: str,
    dry_run: bool,
) -> tuple[Action, dict[str, Any] | None]:
    expire_stale(db, bus)
    a = _get(db, action_id)
    if a.status != "pending":
        raise ActionError(409, f"action déjà traitée ({a.status})")
    d = policy.classify(a.tool)
    if d.approval == "forbidden" or d.level != a.risk_level:
        audit(db, user.username, "approval_refused_policy_changed", action_id=a.id, tool=a.tool)
        raise ActionError(409, "la politique a changé : re-soumettre l'action")
    required = d.required_role
    if required is None or ROLE_RANK[user.role] < ROLE_RANK[required]:
        audit(
            db,
            user.username,
            "approval_denied_role",
            action_id=a.id,
            tool=a.tool,
            level=a.risk_level,
            role=user.role,
            required=required,
        )
        raise ActionError(403, "droits insuffisants pour ce niveau")
    if (
        a.requester_kind == "human"
        and a.requested_by == user.username
        and not settings.allow_self_approval
    ):
        audit(
            db,
            user.username,
            "approval_denied_self",
            action_id=a.id,
            tool=a.tool,
            level=a.risk_level,
        )
        raise ActionError(403, "auto-approbation interdite")
    if seen_hash != a.params_hash:
        audit(db, user.username, "approval_hash_mismatch", action_id=a.id, tool=a.tool)
        raise ActionError(409, "le contenu ne correspond pas à ce que vous avez validé")
    params = json.loads(a.params_json)
    if params_hash(a.tool, params) != a.params_hash:  # falsification en base ou bug
        a.status, a.result_json = "failed", json.dumps({"error": "integrity_violation"})
        db.commit()
        audit(db, "system", "action_integrity_violation", action_id=a.id, tool=a.tool)
        _event(bus, a, "action.failed", "critical")
        raise ActionError(409, "intégrité compromise : action bloquée")
    if dry_run:
        out = executor.run(ExecutionRequest(a.id, a.tool, params, a.risk_level, dry_run=True))
        audit(db, user.username, "action_dry_run", action_id=a.id, tool=a.tool, level=a.risk_level)
        return a, out.output
    now = utcnow()
    claimed = (
        db.query(Action)
        .filter(Action.id == a.id, Action.status == "pending", Action.expires_at > now)
        .update(
            {"status": "approved", "decided_by": user.username, "decided_at": now},
            synchronize_session=False,
        )
    )
    db.commit()
    if claimed != 1:  # déjà prise ou expirée entre-temps
        raise ActionError(409, "action déjà traitée ou expirée")
    db.refresh(a)
    audit(
        db,
        user.username,
        "action_approved",
        action_id=a.id,
        tool=a.tool,
        level=a.risk_level,
        params_hash=a.params_hash,
    )
    _event(bus, a, "action.approved")
    _execute(db, bus, executor, a, user.username)
    return a, None


def reject(db: Session, bus: EventBus, *, user: User, action_id: str) -> Action:
    expire_stale(db, bus)
    a = _get(db, action_id)
    now = utcnow()
    n = (
        db.query(Action)
        .filter(Action.id == a.id, Action.status == "pending")
        .update(
            {"status": "rejected", "decided_by": user.username, "decided_at": now},
            synchronize_session=False,
        )
    )
    db.commit()
    if n != 1:
        raise ActionError(409, f"action déjà traitée ({a.status})")
    db.refresh(a)
    audit(
        db,
        user.username,
        "action_rejected",
        action_id=a.id,
        tool=a.tool,
        level=a.risk_level,
        params_hash=a.params_hash,
    )
    _event(bus, a, "action.rejected", "info")
    return a
