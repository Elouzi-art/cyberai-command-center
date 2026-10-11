"""Configuration runtime. Les secrets viennent de l'environnement, jamais de Git (R2)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./data/app.db"
    config_path: str = "config.yaml"
    allowed_origins: tuple[str, ...] = ("http://localhost:8080",)
    cookie_secure: bool = True
    session_ttl_minutes: int = 480
    login_max_failures: int = 5
    login_window_seconds: int = 300
    event_buffer: int = 1000
    ws_recheck_seconds: float = 30.0
    quota_warn_pct: float = 80.0
    quota_critical_pct: float = 95.0
    demo_agent_enabled: bool = False
    policy_path: str = "policy/tools.yaml"
    approval_ttl_minutes: int = 60
    allow_self_approval: bool = False
    demo_step_delay: float = 0.5

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        origins = tuple(o.strip() for o in e.get("ALLOWED_ORIGINS", "").split(",") if o.strip())
        return cls(
            database_url=e.get("DATABASE_URL", cls.database_url),
            config_path=e.get("CONFIG_PATH", cls.config_path),
            allowed_origins=origins or cls.allowed_origins,
            cookie_secure=e.get("COOKIE_SECURE", "true").lower() != "false",
            demo_agent_enabled=e.get("DEMO_AGENT", "false").lower() == "true",
            policy_path=e.get("POLICY_PATH", cls.policy_path),
            approval_ttl_minutes=int(e.get("APPROVAL_TTL_MINUTES", cls.approval_ttl_minutes)),
            allow_self_approval=e.get("ALLOW_SELF_APPROVAL", "false").lower() == "true",
        )
