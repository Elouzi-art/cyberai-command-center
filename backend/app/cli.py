"""Création d'un utilisateur : `python -m app.cli create-user <nom> <viewer|analyst|admin>`.

Aucun compte par défaut n'existe : pas d'identifiants connus à changer (R2).
"""

from __future__ import annotations

import getpass
import sys

from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.models import User
from app.security import ROLE_RANK, hash_password

MIN_LEN = 12


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] != "create-user" or argv[2] not in ROLE_RANK:
        print("usage: python -m app.cli create-user <username> <viewer|analyst|admin>")
        return 2
    username, role = argv[1], argv[2]
    password = getpass.getpass("Mot de passe (12 caractères min.) : ")
    if len(password) < MIN_LEN or password != getpass.getpass("Confirmer : "):
        print("mot de passe trop court ou différent")
        return 1
    engine = make_engine(Settings.from_env().database_url)
    init_db(engine)
    with make_session_factory(engine)() as db:
        if db.query(User).filter(User.username == username).first():
            print("utilisateur déjà existant")
            return 1
        db.add(User(username=username, password_hash=hash_password(password), role=role))
        db.commit()
    print(f"utilisateur {username} ({role}) créé")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
