"""M1 versioned schemas shared by applications and workflow packages."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, StringConstraints


def require_aware_datetime(value: datetime) -> datetime:
    """Reject host-local timestamps whose UTC offset is unknown."""

    if value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(require_aware_datetime)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class FrozenBoundaryModel(BaseModel):
    """Strict immutable base for durable public payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ContentState(StrEnum):
    """Persisted parent states; explanatory ACTIVE is intentionally absent."""

    PLANNED = "PLANNED"
    RESEARCHING = "RESEARCHING"
    BRIEF_READY = "BRIEF_READY"
    DRAFTING = "DRAFTING"
    CREATIVE_QA = "CREATIVE_QA"
    ASSET_GENERATION = "ASSET_GENERATION"
    MEDIA_ASSEMBLY = "MEDIA_ASSEMBLY"
    PLATFORM_ADAPTATION = "PLATFORM_ADAPTATION"
    CANDIDATES_ACTIVE = "CANDIDATES_ACTIVE"
    LEARNING = "LEARNING"
    ARCHIVED = "ARCHIVED"
    RETRY_WAIT = "RETRY_WAIT"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"
    CANCELLED = "CANCELLED"


class CandidateState(StrEnum):
    """Persisted child states for API and workflow boundaries."""

    CANDIDATE_FROZEN = "CANDIDATE_FROZEN"
    FACT_CHECK = "FACT_CHECK"
    RIGHTS_CHECK = "RIGHTS_CHECK"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    RISK_ROUTING = "RISK_ROUTING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REJECTED = "REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    READY_TO_INTENT = "READY_TO_INTENT"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    PUBLISH_FAILED = "PUBLISH_FAILED"
    PACKAGE_READY = "PACKAGE_READY"
    PACKAGE_DELIVERED = "PACKAGE_DELIVERED"
    MANUAL_RECONCILIATION = "MANUAL_RECONCILIATION"
    CLOSED_UNPUBLISHED = "CLOSED_UNPUBLISHED"
    MONITORING = "MONITORING"
    QUARANTINED = "QUARANTINED"
    TAKEDOWN_PENDING = "TAKEDOWN_PENDING"
    REMOVED = "REMOVED"
    TAKEDOWN_FAILED = "TAKEDOWN_FAILED"
    APPEALED = "APPEALED"


class RightsStatus(StrEnum):
    """Authoritative rights outcomes."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class ApprovalDecision(StrEnum):
    """Human resolution captured by an immutable snapshot."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class ContentUnitV1(FrozenBoundaryModel):
    """Versioned view of mutable parent lifecycle state."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    state: ContentState
    state_version: int = Field(ge=0)
    current_content_version: int = Field(ge=0)
    trace_id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ContentVersionV1(FrozenBoundaryModel):
    """Immutable structured content revision."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    content_unit_id: UUID
    version: int = Field(gt=0)
    payload: dict[str, JsonValue]
    content_hash: Sha256Hex
    created_by_subject_id: UUID
    created_at: AwareDatetime


class ArtifactV1(FrozenBoundaryModel):
    """Immutable object-storage metadata; never contains asset bytes."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    content_unit_id: UUID | None = None
    object_key: NonEmptyText
    object_version: NonEmptyText
    media_type: NonEmptyText
    byte_size: int = Field(ge=0)
    sha256: Sha256Hex
    rights_status: RightsStatus
    created_at: AwareDatetime


class AssetRightV1(FrozenBoundaryModel):
    """Authoritative right attached to one immutable artifact."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    artifact_id: UUID
    consent_grant_id: UUID | None = None
    status: RightsStatus
    rights_type: NonEmptyText
    scope: dict[str, JsonValue]
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    evidence_artifact_id: UUID


class PlatformCandidateV1(FrozenBoundaryModel):
    """Frozen, platform/account/policy-specific publish payload."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    content_unit_id: UUID
    content_version_id: UUID
    account_id: UUID
    platform: NonEmptyText
    title: NonEmptyText
    caption: str
    normalized_tags: tuple[NonEmptyText, ...]
    ordered_artifact_ids: tuple[UUID, ...]
    ai_disclosure: NonEmptyText
    scheduled_at: AwareDatetime | None = None
    schedule_time_zone: NonEmptyText | None = None
    policy_version: NonEmptyText
    canonical_payload: dict[str, JsonValue]
    candidate_hash: Sha256Hex
    created_at: AwareDatetime


class ApprovalSnapshotV1(FrozenBoundaryModel):
    """Immutable human decision bound to candidate and verification hashes."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    approval_request_id: UUID
    candidate_id: UUID
    account_id: UUID
    decision: ApprovalDecision
    candidate_hash: Sha256Hex
    fact_report_hash: Sha256Hex
    rights_manifest_hash: Sha256Hex
    risk_report_hash: Sha256Hex
    account_hash: Sha256Hex
    policy_version: NonEmptyText
    approved_action: NonEmptyText
    approver_subject_ids: tuple[UUID, ...] = Field(min_length=1, max_length=2)
    expires_at: AwareDatetime
    decided_at: AwareDatetime
    snapshot_hash: Sha256Hex


class PublishIntentV1(FrozenBoundaryModel):
    """Immutable approved logical external action."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    candidate_id: UUID
    approval_snapshot_id: UUID
    account_id: UUID
    outbox_message_id: UUID
    request_fingerprint: Sha256Hex
    normalized_schedule_slot: AwareDatetime
    repost_of_intent_id: UUID | None = None
    repost_reason: NonEmptyText | None = None
    created_at: AwareDatetime


class OutboxMessageV1(FrozenBoundaryModel):
    """Transactional message created together with a publish intent."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    publish_intent_id: UUID
    topic: NonEmptyText
    payload: dict[str, JsonValue]
    occurred_at: AwareDatetime
    available_at: AwareDatetime


class AuditEventV1(FrozenBoundaryModel):
    """Append-only audit event with a per-project hash-chain link."""

    schema_version: Literal[1] = 1
    id: UUID
    project_id: UUID
    actor_type: Literal["HUMAN", "SERVICE", "AGENT"]
    actor_id: UUID
    action: NonEmptyText
    resource_type: NonEmptyText
    resource_id: UUID | None = None
    trace_id: UUID
    payload: dict[str, JsonValue]
    previous_event_hash: Sha256Hex | None = None
    event_hash: Sha256Hex
    occurred_at: AwareDatetime
