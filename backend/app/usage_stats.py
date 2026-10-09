"""Agrégats de tokens par fenêtre. R1 : somme donnée seulement si tous les tokens sont connus."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import RequestLog

WINDOWS = {"1m": timedelta(minutes=1), "1h": timedelta(hours=1), "24h": timedelta(days=1)}
Dimension = Literal["agent", "model", "provider"]


def _metric(value: float | int | None, available: bool) -> dict[str, Any]:
    return {"value": value if available else None, "available": available}


def _aggregate(db: Session, since: datetime, group: Any = None) -> list[tuple[Any, ...]]:
    ok = RequestLog.status == "success"
    cols = [
        func.count(),
        func.sum(case((ok, 1), else_=0)),
        func.sum(case((ok, 0), else_=1)),
        func.sum(RequestLog.total_tokens),
        func.sum(case((ok, case((RequestLog.total_tokens.is_(None), 1), else_=0)), else_=0)),
    ]
    stmt = select(*([group] if group is not None else []), *cols).where(
        RequestLog.timestamp >= since
    )
    if group is not None:
        stmt = stmt.group_by(group)
    return [tuple(r) for r in db.execute(stmt)]


def _row(n: int, success: int, errors: int, tokens: int | None, unknown: int) -> dict[str, Any]:
    known = (unknown or 0) == 0
    total = int(tokens or 0)
    return {
        "requests": n,
        "errors": int(errors or 0),
        "tokens": _metric(total, known),
        "avg_tokens_per_request": _metric(
            round(total / success, 1) if success and known else None, bool(success and known)
        ),
    }


def token_windows(db: Session, now: datetime) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, delta in WINDOWS.items():
        rows = _aggregate(db, now - delta)
        n, success, errors, tokens, unknown = rows[0] if rows else (0, 0, 0, 0, 0)
        out[name] = _row(n or 0, success or 0, errors or 0, tokens, unknown or 0)
    return out


def token_breakdown(db: Session, now: datetime, by: Dimension) -> list[dict[str, Any]]:
    col = {"agent": RequestLog.agent, "model": RequestLog.model, "provider": RequestLog.provider}[
        by
    ]
    rows = _aggregate(db, now - WINDOWS["24h"], group=col)
    return [{by: r[0], **_row(r[1], r[2], r[3], r[4], r[5])} for r in rows]
