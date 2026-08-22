from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from agent_ip_api.approval import (
    ApprovalConflict,
    ApprovalForbidden,
    ApprovalNotFound,
    ApprovalServiceError,
    PostgresApprovalService,
)
from agent_ip_api.main import (
    app,
    get_approval_service,
    get_current_approval_actor,
)
from agent_ip_data_models import (
    ApprovalActorType,
    ApprovalActorV1,
    ApprovalBindingViewV1,
    ApprovalCandidateViewV1,
    ApprovalDecision,
    ApprovalDecisionCommandV1,
    ApprovalRequestStatus,
    ApprovalRequestViewV1,
    ApprovalRiskLevel,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

PROJECT_ID = UUID("10000000-0000-0000-0000-000000000001")
REQUEST_ID = UUID("20000000-0000-0000-0000-000000000002")
CANDIDATE_ID = UUID("30000000-0000-0000-0000-000000000003")
ACCOUNT_ID = UUID("40000000-0000-0000-0000-000000000004")
ACTOR_ID = UUID("50000000-0000-0000-0000-000000000005")
REQUESTER_ID = UUID("60000000-0000-0000-0000-000000000006")
NOW = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)
HASH = "ab" * 32


def _actor() -> ApprovalActorV1:
    return ApprovalActorV1(
        subject_id=ACTOR_ID,
        actor_type=ApprovalActorType.HUMAN,
        roles=("APPROVER",),
        project_ids=(PROJECT_ID,),
    )


def _view() -> ApprovalRequestViewV1:
    return ApprovalRequestViewV1(
        approval_request_id=REQUEST_ID,
        project_id=PROJECT_ID,
        status=ApprovalRequestStatus.PENDING,
        state_version=0,
        candidate_state="WAITING_APPROVAL",
        candidate_state_version=0,
        risk_level=ApprovalRiskLevel.R1,
        requested_action="PACKAGE_EXPORT",
        required_approvals=1,
        requested_by_subject_id=REQUESTER_ID,
        viewer_subject_id=ACTOR_ID,
        expires_at=NOW + timedelta(days=1),
        created_at=NOW,
        candidate=ApprovalCandidateViewV1(
            candidate_id=CANDIDATE_ID,
            account_id=ACCOUNT_ID,
            platform="xiaohongshu_pack",
            title="她写给世界的信｜第一封",
            caption="写给仍然愿意认真生活的人。",
            normalized_tags=("写作", "她写给世界的信"),
            ai_disclosure="AI辅助视觉",
        ),
        binding=ApprovalBindingViewV1(
            candidate_hash=HASH,
            fact_report_hash=HASH,
            rights_manifest_hash=HASH,
            risk_report_hash=HASH,
            account_hash=HASH,
            policy_version="policy-v1",
        ),
    )


class FakeApprovalService:
    def __init__(self, error: ApprovalServiceError | None = None) -> None:
        self.error = error
        self.actor: ApprovalActorV1 | None = None
        self.command: ApprovalDecisionCommandV1 | None = None

    def get_request(
        self, actor: ApprovalActorV1, project_id: UUID, approval_request_id: UUID
    ) -> ApprovalRequestViewV1:
        self.actor = actor
        assert (project_id, approval_request_id) == (PROJECT_ID, REQUEST_ID)
        if self.error is not None:
            raise self.error
        return _view()

    def decide(
        self,
        actor: ApprovalActorV1,
        project_id: UUID,
        approval_request_id: UUID,
        command: ApprovalDecisionCommandV1,
    ) -> ApprovalRequestViewV1:
        self.actor = actor
        self.command = command
        assert (project_id, approval_request_id) == (PROJECT_ID, REQUEST_ID)
        if self.error is not None:
            raise self.error
        return _view()


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_get_and_decide_use_server_resolved_actor_and_strict_body() -> None:
    service = FakeApprovalService()
    app.dependency_overrides[get_approval_service] = lambda: service
    app.dependency_overrides[get_current_approval_actor] = _actor
    client = TestClient(app)
    path = f"/api/v1/projects/{PROJECT_ID}/approvals/{REQUEST_ID}"

    get_response = client.get(path)
    post_response = client.post(
        f"{path}/decisions",
        json={"schema_version": 1, "decision": "APPROVED", "expected_version": 0},
    )
    injected_identity = client.post(
        f"{path}/decisions",
        json={
            "schema_version": 1,
            "decision": "APPROVED",
            "expected_version": 0,
            "actor_id": str(REQUESTER_ID),
        },
    )

    assert get_response.status_code == 200
    assert post_response.status_code == 200
    assert injected_identity.status_code == 422
    assert service.actor == _actor()
    assert service.command == ApprovalDecisionCommandV1(
        decision=ApprovalDecision.APPROVED, expected_version=0
    )


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ApprovalNotFound("missing", "missing"), 404),
        (ApprovalForbidden("forbidden", "forbidden"), 403),
        (ApprovalConflict("conflict", "conflict"), 409),
        (ApprovalServiceError("unexpected", "unexpected"), 500),
    ],
)
def test_api_maps_service_errors_to_stable_http_details(
    error: ApprovalServiceError, status_code: int
) -> None:
    app.dependency_overrides[get_approval_service] = lambda: FakeApprovalService(error)
    app.dependency_overrides[get_current_approval_actor] = _actor
    client = TestClient(app)
    path = f"/api/v1/projects/{PROJECT_ID}/approvals/{REQUEST_ID}"
    response = client.get(path)
    decision_response = client.post(
        f"{path}/decisions",
        json={"schema_version": 1, "decision": "REJECTED", "expected_version": 0},
    )

    assert response.status_code == status_code
    assert response.json()["detail"] == {"code": error.code, "message": str(error)}
    assert decision_response.status_code == status_code
    assert decision_response.json()["detail"] == {"code": error.code, "message": str(error)}


