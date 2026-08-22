from __future__ import annotations

import asyncio
import selectors
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from agent_ip_data_models import (
    ApprovalDecision,
    ApprovalSnapshotHashInputV1,
    CandidateHashInputV1,
    approval_snapshot_hash,
    candidate_hash,
    candidate_payload,
)
from agent_ip_workflows.activities import PostgresWorkflowActivities
from agent_ip_workflows.models import IntentCommand, StateTransition
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.errors import (
    CheckViolation,
    ForeignKeyViolation,
    ObjectNotInPrerequisiteState,
    UniqueViolation,
)
from psycopg.types.json import Jsonb

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
    decided_at = datetime(2026, 8, 22, 1, 0, 0, tzinfo=UTC)
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

    command = IntentCommand(
        project_id=str(identifiers["project_id"]),
        candidate_id=str(identifiers["candidate_id"]),
        approval_snapshot_id=str(identifiers["approval_snapshot_id"]),
        account_id=str(identifiers["account_id"]),
        intent_id=str(uuid4()),
        outbox_id=str(uuid4()),
        request_fingerprint="78" * 32,
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
