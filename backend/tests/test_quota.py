"""R1 : quota et reset uniquement si exposés ; mesure périmée => indisponible."""

import asyncio

import httpx

from app.providers.openai_compatible import OpenAICompatibleProvider
from app.providers.quota import build_quota, parse_reset

T0 = 1_000_000.0


def test_parse_durations() -> None:
    assert parse_reset("6m0s", T0) == T0 + 360
    assert parse_reset("1h2m3s", T0) == T0 + 3723
    assert parse_reset("250ms", T0) == T0 + 0.25
    assert parse_reset("1s", T0) == T0 + 1


def test_parse_iso_and_refuses_to_guess() -> None:
    assert parse_reset("2030-01-01T00:00:00Z", T0) == 1893456000.0
    assert parse_reset("2030-01-01T00:00:00", T0) is None  # sans fuseau : ambigu
    assert parse_reset("1700000000", T0) is None  # nombre seul : secondes ou epoch ?
    assert parse_reset("bientôt", T0) is None


def test_no_headers_means_everything_unavailable() -> None:
    q = build_quota({}, None, T0)
    assert all(not getattr(q, f).available for f in type(q).model_fields)


def test_full_quota_status() -> None:
    h = {"remaining_tokens": "280", "limit_tokens": "1000", "reset_tokens": "6m0s"}
    q = build_quota(h, T0, T0 + 60)
    assert q.unit.value == "tokens" and q.remaining.value == 280
    assert q.used_pct.value == 72.0
    assert q.reset_in_seconds.value == 300  # 360 s - 60 s écoulées


def test_missing_limit_gives_no_percentage() -> None:
    q = build_quota({"remaining_tokens": "50"}, T0, T0)
    assert q.remaining.available and not q.used_pct.available and not q.reset_at.available


def test_inconsistent_values_give_no_percentage() -> None:
    q = build_quota({"remaining_tokens": "2000", "limit_tokens": "1000"}, T0, T0)
    assert not q.used_pct.available


def test_stale_after_reset() -> None:
    h = {"remaining_tokens": "10", "limit_tokens": "1000", "reset_tokens": "1m0s"}
    q = build_quota(h, T0, T0 + 61)
    assert not q.remaining.available and not q.used_pct.available


def test_falls_back_to_requests_dimension() -> None:
    q = build_quota({"remaining_requests": "5", "limit_requests": "10"}, T0, T0)
    assert q.unit.value == "requests" and q.used_pct.value == 50.0


def test_provider_exposes_quota_from_real_headers() -> None:
    t = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            headers={
                "x-ratelimit-remaining-tokens": "100",
                "x-ratelimit-limit-tokens": "1000",
                "x-ratelimit-reset-tokens": "10m0s",
            },
            json={"choices": [{"message": {"content": "ok"}}]},
        )
    )
    p = OpenAICompatibleProvider(
        "c", "m", "http://x", "k", ("public",), httpx.AsyncClient(transport=t)
    )
    assert not p.quota().remaining.available  # rien observé encore
    asyncio.run(p.complete("hi"))
    q = p.quota()
    assert q.used_pct.value == 90.0 and q.reset_in_seconds.available
