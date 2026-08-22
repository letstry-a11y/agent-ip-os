from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

from agent_ip_workflows.models import (
    ApprovalResolution,
    CandidateWorkflowInput,
    ContentWorkflowInput,
    IntentCommand,
    PublishOutcome,
    StateTransition,
)
from agent_ip_workflows.workflows import (
    ContentWorkflow,
    PlatformCandidateWorkflow,
    candidate_workflow_id,
)
from temporalio import activity
from temporalio.client import WorkflowHandle
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

PROJECT_ID = "11111111-1111-4111-8111-111111111111"
CONTENT_ID = "22222222-2222-4222-8222-222222222222"
CANDIDATE_A = "33333333-3333-4333-8333-333333333333"
CANDIDATE_B = "44444444-4444-4444-8444-444444444444"
ACCOUNT_ID = "55555555-5555-4555-8555-555555555555"
SNAPSHOT_ID = "66666666-6666-4666-8666-666666666666"
INTENT_ID = "77777777-7777-4777-8777-777777777777"
OUTBOX_ID = "88888888-8888-4888-8888-888888888888"


def _intent(intent_id: str = INTENT_ID) -> IntentCommand:
    return IntentCommand(
        project_id=PROJECT_ID,
        candidate_id=CANDIDATE_A,
        approval_snapshot_id=SNAPSHOT_ID,
        account_id=ACCOUNT_ID,
        intent_id=intent_id,
        outbox_id=OUTBOX_ID,
        request_fingerprint="ab" * 32,
        normalized_schedule_slot="2026-08-22T02:00:00.000Z",
    )


class RecordingActivities:
    def __init__(self) -> None:
        self.transitions: list[StateTransition] = []
        self.intents: list[str] = []
        self.publish_attempts: defaultdict[str, int] = defaultdict(int)
        self.publish_modes: dict[str, str] = {}

    @activity.defn(name="advance_content_state")
    async def advance_content_state(self, value: StateTransition) -> int:
        self.transitions.append(value)
        return value.expected_version + 1

    @activity.defn(name="advance_candidate_state")
    async def advance_candidate_state(self, value: StateTransition) -> int:
        self.transitions.append(value)
        return value.expected_version + 1

    @activity.defn(name="create_publish_intent_and_outbox")
    async def create_publish_intent_and_outbox(self, value: IntentCommand) -> IntentCommand:
        self.intents.append(value.intent_id)
        return value

    @activity.defn(name="mock_publish")
    async def mock_publish(self, value: IntentCommand) -> str:
        self.publish_attempts[value.intent_id] += 1
        mode = self.publish_modes.get(value.intent_id, "success")
        if mode == "retry" and self.publish_attempts[value.intent_id] < 3:
            raise ApplicationError("transient mock failure")
        if mode == "permanent":
            raise ApplicationError("permanent mock failure", non_retryable=True)
        if mode == "unknown":
            return PublishOutcome.UNKNOWN.value
        return PublishOutcome.SUCCEEDED.value

    def registry(self) -> list[object]:
        return [
            self.advance_content_state,
            self.advance_candidate_state,
            self.create_publish_intent_and_outbox,
            self.mock_publish,
        ]


async def _wait_for_state(
    activities: RecordingActivities,
    candidate_id: str,
    state: str,
    *,
    after_index: int = 0,
) -> None:
    for _ in range(200):
        if any(
            item.resource_id == candidate_id and item.target_state == state
            for item in activities.transitions[after_index:]
        ):
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"candidate {candidate_id} did not reach {state}")


async def _start_parent(
    environment: WorkflowEnvironment,
    task_queue: str,
    workflow_id: str,
    candidates: tuple[str, ...],
    *,
    timeout: int = 60,
) -> WorkflowHandle[ContentWorkflow, object]:
    return await environment.client.start_workflow(
        ContentWorkflow.run,
        ContentWorkflowInput(
            project_id=PROJECT_ID,
            content_unit_id=CONTENT_ID,
            candidates=tuple(
                CandidateWorkflowInput(
                    project_id=PROJECT_ID,
                    candidate_id=item,
                    approval_timeout_seconds=timeout,
                )
                for item in candidates
            ),
        ),
        id=workflow_id,
        task_queue=task_queue,
    )


async def _resolve(
    environment: WorkflowEnvironment,
    parent_id: str,
    candidate_id: str,
    resolution: ApprovalResolution,
) -> None:
    handle = environment.client.get_workflow_handle(candidate_workflow_id(parent_id, candidate_id))
    await handle.signal(PlatformCandidateWorkflow.resolve, resolution)


