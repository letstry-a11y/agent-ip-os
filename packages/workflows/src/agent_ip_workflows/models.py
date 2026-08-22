"""Serialization-safe Temporal workflow and Activity inputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PublishOutcome(StrEnum):
    """Deterministic Mock outcome returned by the platform boundary."""

    SUCCEEDED = "SUCCEEDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IntentCommand:
    """All values required to atomically create an approved intent and outbox row."""

    project_id: str
    candidate_id: str
    approval_snapshot_id: str
    account_id: str
    intent_id: str
    outbox_id: str
    request_fingerprint: str
    normalized_schedule_slot: str


@dataclass(frozen=True)
class ApprovalResolution:
    """One authorized human decision delivered to a waiting child workflow."""

    decision: str
    intent: IntentCommand | None = None
    publish_outcome: PublishOutcome = PublishOutcome.SUCCEEDED


@dataclass(frozen=True)
class CandidateWorkflowInput:
    """Stable identity and current persisted version of one platform candidate."""

    project_id: str
    candidate_id: str
    state_version: int = 0
    approval_timeout_seconds: int = 86_400


@dataclass(frozen=True)
class ContentWorkflowInput:
    """Parent content identity and independently progressing platform children."""

    project_id: str
    content_unit_id: str
    candidates: tuple[CandidateWorkflowInput, ...]
    state_version: int = 0


@dataclass(frozen=True)
class StateTransition:
    """Compare-and-swap state update performed outside deterministic workflow code."""

    project_id: str
    resource_id: str
    expected_version: int
    target_state: str


@dataclass(frozen=True)
class CandidateWorkflowResult:
    """Terminal or monitorable outcome of one child workflow."""

    candidate_id: str
    final_state: str
    state_version: int


@dataclass(frozen=True)
class ContentWorkflowResult:
    """Parent result preserving every child outcome rather than flattening success."""

    content_unit_id: str
    final_state: str
    state_version: int
    children: tuple[CandidateWorkflowResult, ...]
