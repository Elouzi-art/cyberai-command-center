from pathlib import Path

import pytest

from app import cli
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.models import User


def test_create_user_via_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = f"sqlite:///{tmp_path / 'a.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _p="": "a-long-enough-pass")
    assert cli.main(["create-user", "alice", "analyst"]) == 0
    assert cli.main(["create-user", "alice", "analyst"]) == 1  # doublon refusé
    with make_session_factory(make_engine(Settings.from_env().database_url))() as db:
        u = db.query(User).one()
        assert u.role == "analyst" and u.password_hash.startswith("$argon2")


def test_short_password_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'b.db'}")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _p="": "short")
    assert cli.main(["create-user", "bob", "viewer"]) == 1
