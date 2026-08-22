from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from agent_ip_data_models import (
    MockBoundary,
    MockRequestV1,
    MockResultV1,
    MockScenario,
    hash_canonical_json,
)
from agent_ip_workflows.mock_boundaries import (
    DeterministicMockAdapter,
    MockAgentAdapter,
    MockBoundaryFailure,
    MockMediaAdapter,
    MockPlatformAdapter,
)
from pydantic import ValidationError

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "mock-boundary-v1.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
INVOCATION_ID = UUID("10000000-0000-0000-0000-000000000001")
TRACE_ID = UUID("20000000-0000-0000-0000-000000000002")
ADAPTERS: dict[MockBoundary, DeterministicMockAdapter] = {
    MockBoundary.AGENT: MockAgentAdapter(),
    MockBoundary.MEDIA: MockMediaAdapter(),
    MockBoundary.PLATFORM: MockPlatformAdapter(),
}


def _request(boundary: MockBoundary, scenario: MockScenario) -> MockRequestV1:
    return MockRequestV1(
        invocation_id=INVOCATION_ID,
        trace_id=TRACE_ID,
        boundary=boundary,
        scenario=scenario,
        payload={"column": "她写给世界的信", "fixture": "synthetic-001"},
    )


def _deny_network(*args: object, **kwargs: object) -> None:
    raise AssertionError("M1-05 Mock attempted network access")


@pytest.mark.parametrize(
    "case", [item for item in FIXTURE["cases"] if item["scenario"] == "SUCCESS"]
)
def test_success_matrix_is_deterministic_validated_costed_and_network_free(
    case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "create_connection", _deny_network)
    boundary = MockBoundary(case["boundary"])
    request = _request(boundary, MockScenario.SUCCESS)

    first = asyncio.run(ADAPTERS[boundary].execute(request))
    second = asyncio.run(ADAPTERS[boundary].execute(request))

    assert first == second
    assert MockResultV1.model_validate_json(first.model_dump_json()) == first
    assert first.output_hash == hash_canonical_json(first.output).sha256
    assert first.usage.input_units > 0
    assert first.usage.output_units > 0
    assert first.usage.cost_microunits >= first.usage.input_units
    assert first.usage.currency == "USD"
    assert first.boundary is boundary


@pytest.mark.parametrize(
    "case", [item for item in FIXTURE["cases"] if item["scenario"] != "SUCCESS"]
)
def test_failure_matrix_reports_retry_acceptance_uncertainty_and_cost(
    case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "create_connection", _deny_network)
    boundary = MockBoundary(case["boundary"])
    scenario = MockScenario(case["scenario"])

    with pytest.raises(MockBoundaryFailure) as captured:
        asyncio.run(ADAPTERS[boundary].execute(_request(boundary, scenario)))

    failure = captured.value
    assert failure.code is scenario
    assert failure.retryable is case["retryable"]
    assert failure.request_accepted is case.get("request_accepted", False)
    assert failure.result_uncertain is case.get("result_uncertain", False)
    assert failure.usage.input_units > 0
    assert failure.usage.cost_microunits >= failure.usage.input_units
    assert str(failure) == f"{scenario.value} at Mock boundary"
    if scenario is MockScenario.INVALID_SCHEMA:
        assert isinstance(failure.__cause__, ValidationError)


def test_adapter_rejects_wrong_boundary_and_non_platform_lost_response() -> None:
    wrong_request = _request(MockBoundary.MEDIA, MockScenario.SUCCESS)
    with pytest.raises(ValueError, match="does not match AGENT"):
        asyncio.run(MockAgentAdapter().execute(wrong_request))

    lost_agent_response = _request(MockBoundary.AGENT, MockScenario.LOST_RESPONSE)
    with pytest.raises(ValueError, match="valid only for the Mock platform"):
        asyncio.run(MockAgentAdapter().execute(lost_agent_response))


def test_request_schema_rejects_extra_fields() -> None:
    values = _request(MockBoundary.AGENT, MockScenario.SUCCESS).model_dump()
    values["network_url"] = "https://example.invalid"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MockRequestV1.model_validate(values)


def test_network_guard_itself_fails_closed() -> None:
    guarded_call: Callable[..., None] = _deny_network
    with pytest.raises(AssertionError, match="attempted network access"):
        guarded_call("example.invalid", timeout=1)
