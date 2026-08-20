from pathlib import Path

import pytest

from scripts.dev_stack import compose_command, configured_ports, ensure_runtime_env


def test_runtime_env_generates_required_unique_credentials(tmp_path: Path) -> None:
    environment = ensure_runtime_env(tmp_path / "compose.env")
    values = dict(
        line.split("=", maxsplit=1) for line in environment.read_text(encoding="utf-8").splitlines()
    )

    assert set(values) == {
        "GARAGE_ADMIN_TOKEN",
        "GARAGE_DEFAULT_ACCESS_KEY",
        "GARAGE_DEFAULT_SECRET_KEY",
        "GARAGE_METRICS_TOKEN",
        "GARAGE_RPC_SECRET",
        "POSTGRES_PASSWORD",
    }
    assert values["GARAGE_DEFAULT_ACCESS_KEY"].startswith("GK")
    assert len(values["GARAGE_DEFAULT_SECRET_KEY"]) == 64
    assert len(values["GARAGE_RPC_SECRET"]) == 64
    assert len(set(values.values())) == len(values)


def test_configured_ports_accepts_overrides_and_rejects_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_PORT", "18000")
    assert configured_ports()["API_PORT"] == 18000

    monkeypatch.setenv("WEB_PORT", "18000")
    with pytest.raises(ValueError, match="must be unique"):
        configured_ports()


def test_compose_command_uses_explicit_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime_env = tmp_path / "compose.env"
    monkeypatch.setattr("scripts.dev_stack.ENV_FILE", runtime_env)

    command = compose_command("config", "--quiet")

    assert command[:2] == ["docker", "compose"]
    assert command[-2:] == ["config", "--quiet"]
    assert runtime_env.is_file()
