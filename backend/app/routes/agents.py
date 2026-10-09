from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.agents.demo import AGENT_ID, run_task
from app.deps import csrf_guard, require_role
from app.models import User

router = APIRouter(prefix="/agents", tags=["agents"])
Viewer = Annotated[User, Depends(require_role("viewer"))]
Analyst = Annotated[User, Depends(require_role("analyst"))]


class DemoRunIn(BaseModel):
    fail: bool = False


@router.get("")
def list_agents(request: Request, _user: Viewer) -> list[dict[str, object]]:
    if not request.app.state.settings.demo_agent_enabled:
        return []
    st = request.app.state.demo_state
    last = (
        datetime.fromtimestamp(st.last_activity, UTC).isoformat(timespec="seconds")
        if st.last_activity
        else None
    )
    return [
        {
            "id": AGENT_ID,
            "simulated": True,
            "status": "running" if st.running else "idle",
            "tasks_running": st.running,
            "tasks_completed": st.completed,
            "tasks_failed": st.failed,
            "last_activity": {"value": last, "available": last is not None},
        }
    ]


@router.post("/demo/run", status_code=202, dependencies=[Depends(csrf_guard)])
async def run_demo(body: DemoRunIn, request: Request, _user: Analyst) -> dict[str, str]:
    app = request.app
    if not app.state.settings.demo_agent_enabled:
        raise HTTPException(status_code=404, detail="agent de démonstration désactivé")
    task = asyncio.create_task(
        run_task(app.state.bus, app.state.demo_state, app.state.settings.demo_step_delay, body.fail)
    )
    app.state.tasks.add(task)  # référence forte : évite la collecte du task
    task.add_done_callback(app.state.tasks.discard)
    return {"status": "started"}
