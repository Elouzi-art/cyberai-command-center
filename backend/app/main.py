from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.agents.demo import AGENT_ID, AgentState
from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.events import EventBus
from app.executor import Executor
from app.limiter import LoginLimiter
from app.monitor import QuotaAlertState
from app.policy import Policy
from app.providers import AIProvider
from app.providers.registry import load_providers
from app.routes import actions, agents, auth, events, providers, samples, usage

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
        for d in (cfg.inbox_dir, cfg.outbox_dir):
            os.makedirs(d, mode=0o700, exist_ok=True)
        app.state.policy = Policy.load(
            cfg.policy_path
        )  # échec fermé : pas de politique, pas de démarrage
        app.state.executor = Executor.stub_for(list(app.state.policy.tools()))
        app.state.session_factory = make_session_factory(engine)
        app.state.providers = (
            provider_overrides
            if provider_overrides is not None
            else load_providers(cfg.config_path, os.environ)
        )
        yield
        for t in list(app.state.tasks):
            t.cancel()
        for p in app.state.providers.values():
            await p.aclose()
        engine.dispose()

    app = FastAPI(
        title="CyberAI Command Center",
        version="0.5.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = cfg
    app.state.limiter = LoginLimiter(cfg.login_max_failures, cfg.login_window_seconds)
    app.state.bus = EventBus(cfg.event_buffer)
    app.state.quota_alerts = QuotaAlertState()
    app.state.demo_state = AgentState(AGENT_ID)
    app.state.tasks = set[asyncio.Task[None]]()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(auth.router)
    app.include_router(providers.router)
    app.include_router(usage.router)
    app.include_router(agents.router)
    app.include_router(events.router)
    app.include_router(actions.router)
    app.include_router(samples.router)
    return app


app = create_app()
