"""PostgreSQL state Activities and a network-free Mock publish boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from agent_ip_data_models import (
    PublishRequestFingerprintInputV1,
    publish_request_fingerprint,
)
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from temporalio import activity
from temporalio.exceptions import ApplicationError

from agent_ip_workflows.models import (
    IntentCommand,
    PublishOutcome,
    StateTransition,
    StopCommand,
)
from agent_ip_workflows.publishing import PostgresPublishDispatcher


def _uuid(value: str) -> UUID:
    return UUID(value)


def _digest(value: str) -> bytes:
    if len(value) != 64:
        raise ValueError("SHA-256 value must contain 64 lowercase hexadecimal characters")
    return bytes.fromhex(value)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed


class PostgresWorkflowActivities:
    """Idempotent compare-and-swap Activities backed by authoritative PostgreSQL rows."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database URL must not be blank")
        self._database_url = database_url
        self._dispatcher = PostgresPublishDispatcher(database_url)

    async def _advance_state(
        self,
        transition: StateTransition,
        *,
        table: str,
        id_column: str,
    ) -> int:
        resource_id = _uuid(transition.resource_id)
        project_id = _uuid(transition.project_id)
        query = psycopg.sql.SQL(
            """
            UPDATE {table}
            SET state = %s, state_version = state_version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE project_id = %s AND {id_column} = %s AND state_version = %s
            RETURNING state_version
            """
        ).format(
            table=psycopg.sql.Identifier(table),
            id_column=psycopg.sql.Identifier(id_column),
        )
        async with await psycopg.AsyncConnection.connect(
            self._database_url, autocommit=True, row_factory=tuple_row
        ) as connection:
            cursor = await connection.execute(
                query,
                (
                    transition.target_state,
                    project_id,
                    resource_id,
                    transition.expected_version,
                ),
            )
            updated = await cursor.fetchone()
            if updated is not None:
                return int(updated[0])
            current_cursor = await connection.execute(
                psycopg.sql.SQL(
                    "SELECT state, state_version FROM {table} "
                    "WHERE project_id = %s AND {id_column} = %s"
                ).format(
                    table=psycopg.sql.Identifier(table),
                    id_column=psycopg.sql.Identifier(id_column),
                ),
                (project_id, resource_id),
            )
            current = await current_cursor.fetchone()
        expected_after_retry = transition.expected_version + 1
        if current == (transition.target_state, expected_after_retry):
            return expected_after_retry
        raise ApplicationError(
            "state compare-and-swap conflict",
            type="StateConflict",
            non_retryable=True,
        )

    @activity.defn(name="advance_content_state")
    async def advance_content_state(self, transition: StateTransition) -> int:
        """Advance one content row or return the prior committed retry result."""

        return await self._advance_state(
            transition,
            table="content_units",
            id_column="id",
        )

    @activity.defn(name="advance_candidate_state")
    async def advance_candidate_state(self, transition: StateTransition) -> int:
        """Advance one candidate child row or return the prior committed retry result."""

        return await self._advance_state(
            transition,
            table="platform_candidate_states",
            id_column="candidate_id",
        )

    @activity.defn(name="create_publish_intent_and_outbox")
    async def create_publish_intent_and_outbox(self, command: IntentCommand) -> IntentCommand:
        """Atomically create one logical action; concurrent equivalents converge."""

        project_id = _uuid(command.project_id)
        candidate_id = _uuid(command.candidate_id)
        approval_snapshot_id = _uuid(command.approval_snapshot_id)
        account_id = _uuid(command.account_id)
        intent_id = _uuid(command.intent_id)
        outbox_id = _uuid(command.outbox_id)
        fingerprint = _digest(command.request_fingerprint)
        schedule_slot = _timestamp(command.normalized_schedule_slot)
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=tuple_row
        ) as connection:
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"{project_id}:{fingerprint.hex()}",),
            )
            cursor = await connection.execute(
                """
                SELECT
                    i.id, i.outbox_message_id, o.id, o.publish_intent_id,
                    i.candidate_id, i.approval_snapshot_id, i.account_id,
                    i.request_fingerprint, i.normalized_schedule_slot
                FROM publish_intents i
                JOIN outbox_messages o
                  ON o.project_id = i.project_id AND o.id = i.outbox_message_id
                WHERE i.project_id = %s AND i.id = %s
                """,
                (project_id, intent_id),
            )
            existing = await cursor.fetchone()
            if existing is not None:
                expected = (
                    intent_id,
                    outbox_id,
                    outbox_id,
                    intent_id,
                    candidate_id,
                    approval_snapshot_id,
                    account_id,
                    fingerprint,
                    schedule_slot,
                )
                if existing == expected:
                    return command
                raise ApplicationError(
                    "intent ID is already bound differently",
                    type="IntentConflict",
                    non_retryable=True,
                )
            fingerprint_cursor = await connection.execute(
                """
                SELECT
                    i.id, i.outbox_message_id, i.candidate_id,
                    i.approval_snapshot_id, i.account_id,
                    i.request_fingerprint, i.normalized_schedule_slot
                FROM publish_intents i
                WHERE i.project_id = %s AND i.request_fingerprint = %s
                """,
                (project_id, fingerprint),
            )
            equivalent = await fingerprint_cursor.fetchone()
            if equivalent is not None:
                expected_equivalent = (
                    equivalent[0],
                    equivalent[1],
                    candidate_id,
                    approval_snapshot_id,
                    account_id,
                    fingerprint,
                    schedule_slot,
                )
                if equivalent == expected_equivalent:
                    return IntentCommand(
                        project_id=command.project_id,
                        candidate_id=command.candidate_id,
                        approval_snapshot_id=command.approval_snapshot_id,
                        account_id=command.account_id,
                        intent_id=str(equivalent[0]),
                        outbox_id=str(equivalent[1]),
                        request_fingerprint=command.request_fingerprint,
                        normalized_schedule_slot=command.normalized_schedule_slot,
                    )
                raise ApplicationError(
                    "request fingerprint is already bound differently",
                    type="IntentConflict",
                    non_retryable=True,
                )
            gate_cursor = await connection.execute(
                """
                SELECT
                    c.candidate_hash, c.platform, c.policy_version,
                    s.decision, s.candidate_hash, s.policy_version, s.account_hash,
                    s.expires_at, r.status, a.status, a.account_fingerprint,
                    cs.state,
                    EXISTS (
                        SELECT 1 FROM publish_stop_controls sc
                        WHERE sc.project_id = c.project_id AND sc.stopped
                          AND (
                              sc.scope = 'GLOBAL'
                              OR (sc.scope = 'ACCOUNT' AND sc.account_id = c.account_id)
                          )
                    )
                FROM platform_candidates c
                JOIN platform_candidate_states cs
                  ON cs.project_id = c.project_id AND cs.candidate_id = c.id
                JOIN approval_snapshots s
                  ON s.project_id = c.project_id AND s.id = %s
                 AND s.candidate_id = c.id AND s.account_id = c.account_id
                JOIN approval_requests r
                  ON r.project_id = s.project_id AND r.id = s.approval_request_id
                JOIN platform_accounts a
                  ON a.project_id = c.project_id AND a.id = c.account_id
                WHERE c.project_id = %s AND c.id = %s AND c.account_id = %s
                """,
                (approval_snapshot_id, project_id, candidate_id, account_id),
            )
            gate = await gate_cursor.fetchone()
            if gate is None:
                raise ApplicationError(
                    "approved publish boundary is missing",
                    type="ApprovalInvalid",
                    non_retryable=True,
                )
            expected_fingerprint = publish_request_fingerprint(
                PublishRequestFingerprintInputV1(
                    candidate_hash=bytes(gate[0]).hex(),
                    platform=str(gate[1]),
                    account_id=account_id,
                    normalized_schedule_slot=schedule_slot,
                )
            ).sha256
            now = datetime.now(UTC)
            gate_valid = (
                gate[3] == "APPROVED"
                and gate[4] == gate[0]
                and gate[5] == gate[2]
                and gate[6] == gate[10]
                and gate[7] > now
                and gate[8] == "APPROVED"
                and gate[9] == "ACTIVE"
                and gate[11] in ("APPROVED", "READY_TO_INTENT")
                and not gate[12]
                and expected_fingerprint == command.request_fingerprint
            )
            if not gate_valid:
                raise ApplicationError(
                    "approved publish boundary failed revalidation",
                    type="ApprovalInvalid",
                    non_retryable=True,
                )
            occurred_at = datetime.now(UTC)
            await connection.execute(
                """
                INSERT INTO outbox_messages (
                    id, project_id, publish_intent_id, topic, payload, occurred_at, available_at
                ) VALUES (%s, %s, %s, 'publish.mock.requested', %s, %s, %s)
                """,
                (
                    outbox_id,
                    project_id,
                    intent_id,
                    Jsonb({"intent_id": str(intent_id)}),
                    occurred_at,
                    occurred_at,
                ),
            )
            await connection.execute(
                """
                INSERT INTO publish_intents (
                    id, project_id, candidate_id, approval_snapshot_id, account_id,
                    outbox_message_id, request_fingerprint, normalized_schedule_slot
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    intent_id,
                    project_id,
                    candidate_id,
                    approval_snapshot_id,
                    account_id,
                    outbox_id,
                    fingerprint,
                    schedule_slot,
                ),
            )
            await connection.execute(
                """
                INSERT INTO publish_jobs (
                    id, project_id, publish_intent_id, outbox_message_id, account_id, state
                ) VALUES (%s, %s, %s, %s, %s, 'READY')
                """,
                (intent_id, project_id, intent_id, outbox_id, account_id),
            )
            return command

    @activity.defn(name="set_publish_stop")
    async def set_publish_stop(self, command: StopCommand) -> int:
        """Persist one global or account stop through a compare-and-swap boundary."""

        return await self._dispatcher.set_stop(command)

    @activity.defn(name="mock_publish")
    async def dispatch_mock_publish(self, command: IntentCommand) -> str:
        """Lease, recheck stops, and execute the network-free Mock boundary once."""

        outcome = await self._dispatcher.dispatch(command, _mock_publisher)
        return outcome.value


async def mock_publish(command: IntentCommand) -> str:
    """Return success without network access; M1-05 will add the full failure matrix."""

    _uuid(command.intent_id)
    return PublishOutcome.SUCCEEDED.value


async def _mock_publisher(command: IntentCommand) -> PublishOutcome:
    _uuid(command.intent_id)
    return PublishOutcome.SUCCEEDED


def activity_functions(activities: PostgresWorkflowActivities) -> list[Any]:
    """Return the complete worker Activity registry."""

    return [
        activities.advance_content_state,
        activities.advance_candidate_state,
        activities.create_publish_intent_and_outbox,
        activities.set_publish_stop,
        activities.dispatch_mock_publish,
    ]
