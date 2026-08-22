"""Load and validate versioned Agent contract configuration."""

from __future__ import annotations

from pathlib import Path

from agent_ip_data_models import AgentContractSetV1


def load_agent_contract_set(path: Path) -> AgentContractSetV1:
    """Load one strict contract set from UTF-8 JSON without environment interpolation."""

    return AgentContractSetV1.model_validate_json(path.read_text(encoding="utf-8"))
