from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app import actions as svc
from app.deps import DbDep, csrf_guard, require_role
from app.models import Action, User

router = APIRouter(tags=["actions"])
Analyst = Annotated[User, Depends(require_role("analyst"))]
Viewer = Annotated[User, Depends(require_role("viewer"))]
TOOL = r"^[a-z0-9_.-]{1,64}$"


class ProposeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # aucun champ `risk_level` ni `rollback` accepté
    tool: str = Field(pattern=TOOL)
    params: dict[str, Any] = {}
    agent: str = Field(default="manual", max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    justification_ai: str | None = Field(default=None, max_length=2000)
    evidence: list[Annotated[str, Field(max_length=64)]] = Field(default=[], max_length=20)
    blast_radius: str | None = Field(default=None, max_length=500)


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    params_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dry_run: bool = False


def _raise(e: svc.ActionError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.detail)


@router.get("/policy")
def policy_view(request: Request, _user: Viewer) -> dict[str, object]:
    pol = request.app.state.policy
    return {
        "tools": {
            n: {"level": t["level"], "rollback": t.get("rollback")} for n, t in pol.tools().items()
        }
    }


@router.post("/actions", status_code=201, dependencies=[Depends(csrf_guard)])
async def propose(body: ProposeIn, request: Request, db: DbDep, user: Analyst) -> dict[str, Any]:
    s = request.app.state
    try:
        a = svc.propose(
            db,
            s.bus,
            s.policy,
            s.executor,
            s.settings,
            requested_by=user.username,
            requester_kind="human",
            agent=body.agent,
            tool=body.tool,
            params=body.params,
            justification=body.justification_ai,
            evidence=body.evidence,
            blast_radius=body.blast_radius,
        )
    except svc.ActionError as e:
        raise _raise(e) from None
    return svc.serialize(a)


@router.get("/actions")
async def list_actions(
    request: Request,
    db: DbDep,
    _user: Analyst,
    status: Annotated[
        str | None, Query(pattern="^(pending|approved|rejected|expired|executed|failed)$")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    svc.expire_stale(db, request.app.state.bus)
    q = db.query(Action)
    if status:
        q = q.filter(Action.status == status)
    return [svc.serialize(a) for a in q.order_by(Action.created_at.desc()).limit(limit)]


@router.get("/actions/{action_id}")
async def get_action(action_id: str, request: Request, db: DbDep, _user: Analyst) -> dict[str, Any]:
    svc.expire_stale(db, request.app.state.bus)
    try:
        return svc.serialize(svc._get(db, action_id))
    except svc.ActionError as e:
        raise _raise(e) from None


@router.post("/actions/{action_id}/approve", dependencies=[Depends(csrf_guard)])
async def approve(
    action_id: str, body: ApproveIn, request: Request, db: DbDep, user: Analyst
) -> dict[str, Any]:
    s = request.app.state
    try:
        a, dry = svc.approve(
            db,
            s.bus,
            s.policy,
            s.executor,
            s.settings,
            user=user,
            action_id=action_id,
            seen_hash=body.params_hash,
            dry_run=body.dry_run,
        )
    except svc.ActionError as e:
        raise _raise(e) from None
    out = svc.serialize(a)
    if dry is not None:
        out["dry_run_result"] = dry
    return out


@router.post("/actions/{action_id}/reject", dependencies=[Depends(csrf_guard)])
async def reject(action_id: str, request: Request, db: DbDep, user: Analyst) -> dict[str, Any]:
    try:
        return svc.serialize(svc.reject(db, request.app.state.bus, user=user, action_id=action_id))
    except svc.ActionError as e:
        raise _raise(e) from None
