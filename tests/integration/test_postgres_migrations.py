from __future__ import annotations

import asyncio
import selectors
import shutil
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from agent_ip_api.approval import (
    ApprovalConflict,
    ApprovalForbidden,
    ApprovalNotFound,
    PostgresApprovalService,
)
from agent_ip_data_models import (
    ApprovalActorType,
    ApprovalActorV1,
    ApprovalDecision,
    ApprovalDecisionCommandV1,
    ApprovalInvalidationReason,
    ApprovalRequestStatus,
    ApprovalSnapshotHashInputV1,
    CandidateHashInputV1,
    PublishRequestFingerprintInputV1,
    approval_snapshot_hash,
    candidate_hash,
    candidate_payload,
    publish_request_fingerprint,
)
from agent_ip_workflows.activities import PostgresWorkflowActivities
from agent_ip_workflows.models import (
    IntentCommand,
    PublishOutcome,
    StateTransition,
    StopCommand,
    StopScope,
)
from agent_ip_workflows.publishing import PostgresPublishDispatcher
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    ObjectNotInPrerequisiteState,
    UniqueViolation,
)
from psycopg.types.json import Jsonb
from temporalio.exceptions import ApplicationError

from scripts.db_migrate import MIGRATIONS_DIR, MigrationError, migrate, resolve_database_url


class RedactedDatabaseUrl(str):
    def __repr__(self) -> str:
        return "<redacted PostgreSQL test URL>"


@pytest.fixture
def database_url() -> Iterator[RedactedDatabaseUrl]:
    admin_url = resolve_database_url()
    name = f"agent_ip_test_{uuid4().hex}"
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    values = conninfo_to_dict(admin_url)
    values["dbname"] = name
    test_url = RedactedDatabaseUrl(make_conninfo(**values))
    try:
        yield test_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (name,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_forward_upgrade_preserves_data_and_enables_immutable_guards(database_url: str) -> None:
    assert migrate(database_url, target_sequence=1) == ("0001_core_domain.sql",)
    project_id = uuid4()
    content_id = uuid4()
    version_id = uuid4()
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO ip_projects (id, slug, name) VALUES (%s, %s, %s)",
            (project_id, "m1-forward", "M1 forward test"),
        )
        connection.execute(
            "INSERT INTO content_units (id, project_id, state, trace_id) VALUES (%s, %s, %s, %s)",
            (content_id, project_id, "PLANNED", uuid4()),
        )
        connection.execute(
            """
            INSERT INTO content_versions (
                id, project_id, content_unit_id, version, payload, content_hash,
                created_by_subject_id
            ) VALUES (%s, %s, %s, 1, %s, %s, %s)
            """,
            (
                version_id,
                project_id,
                content_id,
                Jsonb({"title": "first"}),
                bytes.fromhex("11" * 32),
                uuid4(),
            ),
        )

    assert migrate(database_url) == (
        "0002_enforce_immutable_evidence.sql",
        "0003_bind_candidate_content_version.sql",
        "0004_require_distinct_approvers.sql",
        "0005_publish_dispatch_controls.sql",
        "0006_approval_console_bindings.sql",
    )
    assert migrate(database_url) == ()

    with psycopg.connect(database_url, autocommit=True) as connection:
        row = connection.execute(
            "SELECT version, payload FROM content_versions WHERE id = %s", (version_id,)
        ).fetchone()
        assert row == (1, {"title": "first"})
        history = connection.execute(
            "SELECT sequence, name FROM schema_migrations ORDER BY sequence"
        ).fetchall()
        assert history == [
            (1, "0001_core_domain.sql"),
            (2, "0002_enforce_immutable_evidence.sql"),
            (3, "0003_bind_candidate_content_version.sql"),
            (4, "0004_require_distinct_approvers.sql"),
            (5, "0005_publish_dispatch_controls.sql"),
            (6, "0006_approval_console_bindings.sql"),
        ]
        with pytest.raises(ObjectNotInPrerequisiteState, match="append-only"):
            connection.execute(
                "UPDATE content_versions SET payload = %s WHERE id = %s",
                (Jsonb({"title": "changed"}), version_id),
            )


