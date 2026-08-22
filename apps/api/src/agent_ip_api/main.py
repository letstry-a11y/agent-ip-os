"""Local-first control-plane API with external side effects disabled."""

from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID

from agent_ip_data_models import (
    ApprovalActorType,
    ApprovalActorV1,
    ApprovalDecisionCommandV1,
    ApprovalRequestViewV1,
)
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from agent_ip_api.approval import (
    ApprovalConflict,
    ApprovalForbidden,
    ApprovalNotFound,
    ApprovalServiceError,
    PostgresApprovalService,
)


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


def get_approval_service() -> PostgresApprovalService:
    """Build the service only when an approval route is requested."""

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "approval_database_unavailable",
                "message": "database is not configured",
            },
        )
    return PostgresApprovalService(database_url)


def get_current_approval_actor() -> ApprovalActorV1:
    """Resolve the explicitly enabled local Mock human; never trust decision body identity."""

    if os.environ.get("APPROVAL_MOCK_MODE", "").lower() != "true":
        raise HTTPException(
            status_code=503,
            detail={"code": "approval_identity_disabled", "message": "Mock identity is disabled"},
        )
    try:
        subject_id = UUID(os.environ["APPROVAL_MOCK_SUBJECT_ID"])
        project_id = UUID(os.environ["APPROVAL_MOCK_PROJECT_ID"])
    except (KeyError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "approval_identity_invalid", "message": "Mock identity is invalid"},
        ) from error
    return ApprovalActorV1(
        subject_id=subject_id,
        actor_type=ApprovalActorType.HUMAN,
        roles=("APPROVER",),
        project_ids=(project_id,),
    )


ApprovalServiceDependency = Annotated[PostgresApprovalService, Depends(get_approval_service)]
ApprovalActorDependency = Annotated[ApprovalActorV1, Depends(get_current_approval_actor)]


def _approval_http_error(error: ApprovalServiceError) -> HTTPException:
    status_code = 409
    if isinstance(error, ApprovalNotFound):
        status_code = 404
    elif isinstance(error, ApprovalForbidden):
        status_code = 403
    elif not isinstance(error, ApprovalConflict):
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


@app.get(
    "/api/v1/projects/{project_id}/approvals/{approval_request_id}",
    response_model=ApprovalRequestViewV1,
    tags=["approvals"],
)
def get_approval_request(
    project_id: UUID,
    approval_request_id: UUID,
    service: ApprovalServiceDependency,
    actor: ApprovalActorDependency,
) -> ApprovalRequestViewV1:
    """Inspect the exact candidate, bindings, actor, and validity."""

    try:
        return service.get_request(actor, project_id, approval_request_id)
    except ApprovalServiceError as error:
        raise _approval_http_error(error) from error


@app.post(
    "/api/v1/projects/{project_id}/approvals/{approval_request_id}/decisions",
    response_model=ApprovalRequestViewV1,
    tags=["approvals"],
)
def decide_approval_request(
    project_id: UUID,
    approval_request_id: UUID,
    command: ApprovalDecisionCommandV1,
    service: ApprovalServiceDependency,
    actor: ApprovalActorDependency,
) -> ApprovalRequestViewV1:
    """Resolve one pending request with server-side human identity and CAS."""

    try:
        return service.decide(actor, project_id, approval_request_id, command)
    except ApprovalServiceError as error:
        raise _approval_http_error(error) from error
