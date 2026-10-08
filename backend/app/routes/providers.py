from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.audit import audit
from app.deps import DbDep, csrf_guard, require_role
from app.models import RequestLog, User
from app.providers import ProviderError

router = APIRouter(prefix="/providers", tags=["providers"])
Viewer = Annotated[User, Depends(require_role("viewer"))]
Analyst = Annotated[User, Depends(require_role("analyst"))]


class CompleteIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    # Sensibilité des données : le provider doit l'avoir déclarée dans sa configuration.
    sensitivity: Literal["public", "internal", "confidential"] = "confidential"
    agent: str = Field(default="manual", max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")


@router.get("")
def list_providers(request: Request, _user: Viewer) -> list[dict[str, object]]:
    """Ne renvoie ni URL, ni clé, ni secret (R2)."""
    return [
        {
            "id": p.id,
            "model": p.model,
            "data_sensitivity": list(p.data_sensitivity),
            "metrics": p.metrics().model_dump(),
        }
        for p in request.app.state.providers.values()
    ]


@router.post("/{provider_id}/complete", dependencies=[Depends(csrf_guard)])
async def complete(
    provider_id: str, body: CompleteIn, request: Request, db: DbDep, user: Analyst
) -> dict[str, object]:
    provider = request.app.state.providers.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="provider inconnu")
    if body.sensitivity not in provider.data_sensitivity:
        audit(
            db,
            user.username,
            "provider_refused_sensitivity",
            provider=provider_id,
            sensitivity=body.sensitivity,
        )
        raise HTTPException(status_code=403, detail="données non autorisées pour ce provider")
    try:
        result = await provider.complete(body.prompt)
    except ProviderError as exc:
        db.add(
            RequestLog(
                provider=provider.id,
                model=provider.model,
                agent=body.agent,
                latency_ms=exc.latency_ms,
                status="error",
                error_type=exc.error_type,
            )
        )
        db.commit()
        raise HTTPException(status_code=502, detail="erreur du fournisseur") from None
    db.add(
        RequestLog(
            provider=provider.id,
            model=provider.model,
            agent=body.agent,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            latency_ms=result.latency_ms,
            status="success",
        )
    )
    db.commit()
    audit(
        db,
        user.username,
        "provider_request",
        provider=provider_id,
        agent=body.agent,
        sensitivity=body.sensitivity,
    )  # jamais le prompt
    return {
        "text": result.text,
        "provider": result.provider,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "input_tokens": {
            "value": result.input_tokens,
            "available": result.input_tokens is not None,
        },
        "output_tokens": {
            "value": result.output_tokens,
            "available": result.output_tokens is not None,
        },
    }