def test_core_constraints_outbox_atomicity_and_audit_chain(database_url: str) -> None:
    assert migrate(database_url) == (
        "0001_core_domain.sql",
        "0002_enforce_immutable_evidence.sql",
        "0003_bind_candidate_content_version.sql",
        "0004_require_distinct_approvers.sql",
        "0005_publish_dispatch_controls.sql",
        "0006_approval_console_bindings.sql",
    )
    identifiers = _seed_approved_intent(database_url)
    asyncio.run(
        _exercise_real_workflow_activities(database_url, identifiers),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )

    with psycopg.connect(database_url, autocommit=True) as connection:
        candidate = connection.execute(
            """
            SELECT content_version_id, normalized_tags, canonical_payload
            FROM platform_candidates WHERE id = %s
            """,
            (identifiers["candidate_id"],),
        ).fetchone()
        assert candidate == (
            identifiers["content_version_id"],
            ["writing", "xiaohongshu"],
            {
                "account_id": str(identifiers["account_id"]),
                "ai_disclosure": "AI-assisted visual",
                "caption": "Caption",
                "ordered_asset_hashes": ["31" * 32],
                "platform": "xiaohongshu_pack",
                "policy_version": "policy-v1",
                "sorted_tags": ["writing", "xiaohongshu"],
                "title": "Letter 1",
            },
        )
        paired = connection.execute(
            """
            SELECT i.id, o.publish_intent_id
            FROM publish_intents i
            JOIN outbox_messages o
              ON o.project_id = i.project_id AND o.id = i.outbox_message_id
            WHERE i.id = %s
            """,
            (identifiers["intent_id"],),
        ).fetchone()
        assert paired == (identifiers["intent_id"], identifiers["intent_id"])
        assert connection.execute(
            """
            SELECT state, state_version FROM platform_candidate_states
            WHERE project_id = %s AND candidate_id = %s
            """,
            (identifiers["project_id"], identifiers["candidate_id"]),
        ).fetchone() == ("APPROVED", 1)

        with pytest.raises(ForeignKeyViolation), connection.transaction():
            connection.execute(
                """
                    INSERT INTO content_versions (
                        id, project_id, content_unit_id, version, payload, content_hash,
                        created_by_subject_id
                    ) VALUES (%s, %s, %s, 1, '{}'::jsonb, %s, %s)
                    """,
                (
                    uuid4(),
                    identifiers["other_project_id"],
                    identifiers["content_id"],
                    bytes.fromhex("91" * 32),
                    uuid4(),
                ),
            )

        orphan_intent_id = uuid4()
        with pytest.raises(ForeignKeyViolation), connection.transaction():
            connection.execute(
                """
                    INSERT INTO publish_intents (
                        id, project_id, candidate_id, approval_snapshot_id, account_id,
                        outbox_message_id, request_fingerprint, normalized_schedule_slot
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """,
                (
                    orphan_intent_id,
                    identifiers["project_id"],
                    identifiers["candidate_id"],
                    identifiers["approval_snapshot_id"],
                    identifiers["account_id"],
                    uuid4(),
                    bytes.fromhex("92" * 32),
                ),
            )

        with pytest.raises(UniqueViolation), connection.transaction():
            _insert_intent_pair(
                connection,
                identifiers,
                intent_id=uuid4(),
                outbox_id=uuid4(),
                fingerprint=bytes.fromhex("77" * 32),
            )

        duplicate_request_id = uuid4()
        connection.execute(
            """
            INSERT INTO approval_requests (
                id, project_id, candidate_id, risk_level, requested_action,
                required_approvals, status, requested_by_subject_id, expires_at, resolved_at
            ) VALUES (
                %s, %s, %s, 'R2', 'PACKAGE_EXPORT', 2, 'APPROVED', %s,
                CURRENT_TIMESTAMP + interval '1 day', CURRENT_TIMESTAMP
            )
            """,
            (
                duplicate_request_id,
                identifiers["project_id"],
                identifiers["candidate_id"],
                uuid4(),
            ),
        )
        with pytest.raises(CheckViolation), connection.transaction():
            connection.execute(
                """
                INSERT INTO approval_snapshots (
                    id, project_id, approval_request_id, candidate_id, account_id, decision,
                    candidate_hash, fact_report_hash, rights_manifest_hash, risk_report_hash,
                    policy_version, account_hash, approved_action, approver_subject_ids,
                    expires_at, decided_at, snapshot_hash
                ) VALUES (
                    %s, %s, %s, %s, %s, 'APPROVED', %s, %s, %s, %s, 'policy-v1', %s,
                    'PACKAGE_EXPORT', ARRAY[%s, %s]::uuid[],
                    CURRENT_TIMESTAMP + interval '1 day', CURRENT_TIMESTAMP, %s
                )
                """,
                (
                    uuid4(),
                    identifiers["project_id"],
                    duplicate_request_id,
                    identifiers["candidate_id"],
                    identifiers["account_id"],
                    bytes.fromhex("41" * 32),
                    bytes.fromhex("61" * 32),
                    bytes.fromhex("62" * 32),
                    bytes.fromhex("63" * 32),
                    bytes.fromhex("51" * 32),
                    identifiers["approver_subject_id"],
                    identifiers["approver_subject_id"],
                    bytes.fromhex("64" * 32),
                ),
            )

        genesis_hash = bytes.fromhex("a1" * 32)
        child_hash = bytes.fromhex("a2" * 32)
        _insert_audit_event(connection, identifiers["project_id"], None, genesis_hash)
        child_id = _insert_audit_event(
            connection, identifiers["project_id"], genesis_hash, child_hash
        )

        with pytest.raises(UniqueViolation):
            _insert_audit_event(
                connection,
                identifiers["project_id"],
                genesis_hash,
                bytes.fromhex("a3" * 32),
            )
        with pytest.raises(ForeignKeyViolation), connection.transaction():
            _insert_audit_event(
                connection,
                identifiers["project_id"],
                bytes.fromhex("ff" * 32),
                bytes.fromhex("a4" * 32),
            )
        with pytest.raises(ObjectNotInPrerequisiteState, match="append-only"):
            connection.execute("DELETE FROM audit_events WHERE id = %s", (child_id,))


