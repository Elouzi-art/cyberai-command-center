"""Quarantaine : dépôt, lecture du résultat, suppression. Jamais d'exécution ni de téléchargement.

Aucun nom de fichier fourni par l'utilisateur n'est utilisé sur le disque : tout passe par un
identifiant aléatoire. Les fichiers sont créés en 0600, sans suivre de lien symbolique.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

SAMPLE_ID_RE = re.compile(r"^smp_[0-9a-f]{16}$")
MAX_RESULT_BYTES = 262_144
_NAME_OK = re.compile(r"[^A-Za-z0-9._ -]")


class UploadError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class InvalidResult(Exception):
    pass


def new_id() -> str:
    return f"smp_{uuid.uuid4().hex[:16]}"


def safe_name(name: str) -> str:
    """Nom d'affichage : dernier segment, caractères sûrs uniquement, 128 caractères au plus."""
    base = re.split(r"[\\/]", name)[-1]
    base = _NAME_OK.sub("_", base).strip(" .")
    return base[:128] or "sample.bin"


async def store_stream(
    stream: AsyncIterator[bytes], inbox: Path, sample_id: str, limit: int
) -> tuple[str, int]:
    directory = inbox / sample_id
    directory.mkdir(mode=0o700)
    h = hashlib.sha256()
    size = 0
    try:
        fd = os.open(
            directory / "sample.bin", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(fd, "wb") as fh:
            async for chunk in stream:
                size += len(chunk)
                if size > limit:
                    raise UploadError(413, "fichier trop volumineux")
                h.update(chunk)
                fh.write(chunk)
        if size == 0:
            raise UploadError(400, "fichier vide")
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)  # jamais de reste après un échec
        raise
    return h.hexdigest(), size


def commit_job(inbox: Path, sample_id: str, sha256: str, size: int) -> None:
    """job.json est écrit EN DERNIER : l'analyseur ignore un dossier qui n'en a pas."""
    directory = inbox / sample_id
    tmp = directory / ".job.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"sample_id": sample_id, "sha256": sha256, "size": size}, fh)
    os.replace(tmp, directory / "job.json")


def read_result(outbox: Path, sample_id: str) -> dict[str, Any] | None:
    """None si pas encore de résultat ; InvalidResult si suspect (lien, taille, JSON)."""
    path = outbox / f"{sample_id}.json"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError as exc:  # lien symbolique ou autre anomalie
        raise InvalidResult("ouverture refusée") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_RESULT_BYTES:
            raise InvalidResult("fichier de résultat non conforme")
        with os.fdopen(fd, "rb", closefd=False) as fh:
            raw = fh.read(MAX_RESULT_BYTES + 1)
    finally:
        os.close(fd)
    try:
        out = json.loads(raw)
    except ValueError as exc:
        raise InvalidResult("JSON invalide") from exc
    if not isinstance(out, dict):
        raise InvalidResult("structure inattendue")
    return out


def delete_sample(inbox: Path, outbox: Path, sample_id: str) -> None:
    shutil.rmtree(inbox / sample_id, ignore_errors=True)
    (outbox / f"{sample_id}.json").unlink(missing_ok=True)
