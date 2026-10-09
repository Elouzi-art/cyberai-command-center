"""Abstraction fournisseur IA. R1 : pas de métrique inventée. R8 : pas de couplage hors adapter."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, model_validator

if TYPE_CHECKING:
    from app.providers.quota import QuotaStatus


class MetricValue(BaseModel):
    value: float | str | None = None
    available: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.available and self.value is not None:
            raise ValueError("une métrique indisponible ne peut pas avoir de valeur (R1)")
        if self.available and self.value is None:
            raise ValueError("une métrique disponible doit avoir une valeur (R1)")
        return self

    @classmethod
    def unavailable(cls) -> MetricValue:
        return cls(value=None, available=False)

    @classmethod
    def of(cls, value: float | str) -> MetricValue:
        return cls(value=value, available=True)


class ProviderMetrics(BaseModel):
    model: MetricValue
    requests: MetricValue
    tokens: MetricValue
    latency_ms: MetricValue
    errors: MetricValue
    rate_limit: MetricValue
    quota_remaining: MetricValue
    reset_time: MetricValue
    cost: MetricValue
    health: MetricValue


@dataclass
class RawResult:
    """Ce qu'un adapter renvoie. Tout champ non exposé par le fournisseur reste None."""

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    headers: dict[str, str] = field(default_factory=dict)  # clés normalisées, voir adapters


class CompletionResult(BaseModel):
    text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


class ProviderError(Exception):
    """Erreur normalisée : ne transporte jamais le contenu de la requête ni de secret."""

    def __init__(self, error_type: str, latency_ms: int) -> None:
        super().__init__(error_type)
        self.error_type = error_type
        self.latency_ms = latency_ms


def parse_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


@dataclass
class _Stats:
    requests: int = 0
    ok: int = 0
    errors: int = 0
    latency_sum_ms: int = 0
    tokens_total: int = 0
    tokens_complete: bool = True
    last_ok: bool | None = None
    last_headers: dict[str, str] = field(default_factory=dict)
    observed_at: float | None = None


def _header_metric(headers: dict[str, str], key: str) -> MetricValue:
    raw = headers.get(key, "").strip()
    if not raw:
        return MetricValue.unavailable()
    try:
        return MetricValue.of(float(raw))
    except ValueError:
        return MetricValue.of(raw)


class AIProvider(ABC):
    """Tout fournisseur (cloud ou local) implémente `_call` ; le reste est commun."""

    def __init__(self, provider_id: str, model: str, data_sensitivity: tuple[str, ...]) -> None:
        self.id = provider_id
        self.model = model
        self.data_sensitivity = data_sensitivity
        self._stats = _Stats()

    @abstractmethod
    async def _call(self, prompt: str) -> RawResult: ...

    async def aclose(self) -> None:  # pragma: no cover - surchargé si besoin
        return None

    async def complete(self, prompt: str) -> CompletionResult:
        start = time.perf_counter()
        self._stats.requests += 1
        try:
            raw = await self._call(prompt)
        except Exception as exc:
            latency = int((time.perf_counter() - start) * 1000)
            self._stats.errors += 1
            self._stats.latency_sum_ms += latency
            self._stats.last_ok = False
            raise ProviderError(type(exc).__name__, latency) from exc
        latency = int((time.perf_counter() - start) * 1000)
        self._stats.ok += 1
        self._stats.latency_sum_ms += latency
        self._stats.last_ok = True
        self._stats.last_headers = raw.headers
        self._stats.observed_at = time.time()
        if raw.input_tokens is None or raw.output_tokens is None:
            self._stats.tokens_complete = False
        else:
            self._stats.tokens_total += raw.input_tokens + raw.output_tokens
        return CompletionResult(
            text=raw.text,
            provider=self.id,
            model=self.model,
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            latency_ms=latency,
        )

    def quota(self, now: float | None = None) -> QuotaStatus:
        from app.providers.quota import build_quota

        return build_quota(self._stats.last_headers, self._stats.observed_at, now)

    def metrics(self) -> ProviderMetrics:
        """Mesures réelles uniquement. Tout ce qui n'est pas exposé reste `unavailable()` (R1)."""
        s = self._stats
        total = s.requests
        hdr = s.last_headers
        return ProviderMetrics(
            model=MetricValue.of(self.model),
            requests=MetricValue.of(total),
            tokens=(
                MetricValue.of(s.tokens_total)
                if s.ok > 0 and s.tokens_complete
                else MetricValue.unavailable()
            ),
            latency_ms=(
                MetricValue.of(s.latency_sum_ms / total) if total else MetricValue.unavailable()
            ),
            errors=MetricValue.of(s.errors),
            rate_limit=_header_metric(hdr, "remaining_requests"),
            quota_remaining=_header_metric(hdr, "remaining_tokens"),
            reset_time=(
                _header_metric(hdr, "reset_tokens")
                if hdr.get("reset_tokens")
                else _header_metric(hdr, "reset_requests")
            ),
            cost=MetricValue.unavailable(),  # aucune donnée de tarification fiable en Sprint 1
            health=(
                MetricValue.of("ok" if s.last_ok else "degraded")
                if s.last_ok is not None
                else MetricValue.unavailable()
            ),
        )
