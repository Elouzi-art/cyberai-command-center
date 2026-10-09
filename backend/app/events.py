"""Schéma d'événements unifié (schemas/event.v1.json) et bus en mémoire.

Le frontend ne dépend que de ce schéma (R3). `publish` doit être appelé depuis la boucle asyncio.
Les `data` ne contiennent jamais de prompt, de secret ni de contenu de fichier.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

Severity = Literal["info", "low", "medium", "high", "critical"]


class Event(BaseModel):
    id: str
    timestamp: str
    source: str
    agent: str
    type: str
    severity: Severity
    data: dict[str, Any]
    confidence: float | None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventBus:
    def __init__(self, size: int = 1000) -> None:
        self._buf: deque[Event] = deque(maxlen=size)
        self._subs: set[asyncio.Queue[Event]] = set()

    def publish(
        self,
        *,
        source: str,
        agent: str,
        type: str,
        severity: Severity = "info",
        data: dict[str, Any] | None = None,
        confidence: float | None = None,
    ) -> Event:
        ev = Event(
            id=f"evt_{uuid.uuid4().hex[:16]}",
            timestamp=_now(),
            source=source,
            agent=agent,
            type=type,
            severity=severity,
            data=data or {},
            confidence=confidence,
        )
        self._buf.append(ev)
        for q in self._subs:
            if q.full():  # consommateur lent : on perd le plus ancien, jamais le producteur
                q.get_nowait()
            q.put_nowait(ev)
        return ev

    def recent(self, limit: int = 100, type_prefix: str | None = None) -> list[Event]:
        items = [e for e in self._buf if type_prefix is None or e.type.startswith(type_prefix)]
        return items[-limit:] if limit > 0 else []

    def subscribe(self, maxsize: int = 100) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subs.discard(q)
