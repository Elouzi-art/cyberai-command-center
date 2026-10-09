"""Quota et temps avant reset. Rien n'est déduit : le manquant est indisponible (R1)."""

from __future__ import annotations

import re
import time
from datetime import datetime

from pydantic import BaseModel

from app.providers.base import MetricValue

_DURATION = re.compile(r"(?:\d+(?:\.\d+)?(?:ms|h|m|s))+")
_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_UNIT = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


class QuotaStatus(BaseModel):
    unit: MetricValue
    remaining: MetricValue
    limit: MetricValue
    used_pct: MetricValue
    reset_at: MetricValue
    reset_in_seconds: MetricValue

    @classmethod
    def unavailable(cls) -> QuotaStatus:
        u = MetricValue.unavailable
        return cls(
            unit=u(), remaining=u(), limit=u(), used_pct=u(), reset_at=u(), reset_in_seconds=u()
        )


def parse_reset(raw: str, observed_at: float) -> float | None:
    """Retourne l'instant de reset (epoch). Formats : durée relative (`6m0s`) ou date ISO 8601.

    Un nombre seul est ambigu (secondes ou epoch ?) : on ne devine pas.
    """
    raw = raw.strip()
    if _DURATION.fullmatch(raw):
        secs = sum(float(v) * _UNIT[u] for v, u in _PART.findall(raw))
        return observed_at + secs
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt.timestamp() if dt.tzinfo else None


def _num(headers: dict[str, str], key: str) -> float | None:
    try:
        return float(headers[key])
    except (KeyError, ValueError):
        return None


def build_quota(
    headers: dict[str, str], observed_at: float | None, now: float | None = None
) -> QuotaStatus:
    if not headers or observed_at is None:
        return QuotaStatus.unavailable()
    now = time.time() if now is None else now
    unit = "tokens" if _num(headers, "remaining_tokens") is not None else "requests"
    remaining = _num(headers, f"remaining_{unit}")
    if remaining is None:
        return QuotaStatus.unavailable()
    reset_raw = headers.get(f"reset_{unit}", "")
    reset_epoch = parse_reset(reset_raw, observed_at) if reset_raw else None
    if reset_epoch is not None and now >= reset_epoch:
        return QuotaStatus.unavailable()  # la fenêtre a été réinitialisée : la mesure est périmée
    limit = _num(headers, f"limit_{unit}")
    used = None
    if limit and limit > 0 and remaining <= limit:
        used = round((limit - remaining) / limit * 100, 1)
    avail = MetricValue.of
    off = MetricValue.unavailable
    return QuotaStatus(
        unit=avail(unit),
        remaining=avail(remaining),
        limit=avail(limit) if limit is not None else off(),
        used_pct=avail(used) if used is not None else off(),
        reset_at=(
            avail(datetime.fromtimestamp(reset_epoch).astimezone().isoformat(timespec="seconds"))
            if reset_epoch is not None
            else off()
        ),
        reset_in_seconds=avail(round(reset_epoch - now)) if reset_epoch is not None else off(),
    )
