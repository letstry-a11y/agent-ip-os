"""Minimal control-plane application for the M0 engineering baseline."""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable health response used by local and CI smoke checks."""

    status: str
    service: str
    external_side_effects_enabled: bool


app = FastAPI(
    title="Agent IP OS API",
    summary="Auditable control plane for the Agent IP OS MVP",
    version="0.0.1",
)


@app.get("/healthz", response_model=HealthResponse, tags=["operations"])
async def health() -> HealthResponse:
    """Report process health without inspecting or exposing credentials."""

    return HealthResponse(
        status="ok",
        service="agent-ip-api",
        external_side_effects_enabled=False,
    )
