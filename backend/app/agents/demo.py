"""Agent de démonstration : produit des événements pour développer le dashboard.

Ses chiffres sont SIMULÉS : `data.simulated = true`, source `demo_agent`, jamais écrits dans
`request_log` ni comptés dans `/usage/tokens` (R1). Désactivé par défaut (`DEMO_AGENT=true`).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

from app.events import EventBus

AGENT_ID = "demo"


@dataclass
class AgentState:
    id: str
    running: int = 0
    completed: int = 0
    failed: int = 0
    last_activity: float | None = None


async def run_task(bus: EventBus, state: AgentState, delay: float, fail: bool) -> None:
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    state.running += 1
    state.last_activity = time.time()
    bus.publish(
        source="demo_agent",
        agent=AGENT_ID,
        type="agent.started",
        data={"task_id": task_id, "simulated": True},
    )
    try:
        for step in (1, 2, 3):
            await asyncio.sleep(delay)
            bus.publish(
                source="demo_agent",
                agent=AGENT_ID,
                type="token.usage",
                data={
                    "task_id": task_id,
                    "simulated": True,
                    "input_tokens": {"value": 100 * step, "available": True},
                    "output_tokens": {"value": 40 * step, "available": True},
                },
            )
            if fail and step == 2:
                raise RuntimeError("échec simulé")
        state.completed += 1
        bus.publish(
            source="demo_agent",
            agent=AGENT_ID,
            type="agent.completed",
            data={"task_id": task_id, "simulated": True},
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        state.failed += 1
        bus.publish(
            source="demo_agent",
            agent=AGENT_ID,
            type="agent.failed",
            severity="medium",
            data={"task_id": task_id, "simulated": True, "error_type": type(exc).__name__},
        )
    finally:
        state.running -= 1
        state.last_activity = time.time()
