"""Cross-runtime canonical JSON, candidate hashes, and approval validity."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field

from agent_ip_data_models.core import (
    ApprovalDecision,
    ApprovalSnapshotV1,
    FrozenBoundaryModel,
    Sha256Hex,
    require_aware_datetime,
)

MAX_SAFE_INTEGER = 9_007_199_254_740_991
type CanonicalValue = (
    None | bool | int | str | Sequence[CanonicalValue] | Mapping[str, CanonicalValue]
)


class CanonicalJsonError(ValueError):
    """Raised when a value cannot be represented by canonical JSON v1."""


def require_non_blank(value: str) -> str:
    """Preserve exact text while rejecting an empty or whitespace-only value."""

    if not value.strip():
        raise ValueError("text must contain a non-whitespace character")
    return value


PreservedNonBlankText = Annotated[str, AfterValidator(require_non_blank)]


def normalize_unicode(value: str) -> str:
    """Return NFC text and reject Unicode surrogate code points."""

    normalized = unicodedata.normalize("NFC", value)
    if any(0xD800 <= ord(character) <= 0xDFFF for character in normalized):
        raise CanonicalJsonError("Unicode surrogate code points are not supported")
    return normalized


def _encode_string(value: str) -> str:
    return json.dumps(normalize_unicode(value), ensure_ascii=False, separators=(",", ":"))


def _canonical_text(value: CanonicalValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise CanonicalJsonError("integer is outside the IEEE-754 safe range")
        return str(value)
    if isinstance(value, str):
        return _encode_string(value)
    if isinstance(value, Mapping):
        normalized_items: dict[str, CanonicalValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalJsonError("object keys must be strings")
            normalized_key = normalize_unicode(key)
            if normalized_key in normalized_items:
                raise CanonicalJsonError("object keys collide after Unicode NFC normalization")
            normalized_items[normalized_key] = item
        ordered_keys = sorted(normalized_items, key=lambda item: item.encode("utf-8"))
        return (
            "{"
            + ",".join(
                f"{_encode_string(key)}:{_canonical_text(normalized_items[key])}"
                for key in ordered_keys
            )
            + "}"
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ",".join(_canonical_text(item) for item in value) + "]"
    raise CanonicalJsonError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(value: CanonicalValue) -> bytes:
    """Encode a supported value as canonical JSON v1 UTF-8 bytes."""

    return _canonical_text(value).encode("utf-8")


def canonical_json_text(value: CanonicalValue) -> str:
    """Encode a supported value as canonical JSON v1 text."""

    return canonical_json_bytes(value).decode("utf-8")


class CanonicalHashV1(FrozenBoundaryModel):
    """Canonical bytes rendered as text plus their SHA-256 identity."""

    schema_version: Literal[1] = 1
    canonical_json: str
    sha256: Sha256Hex


def hash_canonical_json(value: CanonicalValue) -> CanonicalHashV1:
    """Return canonical text and the lowercase SHA-256 digest of its UTF-8 bytes."""

    encoded = canonical_json_bytes(value)
    return CanonicalHashV1(
        canonical_json=encoded.decode("utf-8"),
        sha256=hashlib.sha256(encoded).hexdigest(),
    )


def canonical_utc_milliseconds(value: datetime) -> str:
    """Return an aware timestamp as UTC RFC 3339 with lossless millisecond precision."""

    require_aware_datetime(value)
    if value.microsecond % 1000:
        raise CanonicalJsonError("timestamp has unsupported sub-millisecond precision")
    normalized = value.astimezone(UTC)
    milliseconds = normalized.microsecond // 1000
    return (
        f"{normalized.year:04d}-{normalized.month:02d}-{normalized.day:02d}T"
        f"{normalized.hour:02d}:{normalized.minute:02d}:{normalized.second:02d}."
        f"{milliseconds:03d}Z"
    )


def _utf8_sort_key(value: str) -> bytes:
    return value.encode("utf-8")


def normalize_sorted_tags(tags: Sequence[str]) -> tuple[str, ...]:
    """Normalize, validate, deduplicate, and UTF-8-sort candidate tags."""

    normalized: set[str] = set()
    for tag in tags:
        candidate = normalize_unicode(tag).strip()
        if not candidate:
            raise CanonicalJsonError("candidate tags must not be blank")
        normalized.add(candidate)
    return tuple(sorted(normalized, key=_utf8_sort_key))


class CandidateHashInputV1(FrozenBoundaryModel):
    """Final candidate fields whose exact values determine candidate identity."""

    schema_version: Literal[1] = 1
    title: PreservedNonBlankText
    caption: str
    tags: tuple[str, ...]
    ordered_asset_hashes: tuple[Sha256Hex, ...] = Field(min_length=1)
    ai_disclosure: PreservedNonBlankText
    platform: PreservedNonBlankText
    account_id: UUID
    policy_version: PreservedNonBlankText


def candidate_payload(value: CandidateHashInputV1) -> dict[str, CanonicalValue]:
    """Build the normative candidate-hash payload."""

    return {
        "account_id": str(value.account_id),
        "ai_disclosure": value.ai_disclosure,
        "caption": value.caption,
        "ordered_asset_hashes": value.ordered_asset_hashes,
        "platform": value.platform,
        "policy_version": value.policy_version,
        "sorted_tags": normalize_sorted_tags(value.tags),
        "title": value.title,
    }


def candidate_hash(value: CandidateHashInputV1) -> CanonicalHashV1:
    """Compute candidate identity over canonical JSON v1."""

    return hash_canonical_json(candidate_payload(value))


class ApprovalSnapshotHashInputV1(FrozenBoundaryModel):
    """All immutable fields bound by an approval hash; MVP accepts one approver."""

    schema_version: Literal[1] = 1
    project_id: UUID
    approval_request_id: UUID
    candidate_id: UUID
    account_id: UUID
    decision: ApprovalDecision
    candidate_hash: Sha256Hex
    fact_report_hash: Sha256Hex
    rights_manifest_hash: Sha256Hex
    risk_report_hash: Sha256Hex
    account_hash: Sha256Hex
    policy_version: PreservedNonBlankText
    approved_action: PreservedNonBlankText
    approver_subject_ids: tuple[UUID, ...] = Field(min_length=1, max_length=2)
    expires_at: datetime
    decided_at: datetime


def approval_snapshot_payload(
    value: ApprovalSnapshotHashInputV1,
) -> dict[str, CanonicalValue]:
    """Build the payload; one human is sufficient and any optional second is distinct."""

    approvers = tuple(
        sorted((str(item) for item in value.approver_subject_ids), key=_utf8_sort_key)
    )
    if len(set(approvers)) != len(approvers):
        raise CanonicalJsonError("approval snapshots require distinct approvers")
    return {
        "account_hash": value.account_hash,
        "account_id": str(value.account_id),
        "approval_request_id": str(value.approval_request_id),
        "approved_action": value.approved_action,
        "approver_subject_ids": approvers,
        "candidate_hash": value.candidate_hash,
        "candidate_id": str(value.candidate_id),
        "decided_at": canonical_utc_milliseconds(value.decided_at),
        "decision": value.decision.value,
        "expires_at": canonical_utc_milliseconds(value.expires_at),
        "fact_report_hash": value.fact_report_hash,
        "policy_version": value.policy_version,
        "project_id": str(value.project_id),
        "rights_manifest_hash": value.rights_manifest_hash,
        "risk_report_hash": value.risk_report_hash,
        "schema_version": value.schema_version,
    }


def approval_snapshot_hash(value: ApprovalSnapshotHashInputV1) -> CanonicalHashV1:
    """Compute approval snapshot identity over canonical JSON v1."""

    return hash_canonical_json(approval_snapshot_payload(value))


class ApprovalBindingV1(FrozenBoundaryModel):
    """Current authoritative values that an approval must still match."""

    schema_version: Literal[1] = 1
    candidate_id: UUID
    account_id: UUID
    candidate_hash: Sha256Hex
    fact_report_hash: Sha256Hex
    rights_manifest_hash: Sha256Hex
    risk_report_hash: Sha256Hex
    account_hash: Sha256Hex
    policy_version: PreservedNonBlankText
    approved_action: PreservedNonBlankText


class ApprovalInvalidationReason(StrEnum):
    """Fail-closed reasons exposed to later workflow/API layers."""

    SNAPSHOT_HASH_MISMATCH = "SNAPSHOT_HASH_MISMATCH"
    DECISION_NOT_APPROVED = "DECISION_NOT_APPROVED"
    EXPIRED = "EXPIRED"
    CANDIDATE_CHANGED = "CANDIDATE_CHANGED"
    FACT_REPORT_CHANGED = "FACT_REPORT_CHANGED"
    RIGHTS_MANIFEST_CHANGED = "RIGHTS_MANIFEST_CHANGED"
    RISK_REPORT_CHANGED = "RISK_REPORT_CHANGED"
    POLICY_CHANGED = "POLICY_CHANGED"
    ACCOUNT_CHANGED = "ACCOUNT_CHANGED"
    ACTION_CHANGED = "ACTION_CHANGED"


class ApprovalValidityV1(FrozenBoundaryModel):
    """Deterministic approval validity result."""

    schema_version: Literal[1] = 1
    valid: bool
    reasons: tuple[ApprovalInvalidationReason, ...]


def _snapshot_hash_input(snapshot: ApprovalSnapshotV1) -> ApprovalSnapshotHashInputV1:
    return ApprovalSnapshotHashInputV1(
        project_id=snapshot.project_id,
        approval_request_id=snapshot.approval_request_id,
        candidate_id=snapshot.candidate_id,
        account_id=snapshot.account_id,
        decision=snapshot.decision,
        candidate_hash=snapshot.candidate_hash,
        fact_report_hash=snapshot.fact_report_hash,
        rights_manifest_hash=snapshot.rights_manifest_hash,
        risk_report_hash=snapshot.risk_report_hash,
        account_hash=snapshot.account_hash,
        policy_version=snapshot.policy_version,
        approved_action=snapshot.approved_action,
        approver_subject_ids=snapshot.approver_subject_ids,
        expires_at=snapshot.expires_at,
        decided_at=snapshot.decided_at,
    )


def evaluate_approval(
    snapshot: ApprovalSnapshotV1,
    current: ApprovalBindingV1,
    *,
    checked_at: datetime,
) -> ApprovalValidityV1:
    """Fail closed when an approval is altered, expired, or no longer bound to truth."""

    require_aware_datetime(checked_at)
    reasons: list[ApprovalInvalidationReason] = []
    try:
        expected_hash = approval_snapshot_hash(_snapshot_hash_input(snapshot)).sha256
    except ValueError:
        expected_hash = ""
    if expected_hash != snapshot.snapshot_hash:
        reasons.append(ApprovalInvalidationReason.SNAPSHOT_HASH_MISMATCH)
    if snapshot.decision is not ApprovalDecision.APPROVED:
        reasons.append(ApprovalInvalidationReason.DECISION_NOT_APPROVED)
    if checked_at >= snapshot.expires_at:
        reasons.append(ApprovalInvalidationReason.EXPIRED)
    if (
        current.candidate_id != snapshot.candidate_id
        or current.candidate_hash != snapshot.candidate_hash
    ):
        reasons.append(ApprovalInvalidationReason.CANDIDATE_CHANGED)
    if current.fact_report_hash != snapshot.fact_report_hash:
        reasons.append(ApprovalInvalidationReason.FACT_REPORT_CHANGED)
    if current.rights_manifest_hash != snapshot.rights_manifest_hash:
        reasons.append(ApprovalInvalidationReason.RIGHTS_MANIFEST_CHANGED)
    if current.risk_report_hash != snapshot.risk_report_hash:
        reasons.append(ApprovalInvalidationReason.RISK_REPORT_CHANGED)
    if current.policy_version != snapshot.policy_version:
        reasons.append(ApprovalInvalidationReason.POLICY_CHANGED)
    if current.account_id != snapshot.account_id or current.account_hash != snapshot.account_hash:
        reasons.append(ApprovalInvalidationReason.ACCOUNT_CHANGED)
    if current.approved_action != snapshot.approved_action:
        reasons.append(ApprovalInvalidationReason.ACTION_CHANGED)
    return ApprovalValidityV1(valid=not reasons, reasons=tuple(reasons))
