from collections.abc import Callable

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import PASSWORD, POLICY, login


def test_login_ok_sets_hardened_cookie(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    r = c.post("/auth/login", json={"username": "ana", "password": PASSWORD})
    assert r.status_code == 200 and r.json() == {"username": "ana", "role": "analyst"}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert c.get("/auth/me").json()["username"] == "ana"


def test_secure_flag_by_default() -> None:
    with TestClient(create_app(Settings(database_url="sqlite://", policy_path=POLICY))) as c:
        with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
            from app.models import User
            from app.security import hash_password

            db.add(User(username="u", password_hash=hash_password(PASSWORD), role="viewer"))
            db.commit()
        r = c.post("/auth/login", json={"username": "u", "password": PASSWORD})
        assert "secure" in r.headers["set-cookie"].lower()


def test_wrong_password_and_unknown_user_look_identical(
    make_client: Callable[..., TestClient],
) -> None:
    c = make_client()
    a = c.post("/auth/login", json={"username": "ana", "password": "wrong"})
    b = c.post("/auth/login", json={"username": "ghost", "password": "wrong"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_bruteforce_is_throttled(make_client: Callable[..., TestClient]) -> None:
    c = make_client(login_max_failures=3)
    for _ in range(3):
        assert login(c, "ana", "bad") == 401
    assert login(c, "ana", PASSWORD) == 429  # même le bon mot de passe est refusé


def test_logout_invalidates_session(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    login(c, "vic")
    c.post("/auth/logout")
    assert c.get("/auth/me").status_code == 401


def test_foreign_origin_rejected(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    r = c.post(
        "/auth/login",
        json={"username": "vic", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_passwords_never_stored_in_clear(make_client: Callable[..., TestClient]) -> None:
    c = make_client()
    from app.models import User

    with c.app.state.session_factory() as db:  # type: ignore[attr-defined]
        for u in db.query(User).all():
            assert PASSWORD not in u.password_hash and u.password_hash.startswith("$argon2")
