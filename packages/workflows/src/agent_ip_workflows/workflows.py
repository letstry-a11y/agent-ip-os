"""Deterministic parent and platform-child Temporal workflows."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import cast

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from agent_ip_workflows.models import (
    ApprovalResolution,
    CandidateWorkflowInput,
    CandidateWorkflowResult,
    ContentWorkflowInput,
    ContentWorkflowResult,
    IntentCommand,
    PublishOutcome,
    StateTransition,
)

ACTIVITY_TIMEOUT = timedelta(seconds=30)
ACTIVITY_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(milliseconds=100),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=1),
    maximum_attempts=3,
)


def candidate_workflow_id(parent_workflow_id: str, candidate_id: str) -> str:
    """Return the stable child ID used by API clients to signal one candidate."""

    return f"{parent_workflow_id}/candidate/{candidate_id}"


@workflow.defn
class PlatformCandidateWorkflow:
    """Progress one platform candidate independently and wait durably for one human."""

    def __init__(self) -> None:
        self._resolution: ApprovalResolution | None = None
        self._state = "CANDIDATE_FROZEN"
        self._state_version = 0

    @workflow.signal
    def resolve(self, resolution: ApprovalResolution) -> None:
        """Accept the first authorized resolution; later duplicate signals are no-ops."""

        if self._resolution is None:
            self._resolution = resolution

    @workflow.query
    def status(self) -> CandidateWorkflowResult:
        """Expose replay-safe child status without consulting a cache."""

        return CandidateWorkflowResult(
            candidate_id=workflow.info().workflow_id.rsplit("/", maxsplit=1)[-1],
            final_state=self._state,
            state_version=self._state_version,
        )

    async def _transition(self, workflow_input: CandidateWorkflowInput, target: str) -> None:
        transition = StateTransition(
            project_id=workflow_input.project_id,
            resource_id=workflow_input.candidate_id,
            expected_version=self._state_version,
            target_state=target,
        )
        version = await workflow.execute_activity(
            "advance_candidate_state",
            transition,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY,
        )
        self._state_version = cast(int, version)
        self._state = target

    async def _finish(
        self, workflow_input: CandidateWorkflowInput, target: str
    ) -> CandidateWorkflowResult:
        await self._transition(workflow_input, target)
        return CandidateWorkflowResult(
            candidate_id=workflow_input.candidate_id,
            final_state=self._state,
            state_version=self._state_version,
        )

    @workflow.run
    async def run(self, workflow_input: CandidateWorkflowInput) -> CandidateWorkflowResult:
        self._state_version = workflow_input.state_version
        for state in (
            "FACT_CHECK",
            "RIGHTS_CHECK",
            "COMPLIANCE_CHECK",
            "RISK_ROUTING",
            "WAITING_APPROVAL",
        ):
            await self._transition(workflow_input, state)

        try:
            await workflow.wait_condition(
                lambda: self._resolution is not None,
                timeout=timedelta(seconds=workflow_input.approval_timeout_seconds),
            )
        except TimeoutError:
            return await self._finish(workflow_input, "APPROVAL_EXPIRED")

        resolution = cast(ApprovalResolution, self._resolution)
        if resolution.decision == "REJECTED":
            return await self._finish(workflow_input, "REJECTED")
        if resolution.decision == "REVISION_REQUESTED":
            await self._transition(workflow_input, "REVISION_REQUESTED")
            return await self._finish(workflow_input, "SUPERSEDED")
        if resolution.decision != "APPROVED" or resolution.intent is None:
            return await self._finish(workflow_input, "QUARANTINED")

        await self._transition(workflow_input, "APPROVED")
        await self._transition(workflow_input, "READY_TO_INTENT")
        bound_intent = await workflow.execute_activity(
            "create_publish_intent_and_outbox",
            resolution.intent,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY,
        )
        await self._transition(workflow_input, "SCHEDULED")
        await self._transition(workflow_input, "PUBLISHING")
        try:
            raw_outcome = await workflow.execute_activity(
                "mock_publish",
                cast(IntentCommand, bound_intent),
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=ACTIVITY_RETRY_POLICY,
            )
        except ActivityError:
            return await self._finish(workflow_input, "PUBLISH_FAILED")
        outcome = PublishOutcome(cast(str, raw_outcome))
        if outcome is PublishOutcome.UNKNOWN:
            return await self._finish(workflow_input, "RECONCILIATION_REQUIRED")
        if outcome is not PublishOutcome.SUCCEEDED:
            return await self._finish(workflow_input, "PUBLISH_FAILED")
        return await self._finish(workflow_input, "PUBLISHED")


@workflow.defn
class ContentWorkflow:
    """Own parent progression while preserving every independent child result."""

    def __init__(self) -> None:
        self._state = "DRAFTING"
        self._state_version = 0

    async def _transition(self, workflow_input: ContentWorkflowInput, target: str) -> None:
        transition = StateTransition(
            project_id=workflow_input.project_id,
            resource_id=workflow_input.content_unit_id,
            expected_version=self._state_version,
            target_state=target,
        )
        version = await workflow.execute_activity(
            "advance_content_state",
            transition,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY_POLICY,
        )
        self._state_version = cast(int, version)
        self._state = target

    @workflow.run
    async def run(self, workflow_input: ContentWorkflowInput) -> ContentWorkflowResult:
        self._state_version = workflow_input.state_version
        await self._transition(workflow_input, "PLATFORM_ADAPTATION")
        handles = []
        parent_id = workflow.info().workflow_id
        for candidate in workflow_input.candidates:
            handles.append(
                await workflow.start_child_workflow(
                    PlatformCandidateWorkflow.run,
                    candidate,
                    id=candidate_workflow_id(parent_id, candidate.candidate_id),
                )
            )
        await self._transition(workflow_input, "CANDIDATES_ACTIVE")
        children = tuple(await asyncio.gather(*handles))
        await self._transition(workflow_input, "LEARNING")
        return ContentWorkflowResult(
            content_unit_id=workflow_input.content_unit_id,
            final_state=self._state,
            state_version=self._state_version,
            children=children,
        )