async def _run_restart_and_terminal_scenarios(database_file: Path) -> None:
    task_queue = "m1-02-restart-test"
    activities = RecordingActivities()
    parent_id = "content-restart"
    first_environment = await WorkflowEnvironment.start_local(
        dev_server_database_filename=str(database_file)
    )
    async with (
        first_environment,
        Worker(
            first_environment.client,
            task_queue=task_queue,
            workflows=[ContentWorkflow, PlatformCandidateWorkflow],
            activities=activities.registry(),
        ),
    ):
        await _start_parent(
            first_environment,
            task_queue,
            parent_id,
            (CANDIDATE_A, CANDIDATE_B),
        )
        await _wait_for_state(activities, CANDIDATE_A, "WAITING_APPROVAL")
        await _wait_for_state(activities, CANDIDATE_B, "WAITING_APPROVAL")
        waiting = await first_environment.client.get_workflow_handle_for(
            PlatformCandidateWorkflow.run,
            candidate_workflow_id(parent_id, CANDIDATE_A),
        ).query(PlatformCandidateWorkflow.status)
        assert waiting.final_state == "WAITING_APPROVAL"

    second_environment = await WorkflowEnvironment.start_local(
        dev_server_database_filename=str(database_file)
    )
    async with (
        second_environment,
        Worker(
            second_environment.client,
            task_queue=task_queue,
            workflows=[ContentWorkflow, PlatformCandidateWorkflow],
            activities=activities.registry(),
        ),
    ):
        await _resolve(
            second_environment,
            parent_id,
            CANDIDATE_A,
            ApprovalResolution(decision="APPROVED", intent=_intent()),
        )
        await _resolve(
            second_environment,
            parent_id,
            CANDIDATE_B,
            ApprovalResolution(decision="REJECTED"),
        )
        await _resolve(
            second_environment,
            parent_id,
            CANDIDATE_B,
            ApprovalResolution(decision="APPROVED", intent=_intent()),
        )
        restarted = await second_environment.client.get_workflow_handle_for(
            ContentWorkflow.run, parent_id
        ).result()
        assert restarted.final_state == "LEARNING"
        assert [item.final_state for item in restarted.children] == ["PUBLISHED", "REJECTED"]
        assert activities.intents == [INTENT_ID]

        await _exercise_terminal_cases(second_environment, task_queue, activities)


async def _exercise_terminal_cases(
    environment: WorkflowEnvironment,
    task_queue: str,
    activities: RecordingActivities,
) -> None:
    cases = (
        ("revision", ApprovalResolution(decision="REVISION_REQUESTED"), "SUPERSEDED"),
        ("invalid", ApprovalResolution(decision="INVALID"), "QUARANTINED"),
        ("missing-intent", ApprovalResolution(decision="APPROVED"), "QUARANTINED"),
    )
    for name, resolution, expected in cases:
        workflow_id = f"content-{name}"
        marker = len(activities.transitions)
        handle = await _start_parent(environment, task_queue, workflow_id, (CANDIDATE_A,))
        await _wait_for_state(activities, CANDIDATE_A, "WAITING_APPROVAL", after_index=marker)
        await _resolve(environment, workflow_id, CANDIDATE_A, resolution)
        result = await handle.result()
        assert result.children[0].final_state == expected

    for mode, expected in (
        ("retry", "PUBLISHED"),
        ("unknown", "RECONCILIATION_REQUIRED"),
        ("permanent", "PUBLISH_FAILED"),
    ):
        workflow_id = f"content-{mode}"
        intent_id = f"{mode:0<8}-7777-4777-8777-777777777777"
        activities.publish_modes[intent_id] = mode
        marker = len(activities.transitions)
        handle = await _start_parent(environment, task_queue, workflow_id, (CANDIDATE_A,))
        await _wait_for_state(activities, CANDIDATE_A, "WAITING_APPROVAL", after_index=marker)
        await _resolve(
            environment,
            workflow_id,
            CANDIDATE_A,
            ApprovalResolution(decision="APPROVED", intent=_intent(intent_id)),
        )
        result = await handle.result()
        assert result.children[0].final_state == expected
    assert activities.publish_attempts["retry000-7777-4777-8777-777777777777"] == 3

    empty = await _start_parent(environment, task_queue, "content-empty", ())
    assert (await empty.result()).children == ()

    expired = await _start_parent(
        environment,
        task_queue,
        "content-expired",
        (CANDIDATE_A,),
        timeout=1,
    )
    assert (await expired.result()).children[0].final_state == "APPROVAL_EXPIRED"


def test_workflow_survives_worker_and_temporal_restart(tmp_path: Path) -> None:
    asyncio.run(_run_restart_and_terminal_scenarios(tmp_path / "temporal.db"))
