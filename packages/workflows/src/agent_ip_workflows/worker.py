"""Workflow worker process for the local modular monolith."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker

from agent_ip_workflows.activities import PostgresWorkflowActivities, activity_functions
from agent_ip_workflows.workflows import ContentWorkflow, PlatformCandidateWorkflow

TASK_QUEUE = "agent-ip-content-v1"


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _require_mock_boundary() -> None:
    if os.environ.get("DRY_RUN", "").lower() != "true":
        raise RuntimeError("workflow worker requires DRY_RUN=true")
    if os.environ.get("EXTERNAL_SIDE_EFFECTS_ENABLED", "").lower() != "false":
        raise RuntimeError("workflow worker requires external side effects disabled")


async def run_worker() -> None:
    """Connect to local Temporal/PostgreSQL and serve deterministic workflow tasks."""

    _require_mock_boundary()
    client = await Client.connect(_required_environment("TEMPORAL_ADDRESS"))
    activities = PostgresWorkflowActivities(_required_environment("DATABASE_URL"))
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ContentWorkflow, PlatformCandidateWorkflow],
        activities=activity_functions(activities),
    )
    Path(os.environ.get("WORKER_READY_FILE", "/tmp/workflow-worker-ready")).touch()
    await worker.run()


def main() -> None:
    """Run the worker until its process receives a shutdown signal."""

    asyncio.run(run_worker())


if __name__ == "__main__":  # pragma: no cover - exercised by the container entrypoint
    main()
