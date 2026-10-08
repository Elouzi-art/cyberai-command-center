from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.providers import AIProvider, RawResult
from app.security import hash_password

PASSWORD = "correct-horse-battery"


class FakeProvider(AIProvider):
    def __init__(self, raw: RawResult | Exception, sens: tuple[str, ...] = ("public",)) -> None:
        super().__init__("fake", "fake-model", sens)
        self._raw = raw

    async def _call(self, prompt: str) -> RawResult:
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


@pytest.fixture
def make_client() -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def _make(providers: dict[str, AIProvider] | None = None, **overrides: object) -> TestClient:
        settings = Settings(database_url="sqlite://", cookie_secure=False, **overrides)  # type: ignore[arg-type]
        client = TestClient(create_app(settings, providers if providers is not None else {}))
        client.__enter__()
        clients.append(client)
        for name, role in (("vic", "viewer"), ("ana", "analyst"), ("root", "admin")):
            with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
                db.add(User(username=name, password_hash=hash_password(PASSWORD), role=role))
                db.commit()
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


def login(client: TestClient, username: str, password: str = PASSWORD) -> int:
    return client.post("/auth/login", json={"username": username, "password": password}).status_code
