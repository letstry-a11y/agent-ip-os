"""Versioned provider-neutral contracts for text and media generation."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from agent_ip_data_models.core import (
    AwareDatetime,
    FrozenBoundaryModel,
    NonEmptyText,
    Sha256Hex,
)


class ProviderKind(StrEnum):
    """Provider families supported by the narrow MVP."""

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class ProviderJobStatus(StrEnum):
    """Portable asynchronous job states."""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ProviderErrorCode(StrEnum):
    """Stable error taxonomy used for retry and escalation decisions."""

    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    AUTHORIZATION = "AUTHORIZATION"
    CONTENT_POLICY = "CONTENT_POLICY"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    TRANSIENT = "TRANSIENT"
    CANCELLED = "CANCELLED"
    INTERNAL = "INTERNAL"


class ProviderRequestV1(FrozenBoundaryModel):
    """One provider-neutral request with an explicit cost and timeout envelope."""

    schema_version: Literal[1] = 1
    request_id: UUID
    trace_id: UUID
    provider_kind: ProviderKind
    operation: NonEmptyText
    input: dict[str, JsonValue]
    requested_model: NonEmptyText | None = None
    source_ids: tuple[UUID, ...] = ()
    timeout_seconds: int = Field(gt=0, le=3_600)
    max_cost_microunits: int = Field(ge=0)


class ProviderUsageV1(FrozenBoundaryModel):
    """Usage and cost values returned for every accepted provider job."""

    schema_version: Literal[1] = 1
    input_units: int = Field(ge=0)
    output_units: int = Field(ge=0)
    cost_microunits: int = Field(ge=0)
    currency: Literal["CNY", "USD"]


class ProviderRateLimitV1(FrozenBoundaryModel):
    """Portable snapshot of the provider's current request limit."""

    schema_version: Literal[1] = 1
    limit: int = Field(gt=0)
    remaining: int = Field(ge=0)
    reset_at: AwareDatetime

    @model_validator(mode="after")
    def remaining_does_not_exceed_limit(self) -> ProviderRateLimitV1:
        """Reject contradictory rate-limit evidence."""

        if self.remaining > self.limit:
            raise ValueError("remaining must not exceed limit")
        return self


class ProviderProvenanceV1(FrozenBoundaryModel):
    """Durable provider/model/source evidence without credentials or conversation IDs."""

    schema_version: Literal[1] = 1
    provider_id: NonEmptyText
    model_id: NonEmptyText
    model_version: NonEmptyText
    request_hash: Sha256Hex
    source_ids: tuple[UUID, ...] = ()
    content_credential: NonEmptyText | None = None
    synthetic: bool


class ProviderFailureV1(FrozenBoundaryModel):
    """Structured failure evidence suitable for retry policy decisions."""

    schema_version: Literal[1] = 1
    code: ProviderErrorCode
    message: NonEmptyText
    retryable: bool
    request_accepted: bool
    retry_after_seconds: int | None = Field(default=None, ge=0)
    usage: ProviderUsageV1 | None = None
    rate_limit: ProviderRateLimitV1 | None = None


class ProviderJobV1(FrozenBoundaryModel):
    """Asynchronous provider job snapshot returned by submit, status, and cancel."""

    schema_version: Literal[1] = 1
    job_id: UUID
    request_id: UUID
    trace_id: UUID
    provider_kind: ProviderKind
    status: ProviderJobStatus
    output: dict[str, JsonValue] | None = None
    output_hash: Sha256Hex | None = None
    failure: ProviderFailureV1 | None = None
    usage: ProviderUsageV1
    provenance: ProviderProvenanceV1
    rate_limit: ProviderRateLimitV1
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def terminal_evidence_is_consistent(self) -> ProviderJobV1:
        """Require success output or failure evidence only in matching terminal states."""

        if self.status is ProviderJobStatus.SUCCEEDED:
            if self.output is None or self.output_hash is None or self.failure is not None:
                raise ValueError("successful job requires output/hash and no failure")
        elif self.status is ProviderJobStatus.FAILED:
            if self.failure is None or self.output is not None or self.output_hash is not None:
                raise ValueError("failed job requires failure and no output/hash")
        elif self.output is not None or self.output_hash is not None or self.failure is not None:
            raise ValueError("non-result job cannot contain output, hash, or failure")
        return self
