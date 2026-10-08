from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, actor: str, action: str, **detail: object) -> None:
    """R9 : décision sensible tracée. Ne jamais passer de secret ni de prompt dans `detail`."""
    db.add(AuditLog(actor=actor[:64], action=action[:64], detail=json.dumps(detail, default=str)))
    db.commit()
