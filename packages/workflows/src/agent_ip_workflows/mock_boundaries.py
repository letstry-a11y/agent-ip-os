"""Deterministic Agent, media, and platform Mocks with no external effects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, cast

from agent_ip_data_models import (
    MockBoundary,
    MockRequestV1,
    MockResultV1,
    MockScenario,
    MockUsageV1,
    canonical_json_bytes,
    hash_canonical_json,
)
from agent_ip_data_models.hashing import CanonicalValue
from pydantic import JsonValue, ValidationError


class MockBoundaryFailure(RuntimeError):
    """Typed failure evidence for one deterministic Mock invocation."""

    def __init__(
        self,
        code: MockScenario,
        *,
        retryable: bool,
        request_accepted: bool,
        result_uncertain: bool,
        usage: MockUsageV1,
    ) -> None:
        super().__init__(f"{code.value} at Mock boundary")
        self.code = code
        self.retryable = retryable
        self.request_accepted = request_accepted
        self.result_uncertain = result_uncertain
        self.usage = usage


class DeterministicMockAdapter(ABC):
    """Shared failure semantics and cost accounting for all M1 Mock boundaries."""

    boundary: ClassVar[MockBoundary]
    output_units: ClassVar[int]
    base_cost_microunits: ClassVar[int]

    async def execute(self, request: MockRequestV1) -> MockResultV1:
        """Execute immediately without network, sleeping, credentials, or external state."""

        if request.boundary is not self.boundary:
            raise ValueError(
                f"request boundary {request.boundary.value} does not match {self.boundary.value}"
            )
        usage = self._usage(request)
        scenario = request.scenario
        if scenario is MockScenario.TIMEOUT:
            raise self._failure(scenario, retryable=True, usage=usage)
        if scenario is MockScenario.TRANSIENT_FAILURE:
            raise self._failure(scenario, retryable=True, usage=usage)
        if scenario is MockScenario.PERMANENT_FAILURE:
            raise self._failure(scenario, retryable=False, usage=usage)
        if scenario is MockScenario.CANCELLED:
            raise self._failure(scenario, retryable=False, usage=usage)
        if scenario is MockScenario.LOST_RESPONSE:
            if self.boundary is not MockBoundary.PLATFORM:
                raise ValueError("LOST_RESPONSE is valid only for the Mock platform boundary")
            raise MockBoundaryFailure(
                scenario,
                retryable=False,
                request_accepted=True,
                result_uncertain=True,
                usage=usage,
            )

        output = self._success_output(request)
        result_values: dict[str, object] = {
            "invocation_id": request.invocation_id,
            "trace_id": request.trace_id,
            "boundary": request.boundary,
            "output": output,
            "output_hash": hash_canonical_json(cast(CanonicalValue, output)).sha256,
            "usage": usage,
        }
        if scenario is MockScenario.INVALID_SCHEMA:
            result_values["output"] = "malformed structured output"
        try:
            return MockResultV1.model_validate(result_values)
        except ValidationError as error:
            raise self._failure(
                MockScenario.INVALID_SCHEMA, retryable=False, usage=usage
            ) from error

    def _usage(self, request: MockRequestV1) -> MockUsageV1:
        input_units = len(canonical_json_bytes(cast(CanonicalValue, request.payload)))
        output_units = self.output_units
        return MockUsageV1(
            input_units=input_units,
            output_units=output_units,
            cost_microunits=self.base_cost_microunits + input_units + output_units,
        )

    @staticmethod
    def _failure(code: MockScenario, *, retryable: bool, usage: MockUsageV1) -> MockBoundaryFailure:
        return MockBoundaryFailure(
            code,
            retryable=retryable,
            request_accepted=False,
            result_uncertain=False,
            usage=usage,
        )

    @abstractmethod
    def _success_output(self, request: MockRequestV1) -> dict[str, JsonValue]:
        """Return one boundary-specific synthetic output."""


class MockAgentAdapter(DeterministicMockAdapter):
    """Produce a structured, non-Provider Agent proposal."""

    boundary = MockBoundary.AGENT
    output_units = 96
    base_cost_microunits = 1_000

    def _success_output(self, request: MockRequestV1) -> dict[str, JsonValue]:
        digest = hash_canonical_json(cast(CanonicalValue, request.payload)).sha256
        return {
            "proposal_id": f"mock-agent-{digest[:16]}",
            "column": "她写给世界的信",
            "body": "Mock-only structured proposal; no Provider was called.",
        }


class MockMediaAdapter(DeterministicMockAdapter):
    """Produce synthetic media metadata without creating identity or asset bytes."""

    boundary = MockBoundary.MEDIA
    output_units = 48
    base_cost_microunits = 2_000

    def _success_output(self, request: MockRequestV1) -> dict[str, JsonValue]:
        digest = hash_canonical_json(cast(CanonicalValue, request.payload)).sha256
        return {
            "artifact_id": f"mock-media-{digest[:16]}",
            "object_key": f"mock/media/{digest}.bin",
            "media_type": "application/x-agent-ip-mock",
            "sha256": digest,
            "byte_size": 0,
        }


class MockPlatformAdapter(DeterministicMockAdapter):
    """Produce a synthetic platform result without contacting a platform."""

    boundary = MockBoundary.PLATFORM
    output_units = 24
    base_cost_microunits = 0

    def _success_output(self, request: MockRequestV1) -> dict[str, JsonValue]:
        digest = hash_canonical_json(cast(CanonicalValue, request.payload)).sha256
        return {
            "platform_post_id": f"mock-post-{digest[:16]}",
            "status": "PUBLISHED",
            "request_fingerprint": digest,
        }
