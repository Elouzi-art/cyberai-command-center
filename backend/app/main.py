from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.deps import require_role
from app.limiter import LoginLimiter
from app.models import User
from app.providers import AIProvider
from app.providers.registry import load_providers
from app.routes import auth, providers, usage

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, provider_overrides: dict[str, AIProvider] | None = None
) -> FastAPI:
    cfg = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if cfg.database_url.startswith("sqlite:///") and ":memory:" not in cfg.database_url:
            path = cfg.database_url.removeprefix("sqlite:///")
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        engine = make_engine(cfg.database_url)
        init_db(engine)
        app.state.session_factory = make_session_factory(engine)
        app.state.providers = (
            provider_overrides
            if provider_overrides is not None
            else load_providers(cfg.config_path, os.environ)
        )
        yield
        for p in app.state.providers.values():
            await p.aclose()
        engine.dispose()

    app = FastAPI(
        title="CyberAI Command Center",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = cfg
    app.state.limiter = LoginLimiter(cfg.login_max_failures, cfg.login_window_seconds)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/agents")
    def agents(_user: Annotated[User, Depends(require_role("viewer"))]) -> list[dict[str, str]]:
        return []  # Sprint 2+ : Agent Manager

    app.include_router(auth.router)
    app.include_router(providers.router)
    app.include_router(usage.router)
    return app


app = create_app()
