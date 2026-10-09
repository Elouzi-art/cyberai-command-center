from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket
from pydantic import BaseModel

from app.deps import COOKIE, require_role, user_from_token
from app.events import Event
from app.models import User

router = APIRouter(tags=["events"])
Viewer = Annotated[User, Depends(require_role("viewer"))]


class EventsOut(BaseModel):
    events: list[Event]


@router.get("/events")
def list_events(
    _user: Viewer,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    type: Annotated[str | None, Query(max_length=64)] = None,
) -> EventsOut:
    return EventsOut(events=request.app.state.bus.recent(limit, type))


def _session_valid(ws: WebSocket) -> bool:
    with ws.app.state.session_factory() as db:
        return user_from_token(db, ws.cookies.get(COOKIE)) is not None


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket, replay: Annotated[int, Query(ge=0, le=200)] = 0) -> None:
    settings = ws.app.state.settings
    origin = ws.headers.get("origin")
    # Anti Cross-Site WebSocket Hijacking : un navigateur envoie toujours Origin.
    if origin is not None and origin not in settings.allowed_origins:
        await ws.close(code=1008)
        return
    if not _session_valid(ws):
        await ws.close(code=1008)
        return
    bus = ws.app.state.bus
    await ws.accept()
    queue = bus.subscribe()
    for ev in bus.recent(replay):
        await ws.send_json(ev.model_dump())
    recv = asyncio.create_task(ws.receive())
    get = asyncio.create_task(queue.get())
    try:
        while True:
            done, _ = await asyncio.wait(
                {recv, get},
                timeout=settings.ws_recheck_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                if not _session_valid(ws):  # session expirée ou révoquée : on coupe le flux
                    await ws.close(code=1008)
                    return
                continue
            if recv in done:
                if recv.result()["type"] == "websocket.disconnect":
                    return
                recv = asyncio.create_task(ws.receive())
            if get in done:
                await ws.send_json(get.result().model_dump())
                get = asyncio.create_task(queue.get())
    except Exception:  # noqa: BLE001 - client parti : on nettoie
        return
    finally:
        recv.cancel()
        get.cancel()
        bus.unsubscribe(queue)