def test_migration_checksum_history_rejects_rewritten_file(
    database_url: str, tmp_path: Path
) -> None:
    copied = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS_DIR, copied)
    assert migrate(database_url, directory=copied, target_sequence=1) == ("0001_core_domain.sql",)
    first = copied / "0001_core_domain.sql"
    first.write_text(first.read_text(encoding="utf-8") + "\n-- rewritten\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="migration history mismatch"):
        migrate(database_url, directory=copied, target_sequence=1)

    first.unlink()
    with pytest.raises(MigrationError, match="migration history mismatch"):
        migrate(database_url, directory=copied)


def test_candidate_binding_forward_fix_refuses_unsafe_inference(database_url: str) -> None:
    assert migrate(database_url, target_sequence=2) == (
        "0001_core_domain.sql",
        "0002_enforce_immutable_evidence.sql",
    )
    project_id = uuid4()
    content_id = uuid4()
    account_id = uuid4()
    candidate_id = uuid4()
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO ip_projects (id, slug, name) VALUES (%s, 'legacy', 'Legacy')",
            (project_id,),
        )
        connection.execute(
            """
            INSERT INTO content_units (id, project_id, state, trace_id)
            VALUES (%s, %s, 'PLANNED', %s)
            """,
            (content_id, project_id, uuid4()),
        )
        connection.execute(
            """
            INSERT INTO platform_accounts (
                id, project_id, platform, environment, status, capabilities_version,
                account_fingerprint
            ) VALUES (%s, %s, 'mock', 'MOCK', 'ACTIVE', 'v1', %s)
            """,
            (account_id, project_id, bytes.fromhex("b1" * 32)),
        )
        connection.execute(
            """
            INSERT INTO platform_candidates (
                id, project_id, content_unit_id, account_id, platform, title, caption,
                normalized_tags, ai_disclosure, policy_version, canonical_payload,
                candidate_hash
            ) VALUES (
                %s, %s, %s, %s, 'mock', 'Legacy', '', ARRAY[]::text[],
                'AI-assisted', 'v1', '{}'::jsonb, %s
            )
            """,
            (candidate_id, project_id, content_id, account_id, bytes.fromhex("b2" * 32)),
        )

    with pytest.raises(ObjectNotInPrerequisiteState, match="cannot infer"):
        migrate(database_url)

    with psycopg.connect(database_url) as connection:
        history = connection.execute(
            "SELECT sequence FROM schema_migrations ORDER BY sequence"
        ).fetchall()
        assert history == [(1,), (2,)]
        assert connection.execute(
            "SELECT id FROM platform_candidates WHERE id = %s", (candidate_id,)
        ).fetchone() == (candidate_id,)
        assert connection.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'platform_candidates' AND column_name = 'content_version_id'
            """
        ).fetchone() == (0,)


def test_one_hundred_concurrent_repeats_converge_on_one_logical_action(
    database_url: str,
) -> None:
    assert migrate(database_url)
    identifiers = _seed_approved_intent(database_url)
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            """
            UPDATE platform_candidate_states
            SET state = 'READY_TO_INTENT', state_version = state_version + 1
            WHERE project_id = %s AND candidate_id = %s
            """,
            (identifiers["project_id"], identifiers["candidate_id"]),
        )
    base = _new_command(database_url, identifiers, schedule_hour=3)

    async def submit_all() -> tuple[IntentCommand, ...]:
        activities = PostgresWorkflowActivities(database_url)
        limit = asyncio.Semaphore(20)

        async def submit(index: int) -> IntentCommand:
            async with limit:
                command = IntentCommand(
                    **{
                        **base.__dict__,
                        "intent_id": str(uuid4()),
                        "outbox_id": str(uuid4()),
                    }
                )
                return await activities.create_publish_intent_and_outbox(command)

        return tuple(await asyncio.gather(*(submit(index) for index in range(100))))

    results = asyncio.run(
        submit_all(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
    assert len({item.intent_id for item in results}) == 1
    assert len({item.outbox_id for item in results}) == 1
    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            """
            SELECT count(*) FROM publish_intents
            WHERE project_id = %s AND request_fingerprint = %s
            """,
            (identifiers["project_id"], bytes.fromhex(base.request_fingerprint)),
        ).fetchone() == (1,)
        assert connection.execute(
            """
            SELECT count(*)
            FROM publish_jobs j
            JOIN publish_intents i
              ON i.project_id = j.project_id AND i.id = j.publish_intent_id
            WHERE i.project_id = %s AND i.request_fingerprint = %s
            """,
            (identifiers["project_id"], bytes.fromhex(base.request_fingerprint)),
        ).fetchone() == (1,)


@pytest.mark.parametrize("scope", [StopScope.GLOBAL, StopScope.ACCOUNT])
def test_stop_raised_after_lease_blocks_the_external_request(
    database_url: str, scope: StopScope
) -> None:
    assert migrate(database_url)
    identifiers = _seed_approved_intent(database_url)
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            """
            UPDATE platform_candidate_states SET state = 'READY_TO_INTENT'
            WHERE project_id = %s AND candidate_id = %s
            """,
            (identifiers["project_id"], identifiers["candidate_id"]),
        )
    command = _new_command(database_url, identifiers, schedule_hour=4)

    async def exercise() -> tuple[PublishOutcome, int]:
        activities = PostgresWorkflowActivities(database_url)
        await activities.create_publish_intent_and_outbox(command)
        dispatcher = PostgresPublishDispatcher(database_url)
        calls = 0

        async def raise_stop() -> None:
            await dispatcher.set_stop(
                StopCommand(
                    control_id=str(uuid4()),
                    project_id=str(identifiers["project_id"]),
                    scope=scope,
                    account_id=(
                        str(identifiers["account_id"]) if scope is StopScope.ACCOUNT else None
                    ),
                    stopped=True,
                    reason="operator stop race test",
                    expected_version=-1,
                    updated_by_subject_id=str(uuid4()),
                )
            )

        async def publisher(_: IntentCommand) -> PublishOutcome:
            nonlocal calls
            calls += 1
            return PublishOutcome.SUCCEEDED

        outcome = await dispatcher.dispatch(command, publisher, after_lease=raise_stop)
        return outcome, calls

    outcome, calls = asyncio.run(
        exercise(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
    assert outcome is PublishOutcome.STOPPED
    assert calls == 0
    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            "SELECT state FROM publish_jobs WHERE publish_intent_id = %s",
            (UUID(command.intent_id),),
        ).fetchone() == ("STOPPED",)
        assert connection.execute(
            "SELECT count(*) FROM publish_attempts WHERE publish_intent_id = %s",
            (UUID(command.intent_id),),
        ).fetchone() == (0,)


def test_unknown_outcome_requires_reconciliation_and_is_never_retried(
    database_url: str,
) -> None:
    assert migrate(database_url)
    identifiers = _seed_approved_intent(database_url)
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            """
            UPDATE platform_candidate_states SET state = 'READY_TO_INTENT'
            WHERE project_id = %s AND candidate_id = %s
            """,
            (identifiers["project_id"], identifiers["candidate_id"]),
        )
    command = _new_command(database_url, identifiers, schedule_hour=5)

    async def exercise() -> tuple[PublishOutcome, PublishOutcome, int]:
        activities = PostgresWorkflowActivities(database_url)
        await activities.create_publish_intent_and_outbox(command)
        dispatcher = PostgresPublishDispatcher(database_url)
        calls = 0

        async def publisher(_: IntentCommand) -> PublishOutcome:
            nonlocal calls
            calls += 1
            return PublishOutcome.UNKNOWN

        first = await dispatcher.dispatch(command, publisher)
        second = await dispatcher.dispatch(command, publisher)
        return first, second, calls

    first, second, calls = asyncio.run(
        exercise(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
    assert (first, second, calls) == (
        PublishOutcome.UNKNOWN,
        PublishOutcome.UNKNOWN,
        1,
    )
    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            "SELECT state FROM publish_jobs WHERE publish_intent_id = %s",
            (UUID(command.intent_id),),
        ).fetchone() == ("RECONCILIATION_REQUIRED",)
        assert connection.execute(
            "SELECT outcome FROM publish_attempts WHERE publish_intent_id = %s",
            (UUID(command.intent_id),),
        ).fetchall() == [("UNKNOWN",)]


def test_stop_control_compare_and_swap_is_idempotent_and_fail_closed(
    database_url: str,
) -> None:
    assert migrate(database_url)
    identifiers = _seed_approved_intent(database_url)
    dispatcher = PostgresPublishDispatcher(database_url)
    actor_id = str(uuid4())
    control_id = str(uuid4())
    create = StopCommand(
        control_id=control_id,
        project_id=str(identifiers["project_id"]),
        scope=StopScope.GLOBAL,
        account_id=None,
        stopped=True,
        reason="operator pause",
        expected_version=-1,
        updated_by_subject_id=actor_id,
    )

    async def exercise() -> tuple[int, int, int, int]:
        created = await dispatcher.set_stop(create)
        create_retry = await dispatcher.set_stop(create)
        clear = replace(create, stopped=False, reason=None, expected_version=0)
        cleared = await dispatcher.set_stop(clear)
        clear_retry = await dispatcher.set_stop(clear)
        with pytest.raises(ApplicationError, match="compare-and-swap"):
            await dispatcher.set_stop(replace(clear, control_id=str(uuid4()), expected_version=1))
        with pytest.raises(ApplicationError, match="compare-and-swap"):
            await dispatcher.set_stop(replace(create, expected_version=0))
        with pytest.raises(ApplicationError, match="compare-and-swap"):
            await dispatcher.set_stop(
                StopCommand(
                    control_id=str(uuid4()),
                    project_id=str(identifiers["project_id"]),
                    scope=StopScope.ACCOUNT,
                    account_id=str(identifiers["account_id"]),
                    stopped=True,
                    reason="bad create version",
                    expected_version=0,
                    updated_by_subject_id=actor_id,
                )
            )
        return created, create_retry, cleared, clear_retry

    assert asyncio.run(
        exercise(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    ) == (0, 0, 1, 1)

    with pytest.raises(ValueError, match="must not be blank"):
        PostgresPublishDispatcher(" ")
    with pytest.raises(ValueError, match="positive"):
        PostgresPublishDispatcher(database_url, lease_duration=timedelta(0))
    malformed = (
        replace(create, expected_version=-2),
        replace(create, account_id=str(identifiers["account_id"])),
        replace(create, reason=None),
    )
    for command in malformed:
        with pytest.raises(ValueError):
            asyncio.run(dispatcher.set_stop(command))


def test_dispatch_rechecks_gates_and_preserves_every_terminal_outcome(
    database_url: str,
) -> None:
    assert migrate(database_url)
    identifiers = _seed_approved_intent(database_url)
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            """
            UPDATE platform_candidate_states SET state = 'READY_TO_INTENT'
            WHERE project_id = %s AND candidate_id = %s
            """,
            (identifiers["project_id"], identifiers["candidate_id"]),
        )

    async def exercise() -> None:
        activities = PostgresWorkflowActivities(database_url)
        dispatcher = PostgresPublishDispatcher(database_url)

        missing = _new_command(database_url, identifiers, schedule_hour=6)
        with pytest.raises(ApplicationError, match="not dispatchable"):
            await dispatcher.dispatch(missing, _success_publisher)

        success = _new_command(database_url, identifiers, schedule_hour=7)
        await activities.create_publish_intent_and_outbox(success)
        success_calls = 0

        async def succeeds(_: IntentCommand) -> PublishOutcome:
            nonlocal success_calls
            success_calls += 1
            return PublishOutcome.SUCCEEDED

        assert await dispatcher.dispatch(success, succeeds) is PublishOutcome.SUCCEEDED
        assert await dispatcher.dispatch(success, succeeds) is PublishOutcome.SUCCEEDED
        assert success_calls == 1
        with pytest.raises(ApplicationError, match="does not match"):
            await dispatcher.dispatch(replace(success, outbox_id=str(uuid4())), succeeds)

        publisher_error = _new_command(database_url, identifiers, schedule_hour=8)
        await activities.create_publish_intent_and_outbox(publisher_error)

        async def raises(_: IntentCommand) -> PublishOutcome:
            raise RuntimeError("lost response")

        assert await dispatcher.dispatch(publisher_error, raises) is PublishOutcome.UNKNOWN

        stale = _new_command(database_url, identifiers, schedule_hour=9)
        await activities.create_publish_intent_and_outbox(stale)
        with psycopg.connect(database_url, autocommit=True) as connection:
            connection.execute(
                "UPDATE platform_accounts SET status = 'PAUSED' WHERE id = %s",
                (identifiers["account_id"],),
            )
        assert await dispatcher.dispatch(stale, succeeds) is PublishOutcome.FAILED
        with psycopg.connect(database_url, autocommit=True) as connection:
            connection.execute(
                "UPDATE platform_accounts SET status = 'ACTIVE' WHERE id = %s",
                (identifiers["account_id"],),
            )
        assert await dispatcher.dispatch(stale, succeeds) is PublishOutcome.FAILED

        delivered_conflict = _new_command(database_url, identifiers, schedule_hour=13)
        await activities.create_publish_intent_and_outbox(delivered_conflict)
        with psycopg.connect(database_url, autocommit=True) as connection:
            connection.execute(
                "UPDATE outbox_messages SET delivered_at = CURRENT_TIMESTAMP WHERE id = %s",
                (UUID(delivered_conflict.outbox_id),),
            )
        with pytest.raises(ApplicationError, match="no terminal publish state"):
            await dispatcher.dispatch(delivered_conflict, succeeds)

        stopped = _new_command(database_url, identifiers, schedule_hour=10)
        await activities.create_publish_intent_and_outbox(stopped)
        control = StopCommand(
            control_id=str(uuid4()),
            project_id=str(identifiers["project_id"]),
            scope=StopScope.ACCOUNT,
            account_id=str(identifiers["account_id"]),
            stopped=True,
            reason="pre-dispatch stop",
            expected_version=-1,
            updated_by_subject_id=str(uuid4()),
        )
        assert await dispatcher.set_stop(control) == 0
        assert await dispatcher.dispatch(stopped, succeeds) is PublishOutcome.STOPPED
        assert (
            await dispatcher.set_stop(
                replace(control, stopped=False, reason=None, expected_version=0)
            )
            == 1
        )

        invalid_outcome = _new_command(database_url, identifiers, schedule_hour=11)
        await activities.create_publish_intent_and_outbox(invalid_outcome)

        async def invalid(_: IntentCommand) -> PublishOutcome:
            return PublishOutcome.STOPPED

        assert await dispatcher.dispatch(invalid_outcome, invalid) is PublishOutcome.FAILED

        busy = _new_command(database_url, identifiers, schedule_hour=12)
        await activities.create_publish_intent_and_outbox(busy)
        other = PostgresPublishDispatcher(database_url)
        observed: list[PublishOutcome] = []

        async def check_other_worker() -> None:
            observed.append(await other.dispatch(busy, succeeds))

        assert (
            await dispatcher.dispatch(busy, succeeds, after_lease=check_other_worker)
            is PublishOutcome.SUCCEEDED
        )
        assert observed == [PublishOutcome.BUSY]

        same_worker = _new_command(database_url, identifiers, schedule_hour=14)
        await activities.create_publish_intent_and_outbox(same_worker)

        async def reacquire_same_worker() -> None:
            assert not isinstance(await dispatcher._acquire(same_worker), PublishOutcome)

        assert (
            await dispatcher.dispatch(same_worker, succeeds, after_lease=reacquire_same_worker)
            is PublishOutcome.SUCCEEDED
        )

        stale_at_request = _new_command(database_url, identifiers, schedule_hour=15)
        await activities.create_publish_intent_and_outbox(stale_at_request)

        async def pause_account() -> None:
            with psycopg.connect(database_url, autocommit=True) as connection:
                connection.execute(
                    "UPDATE platform_accounts SET status = 'PAUSED' WHERE id = %s",
                    (identifiers["account_id"],),
                )

        assert (
            await dispatcher.dispatch(stale_at_request, succeeds, after_lease=pause_account)
            is PublishOutcome.FAILED
        )
        with psycopg.connect(database_url, autocommit=True) as connection:
            connection.execute(
                "UPDATE platform_accounts SET status = 'ACTIVE' WHERE id = %s",
                (identifiers["account_id"],),
            )

        invalid_lease = _new_command(database_url, identifiers, schedule_hour=16)
        await activities.create_publish_intent_and_outbox(invalid_lease)

        async def replace_owner() -> None:
            with psycopg.connect(database_url, autocommit=True) as connection:
                connection.execute(
                    """
                    UPDATE publish_jobs SET lease_owner_id = %s
                    WHERE publish_intent_id = %s
                    """,
                    (uuid4(), UUID(invalid_lease.intent_id)),
                )

        assert (
            await dispatcher.dispatch(invalid_lease, succeeds, after_lease=replace_owner)
            is PublishOutcome.BUSY
        )

        lost_lease = _new_command(database_url, identifiers, schedule_hour=17)
        await activities.create_publish_intent_and_outbox(lost_lease)

        async def loses_lease(_: IntentCommand) -> PublishOutcome:
            with psycopg.connect(database_url, autocommit=True) as connection:
                connection.execute(
                    """
                    UPDATE publish_jobs
                    SET state = 'FAILED', lease_token = NULL, lease_owner_id = NULL,
                        lease_acquired_at = NULL, lease_expires_at = NULL
                    WHERE publish_intent_id = %s
                    """,
                    (UUID(lost_lease.intent_id),),
                )
            return PublishOutcome.SUCCEEDED

        with pytest.raises(ApplicationError, match="lease was lost"):
            await dispatcher.dispatch(lost_lease, loses_lease)

    asyncio.run(
        exercise(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )


async def _success_publisher(_: IntentCommand) -> PublishOutcome:
    return PublishOutcome.SUCCEEDED


def _seed_approved_intent(database_url: str) -> dict[str, UUID]:
    identifiers = {
        "project_id": uuid4(),
        "other_project_id": uuid4(),
        "content_id": uuid4(),
        "content_version_id": uuid4(),
        "artifact_id": uuid4(),
        "account_id": uuid4(),
        "candidate_id": uuid4(),
        "approval_request_id": uuid4(),
        "approval_snapshot_id": uuid4(),
        "approver_subject_id": uuid4(),
        "intent_id": uuid4(),
        "outbox_id": uuid4(),
    }
    digest = bytes.fromhex("31" * 32)
    account_hash = bytes.fromhex("51" * 32)
    current = datetime.now(UTC)
    decided_at = current.replace(microsecond=(current.microsecond // 1000) * 1000) - timedelta(
        minutes=1
    )
    expires_at = decided_at + timedelta(days=1)
    candidate_material = CandidateHashInputV1(
        title="Letter 1",
        caption="Caption",
        tags=("writing", "xiaohongshu"),
        ordered_asset_hashes=(digest.hex(),),
        ai_disclosure="AI-assisted visual",
        platform="xiaohongshu_pack",
        account_id=identifiers["account_id"],
        policy_version="policy-v1",
    )
    candidate_result = candidate_hash(candidate_material)
    snapshot_material = ApprovalSnapshotHashInputV1(
        project_id=identifiers["project_id"],
        approval_request_id=identifiers["approval_request_id"],
        candidate_id=identifiers["candidate_id"],
        account_id=identifiers["account_id"],
        decision=ApprovalDecision.APPROVED,
        candidate_hash=candidate_result.sha256,
        fact_report_hash="61" * 32,
        rights_manifest_hash="62" * 32,
        risk_report_hash="63" * 32,
        account_hash=account_hash.hex(),
        policy_version="policy-v1",
        approved_action="PACKAGE_EXPORT",
        approver_subject_ids=(identifiers["approver_subject_id"],),
        expires_at=expires_at,
        decided_at=decided_at,
    )
    snapshot_result = approval_snapshot_hash(snapshot_material)
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO ip_projects (id, slug, name) VALUES (%s, 'm1-main', 'M1 main')",
            (identifiers["project_id"],),
        )
        connection.execute(
            "INSERT INTO ip_projects (id, slug, name) VALUES (%s, 'm1-other', 'M1 other')",
            (identifiers["other_project_id"],),
        )
        connection.execute(
            """
            INSERT INTO content_units (id, project_id, state, trace_id)
            VALUES (%s, %s, 'PLANNED', %s)
            """,
            (identifiers["content_id"], identifiers["project_id"], uuid4()),
        )
        connection.execute(
            """
            INSERT INTO content_versions (
                id, project_id, content_unit_id, version, payload, content_hash,
                created_by_subject_id
            ) VALUES (%s, %s, %s, 1, '{}'::jsonb, %s, %s)
            """,
            (
                identifiers["content_version_id"],
                identifiers["project_id"],
                identifiers["content_id"],
                bytes.fromhex("21" * 32),
                uuid4(),
            ),
        )
        connection.execute(
            """
            INSERT INTO artifacts (
                id, project_id, content_unit_id, object_key, object_version, media_type,
                byte_size, sha256_digest, rights_status
            ) VALUES (%s, %s, %s, 'letters/1.jpg', 'v1', 'image/jpeg', 1024, %s, 'APPROVED')
            """,
            (
                identifiers["artifact_id"],
                identifiers["project_id"],
                identifiers["content_id"],
                digest,
            ),
        )
        connection.execute(
            """
            INSERT INTO asset_rights (
                id, project_id, artifact_id, status, rights_type, scope, valid_from,
                valid_until, evidence_artifact_id
            ) VALUES (
                %s, %s, %s, 'APPROVED', 'synthetic-fixture', '{"platform":"package"}',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + interval '1 year', %s
            )
            """,
            (
                uuid4(),
                identifiers["project_id"],
                identifiers["artifact_id"],
                identifiers["artifact_id"],
            ),
        )
        connection.execute(
            """
            INSERT INTO platform_accounts (
                id, project_id, platform, environment, status, capabilities_version,
                account_fingerprint
            ) VALUES (%s, %s, 'xiaohongshu_pack', 'PACKAGE', 'ACTIVE', 'v1', %s)
            """,
            (identifiers["account_id"], identifiers["project_id"], account_hash),
        )
        connection.execute(
            """
            INSERT INTO platform_candidates (
                id, project_id, content_unit_id, content_version_id, account_id, platform,
                title, caption, normalized_tags, ai_disclosure, policy_version,
                canonical_payload, candidate_hash
            ) VALUES (
                %s, %s, %s, %s, %s, 'xiaohongshu_pack', 'Letter 1', 'Caption',
                ARRAY['writing', 'xiaohongshu'], 'AI-assisted visual', 'policy-v1',
                %s, %s
            )
            """,
            (
                identifiers["candidate_id"],
                identifiers["project_id"],
                identifiers["content_id"],
                identifiers["content_version_id"],
                identifiers["account_id"],
                Jsonb(candidate_payload(candidate_material)),
                bytes.fromhex(candidate_result.sha256),
            ),
        )
        connection.execute(
            """
            INSERT INTO platform_candidate_states (candidate_id, project_id, state)
            VALUES (%s, %s, 'WAITING_APPROVAL')
            """,
            (identifiers["candidate_id"], identifiers["project_id"]),
        )
        connection.execute(
            """
            INSERT INTO candidate_artifacts (
                project_id, candidate_id, position, artifact_id, artifact_hash
            ) VALUES (%s, %s, 0, %s, %s)
            """,
            (
                identifiers["project_id"],
                identifiers["candidate_id"],
                identifiers["artifact_id"],
                digest,
            ),
        )
        connection.execute(
            """
            INSERT INTO approval_requests (
                id, project_id, candidate_id, risk_level, requested_action,
                required_approvals, status, requested_by_subject_id, expires_at, resolved_at
            ) VALUES (
                %s, %s, %s, 'R1', 'PACKAGE_EXPORT', 1, 'APPROVED', %s,
                %s, %s
            )
            """,
            (
                identifiers["approval_request_id"],
                identifiers["project_id"],
                identifiers["candidate_id"],
                uuid4(),
                expires_at,
                decided_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO approval_snapshots (
                id, project_id, approval_request_id, candidate_id, account_id, decision,
                candidate_hash, fact_report_hash, rights_manifest_hash, risk_report_hash,
                policy_version, account_hash, approved_action, approver_subject_ids,
                expires_at, decided_at, snapshot_hash
            ) VALUES (
                %s, %s, %s, %s, %s, 'APPROVED', %s, %s, %s, %s, 'policy-v1', %s,
                'PACKAGE_EXPORT', ARRAY[%s]::uuid[], %s, %s, %s
            )
            """,
            (
                identifiers["approval_snapshot_id"],
                identifiers["project_id"],
                identifiers["approval_request_id"],
                identifiers["candidate_id"],
                identifiers["account_id"],
                bytes.fromhex(candidate_result.sha256),
                bytes.fromhex("61" * 32),
                bytes.fromhex("62" * 32),
                bytes.fromhex("63" * 32),
                account_hash,
                identifiers["approver_subject_id"],
                expires_at,
                decided_at,
                bytes.fromhex(snapshot_result.sha256),
            ),
        )
        with connection.transaction():
            _insert_intent_pair(
                connection,
                identifiers,
                intent_id=identifiers["intent_id"],
                outbox_id=identifiers["outbox_id"],
                fingerprint=bytes.fromhex("77" * 32),
            )
    return identifiers


