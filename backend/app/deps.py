from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import SessionRow, User, utcnow
from app.security import ROLE_RANK, hash_token

COOKIE = "session"


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as db:
        yield db


DbDep = Annotated[Session, Depends(get_db)]


def user_from_token(db: Session, token: str | None) -> User | None:
    """Résout un jeton de session en utilisateur (HTTP et WebSocket partagent cette logique)."""
    if not token:
        return None
    row = db.get(SessionRow, hash_token(token))
    if row is None:
        return None
    if row.expires_at < utcnow():
        db.delete(row)
        db.commit()
        return None
    return db.get(User, row.user_id)


def current_user(request: Request, db: DbDep) -> User:
    user = user_from_token(db, request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="authentification requise")
    return user


UserDep = Annotated[User, Depends(current_user)]


def require_role(minimum: str) -> Callable[[User], User]:
    def dep(user: UserDep) -> User:
        if ROLE_RANK.get(user.role, 0) < ROLE_RANK[minimum]:
            raise HTTPException(status_code=403, detail="droits insuffisants")
        return user

    return dep


def csrf_guard(request: Request) -> None:
    """Défense en profondeur (cookie SameSite=Strict déjà posé) : refuse un Origin inconnu."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in request.app.state.settings.allowed_origins:
        raise HTTPException(status_code=403, detail="origine refusée")
