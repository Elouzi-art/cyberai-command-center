"""Les erreurs de validation (422) ne renvoient jamais la valeur saisie (mot de passe, contenu)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import login

Make = Callable[..., TestClient]
MARK = "VALEUR-SECRETE-123"


def test_login_422_never_echoes_the_password(make_client: Make) -> None:
    c = make_client()
    r = c.post("/auth/login", json={"username": "admin", "password": MARK + "x" * 300})
    assert r.status_code == 422
    assert MARK not in r.text and '"input"' not in r.text and '"ctx"' not in r.text
    assert r.json()["detail"][0]["loc"] == ["body", "password"]


def test_login_422_error_shape_is_stable_and_minimal(make_client: Make) -> None:
    c = make_client()
    detail = c.post("/auth/login", json={"username": "", "password": ""}).json()["detail"]
    assert {frozenset(e) for e in detail} == {frozenset({"loc", "msg", "type"})}
    assert {e["loc"][-1] for e in detail} == {"username", "password"}


def test_forbidden_extra_field_value_is_not_echoed(make_client: Make) -> None:
    c = make_client()
    login(c, "ana")
    r = c.post("/actions", json={"tool": "net.scan", "risk_level": MARK})
    assert r.status_code == 422 and MARK not in r.text


@pytest.mark.parametrize(
    "path", [f"/samples?limit={MARK}", f"/events?limit={MARK}", f"/actions?status={MARK}"]
)
def test_query_parameter_values_are_not_echoed(make_client: Make, path: str) -> None:
    c = make_client()
    login(c, "root")
    r = c.get(path)
    assert r.status_code == 422 and MARK not in r.text


def test_other_errors_are_unchanged(make_client: Make) -> None:
    c = make_client()
    assert c.post("/auth/login", json={"username": "a", "password": "b"}).status_code == 401
    assert c.get("/providers").status_code == 401
    assert c.get("/nexiste-pas").status_code == 404