def _new_command(
    database_url: str,
    identifiers: dict[str, UUID],
    *,
    schedule_hour: int,
) -> IntentCommand:
    schedule_slot = datetime.now(UTC).replace(
        hour=schedule_hour, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    with psycopg.connect(database_url) as connection:
        candidate_hash_value, platform = connection.execute(
            "SELECT candidate_hash, platform FROM platform_candidates WHERE id = %s",
            (identifiers["candidate_id"],),
        ).fetchone()
    fingerprint = publish_request_fingerprint(
        PublishRequestFingerprintInputV1(
            candidate_hash=bytes(candidate_hash_value).hex(),
            platform=platform,
            account_id=identifiers["account_id"],
            normalized_schedule_slot=schedule_slot,
        )
    ).sha256
    return IntentCommand(
        project_id=str(identifiers["project_id"]),
        candidate_id=str(identifiers["candidate_id"]),
        approval_snapshot_id=str(identifiers["approval_snapshot_id"]),
        account_id=str(identifiers["account_id"]),
        intent_id=str(uuid4()),
        outbox_id=str(uuid4()),
        request_fingerprint=fingerprint,
        normalized_schedule_slot=schedule_slot.isoformat(),
    )


async def _exercise_real_workflow_activities(
    database_url: str, identifiers: dict[str, UUID]
) -> None:
    activities = PostgresWorkflowActivities(database_url)
    transition = StateTransition(
        project_id=str(identifiers["project_id"]),
        resource_id=str(identifiers["candidate_id"]),
        expected_version=0,
        target_state="APPROVED",
    )
    assert await activities.advance_candidate_state(transition) == 1
    assert await activities.advance_candidate_state(transition) == 1

    schedule_slot = datetime(2026, 8, 22, 2, tzinfo=UTC)
    with psycopg.connect(database_url) as connection:
        candidate_hash_value, platform = connection.execute(
            "SELECT candidate_hash, platform FROM platform_candidates WHERE id = %s",
            (identifiers["candidate_id"],),
        ).fetchone()
    request_fingerprint = publish_request_fingerprint(
        PublishRequestFingerprintInputV1(
            candidate_hash=bytes(candidate_hash_value).hex(),
            platform=platform,
            account_id=identifiers["account_id"],
            normalized_schedule_slot=schedule_slot,
        )
    ).sha256
    command = IntentCommand(
        project_id=str(identifiers["project_id"]),
        candidate_id=str(identifiers["candidate_id"]),
        approval_snapshot_id=str(identifiers["approval_snapshot_id"]),
        account_id=str(identifiers["account_id"]),
        intent_id=str(uuid4()),
        outbox_id=str(uuid4()),
        request_fingerprint=request_fingerprint,
        normalized_schedule_slot="2026-08-22T02:00:00+00:00",
    )
    await activities.create_publish_intent_and_outbox(command)
    await activities.create_publish_intent_and_outbox(command)


def _insert_intent_pair(
    connection: psycopg.Connection[tuple[object, ...]],
    identifiers: dict[str, UUID],
    *,
    intent_id: UUID,
    outbox_id: UUID,
    fingerprint: bytes,
) -> None:
    connection.execute(
        """
        INSERT INTO outbox_messages (
            id, project_id, publish_intent_id, topic, payload, occurred_at, available_at
        ) VALUES (%s, %s, %s, 'publish.mock.requested', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            outbox_id,
            identifiers["project_id"],
            intent_id,
            Jsonb({"intent_id": str(intent_id)}),
        ),
    )
    connection.execute(
        """
        INSERT INTO publish_intents (
            id, project_id, candidate_id, approval_snapshot_id, account_id,
            outbox_message_id, request_fingerprint, normalized_schedule_slot
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (
            intent_id,
            identifiers["project_id"],
            identifiers["candidate_id"],
            identifiers["approval_snapshot_id"],
            identifiers["account_id"],
            outbox_id,
            fingerprint,
        ),
    )


def _insert_audit_event(
    connection: psycopg.Connection[tuple[object, ...]],
    project_id: UUID,
    previous_hash: bytes | None,
    event_hash: bytes,
) -> UUID:
    event_id = uuid4()
    connection.execute(
        """
        INSERT INTO audit_events (
            id, project_id, actor_type, actor_id, action, resource_type, trace_id,
            payload, previous_event_hash, event_hash, occurred_at
        ) VALUES (
            %s, %s, 'SERVICE', %s, 'test.event', 'integration-test', %s,
            '{}'::jsonb, %s, %s, CURRENT_TIMESTAMP
        )
        """,
        (event_id, project_id, uuid4(), uuid4(), previous_hash, event_hash),
    )
    return event_id


@pytest.mark.parametrize(
    ("decision", "request_status", "candidate_state", "valid", "reasons"),
    [
        (ApprovalDecision.APPROVED, "APPROVED", "APPROVED", True, ()),
        (
            ApprovalDecision.REJECTED,
            "REJECTED",
            "REJECTED",
            False,
            (ApprovalInvalidationReason.DECISION_NOT_APPROVED,),
        ),
        (
            ApprovalDecision.REVISION_REQUESTED,
            "REVISION_REQUESTED",
            "REVISION_REQUESTED",
            False,
            (ApprovalInvalidationReason.DECISION_NOT_APPROVED,),
        ),
    ],
)
def test_approval_service_records_server_side_human_decisions_atomically(
    database_url: str,
    decision: ApprovalDecision,
    request_status: str,
    candidate_state: str,
    valid: bool,
    reasons: tuple[ApprovalInvalidationReason, ...],
) -> None:
    identifiers = _seed_pending_approval(database_url)
    service = PostgresApprovalService(database_url)
    actor = _approval_actor(identifiers)

    pending = service.get_request(
        actor, identifiers["project_id"], identifiers["approval_request_id"]
    )
    result = service.decide(
        actor,
        identifiers["project_id"],
        identifiers["approval_request_id"],
        ApprovalDecisionCommandV1(decision=decision, expected_version=0),
        decided_at=identifiers["decision_time"],
    )

    assert pending.status is ApprovalRequestStatus.PENDING
    assert pending.approval_valid is None
    assert pending.viewer_subject_id == identifiers["approver_subject_id"]
    assert result.status.value == request_status
    assert result.candidate_state == candidate_state
    assert result.state_version == 1
    assert result.candidate_state_version == 1
    assert result.approver_subject_ids == (identifiers["approver_subject_id"],)
    assert result.approval_valid is valid
    assert result.invalidation_reasons == reasons
    assert result.snapshot_hash is not None
    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM approval_snapshots WHERE approval_request_id = %s",
            (identifiers["approval_request_id"],),
        ).fetchone() == (1,)


def test_approval_service_enforces_identity_project_role_and_initiator_separation(
    database_url: str,
) -> None:
    identifiers = _seed_pending_approval(database_url)
    service = PostgresApprovalService(database_url)
    actor = _approval_actor(identifiers)
    command = ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=0)

    with pytest.raises(ApprovalForbidden, match="only a human"):
        service.get_request(
            actor.model_copy(update={"actor_type": ApprovalActorType.AGENT}),
            identifiers["project_id"],
            identifiers["approval_request_id"],
        )
    with pytest.raises(ApprovalForbidden, match="approver role"):
        service.get_request(
            actor.model_copy(update={"roles": ("VIEWER",)}),
            identifiers["project_id"],
            identifiers["approval_request_id"],
        )
    with pytest.raises(ApprovalForbidden, match="not authorized"):
        service.get_request(
            actor.model_copy(update={"project_ids": (uuid4(),)}),
            identifiers["project_id"],
            identifiers["approval_request_id"],
        )
    with pytest.raises(ApprovalForbidden, match="initiator cannot"):
        service.decide(
            actor.model_copy(update={"subject_id": identifiers["requested_by_subject_id"]}),
            identifiers["project_id"],
            identifiers["approval_request_id"],
            command,
        )
    with pytest.raises(ApprovalNotFound, match="not found"):
        service.get_request(actor, identifiers["project_id"], uuid4())


