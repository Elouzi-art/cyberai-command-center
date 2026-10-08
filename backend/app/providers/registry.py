from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field

from app.providers.base import AIProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider

log = logging.getLogger(__name__)
SENSITIVITIES = ("public", "internal", "confidential")


class ConfigError(Exception):
    pass


class ProviderConfig(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    type: Literal["ollama", "openai_compatible"]
    model: str
    enabled: bool = True
    base_url: str | None = None
    api_key_env: str | None = None
    data_sensitivity: list[Literal["public", "internal", "confidential"]] = ["public"]


def _check_url(url: str) -> str:
    if urlparse(url).scheme not in ("http", "https"):
        raise ConfigError("base_url doit être http(s)")
    return url


def build_provider(cfg: ProviderConfig, env: Mapping[str, str]) -> AIProvider:
    sens = tuple(cfg.data_sensitivity)
    if cfg.type == "ollama":
        base = _check_url(cfg.base_url or env.get("OLLAMA_BASE_URL", "http://localhost:11434"))
        return OllamaProvider(cfg.id, cfg.model, base, sens)
    if not cfg.base_url or not cfg.api_key_env:
        raise ConfigError(f"{cfg.id}: base_url et api_key_env requis")
    key = env.get(cfg.api_key_env, "")
    if not key:
        raise ConfigError(f"{cfg.id}: variable d'environnement {cfg.api_key_env} vide")
    return OpenAICompatibleProvider(cfg.id, cfg.model, _check_url(cfg.base_url), key, sens)


def load_providers(path: str, env: Mapping[str, str]) -> dict[str, AIProvider]:
    p = Path(path)
    if not p.exists():
        log.warning("fichier de configuration absent : aucun provider chargé")
        return {}
    raw = yaml.safe_load(p.read_text()) or {}
    providers: dict[str, AIProvider] = {}
    for item in raw.get("providers", []):
        cfg = ProviderConfig.model_validate(item)
        if cfg.enabled:
            providers[cfg.id] = build_provider(cfg, env)
    return providers
