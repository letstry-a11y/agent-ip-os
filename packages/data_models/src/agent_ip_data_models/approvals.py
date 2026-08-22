"""Versioned schemas for the M1-06 approval API and console."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from agent_ip_data_models.core import (
    ApprovalDecision,
    AwareDatetime,
    FrozenBoundaryModel,
    NonEmptyText,
    Sha256Hex,
)
from agent_ip_data_models.hashing import ApprovalInvalidationReason


class ApprovalActorType(StrEnum):
    """Identity types visible at the approval boundary."""

    HUMAN = "HUMAN"
    SERVICE = "SERVICE"
    AGENT = "AGENT"


class ApprovalRequestStatus(StrEnum):
    """Mutable resolution state of one approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ApprovalRiskLevel(StrEnum):
    """Risk route presented to the human reviewer."""

    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class ApprovalActorV1(FrozenBoundaryModel):
    """Server-resolved actor; decision bodies never contain these fields."""

    schema_version: Literal[1] = 1
    subject_id: UUID
    actor_type: ApprovalActorType
    roles: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    project_ids: Annotated[tuple[UUID, ...], Field(min_length=1)]


class ApprovalDecisionCommandV1(FrozenBoundaryModel):
    """Compare-and-swap human decision input."""

    schema_version: Literal[1] = 1
    # FastAPI has already decoded JSON into Python values before validation; allow the
    # wire-format enum string while retaining strict validation for every other field.
    decision: ApprovalDecision = Field(strict=False)
    expected_version: int = Field(ge=0)


class ApprovalBindingViewV1(FrozenBoundaryModel):
    """Exact hashes and versions reviewed by the human."""

    schema_version: Literal[1] = 1
    candidate_hash: Sha256Hex
    fact_report_hash: Sha256Hex
    rights_manifest_hash: Sha256Hex
    risk_report_hash: Sha256Hex
    account_hash: Sha256Hex
    policy_version: NonEmptyText


class ApprovalCandidateViewV1(FrozenBoundaryModel):
    """Human-readable immutable candidate shown beside the hashes."""

    schema_version: Literal[1] = 1
    candidate_id: UUID
    account_id: UUID
    platform: NonEmptyText
    title: NonEmptyText
    caption: str
    normalized_tags: tuple[NonEmptyText, ...]
    ai_disclosure: NonEmptyText


class ApprovalRequestViewV1(FrozenBoundaryModel):
    """Complete approval page payload with identity and validity evidence."""

    schema_version: Literal[1] = 1
    approval_request_id: UUID
    project_id: UUID
    status: ApprovalRequestStatus
    state_version: int = Field(ge=0)
    candidate_state: NonEmptyText
    candidate_state_version: int = Field(ge=0)
    risk_level: ApprovalRiskLevel
    requested_action: NonEmptyText
    required_approvals: int = Field(ge=1, le=2)
    requested_by_subject_id: UUID
    viewer_subject_id: UUID
    expires_at: AwareDatetime
    created_at: AwareDatetime
    candidate: ApprovalCandidateViewV1
    binding: ApprovalBindingViewV1
    snapshot_hash: Sha256Hex | None = None
    decided_at: AwareDatetime | None = None
    approver_subject_ids: tuple[UUID, ...] = ()
    approval_valid: bool | None = None
    invalidation_reasons: tuple[ApprovalInvalidationReason, ...] = ()
