"""R1/R2/R8 : les adapters reflètent exactement ce que le fournisseur expose."""

import asyncio

import httpx

from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


def test_ollama_reports_tokens_when_present() -> None:
    t = httpx.MockTransport(
        lambda r: httpx.Response(
            200, json={"response": "ok", "prompt_eval_count": 7, "eval_count": 3}
        )
    )
    p = OllamaProvider("o", "m", "http://x", ("public",), _client(t))
    res = asyncio.run(p.complete("hi"))
    assert (res.input_tokens, res.output_tokens, res.total_tokens) == (7, 3, 10)
    assert p.metrics().tokens.model_dump() == {"value": 10, "available": True}
    assert p.metrics().rate_limit.available is False  # local : aucune limite exposée


def test_openai_without_usage_or_headers_is_unavailable() -> None:
    t = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    )
    p = OpenAICompatibleProvider("c", "m", "http://x", "k", ("public",), _client(t))
    res = asyncio.run(p.complete("hi"))
    assert res.total_tokens is None
    m = p.metrics()
    assert m.tokens.available is False and m.quota_remaining.available is False
    assert m.reset_time.available is False


def test_openai_exposes_quota_only_when_headers_present() -> None:
    t = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            headers={"x-ratelimit-remaining-tokens": "1200", "x-ratelimit-reset-tokens": "6m0s"},
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )
    )
    p = OpenAICompatibleProvider("c", "m", "http://x", "k", ("public",), _client(t))
    asyncio.run(p.complete("hi"))
    m = p.metrics()
    assert m.quota_remaining.model_dump() == {"value": 1200.0, "available": True}
    assert m.reset_time.model_dump() == {"value": "6m0s", "available": True}
    assert m.rate_limit.available is False  # remaining-requests absent


def test_api_key_not_in_repr() -> None:
    p = OpenAICompatibleProvider("c", "m", "http://x", "sk-TOPSECRET", ("public",))
    assert "TOPSECRET" not in repr(p)


def test_http_error_counts_and_degrades_health() -> None:
    t = httpx.MockTransport(lambda r: httpx.Response(500))
    p = OllamaProvider("o", "m", "http://x", ("public",), _client(t))
    try:
        asyncio.run(p.complete("hi"))
    except Exception as exc:  # noqa: BLE001
        assert type(exc).__name__ == "ProviderError"
    m = p.metrics()
    assert m.errors.value == 1 and m.health.value == "degraded"
