"""PostgreSQL-backed, Mock-identity approval service for M1-06."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from agent_ip_data_models import (
    ApprovalActorType,
    ApprovalActorV1,
    ApprovalBindingV1,
    ApprovalBindingViewV1,
    ApprovalCandidateViewV1,
    ApprovalDecision,
    ApprovalDecisionCommandV1,
    ApprovalInvalidationReason,
    ApprovalRequestStatus,
    ApprovalRequestViewV1,
    ApprovalRiskLevel,
    ApprovalSnapshotHashInputV1,
    ApprovalSnapshotV1,
    approval_snapshot_hash,
    evaluate_approval,
)
from psycopg.rows import dict_row


class ApprovalServiceError(RuntimeError):
    """Base for stable API-safe approval failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ApprovalNotFound(ApprovalServiceError):
    """The project-scoped request does not exist."""


class ApprovalForbidden(ApprovalServiceError):
    """The server-resolved actor cannot perform this operation."""


class ApprovalConflict(ApprovalServiceError):
    """Current authoritative state rejects the requested transition."""


def utc_milliseconds_now() -> datetime:
    """Return UTC now at the precision supported by canonical JSON v1."""

    current = datetime.now(UTC)
    return current.replace(microsecond=(current.microsecond // 1000) * 1000)


class PostgresApprovalService:
    """Inspect and resolve approval requests in authoritative PostgreSQL transactions."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database URL must not be blank")
        self._database_url = database_url

    def get_request(
        self,
        actor: ApprovalActorV1,
        project_id: UUID,
        approval_request_id: UUID,
        *,
        checked_at: datetime | None = None,
    ) -> ApprovalRequestViewV1:
        """Return the project-scoped request and current snapshot validity."""

        self._authorize_view(actor, project_id)
        with psycopg.connect(self._database_url, row_factory=dict_row) as connection:
            row = self._select_row(connection, project_id, approval_request_id, lock=False)
        return self._view(actor, row, checked_at or utc_milliseconds_now())

    def decide(
        self,
        actor: ApprovalActorV1,
        project_id: UUID,
        approval_request_id: UUID,
        command: ApprovalDecisionCommandV1,
        *,
        decided_at: datetime | None = None,
    ) -> ApprovalRequestViewV1:
        """Atomically record one human decision and advance the candidate."""

        self._authorize_view(actor, project_id)
        decision_time = decided_at or utc_milliseconds_now()
        expired = False
        with (
            psycopg.connect(self._database_url, row_factory=dict_row) as connection,
            connection.transaction(),
        ):
            row = self._select_row(connection, project_id, approval_request_id, lock=True)
            self._authorize_decision(actor, row)
            if row["state_version"] != command.expected_version:
                raise ApprovalConflict(
                    "stale_approval_version", "approval request version is stale"
                )
            if row["request_status"] != ApprovalRequestStatus.PENDING.value:
                raise ApprovalConflict(
                    "approval_already_resolved", "approval request is already resolved"
                )
            if decision_time >= row["expires_at"]:
                self._expire(connection, row, decision_time)
                expired = True
            else:
                self._record_decision(connection, row, actor, command.decision, decision_time)
        if expired:
            raise ApprovalConflict("approval_expired", "approval request has expired")
        return self.get_request(actor, project_id, approval_request_id, checked_at=decision_time)

    @staticmethod
    def _authorize_view(actor: ApprovalActorV1, project_id: UUID) -> None:
        if actor.actor_type is not ApprovalActorType.HUMAN:
            raise ApprovalForbidden("human_required", "only a human can use approval controls")
        if "APPROVER" not in actor.roles:
            raise ApprovalForbidden("approver_role_required", "approver role is required")
        if project_id not in actor.project_ids:
            raise ApprovalForbidden("project_forbidden", "actor is not authorized for this project")

    @staticmethod
    def _authorize_decision(actor: ApprovalActorV1, row: dict[str, Any]) -> None:
        if actor.subject_id == row["requested_by_subject_id"]:
            raise ApprovalForbidden(
                "initiator_cannot_approve", "request initiator cannot resolve the same request"
            )

    @staticmethod
    def _select_row(
        connection: psycopg.Connection[dict[str, Any]],
        project_id: UUID,
        approval_request_id: UUID,
        *,
        lock: bool,
    ) -> dict[str, Any]:
        query = """
            SELECT
                ar.id AS approval_request_id,
                ar.project_id,
                ar.candidate_id,
                ar.risk_level,
                ar.requested_action,
                ar.required_approvals,
                ar.status AS request_status,
                ar.state_version,
                ar.requested_by_subject_id,
                ar.expires_at,
                ar.created_at,
                pc.account_id,
                pc.platform,
                pc.title,
                pc.caption,
                pc.normalized_tags,
                pc.ai_disclosure,
                pc.policy_version,
                pc.candidate_hash AS current_candidate_hash,
                pcs.state AS candidate_state,
                pcs.state_version AS candidate_state_version,
                arb.candidate_hash AS bound_candidate_hash,
                arb.fact_report_hash,
                arb.rights_manifest_hash,
                arb.risk_report_hash,
                arb.account_hash AS bound_account_hash,
                pa.account_fingerprint AS current_account_hash,
                aps.id AS snapshot_id,
                aps.decision AS snapshot_decision,
                aps.candidate_hash AS snapshot_candidate_hash,
                aps.fact_report_hash AS snapshot_fact_report_hash,
                aps.rights_manifest_hash AS snapshot_rights_manifest_hash,
                aps.risk_report_hash AS snapshot_risk_report_hash,
                aps.policy_version AS snapshot_policy_version,
                aps.account_hash AS snapshot_account_hash,
                aps.approved_action AS snapshot_approved_action,
                aps.approver_subject_ids,
                aps.expires_at AS snapshot_expires_at,
                aps.decided_at,
                aps.snapshot_hash
            FROM approval_requests ar
            JOIN approval_request_bindings arb
              ON arb.project_id = ar.project_id AND arb.approval_request_id = ar.id
            JOIN platform_candidates pc
              ON pc.project_id = ar.project_id AND pc.id = ar.candidate_id
            JOIN platform_candidate_states pcs
              ON pcs.project_id = ar.project_id AND pcs.candidate_id = ar.candidate_id
            JOIN platform_accounts pa
              ON pa.project_id = ar.project_id AND pa.id = pc.account_id
            LEFT JOIN approval_snapshots aps
              ON aps.project_id = ar.project_id AND aps.approval_request_id = ar.id
            WHERE ar.project_id = %s AND ar.id = %s
        """
        if lock:
            query += " FOR UPDATE OF ar, pcs"
        row = connection.execute(query, (project_id, approval_request_id)).fetchone()
        if row is None:
            raise ApprovalNotFound("approval_not_found", "approval request was not found")
        return row

    @staticmethod
    def _expire(
        connection: psycopg.Connection[dict[str, Any]],
        row: dict[str, Any],
        decision_time: datetime,
    ) -> None:
        connection.execute(
            """
            UPDATE approval_requests
            SET status = 'EXPIRED', resolved_at = %s, state_version = state_version + 1
            WHERE project_id = %s AND id = %s AND status = 'PENDING'
              AND state_version = %s
            """,
            (
                decision_time,
                row["project_id"],
                row["approval_request_id"],
                row["state_version"],
            ),
        )
        connection.execute(
            """
            UPDATE platform_candidate_states
            SET state = 'APPROVAL_EXPIRED', state_version = state_version + 1,
                updated_at = %s
            WHERE project_id = %s AND candidate_id = %s AND state = 'WAITING_APPROVAL'
              AND state_version = %s
            """,
            (
                decision_time,
                row["project_id"],
                row["candidate_id"],
                row["candidate_state_version"],
            ),
        )

    @staticmethod
    def _record_decision(
        connection: psycopg.Connection[dict[str, Any]],
        row: dict[str, Any],
        actor: ApprovalActorV1,
        decision: ApprovalDecision,
        decision_time: datetime,
    ) -> None:
        if row["candidate_state"] != "WAITING_APPROVAL":
            raise ApprovalConflict("candidate_not_waiting", "candidate is not waiting for approval")
        if row["required_approvals"] != 1:
            raise ApprovalConflict(
                "unsupported_approval_count", "M1-06 supports one authorized human"
            )
        if (
            row["risk_level"] == ApprovalRiskLevel.R4.value
            and decision is ApprovalDecision.APPROVED
        ):
            raise ApprovalConflict("r4_approval_forbidden", "R4 candidates cannot be approved")
        try:
            snapshot_input = ApprovalSnapshotHashInputV1(
                project_id=row["project_id"],
                approval_request_id=row["approval_request_id"],
                candidate_id=row["candidate_id"],
                account_id=row["account_id"],
                decision=decision,
                candidate_hash=bytes(row["bound_candidate_hash"]).hex(),
                fact_report_hash=bytes(row["fact_report_hash"]).hex(),
                rights_manifest_hash=bytes(row["rights_manifest_hash"]).hex(),
                risk_report_hash=bytes(row["risk_report_hash"]).hex(),
                account_hash=bytes(row["bound_account_hash"]).hex(),
                policy_version=row["policy_version"],
                approved_action=row["requested_action"],
                approver_subject_ids=(actor.subject_id,),
                expires_at=row["expires_at"],
                decided_at=decision_time,
            )
            snapshot_hash = approval_snapshot_hash(snapshot_input).sha256
        except ValueError as error:
            raise ApprovalConflict(
                "invalid_approval_binding", "approval binding cannot be canonicalized"
            ) from error
        snapshot_id = uuid4()
        connection.execute(
            """
            INSERT INTO approval_snapshots (
                id, project_id, approval_request_id, candidate_id, account_id, decision,
                candidate_hash, fact_report_hash, rights_manifest_hash, risk_report_hash,
                policy_version, account_hash, approved_action, approver_subject_ids,
                expires_at, decided_at, snapshot_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                ARRAY[%s]::uuid[], %s, %s, %s
            )
            """,
            (
                snapshot_id,
                row["project_id"],
                row["approval_request_id"],
                row["candidate_id"],
                row["account_id"],
                decision.value,
                row["bound_candidate_hash"],
                row["fact_report_hash"],
                row["rights_manifest_hash"],
                row["risk_report_hash"],
                row["policy_version"],
                row["bound_account_hash"],
                row["requested_action"],
                actor.subject_id,
                row["expires_at"],
                decision_time,
                bytes.fromhex(snapshot_hash),
            ),
        )
        target = decision.value
        updated_request = connection.execute(
            """
            UPDATE approval_requests
            SET status = %s, resolved_at = %s, state_version = state_version + 1
            WHERE project_id = %s AND id = %s AND status = 'PENDING'
              AND state_version = %s
            RETURNING state_version
            """,
            (
                target,
                decision_time,
                row["project_id"],
                row["approval_request_id"],
                row["state_version"],
            ),
        ).fetchone()
        updated_candidate = connection.execute(
            """
            UPDATE platform_candidate_states
            SET state = %s, state_version = state_version + 1, updated_at = %s
            WHERE project_id = %s AND candidate_id = %s AND state = 'WAITING_APPROVAL'
              AND state_version = %s
            RETURNING state_version
            """,
            (
                target,
                decision_time,
                row["project_id"],
                row["candidate_id"],
                row["candidate_state_version"],
            ),
        ).fetchone()
        if updated_request is None or updated_candidate is None:
            raise ApprovalConflict("approval_race", "approval state changed concurrently")

    @staticmethod
    def _view(
        actor: ApprovalActorV1, row: dict[str, Any], checked_at: datetime
    ) -> ApprovalRequestViewV1:
        status = ApprovalRequestStatus(row["request_status"])
        snapshot_hash: str | None = None
        decided_at: datetime | None = None
        approvers: tuple[UUID, ...] = ()
        valid: bool | None = None
        reasons: tuple[ApprovalInvalidationReason, ...] = ()
        if row["snapshot_id"] is not None:
            snapshot = ApprovalSnapshotV1(
                id=row["snapshot_id"],
                project_id=row["project_id"],
                approval_request_id=row["approval_request_id"],
                candidate_id=row["candidate_id"],
                account_id=row["account_id"],
                decision=ApprovalDecision(row["snapshot_decision"]),
                candidate_hash=bytes(row["snapshot_candidate_hash"]).hex(),
                fact_report_hash=bytes(row["snapshot_fact_report_hash"]).hex(),
                rights_manifest_hash=bytes(row["snapshot_rights_manifest_hash"]).hex(),
                risk_report_hash=bytes(row["snapshot_risk_report_hash"]).hex(),
                account_hash=bytes(row["snapshot_account_hash"]).hex(),
                policy_version=row["snapshot_policy_version"],
                approved_action=row["snapshot_approved_action"],
                approver_subject_ids=tuple(row["approver_subject_ids"]),
                expires_at=row["snapshot_expires_at"],
                decided_at=row["decided_at"],
                snapshot_hash=bytes(row["snapshot_hash"]).hex(),
            )
            current = ApprovalBindingV1(
                candidate_id=row["candidate_id"],
                account_id=row["account_id"],
                candidate_hash=bytes(row["current_candidate_hash"]).hex(),
                fact_report_hash=bytes(row["fact_report_hash"]).hex(),
                rights_manifest_hash=bytes(row["rights_manifest_hash"]).hex(),
                risk_report_hash=bytes(row["risk_report_hash"]).hex(),
                account_hash=bytes(row["current_account_hash"]).hex(),
                policy_version=row["policy_version"],
                approved_action=row["requested_action"],
            )
            validity = evaluate_approval(snapshot, current, checked_at=checked_at)
            snapshot_hash = snapshot.snapshot_hash
            decided_at = snapshot.decided_at
            approvers = snapshot.approver_subject_ids
            valid = validity.valid
            reasons = validity.reasons
        elif status is ApprovalRequestStatus.PENDING and checked_at >= row["expires_at"]:
            status = ApprovalRequestStatus.EXPIRED
            valid = False
            reasons = (ApprovalInvalidationReason.EXPIRED,)
        return ApprovalRequestViewV1(
            approval_request_id=row["approval_request_id"],
            project_id=row["project_id"],
            status=status,
            state_version=row["state_version"],
            candidate_state=row["candidate_state"],
            candidate_state_version=row["candidate_state_version"],
            risk_level=ApprovalRiskLevel(row["risk_level"]),
            requested_action=row["requested_action"],
            required_approvals=row["required_approvals"],
            requested_by_subject_id=row["requested_by_subject_id"],
            viewer_subject_id=actor.subject_id,
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            candidate=ApprovalCandidateViewV1(
                candidate_id=row["candidate_id"],
                account_id=row["account_id"],
                platform=row["platform"],
                title=row["title"],
                caption=row["caption"],
                normalized_tags=tuple(row["normalized_tags"]),
                ai_disclosure=row["ai_disclosure"],
            ),
            binding=ApprovalBindingViewV1(
                candidate_hash=bytes(row["bound_candidate_hash"]).hex(),
                fact_report_hash=bytes(row["fact_report_hash"]).hex(),
                rights_manifest_hash=bytes(row["rights_manifest_hash"]).hex(),
                risk_report_hash=bytes(row["risk_report_hash"]).hex(),
                account_hash=bytes(row["bound_account_hash"]).hex(),
                policy_version=row["policy_version"],
            ),
            snapshot_hash=snapshot_hash,
            decided_at=decided_at,
            approver_subject_ids=approvers,
            approval_valid=valid,
            invalidation_reasons=reasons,
        )
