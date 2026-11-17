"""Lightweight liveness-only ASGI app; no trading session is constructed."""
from fastapi import FastAPI
from . import HEALTH_RESPONSE

app = FastAPI(
    title="Crypto Paper Lab API — Liveness",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

@app.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    return dict(HEALTH_RESPONSE)
