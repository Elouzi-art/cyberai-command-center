"""Abstraction fournisseur IA. R1 : pas de métrique inventée. R8 : pas de couplage hors adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self

from pydantic import BaseModel, model_validator


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


class AIProvider(ABC):
    """Tout fournisseur (cloud ou local) implémente cette interface."""

    id: str

    @abstractmethod
    async def complete(self, prompt: str) -> str: ...

    @abstractmethod
    def metrics(self) -> ProviderMetrics:
        """Toute métrique non exposée par le fournisseur DOIT être MetricValue.unavailable()."""
