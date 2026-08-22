from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from agent_ip_data_models import (
    ApprovalBindingV1,
    ApprovalDecision,
    ApprovalInvalidationReason,
    ApprovalSnapshotHashInputV1,
    ApprovalSnapshotV1,
    CandidateHashInputV1,
    CanonicalJsonError,
    approval_snapshot_hash,
    approval_snapshot_payload,
    candidate_hash,
    candidate_payload,
    canonical_json_bytes,
    canonical_json_text,
    canonical_utc_milliseconds,
    evaluate_approval,
    hash_canonical_json,
    normalize_sorted_tags,
)
from pydantic import ValidationError

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "canonical-json-v1.json").read_text(encoding="utf-8")
)


def _candidate_input() -> CandidateHashInputV1:
    values = FIXTURE["candidate_vector"]["input"]
    return CandidateHashInputV1(
        title=values["title"],
        caption=values["caption"],
        tags=tuple(values["tags"]),
        ordered_asset_hashes=tuple(values["ordered_asset_hashes"]),
        ai_disclosure=values["ai_disclosure"],
        platform=values["platform"],
        account_id=UUID(values["account_id"]),
        policy_version=values["policy_version"],
    )


def _approval_input() -> ApprovalSnapshotHashInputV1:
    values = FIXTURE["approval_vector"]["input"]
    return ApprovalSnapshotHashInputV1(
        project_id=UUID(values["project_id"]),
        approval_request_id=UUID(values["approval_request_id"]),
        candidate_id=UUID(values["candidate_id"]),
        account_id=UUID(values["account_id"]),
        decision=ApprovalDecision(values["decision"]),
        candidate_hash=values["candidate_hash"],
        fact_report_hash=values["fact_report_hash"],
        rights_manifest_hash=values["rights_manifest_hash"],
        risk_report_hash=values["risk_report_hash"],
        account_hash=values["account_hash"],
        policy_version=values["policy_version"],
        approved_action=values["approved_action"],
        approver_subject_ids=tuple(UUID(item) for item in values["approver_subject_ids"]),
        expires_at=datetime.fromisoformat(values["expires_at"]),
        decided_at=datetime.fromisoformat(values["decided_at"]),
    )


def _snapshot(material: ApprovalSnapshotHashInputV1) -> ApprovalSnapshotV1:
    return ApprovalSnapshotV1(
        id=uuid4(),
        project_id=material.project_id,
        approval_request_id=material.approval_request_id,
        candidate_id=material.candidate_id,
        account_id=material.account_id,
        decision=material.decision,
        candidate_hash=material.candidate_hash,
        fact_report_hash=material.fact_report_hash,
        rights_manifest_hash=material.rights_manifest_hash,
        risk_report_hash=material.risk_report_hash,
        account_hash=material.account_hash,
        policy_version=material.policy_version,
        approved_action=material.approved_action,
        approver_subject_ids=material.approver_subject_ids,
        expires_at=material.expires_at,
        decided_at=material.decided_at,
        snapshot_hash=approval_snapshot_hash(material).sha256,
    )


def _binding(material: ApprovalSnapshotHashInputV1) -> ApprovalBindingV1:
    return ApprovalBindingV1(
        candidate_id=material.candidate_id,
        account_id=material.account_id,
        candidate_hash=material.candidate_hash,
        fact_report_hash=material.fact_report_hash,
        rights_manifest_hash=material.rights_manifest_hash,
        risk_report_hash=material.risk_report_hash,
        account_hash=material.account_hash,
        policy_version=material.policy_version,
        approved_action=material.approved_action,
    )


def test_python_matches_all_cross_runtime_golden_vectors() -> None:
    assert FIXTURE["spec_version"] == 1
    for vector in FIXTURE["canonical_vectors"]:
        result = hash_canonical_json(vector["input"])
        assert result.canonical_json == vector["canonical_json"]
        assert result.sha256 == vector["sha256"]
        assert canonical_json_bytes(vector["input"]) == vector["canonical_json"].encode()

    candidate = candidate_hash(_candidate_input())
    assert candidate_payload(_candidate_input())["sorted_tags"] == (
        "AI分身",
        "Ångstrom",
        "写作",
    )
    assert candidate.canonical_json == FIXTURE["candidate_vector"]["canonical_json"]
    assert candidate.sha256 == FIXTURE["candidate_vector"]["sha256"]

    approval = approval_snapshot_hash(_approval_input())
    assert approval.canonical_json == FIXTURE["approval_vector"]["canonical_json"]
    assert approval.sha256 == FIXTURE["approval_vector"]["sha256"]