def test_approval_service_exposes_invalidation_after_account_binding_changes(
    database_url: str,
) -> None:
    identifiers = _seed_pending_approval(database_url)
    service = PostgresApprovalService(database_url)
    actor = _approval_actor(identifiers)
    service.decide(
        actor,
        identifiers["project_id"],
        identifiers["approval_request_id"],
        ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=0),
        decided_at=identifiers["decision_time"],
    )

    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            "UPDATE platform_accounts SET account_fingerprint = %s "
            "WHERE project_id = %s AND id = %s",
            (bytes.fromhex("71" * 32), identifiers["project_id"], identifiers["account_id"]),
        )

    invalidated = service.get_request(
        actor,
        identifiers["project_id"],
        identifiers["approval_request_id"],
        checked_at=identifiers["decision_time"] + timedelta(minutes=1),
    )
    assert invalidated.status is ApprovalRequestStatus.APPROVED
    assert invalidated.approval_valid is False
    assert invalidated.invalidation_reasons == (ApprovalInvalidationReason.ACCOUNT_CHANGED,)


def test_approval_service_fails_closed_on_stale_terminal_r4_and_unsupported_requests(
    database_url: str,
) -> None:
    service = PostgresApprovalService(database_url)
    stale = _seed_pending_approval(database_url)
    actor = _approval_actor(stale)
    with pytest.raises(ApprovalConflict, match="version is stale"):
        service.decide(
            actor,
            stale["project_id"],
            stale["approval_request_id"],
            ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=1),
        )

    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            "UPDATE platform_candidate_states SET state = 'RISK_ROUTING' WHERE candidate_id = %s",
            (stale["candidate_id"],),
        )
    with pytest.raises(ApprovalConflict, match="not waiting"):
        service.decide(
            actor,
            stale["project_id"],
            stale["approval_request_id"],
            ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=0),
        )

    two_people = _seed_pending_approval(database_url, required_approvals=2)
    with pytest.raises(ApprovalConflict, match="supports one"):
        service.decide(
            _approval_actor(two_people),
            two_people["project_id"],
            two_people["approval_request_id"],
            ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=0),
        )

    r4 = _seed_pending_approval(database_url, risk_level="R4")
    with pytest.raises(ApprovalConflict, match="R4 candidates"):
        service.decide(
            _approval_actor(r4),
            r4["project_id"],
            r4["approval_request_id"],
            ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=0),
        )

    resolved = _seed_pending_approval(database_url)
    resolved_actor = _approval_actor(resolved)
    resolved_command = ApprovalDecisionCommandV1(
        decision=ApprovalDecision.REJECTED, expected_version=0
    )
    service.decide(
        resolved_actor,
        resolved["project_id"],
        resolved["approval_request_id"],
        resolved_command,
        decided_at=resolved["decision_time"],
    )
    with pytest.raises(ApprovalConflict, match="already resolved"):
        service.decide(
            resolved_actor,
            resolved["project_id"],
            resolved["approval_request_id"],
            ApprovalDecisionCommandV1(
                decision=ApprovalDecision.REJECTED,
                expected_version=1,
            ),
            decided_at=resolved["decision_time"],
        )


