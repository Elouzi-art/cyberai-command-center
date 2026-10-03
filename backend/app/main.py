from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

app = FastAPI(title="CyberAI Command Center", version="0.1.0", docs_url=None, redoc_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)


@app.get("/agents")
def agents() -> list[dict[str, str]]:
    return []  # Sprint 1+ : Agent Manager


@app.get("/providers")
def providers() -> list[dict[str, str]]:
    return []  # Sprint 1+ : registre de providers
