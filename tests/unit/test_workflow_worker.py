from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import agent_ip_workflows.worker as worker_module
import pytest


class FakeWorker:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self.ran = False

    async def run(self) -> None:
        self.ran = True


def test_environment_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING", raising=False)
    with pytest.raises(RuntimeError, match="MISSING is required"):
        worker_module._required_environment("MISSING")
    monkeypatch.setenv("MISSING", " value ")
    assert worker_module._required_environment("MISSING") == "value"

    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("EXTERNAL_SIDE_EFFECTS_ENABLED", "false")
    with pytest.raises(RuntimeError, match="DRY_RUN=true"):
        worker_module._require_mock_boundary()
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("EXTERNAL_SIDE_EFFECTS_ENABLED", "true")
    with pytest.raises(RuntimeError, match="side effects disabled"):
        worker_module._require_mock_boundary()
    monkeypatch.setenv("EXTERNAL_SIDE_EFFECTS_ENABLED", "false")
    worker_module._require_mock_boundary()


def test_worker_connects_registers_and_marks_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ready = tmp_path / "ready"
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("EXTERNAL_SIDE_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("WORKER_READY_FILE", str(ready))

    async def connect(address: str) -> object:
        assert address == "127.0.0.1:7233"
        return object()

    created: list[FakeWorker] = []

    def worker_factory(*args: object, **kwargs: object) -> FakeWorker:
        worker = FakeWorker(*args, **kwargs)
        created.append(worker)
        return worker

    monkeypatch.setattr(worker_module.Client, "connect", connect)
    monkeypatch.setattr(worker_module, "Worker", worker_factory)
    asyncio.run(worker_module.run_worker())
    assert ready.is_file()
    assert created[0].ran is True
    assert created[0].kwargs["task_queue"] == worker_module.TASK_QUEUE


def test_main_delegates_to_asyncio(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[Coroutine[Any, Any, None]] = []

    def run(coroutine: Coroutine[Any, Any, None]) -> None:
        observed.append(coroutine)
        coroutine.close()

    monkeypatch.setattr(worker_module.asyncio, "run", run)
    worker_module.main()
    assert len(observed) == 1
