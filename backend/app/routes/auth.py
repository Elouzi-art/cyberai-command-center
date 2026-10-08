from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.audit import audit
from app.deps import COOKIE, DbDep, UserDep, csrf_guard
from app.models import SessionRow, User, utcnow
from app.security import DUMMY_HASH, hash_token, new_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login", dependencies=[Depends(csrf_guard)])
def login(body: LoginIn, request: Request, response: Response, db: DbDep) -> dict[str, str]:
    settings = request.app.state.settings
    limiter = request.app.state.limiter
    ip = request.client.host if request.client else "?"
    key = f"{body.username.lower()}|{ip}"
    if limiter.blocked(key):
        audit(db, body.username, "login_blocked", ip=ip)
        raise HTTPException(status_code=429, detail="trop de tentatives")
    user = db.query(User).filter(User.username == body.username).one_or_none()
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if user is None or not ok:
        limiter.fail(key)
        audit(db, body.username, "login_failed", ip=ip)
        raise HTTPException(status_code=401, detail="identifiants invalides")
    limiter.reset(key)
    token = new_token()
    ttl = timedelta(minutes=settings.session_ttl_minutes)
    db.add(SessionRow(token_hash=hash_token(token), user_id=user.id, expires_at=utcnow() + ttl))
    db.commit()
    audit(db, user.username, "login_ok", ip=ip)
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )
    return {"username": user.username, "role": user.role}


@router.post("/logout", dependencies=[Depends(csrf_guard)])
def logout(request: Request, response: Response, db: DbDep) -> dict[str, str]:
    token = request.cookies.get(COOKIE)
    if token and (row := db.get(SessionRow, hash_token(token))):
        db.delete(row)
        db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"status": "ok"}


@router.get("/me")
def me(user: UserDep) -> dict[str, str]:
    return {"username": user.username, "role": user.role}
