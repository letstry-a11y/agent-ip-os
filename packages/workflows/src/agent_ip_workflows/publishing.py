"""Lease-guarded PostgreSQL outbox dispatch with fail-closed stop checks."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
from agent_ip_data_models import (
    PublishRequestFingerprintInputV1,
    publish_request_fingerprint,
)
from psycopg.rows import tuple_row
from temporalio.exceptions import ApplicationError

from agent_ip_workflows.models import IntentCommand, PublishOutcome, StopCommand, StopScope

Publisher = Callable[[IntentCommand], Awaitable[PublishOutcome]]
AfterLeaseHook = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class _Lease:
    project_id: UUID
    job_id: UUID
    intent_id: UUID
    token: UUID
    attempt_number: int


class PostgresPublishDispatcher:
    """Own one short lease and recheck all kill switches at the request boundary."""

    def __init__(
        self,
        database_url: str,
        *,
        worker_id: UUID | None = None,
        lease_duration: timedelta = timedelta(seconds=5),
    ) -> None:
        if not database_url.strip():
            raise ValueError("database URL must not be blank")
        if lease_duration <= timedelta(0):
            raise ValueError("lease duration must be positive")
        self._database_url = database_url
        self._worker_id = worker_id or uuid4()
        self._lease_duration = lease_duration

    async def set_stop(self, command: StopCommand) -> int:
        """Create or compare-and-swap one authoritative stop control."""

        project_id = UUID(command.project_id)
        control_id = UUID(command.control_id)
        actor_id = UUID(command.updated_by_subject_id)
        account_id = UUID(command.account_id) if command.account_id is not None else None
        if command.expected_version < -1:
            raise ValueError("expected stop version must be -1 for create or non-negative")
        if (command.scope is StopScope.GLOBAL) != (account_id is None):
            raise ValueError("GLOBAL requires no account; ACCOUNT requires one account")
        if command.stopped != (command.reason is not None and bool(command.reason.strip())):
            raise ValueError("active stops require a reason; cleared stops require no reason")

        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=tuple_row
        ) as connection:
            cursor = await connection.execute(
                """
                SELECT id, stopped, reason, state_version
                FROM publish_stop_controls
                WHERE project_id = %s AND scope = %s
                  AND account_id IS NOT DISTINCT FROM %s
                FOR UPDATE
                """,
                (project_id, command.scope.value, account_id),
            )
            existing = await cursor.fetchone()
            if existing is None:
                if command.expected_version != -1:
                    raise self._stop_conflict()
                await connection.execute(
                    """
                    INSERT INTO publish_stop_controls (
                        id, project_id, scope, account_id, stopped, reason,
                        updated_by_subject_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        control_id,
                        project_id,
                        command.scope.value,
                        account_id,
                        command.stopped,
                        command.reason,
                        actor_id,
                    ),
                )
                return 0

            current_id, stopped, reason, version = existing
            if current_id != control_id:
                raise self._stop_conflict()
            if version == command.expected_version + 1 and (
                stopped,
                reason,
            ) == (command.stopped, command.reason):
                return int(version)
            if version != command.expected_version:
                raise self._stop_conflict()
            updated = await connection.execute(
                """
                UPDATE publish_stop_controls
                SET stopped = %s, reason = %s, state_version = state_version + 1,
                    updated_by_subject_id = %s, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = %s AND id = %s AND state_version = %s
                RETURNING state_version
                """,
                (
                    command.stopped,
                    command.reason,
                    actor_id,
                    project_id,
                    control_id,
                    command.expected_version,
                ),
            )
            row = await updated.fetchone()
            if row is None:  # pragma: no cover - row remains locked until commit
                raise self._stop_conflict()
            return int(row[0])

    async def dispatch(
        self,
        command: IntentCommand,
        publisher: Publisher,
        *,
        after_lease: AfterLeaseHook | None = None,
    ) -> PublishOutcome:
        """Dispatch one intent once; UNKNOWN and known terminal outcomes never retry."""

        acquired = await self._acquire(command)
        if isinstance(acquired, PublishOutcome):
            return acquired
        if after_lease is not None:
            await after_lease()
        gate = await self._start_attempt(command, acquired)
        if gate is not None:
            return gate
        try:
            outcome = await publisher(command)
        except Exception:
            await self._finish(acquired, PublishOutcome.UNKNOWN, "publisher_exception")
            return PublishOutcome.UNKNOWN
        if outcome not in (PublishOutcome.SUCCEEDED, PublishOutcome.UNKNOWN, PublishOutcome.FAILED):
            outcome = PublishOutcome.FAILED
        await self._finish(acquired, outcome, None)
        return outcome

    @staticmethod
    def _stop_conflict() -> ApplicationError:
        return ApplicationError(
            "publish stop compare-and-swap conflict",
            type="StopConflict",
            non_retryable=True,
        )

    async def _stop_active(
        self,
        connection: psycopg.AsyncConnection[tuple[object, ...]],
        project_id: UUID,
        account_id: UUID,
    ) -> bool:
        cursor = await connection.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM publish_stop_controls
                WHERE project_id = %s AND stopped
                  AND (scope = 'GLOBAL' OR (scope = 'ACCOUNT' AND account_id = %s))
            )
            """,
            (project_id, account_id),
        )
        row = await cursor.fetchone()
        return row is not None and bool(row[0])

    async def _acquire(self, command: IntentCommand) -> _Lease | PublishOutcome:
        project_id = UUID(command.project_id)
        intent_id = UUID(command.intent_id)
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=tuple_row
        ) as connection:
            cursor = await connection.execute(
                """
                SELECT
                    i.outbox_message_id, i.candidate_id, i.approval_snapshot_id,
                    i.account_id, i.request_fingerprint, i.normalized_schedule_slot,
                    c.candidate_hash, c.platform, c.policy_version,
                    s.decision, s.candidate_hash, s.policy_version, s.account_hash,
                    s.expires_at, r.status, a.status, a.account_fingerprint,
                    o.delivered_at, j.id, j.state, j.lease_token, j.lease_owner_id,
                    j.lease_expires_at, j.attempt_count
                FROM publish_intents i
                JOIN outbox_messages o
                  ON o.project_id = i.project_id AND o.id = i.outbox_message_id
                JOIN publish_jobs j
                  ON j.project_id = i.project_id AND j.publish_intent_id = i.id
                JOIN platform_candidates c
                  ON c.project_id = i.project_id AND c.id = i.candidate_id
                JOIN approval_snapshots s
                  ON s.project_id = i.project_id AND s.id = i.approval_snapshot_id
                JOIN approval_requests r
                  ON r.project_id = s.project_id AND r.id = s.approval_request_id
                JOIN platform_accounts a
                  ON a.project_id = i.project_id AND a.id = i.account_id
                WHERE i.project_id = %s AND i.id = %s
                FOR UPDATE OF j, o
                """,
                (project_id, intent_id),
            )
            row = await cursor.fetchone()
            if row is None:
                raise ApplicationError(
                    "publish intent is not dispatchable",
                    type="IntentNotDispatchable",
                    non_retryable=True,
                )
            (
                outbox_id,
                candidate_id,
                snapshot_id,
                account_id,
                fingerprint,
                schedule_slot,
                candidate_hash,
                platform,
                candidate_policy,
                decision,
                snapshot_candidate_hash,
                snapshot_policy,
                snapshot_account_hash,
                expires_at,
                request_status,
                account_status,
                account_hash,
                delivered_at,
                job_id,
                state,
                lease_token,
                lease_owner,
                lease_expires,
                attempt_count,
            ) = row
            expected_fingerprint = bytes.fromhex(
                publish_request_fingerprint(
                    PublishRequestFingerprintInputV1(
                        candidate_hash=bytes(candidate_hash).hex(),
                        platform=str(platform),
                        account_id=account_id,
                        normalized_schedule_slot=schedule_slot,
                    )
                ).sha256
            )
            expected_binding = (
                UUID(command.outbox_id),
                UUID(command.candidate_id),
                UUID(command.approval_snapshot_id),
                UUID(command.account_id),
                bytes.fromhex(command.request_fingerprint),
                _parse_timestamp(command.normalized_schedule_slot),
            )
            if row[:6] != expected_binding or fingerprint != expected_fingerprint:
                raise ApplicationError(
                    "publish command does not match its authoritative intent",
                    type="IntentConflict",
                    non_retryable=True,
                )
            now = datetime.now(UTC)
            valid = (
                decision == "APPROVED"
                and request_status == "APPROVED"
                and expires_at > now
                and account_status == "ACTIVE"
                and candidate_hash == snapshot_candidate_hash
                and candidate_policy == snapshot_policy
                and account_hash == snapshot_account_hash
            )
            if not valid:
                await self._terminal_job(connection, project_id, job_id, "FAILED", "STALE_GATE")
                return PublishOutcome.FAILED
            if state == "RECONCILIATION_REQUIRED":
                return PublishOutcome.UNKNOWN
            if state == "FAILED":
                return PublishOutcome.FAILED
            if state == "SUCCEEDED":
                return PublishOutcome.SUCCEEDED
            if delivered_at is not None:
                raise ApplicationError(
                    "delivered outbox has no terminal publish state",
                    type="PublishStateConflict",
                    non_retryable=True,
                )
            if await self._stop_active(connection, project_id, account_id):
                await self._terminal_job(
                    connection, project_id, job_id, "STOPPED", "PUBLISH_STOPPED"
                )
                return PublishOutcome.STOPPED
            if state == "LEASED" and lease_expires is not None and lease_expires > now:
                if lease_owner != self._worker_id:
                    return PublishOutcome.BUSY
                return _Lease(
                    project_id=project_id,
                    job_id=job_id,
                    intent_id=intent_id,
                    token=lease_token,
                    attempt_number=int(attempt_count),
                )

            token = uuid4()
            acquired_at = now
            expires = acquired_at + self._lease_duration
            updated = await connection.execute(
                """
                UPDATE publish_jobs
                SET state = 'LEASED', lease_token = %s, lease_owner_id = %s,
                    lease_acquired_at = %s, lease_expires_at = %s,
                    attempt_count = attempt_count + 1, last_error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE project_id = %s AND id = %s
                RETURNING attempt_count
                """,
                (token, self._worker_id, acquired_at, expires, project_id, job_id),
            )
            count_row = await updated.fetchone()
            if count_row is None:  # pragma: no cover - row is locked in this transaction
                raise RuntimeError("locked publish job disappeared")
            await connection.execute(
                """
                UPDATE outbox_messages
                SET claimed_at = CURRENT_TIMESTAMP, attempt_count = attempt_count + 1,
                    last_error = NULL
                WHERE project_id = %s AND id = %s
                """,
                (project_id, outbox_id),
            )
            return _Lease(project_id, job_id, intent_id, token, int(count_row[0]))

    async def _start_attempt(self, command: IntentCommand, lease: _Lease) -> PublishOutcome | None:
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=tuple_row
        ) as connection:
            cursor = await connection.execute(
                """
                SELECT j.account_id, j.state, j.lease_token, j.lease_owner_id,
                       j.lease_expires_at, a.status, s.decision, s.expires_at, r.status,
                       c.candidate_hash, s.candidate_hash, c.policy_version,
                       s.policy_version, a.account_fingerprint, s.account_hash,
                       i.request_fingerprint
                FROM publish_jobs j
                JOIN publish_intents i
                  ON i.project_id = j.project_id AND i.id = j.publish_intent_id
                JOIN platform_accounts a
                  ON a.project_id = j.project_id AND a.id = j.account_id
                JOIN approval_snapshots s
                  ON s.project_id = i.project_id AND s.id = i.approval_snapshot_id
                JOIN approval_requests r
                  ON r.project_id = s.project_id AND r.id = s.approval_request_id
                JOIN platform_candidates c
                  ON c.project_id = i.project_id AND c.id = i.candidate_id
                WHERE j.project_id = %s AND j.id = %s
                FOR UPDATE OF j
                """,
                (lease.project_id, lease.job_id),
            )
            row = await cursor.fetchone()
            if row is None:  # pragma: no cover - acquired jobs cannot be deleted
                return PublishOutcome.FAILED
            account_id = row[0]
            now = datetime.now(UTC)
            lease_valid = (
                row[1] == "LEASED"
                and row[2] == lease.token
                and row[3] == self._worker_id
                and row[4] > now
            )
            if not lease_valid:
                return PublishOutcome.BUSY
            if await self._stop_active(connection, lease.project_id, account_id):
                await self._terminal_job(
                    connection,
                    lease.project_id,
                    lease.job_id,
                    "STOPPED",
                    "PUBLISH_STOPPED",
                )
                return PublishOutcome.STOPPED
            current_valid = (
                row[5] == "ACTIVE"
                and row[6] == "APPROVED"
                and row[7] > now
                and row[8] == "APPROVED"
                and row[9] == row[10]
                and row[11] == row[12]
                and row[13] == row[14]
            )
            if not current_valid:
                await self._terminal_job(
                    connection, lease.project_id, lease.job_id, "FAILED", "STALE_GATE"
                )
                return PublishOutcome.FAILED
            await connection.execute(
                """
                INSERT INTO publish_attempts (
                    id, project_id, publish_job_id, publish_intent_id, attempt_number,
                    lease_token, outcome, request_fingerprint
                ) VALUES (%s, %s, %s, %s, %s, %s, 'STARTED', %s)
                ON CONFLICT (project_id, publish_job_id, attempt_number) DO NOTHING
                """,
                (
                    uuid4(),
                    lease.project_id,
                    lease.job_id,
                    lease.intent_id,
                    lease.attempt_number,
                    lease.token,
                    row[15],
                ),
            )
            return None

    async def _finish(
        self,
        lease: _Lease,
        outcome: PublishOutcome,
        error_class: str | None,
    ) -> None:
        job_state = {
            PublishOutcome.SUCCEEDED: "SUCCEEDED",
            PublishOutcome.UNKNOWN: "RECONCILIATION_REQUIRED",
            PublishOutcome.FAILED: "FAILED",
        }[outcome]
        attempt_outcome = {
            PublishOutcome.SUCCEEDED: "SUCCEEDED",
            PublishOutcome.UNKNOWN: "UNKNOWN",
            PublishOutcome.FAILED: "KNOWN_FAILED",
        }[outcome]
        response_hash = hashlib.sha256(outcome.value.encode()).digest()
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=tuple_row
        ) as connection:
            updated = await connection.execute(
                """
                UPDATE publish_jobs
                SET state = %s, lease_token = NULL, lease_owner_id = NULL,
                    lease_acquired_at = NULL, lease_expires_at = NULL,
                    last_error = %s, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = %s AND id = %s AND state = 'LEASED'
                  AND lease_token = %s AND lease_owner_id = %s
                RETURNING outbox_message_id
                """,
                (
                    job_state,
                    error_class,
                    lease.project_id,
                    lease.job_id,
                    lease.token,
                    self._worker_id,
                ),
            )
            row = await updated.fetchone()
            if row is None:
                raise ApplicationError(
                    "publish lease was lost before completion",
                    type="LeaseLost",
                    non_retryable=True,
                )
            await connection.execute(
                """
                UPDATE publish_attempts
                SET outcome = %s, response_hash = %s, error_class = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE project_id = %s AND publish_job_id = %s
                  AND attempt_number = %s AND outcome = 'STARTED'
                """,
                (
                    attempt_outcome,
                    response_hash,
                    error_class,
                    lease.project_id,
                    lease.job_id,
                    lease.attempt_number,
                ),
            )
            await connection.execute(
                """
                UPDATE outbox_messages
                SET delivered_at = CURRENT_TIMESTAMP, last_error = %s
                WHERE project_id = %s AND id = %s
                """,
                (error_class, lease.project_id, row[0]),
            )

    async def _terminal_job(
        self,
        connection: psycopg.AsyncConnection[tuple[object, ...]],
        project_id: UUID,
        job_id: UUID,
        state: str,
        error: str,
    ) -> None:
        await connection.execute(
            """
            UPDATE publish_jobs
            SET state = %s, lease_token = NULL, lease_owner_id = NULL,
                lease_acquired_at = NULL, lease_expires_at = NULL,
                last_error = %s, updated_at = CURRENT_TIMESTAMP
            WHERE project_id = %s AND id = %s
            """,
            (state, error, project_id, job_id),
        )
        await connection.execute(
            """
            UPDATE outbox_messages o
            SET last_error = %s
            FROM publish_jobs j
            WHERE j.project_id = %s AND j.id = %s
              AND o.project_id = j.project_id AND o.id = j.outbox_message_id
            """,
            (error, project_id, job_id),
        )


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed
