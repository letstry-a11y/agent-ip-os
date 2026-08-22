"""Versioned schemas for deterministic, network-free M1 Mock boundaries."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue

from agent_ip_data_models.core import FrozenBoundaryModel, Sha256Hex


class MockBoundary(StrEnum):
    """The three external-shaped boundaries exercised before real integrations exist."""

    AGENT = "AGENT"
    MEDIA = "MEDIA"
    PLATFORM = "PLATFORM"


class MockScenario(StrEnum):
    """Deterministic success and failure modes used by the M1 fault matrix."""

    SUCCESS = "SUCCESS"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    TIMEOUT = "TIMEOUT"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    CANCELLED = "CANCELLED"
    LOST_RESPONSE = "LOST_RESPONSE"


class MockUsageV1(FrozenBoundaryModel):
    """Integer usage and cost data suitable for later aggregation."""

    schema_version: Literal[1] = 1
    input_units: int = Field(ge=0)
    output_units: int = Field(ge=0)
    cost_microunits: int = Field(ge=0)
    currency: Literal["USD"] = "USD"


class MockRequestV1(FrozenBoundaryModel):
    """One deterministic Mock invocation."""

    schema_version: Literal[1] = 1
    invocation_id: UUID
    trace_id: UUID
    boundary: MockBoundary
    scenario: MockScenario
    payload: dict[str, JsonValue]


class MockResultV1(FrozenBoundaryModel):
    """Validated Mock output with stable identity and cost evidence."""

    schema_version: Literal[1] = 1
    invocation_id: UUID
    trace_id: UUID
    boundary: MockBoundary
    output: dict[str, JsonValue]
    output_hash: Sha256Hex
    usage: MockUsageV1