def test_dependencies_fail_closed_and_accept_only_explicit_valid_mock_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(HTTPException) as database_error:
        get_approval_service()
    assert database_error.value.status_code == 503
    monkeypatch.setenv("DATABASE_URL", "postgresql://local/test")
    assert isinstance(get_approval_service(), PostgresApprovalService)

    monkeypatch.delenv("APPROVAL_MOCK_MODE", raising=False)
    with pytest.raises(HTTPException) as disabled_error:
        get_current_approval_actor()
    assert disabled_error.value.detail["code"] == "approval_identity_disabled"

    monkeypatch.setenv("APPROVAL_MOCK_MODE", "true")
    monkeypatch.setenv("APPROVAL_MOCK_SUBJECT_ID", "invalid")
    monkeypatch.setenv("APPROVAL_MOCK_PROJECT_ID", str(PROJECT_ID))
    with pytest.raises(HTTPException) as invalid_error:
        get_current_approval_actor()
    assert invalid_error.value.detail["code"] == "approval_identity_invalid"

    monkeypatch.setenv("APPROVAL_MOCK_SUBJECT_ID", str(ACTOR_ID))
    assert get_current_approval_actor() == _actor()


def test_approval_schemas_and_service_constructor_fail_closed() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        PostgresApprovalService(" ")

    values = _actor().model_dump()
    values["roles"] = ()
    with pytest.raises(ValidationError, match="at least 1 item"):
        ApprovalActorV1.model_validate(values)

    restored = ApprovalRequestViewV1.model_validate_json(_view().model_dump_json())
    assert restored == _view()


class _RaceCursor:
    def __init__(self, row: dict[str, int] | None) -> None:
        self._row = row

    def fetchone(self) -> dict[str, int] | None:
        return self._row


class _RaceConnection:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _query: str, _parameters: object) -> _RaceCursor:
        self.calls += 1
        rows = ({"state_version": 1}, None, {"state_version": 1})
        return _RaceCursor(rows[self.calls - 1])


def test_atomic_decision_detects_a_compare_and_swap_race() -> None:
    row = {
        "project_id": PROJECT_ID,
        "approval_request_id": REQUEST_ID,
        "candidate_id": CANDIDATE_ID,
        "account_id": ACCOUNT_ID,
        "candidate_state": "WAITING_APPROVAL",
        "candidate_state_version": 0,
        "required_approvals": 1,
        "risk_level": "R1",
        "bound_candidate_hash": bytes.fromhex(HASH),
        "fact_report_hash": bytes.fromhex(HASH),
        "rights_manifest_hash": bytes.fromhex(HASH),
        "risk_report_hash": bytes.fromhex(HASH),
        "bound_account_hash": bytes.fromhex(HASH),
        "policy_version": "policy-v1",
        "requested_action": "PACKAGE_EXPORT",
        "expires_at": NOW + timedelta(days=1),
        "state_version": 0,
    }

    with pytest.raises(ApprovalConflict, match="changed concurrently"):
        PostgresApprovalService._record_decision(
            _RaceConnection(),  # type: ignore[arg-type]
            row,
            _actor(),
            ApprovalDecision.APPROVED,
            NOW,
        )
