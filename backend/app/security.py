from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ROLE_RANK = {"viewer": 1, "analyst": 2, "admin": 3}
_ph = PasswordHasher()
# Hash factice : égalise le temps de réponse quand l'utilisateur n'existe pas.
DUMMY_HASH = _ph.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Seul le hash du jeton de session est stocké en base."""
    return hashlib.sha256(token.encode()).hexdigest()
