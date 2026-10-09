from app.events import EventBus
from app.monitor import QuotaAlertState, check_quota
from app.providers import AIProvider, RawResult


class P(AIProvider):
    async def _call(self, prompt: str) -> RawResult:
        raise NotImplementedError


def _provider(headers: dict[str, str], observed: float = 1000.0) -> P:
    p = P("prov", "m", ("public",))
    p._stats.last_headers = headers
    p._stats.observed_at = observed
    return p


def _run(p: P, bus: EventBus, st: QuotaAlertState, now: float) -> None:
    check_quota(p, bus, st, 80, 95, now)


def test_warning_event_has_only_measured_fields() -> None:
    bus, st = EventBus(), QuotaAlertState()
    p = _provider({"remaining_tokens": "150", "limit_tokens": "1000"})  # 85 %, pas de reset
    _run(p, bus, st, 1001.0)
    ev = bus.recent()[0]
    assert ev.type == "rate_limit.warning" and ev.severity == "medium"
    assert ev.data["remaining"] == 150 and ev.data["used_pct"] == 85.0
    assert "reset_at" not in ev.data and "remaining_time" not in ev.data


def test_no_event_below_threshold_or_without_quota() -> None:
    bus, st = EventBus(), QuotaAlertState()
    _run(_provider({"remaining_tokens": "900", "limit_tokens": "1000"}), bus, st, 1001.0)
    _run(_provider({}), bus, st, 1001.0)
    assert bus.recent() == []


def test_no_spam_then_escalation_then_repeat() -> None:
    bus, st = EventBus(), QuotaAlertState()
    warn = _provider({"remaining_tokens": "150", "limit_tokens": "1000", "reset_tokens": "1h"})
    _run(warn, bus, st, 1001.0)
    _run(warn, bus, st, 1002.0)  # même niveau : silence
    assert len(bus.recent()) == 1
    crit = _provider({"remaining_tokens": "10", "limit_tokens": "1000", "reset_tokens": "1h"})
    _run(crit, bus, st, 1003.0)  # escalade : nouvel événement
    assert [e.severity for e in bus.recent()] == ["medium", "high"]
    assert bus.recent()[-1].data["remaining_time"] > 0
    _run(crit, bus, st, 1003.0 + 301)  # rappel après 5 min
    assert len(bus.recent()) == 3