def test_approval_service_exposes_and_persists_expiry_without_snapshot(
    database_url: str,
) -> None:
    checked_at = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    identifiers = _seed_pending_approval(
        database_url,
        created_at=checked_at - timedelta(days=1),
        expires_at=checked_at - timedelta(seconds=1),
    )
    service = PostgresApprovalService(database_url)
    actor = _approval_actor(identifiers)

    view = service.get_request(
        actor,
        identifiers["project_id"],
        identifiers["approval_request_id"],
        checked_at=checked_at,
    )
    assert view.status is ApprovalRequestStatus.EXPIRED
    assert view.approval_valid is False
    assert view.invalidation_reasons == (ApprovalInvalidationReason.EXPIRED,)

    with pytest.raises(ApprovalConflict, match="has expired"):
        service.decide(
            actor,
            identifiers["project_id"],
            identifiers["approval_request_id"],
            ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=0),
            decided_at=checked_at,
        )
    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            "SELECT status, state_version FROM approval_requests WHERE id = %s",
            (identifiers["approval_request_id"],),
        ).fetchone() == ("EXPIRED", 1)
        assert connection.execute(
            "SELECT state, state_version FROM platform_candidate_states WHERE candidate_id = %s",
            (identifiers["candidate_id"],),
        ).fetchone() == ("APPROVAL_EXPIRED", 1)
        assert connection.execute(
            "SELECT count(*) FROM approval_snapshots WHERE approval_request_id = %s",
            (identifiers["approval_request_id"],),
        ).fetchone() == (0,)


