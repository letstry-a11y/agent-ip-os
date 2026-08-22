"""Versioned contracts for the six combined MVP Agent runtime units."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from agent_ip_data_models.core import FrozenBoundaryModel, NonEmptyText
from agent_ip_data_models.providers import ProviderErrorCode


class AgentUnitId(StrEnum):
    """The six logical runtime units allowed in the narrow MVP."""

    PLANNING_RESEARCH = "PLANNING_RESEARCH"
    CREATION = "CREATION"
    MEDIA_PRODUCTION = "MEDIA_PRODUCTION"
    FINAL_VERIFICATION = "FINAL_VERIFICATION"
    PLATFORM_CANDIDATE = "PLATFORM_CANDIDATE"
    BASIC_ANALYTICS = "BASIC_ANALYTICS"


class ModelTier(StrEnum):
    """Portable cost/quality tiers rather than vendor model names."""

    ECONOMY = "ECONOMY"
    BALANCED = "BALANCED"
    PREMIUM = "PREMIUM"


RETRYABLE_PROVIDER_CODES = frozenset(
    {ProviderErrorCode.RATE_LIMIT, ProviderErrorCode.TIMEOUT, ProviderErrorCode.TRANSIENT}
)
BASELINE_FORBIDDEN_ACTIONS = frozenset(
    {"publish", "pay", "sign_contract", "delete_protected", "read_secret"}
)


class AgentRetryPolicyV1(FrozenBoundaryModel):
    """Bounded retry policy restricted to retry-safe Provider failures."""

    schema_version: Literal[1] = 1
    max_attempts: int = Field(ge=1, le=3)
    retry_on: tuple[ProviderErrorCode, ...]

    @model_validator(mode="after")
    def only_retry_safe_codes(self) -> AgentRetryPolicyV1:
        """Reject permanent, policy, authorization, and cancellation retries."""

        if not set(self.retry_on).issubset(RETRYABLE_PROVIDER_CODES):
            raise ValueError("retry_on contains a non-retryable Provider code")
        if len(set(self.retry_on)) != len(self.retry_on):
            raise ValueError("retry_on codes must be unique")
        return self


class AgentContractV1(FrozenBoundaryModel):
    """Server-enforced declarative boundary for one combined runtime unit."""

    schema_version: Literal[1] = 1
    id: AgentUnitId
    name: NonEmptyText
    purpose: NonEmptyText
    input_schema: NonEmptyText
    output_schema: NonEmptyText
    model_tier: ModelTier
    tools: tuple[NonEmptyText, ...]
    read_scopes: tuple[NonEmptyText, ...]
    write_scopes: tuple[NonEmptyText, ...]
    forbidden_actions: tuple[NonEmptyText, ...]
    max_tool_calls: int = Field(ge=0, le=50)
    max_cost_microunits: int = Field(ge=0)
    timeout_seconds: int = Field(gt=0, le=900)
    retry_policy: AgentRetryPolicyV1
    escalate_when: tuple[NonEmptyText, ...]
    prompt_version: NonEmptyText

    @model_validator(mode="after")
    def contract_is_fail_closed(self) -> AgentContractV1:
        """Require unique declarations and the global no-side-effect baseline."""

        collections = {
            "tools": self.tools,
            "read_scopes": self.read_scopes,
            "write_scopes": self.write_scopes,
            "forbidden_actions": self.forbidden_actions,
            "escalate_when": self.escalate_when,
        }
        for name, values in collections.items():
            if len(set(values)) != len(values):
                raise ValueError(f"{name} values must be unique")
        if not BASELINE_FORBIDDEN_ACTIONS.issubset(self.forbidden_actions):
            raise ValueError("contract must include every baseline forbidden action")
        return self


class AgentContractSetV1(FrozenBoundaryModel):
    """Exactly one contract for every allowed MVP unit."""

    schema_version: Literal[1] = 1
    contracts: tuple[AgentContractV1, ...] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def contains_exactly_the_six_mvp_units(self) -> AgentContractSetV1:
        """Reject missing, duplicate, or out-of-scope runtime units."""

        ids = [contract.id for contract in self.contracts]
        if len(set(ids)) != len(ids) or set(ids) != set(AgentUnitId):
            raise ValueError("contract set must contain each MVP Agent unit exactly once")
        return self