def test_canonical_json_rejects_ambiguous_or_unsupported_values() -> None:
    invalid_values: tuple[Any, ...] = (
        9_007_199_254_740_992,
        -9_007_199_254_740_992,
        1.5,
        b"bytes",
        {1: "not-a-string-key"},
        {"é": 1, "e\u0301": 2},
        "\ud800",
    )
    for value in invalid_values:
        with pytest.raises(CanonicalJsonError):
            canonical_json_text(value)

    with pytest.raises(ValidationError, match="non-whitespace"):
        CandidateHashInputV1(
            title="  ",
            caption="",
            tags=(),
            ordered_asset_hashes=("00" * 32,),
            ai_disclosure="AI",
            platform="mock",
            account_id=uuid4(),
            policy_version="v1",
        )
    with pytest.raises(CanonicalJsonError, match="tags must not be blank"):
        normalize_sorted_tags(("ok", "  "))


def test_time_normalization_is_utc_millisecond_and_lossless() -> None:
    value = datetime(2026, 8, 22, 8, 30, 1, 123000, tzinfo=timezone(timedelta(hours=8)))
    assert canonical_utc_milliseconds(value) == "2026-08-22T00:30:01.123Z"
    with pytest.raises(ValueError, match="UTC offset"):
        canonical_utc_milliseconds(value.replace(tzinfo=None))
    with pytest.raises(CanonicalJsonError, match="sub-millisecond"):
        canonical_utc_milliseconds(value.replace(microsecond=123001))


def test_approval_validity_fails_closed_for_every_bound_change() -> None:
    material = _approval_input()
    snapshot = _snapshot(material)
    binding = _binding(material)
    valid = evaluate_approval(
        snapshot,
        binding,
        checked_at=material.expires_at - timedelta(milliseconds=1),
    )
    assert valid.valid is True
    assert valid.reasons == ()

    single_approver_material = material.model_copy(
        update={"approver_subject_ids": (material.approver_subject_ids[0],)}
    )
    single_approver = evaluate_approval(
        _snapshot(single_approver_material),
        _binding(single_approver_material),
        checked_at=single_approver_material.expires_at - timedelta(milliseconds=1),
    )
    assert single_approver.valid is True
    assert single_approver.reasons == ()

    changed_snapshot = snapshot.model_copy(
        update={"decision": ApprovalDecision.REJECTED, "snapshot_hash": "00" * 32}
    )
    changed_binding = binding.model_copy(
        update={
            "candidate_id": uuid4(),
            "candidate_hash": "01" * 32,
            "fact_report_hash": "02" * 32,
            "rights_manifest_hash": "03" * 32,
            "risk_report_hash": "04" * 32,
            "policy_version": "changed-policy",
            "account_id": uuid4(),
            "account_hash": "05" * 32,
            "approved_action": "CHANGED_ACTION",
        }
    )
    invalid = evaluate_approval(
        changed_snapshot,
        changed_binding,
        checked_at=material.expires_at,
    )
    assert invalid.valid is False
    assert invalid.reasons == tuple(ApprovalInvalidationReason)


def test_snapshot_hash_fails_closed_on_precision_or_duplicate_approvers() -> None:
    material = _approval_input()
    snapshot = _snapshot(material).model_copy(
        update={"decided_at": material.decided_at.replace(microsecond=1)}
    )
    result = evaluate_approval(
        snapshot,
        _binding(material),
        checked_at=material.decided_at,
    )
    assert result.reasons == (ApprovalInvalidationReason.SNAPSHOT_HASH_MISMATCH,)

    duplicate = material.model_copy(
        update={"approver_subject_ids": (material.approver_subject_ids[0],) * 2}
    )
    with pytest.raises(CanonicalJsonError, match="distinct approvers"):
        approval_snapshot_payload(duplicate)

    reversed_approvers = material.model_copy(
        update={"approver_subject_ids": tuple(reversed(material.approver_subject_ids))}
    )
    assert approval_snapshot_hash(reversed_approvers) == approval_snapshot_hash(material)
