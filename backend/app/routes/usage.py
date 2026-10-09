from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select

from app.deps import DbDep, require_role
from app.models import RequestLog, User, utcnow
from app.usage_stats import Dimension, token_breakdown, token_windows

router = APIRouter(tags=["usage"])
Viewer = Annotated[User, Depends(require_role("viewer"))]


@router.get("/usage")
def usage(db: DbDep, _user: Viewer) -> list[dict[str, object]]:
    """Agrégats par provider/modèle/agent. Tokens sommés seulement s'ils sont tous connus (R1)."""
    unknown = func.sum(
        case(
            (RequestLog.status == "success", case((RequestLog.total_tokens.is_(None), 1), else_=0)),
            else_=0,
        )
    )
    errors = func.sum(case((RequestLog.status != "success", 1), else_=0))
    stmt = select(
        RequestLog.provider,
        RequestLog.model,
        RequestLog.agent,
        func.count(),
        errors,
        func.avg(RequestLog.latency_ms),
        func.sum(RequestLog.total_tokens),
        unknown,
    ).group_by(RequestLog.provider, RequestLog.model, RequestLog.agent)
    out: list[dict[str, object]] = []
    for provider, model, agent, n, err, avg, tokens, unk in db.execute(stmt):
        known = (unk or 0) == 0 and tokens is not None
        out.append(
            {
                "provider": provider,
                "model": model,
                "agent": agent,
                "requests": n,
                "errors": int(err or 0),
                "latency_ms_avg": float(avg) if avg is not None else None,
                "tokens": {"value": int(tokens) if known else None, "available": known},
            }
        )
    return out


@router.get("/usage/tokens")
def usage_tokens(
    db: DbDep, _user: Viewer, by: Annotated[Dimension | None, Query()] = None
) -> dict[str, Any]:
    """Fenêtres 1 min / 1 h / 24 h et ventilation (24 h) par agent, modèle ou provider.

    Les agents de démonstration (chiffres simulés) ne sont pas dans `request_log`, donc exclus (R1).
    """
    now = utcnow()
    return {
        "windows": token_windows(db, now),
        "breakdown": token_breakdown(db, now, by) if by else [],
    }
