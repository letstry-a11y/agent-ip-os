from datetime import UTC, datetime
from uuid import uuid4

import pytest
from agent_ip_data_models import (
    ApprovalDecision,
    ApprovalSnapshotV1,
    ArtifactV1,
    AssetRightV1,
    AuditEventV1,
    CandidateState,
    ContentState,
    ContentUnitV1,
    ContentVersionV1,
    OutboxMessageV1,
    PlatformCandidateV1,
    PublishIntentV1,
    RightsStatus,
)
from pydantic import ValidationError

NOW = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
HASH = "ab" * 32


def test_versioned_schemas_round_trip_without_losing_domain_types() -> None:
    project_id = uuid4()
    content_id = uuid4()
    content_version_id = uuid4()
    account_id = uuid4()
    candidate_id = uuid4()
    approval_request_id = uuid4()
    approval_snapshot_id = uuid4()
    intent_id = uuid4()
    outbox_id = uuid4()
    artifact_id = uuid4()
    evidence_id = uuid4()
    actor_id = uuid4()
    trace_id = uuid4()

    models = (
        ContentUnitV1(
            id=content_id,
            project_id=project_id,
            state=ContentState.PLANNED,
            state_version=0,
            current_content_version=1,
            trace_id=trace_id,
            created_at=NOW,
            updated_at=NOW,
        ),
        ContentVersionV1(
            id=content_version_id,
            project_id=project_id,
            content_unit_id=content_id,
            version=1,
            payload={"letter": "她写给世界的信"},
            content_hash=HASH,
            created_by_subject_id=actor_id,
            created_at=NOW,
        ),
        ArtifactV1(
            id=artifact_id,
            project_id=project_id,
            content_unit_id=content_id,
            object_key="content/letter-001.jpg",
            object_version="v1",
            media_type="image/jpeg",
            byte_size=1024,
            sha256=HASH,
            rights_status=RightsStatus.APPROVED,
            created_at=NOW,
        ),
        AssetRightV1(
            id=uuid4(),
            project_id=project_id,
            artifact_id=artifact_id,
            status=RightsStatus.APPROVED,
            rights_type="identity-derived-portrait",
            scope={"platforms": ["xiaohongshu_pack"]},
            valid_from=NOW,
            valid_until=NOW.replace(year=2027),
            evidence_artifact_id=evidence_id,
        ),
        PlatformCandidateV1(
            id=candidate_id,
            project_id=project_id,
            content_unit_id=content_id,
            content_version_id=content_version_id,
            account_id=account_id,
            platform="xiaohongshu_pack",
            title="她写给世界的信",
            caption="第一封信",
            normalized_tags=("AI分身", "写作"),
            ordered_artifact_ids=(artifact_id,),
            ai_disclosure="AI辅助视觉",
            policy_version="policy-v1",
            canonical_payload={"title": "她写给世界的信"},
            candidate_hash=HASH,
            created_at=NOW,
        ),
        ApprovalSnapshotV1(
            id=approval_snapshot_id,
            project_id=project_id,
            approval_request_id=approval_request_id,
            candidate_id=candidate_id,
            account_id=account_id,
            decision=ApprovalDecision.APPROVED,
            candidate_hash=HASH,
            fact_report_hash=HASH,
            rights_manifest_hash=HASH,
            risk_report_hash=HASH,
            account_hash=HASH,
            policy_version="policy-v1",
            approved_action="PACKAGE_EXPORT",
            approver_subject_ids=(actor_id,),
            expires_at=NOW.replace(day=21),
            decided_at=NOW,
            snapshot_hash=HASH,
        ),
        PublishIntentV1(
            id=intent_id,
            project_id=project_id,
            candidate_id=candidate_id,
            approval_snapshot_id=approval_snapshot_id,
            account_id=account_id,
            outbox_message_id=outbox_id,
            request_fingerprint=HASH,
            normalized_schedule_slot=NOW,
            created_at=NOW,
        ),
        OutboxMessageV1(
            id=outbox_id,
            project_id=project_id,
            publish_intent_id=intent_id,
            topic="publish.mock.requested",
            payload={"intent_id": str(intent_id)},
            occurred_at=NOW,
            available_at=NOW,
        ),
        AuditEventV1(
            id=uuid4(),
            project_id=project_id,
            actor_type="HUMAN",
            actor_id=actor_id,
            action="approval.recorded",
            resource_type="approval_snapshot",
            resource_id=approval_snapshot_id,
            trace_id=trace_id,
            payload={"decision": "APPROVED"},
            event_hash=HASH,
            occurred_at=NOW,
        ),
    )

    for model in models:
        restored = type(model).model_validate_json(model.model_dump_json())
        assert restored == model
        assert restored.schema_version == 1

    assert CandidateState.CANDIDATE_FROZEN.value == "CANDIDATE_FROZEN"


def test_boundary_schemas_fail_closed_on_naive_time_extra_fields_and_mutation() -> None:
    values = {
        "id": uuid4(),
        "project_id": uuid4(),
        "state": ContentState.PLANNED,
        "state_version": 0,
        "current_content_version": 0,
        "trace_id": uuid4(),
        "created_at": datetime(2026, 8, 20, 8, 0),
        "updated_at": NOW,
    }
    with pytest.raises(ValidationError, match="timestamp must include a UTC offset"):
        ContentUnitV1.model_validate(values)

    values["created_at"] = NOW
    values["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ContentUnitV1.model_validate(values)

    values.pop("unexpected")
    unit = ContentUnitV1.model_validate(values)
    with pytest.raises(ValidationError, match="Instance is frozen"):
        unit.state = ContentState.ARCHIVED


def test_sha256_and_schema_versions_are_strict() -> None:
    values = {
        "id": uuid4(),
        "project_id": uuid4(),
        "content_unit_id": uuid4(),
        "version": 1,
        "payload": {},
        "content_hash": "not-a-hash",
        "created_by_subject_id": uuid4(),
        "created_at": NOW,
    }
    with pytest.raises(ValidationError, match="String should match pattern"):
        ContentVersionV1.model_validate(values)

    values["content_hash"] = HASH
    values["schema_version"] = 2
    with pytest.raises(ValidationError, match="Input should be 1"):
        ContentVersionV1.model_validate(values)

    values["schema_version"] = 1
    values["version"] = "1"
    with pytest.raises(ValidationError, match="Input should be a valid integer"):
        ContentVersionV1.model_validate(values)
