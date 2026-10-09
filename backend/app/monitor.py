"""Surveillance des quotas fournisseurs : émet `rate_limit.warning` seulement sur mesure réelle."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.events import EventBus, Severity
from app.providers import AIProvider

REPEAT_AFTER_SECONDS = 300.0


@dataclass
class QuotaAlertState:
    last: dict[str, tuple[str, float]] = field(default_factory=dict)


def check_quota(
    provider: AIProvider,
    bus: EventBus,
    state: QuotaAlertState,
    warn_pct: float,
    critical_pct: float,
    now: float | None = None,
) -> None:
    now = time.time() if now is None else now
    q = provider.quota(now)
    pct = q.used_pct.value if q.used_pct.available else None
    if not isinstance(pct, float | int):
        state.last.pop(provider.id, None)
        return
    level = "critical" if pct >= critical_pct else "warning" if pct >= warn_pct else None
    if level is None:
        state.last.pop(provider.id, None)
        return
    prev = state.last.get(provider.id)
    if prev and prev[0] == level and now - prev[1] < REPEAT_AFTER_SECONDS:
        return  # pas de spam : même niveau, déjà signalé récemment
    state.last[provider.id] = (level, now)
    data: dict[str, object] = {"provider": provider.id, "used_pct": pct}
    for key, metric in (
        ("unit", q.unit),
        ("remaining", q.remaining),
        ("reset_at", q.reset_at),
        ("remaining_time", q.reset_in_seconds),
    ):
        if metric.available:  # champ absent plutôt que valeur inventée
            data[key] = metric.value
    severity: Severity = "high" if level == "critical" else "medium"
    bus.publish(
        source="api", agent="monitor", type="rate_limit.warning", severity=severity, data=data
    )
