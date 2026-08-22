from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent_ip_agent_runtime import load_agent_contract_set
from agent_ip_data_models import (
    AgentContractSetV1,
    AgentContractV1,
    AgentRetryPolicyV1,
    AgentUnitId,
    ProviderErrorCode,
)
from pydantic import ValidationError

CONTRACT_PATH = Path(__file__).parents[2] / "config" / "agents" / "runtime-units-v1.json"


def test_runtime_contract_file_contains_exactly_six_fail_closed_units() -> None:
    contract_set = load_agent_contract_set(CONTRACT_PATH)

    assert {contract.id for contract in contract_set.contracts} == set(AgentUnitId)
    assert len(contract_set.contracts) == 6
    for contract in contract_set.contracts:
        assert contract.max_cost_microunits == 0
        assert contract.max_tool_calls <= 16
        assert contract.timeout_seconds <= 300
        assert contract.retry_policy.max_attempts == 2
        assert "publish" in contract.forbidden_actions
        assert "read_secret" in contract.forbidden_actions
        assert contract.prompt_version.endswith("-v1")
        assert contract.input_schema.endswith("@v1")
        assert contract.output_schema.endswith("@v1")

    round_trip = AgentContractSetV1.model_validate_json(contract_set.model_dump_json())
    assert round_trip == contract_set


def test_retry_policy_rejects_permanent_and_duplicate_codes() -> None:
    with pytest.raises(ValidationError, match="non-retryable"):
        AgentRetryPolicyV1(max_attempts=2, retry_on=(ProviderErrorCode.AUTHORIZATION,))

    with pytest.raises(ValidationError, match="must be unique"):
        AgentRetryPolicyV1(
            max_attempts=2,
            retry_on=(ProviderErrorCode.TIMEOUT, ProviderErrorCode.TIMEOUT),
        )


def test_contract_rejects_duplicate_declarations_and_missing_global_forbidden_action() -> None:
    contract = load_agent_contract_set(CONTRACT_PATH).contracts[0]
    duplicate_tools = contract.model_dump()
    duplicate_tools["tools"] = (contract.tools[0], contract.tools[0])
    with pytest.raises(ValidationError, match="tools values must be unique"):
        AgentContractV1.model_validate(duplicate_tools)

    missing_forbidden = contract.model_dump()
    missing_forbidden["forbidden_actions"] = tuple(
        action for action in contract.forbidden_actions if action != "read_secret"
    )
    with pytest.raises(ValidationError, match="every baseline forbidden action"):
        AgentContractV1.model_validate(missing_forbidden)


def test_contract_set_rejects_duplicate_or_missing_unit_identity() -> None:
    contract_set = load_agent_contract_set(CONTRACT_PATH)
    values = contract_set.model_dump()
    contracts = list(values["contracts"])
    contracts[-1] = contracts[0]
    values["contracts"] = tuple(contracts)
    with pytest.raises(ValidationError, match="each MVP Agent unit exactly once"):
        AgentContractSetV1.model_validate(values)


def test_contract_file_rejects_unknown_fields(tmp_path: Path) -> None:
    values = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    values["contracts"][0]["credential"] = "not-allowed"
    invalid_path = tmp_path / "invalid-contracts.json"
    invalid_path.write_text(json.dumps(values), encoding="utf-8")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_agent_contract_set(invalid_path)