def test_approval_service_rejects_submillisecond_snapshot_material(database_url: str) -> None:
    decision_time = datetime(2026, 8, 22, 10, 0, 0, 1, tzinfo=UTC)
    identifiers = _seed_pending_approval(database_url, decision_time=decision_time)
    service = PostgresApprovalService(database_url)

    with pytest.raises(ApprovalConflict, match="cannot be canonicalized") as captured:
        service.decide(
            _approval_actor(identifiers),
            identifiers["project_id"],
            identifiers["approval_request_id"],
            ApprovalDecisionCommandV1(decision=ApprovalDecision.APPROVED, expected_version=0),
            decided_at=decision_time,
        )
    assert isinstance(captured.value.__cause__, ValueError)


def _approval_actor(identifiers: dict[str, UUID | datetime]) -> ApprovalActorV1:
    return ApprovalActorV1(
        subject_id=identifiers["approver_subject_id"],
        actor_type=ApprovalActorType.HUMAN,
        roles=("APPROVER",),
        project_ids=(identifiers["project_id"],),
    )


def _seed_pending_approval(
    database_url: str,
    *,
    risk_level: str = "R1",
    required_approvals: int = 1,
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
    decision_time: datetime | None = None,
) -> dict[str, UUID | datetime]:
    migrate(database_url)
    now = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)
    created = created_at or now
    expiry = expires_at or now + timedelta(days=1)
    identifiers: dict[str, UUID | datetime] = {
        "project_id": uuid4(),
        "content_id": uuid4(),
        "content_version_id": uuid4(),
        "account_id": uuid4(),
        "candidate_id": uuid4(),
        "approval_request_id": uuid4(),
        "approver_subject_id": uuid4(),
        "requested_by_subject_id": uuid4(),
        "decision_time": decision_time or now + timedelta(minutes=1),
    }
    account_hash = bytes.fromhex("51" * 32)
    candidate_material = CandidateHashInputV1(
        title="她写给世界的信｜第一封",
        caption="写给仍然愿意认真生活的人。",
        tags=("写作", "她写给世界的信"),
        ordered_asset_hashes=("31" * 32,),
        ai_disclosure="AI辅助视觉",
        platform="xiaohongshu_pack",
        account_id=identifiers["account_id"],
        policy_version="policy-v1",
    )
    candidate_result = candidate_hash(candidate_material)
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO ip_projects (id, slug, name) VALUES (%s, %s, 'Approval test')",
            (
                identifiers["project_id"],
                f"approval-{str(identifiers['project_id'])[:8]}",
            ),
        )
        connection.execute(
            """
            INSERT INTO content_units (id, project_id, state, trace_id)
            VALUES (%s, %s, 'CANDIDATES_ACTIVE', %s)
            """,
            (identifiers["content_id"], identifiers["project_id"], uuid4()),
        )
        connection.execute(
            """
            INSERT INTO content_versions (
                id, project_id, content_unit_id, version, payload, content_hash,
                created_by_subject_id
            ) VALUES (%s, %s, %s, 1, '{}'::jsonb, %s, %s)
            """,
            (
                identifiers["content_version_id"],
                identifiers["project_id"],
                identifiers["content_id"],
                bytes.fromhex("21" * 32),
                uuid4(),
            ),
        )
        connection.execute(
            """
            INSERT INTO platform_accounts (
                id, project_id, platform, environment, status, capabilities_version,
                account_fingerprint
            ) VALUES (%s, %s, 'xiaohongshu_pack', 'PACKAGE', 'ACTIVE', 'v1', %s)
            """,
            (identifiers["account_id"], identifiers["project_id"], account_hash),
        )
        connection.execute(
            """
            INSERT INTO platform_candidates (
                id, project_id, content_unit_id, content_version_id, account_id, platform,
                title, caption, normalized_tags, ai_disclosure, policy_version,
                canonical_payload, candidate_hash
            ) VALUES (
                %s, %s, %s, %s, %s, 'xiaohongshu_pack',
                '她写给世界的信｜第一封', '写给仍然愿意认真生活的人。',
                ARRAY['写作', '她写给世界的信'], 'AI辅助视觉', 'policy-v1', %s, %s
            )
            """,
            (
                identifiers["candidate_id"],
                identifiers["project_id"],
                identifiers["content_id"],
                identifiers["content_version_id"],
                identifiers["account_id"],
                Jsonb(candidate_payload(candidate_material)),
                bytes.fromhex(candidate_result.sha256),
            ),
        )
        connection.execute(
            """
            INSERT INTO platform_candidate_states (candidate_id, project_id, state)
            VALUES (%s, %s, 'WAITING_APPROVAL')
            """,
            (identifiers["candidate_id"], identifiers["project_id"]),
        )
        connection.execute(
            """
            INSERT INTO approval_requests (
                id, project_id, candidate_id, risk_level, requested_action,
                required_approvals, status, requested_by_subject_id, expires_at, created_at
            ) VALUES (%s, %s, %s, %s, 'PACKAGE_EXPORT', %s, 'PENDING', %s, %s, %s)
            """,
            (
                identifiers["approval_request_id"],
                identifiers["project_id"],
                identifiers["candidate_id"],
                risk_level,
                required_approvals,
                identifiers["requested_by_subject_id"],
                expiry,
                created,
            ),
        )
        connection.execute(
            """
            INSERT INTO approval_request_bindings (
                approval_request_id, project_id, candidate_id, account_id, candidate_hash,
                fact_report_hash, rights_manifest_hash, risk_report_hash, policy_version,
                account_hash, requested_action
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'policy-v1', %s, 'PACKAGE_EXPORT')
            """,
            (
                identifiers["approval_request_id"],
                identifiers["project_id"],
                identifiers["candidate_id"],
                identifiers["account_id"],
                bytes.fromhex(candidate_result.sha256),
                bytes.fromhex("61" * 32),
                bytes.fromhex("62" * 32),
                bytes.fromhex("63" * 32),
                account_hash,
            ),
        )
    return identifiers
