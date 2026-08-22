from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import agent_ip_workflows.activities as activities_module
import pytest
from agent_ip_data_models import (
    PublishRequestFingerprintInputV1,
    publish_request_fingerprint,
)
from agent_ip_workflows.activities import (
    PostgresWorkflowActivities,
    _digest,
    _timestamp,
    _uuid,
    activity_functions,
    mock_publish,
)
from agent_ip_workflows.models import (
    IntentCommand,
    PublishOutcome,
    StateTransition,
    StopCommand,
    StopScope,
)
from agent_ip_workflows.publishing import _parse_timestamp
from temporalio.exceptions import ApplicationError

PROJECT_ID = "11111111-1111-4111-8111-111111111111"
RESOURCE_ID = "22222222-2222-4222-8222-222222222222"


class FakeCursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    async def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class FakeConnection:
    def __init__(self, rows: list[tuple[object, ...] | None]) -> None:
        self._rows = rows
        self.executions: list[tuple[object, object]] = []

    async def __aenter__(self) -> FakeConnection:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, query: object, params: object = None) -> FakeCursor:
        self.executions.append((query, params))
        row = self._rows.pop(0) if self._rows else None
        return FakeCursor(row)


def _connect_factory(connection: FakeConnection) -> Callable[..., Any]:
    async def connect(*args: object, **kwargs: object) -> FakeConnection:
        return connection

    return connect


def _transition(target: str = "FACT_CHECK") -> StateTransition:
    return StateTransition(
        project_id=PROJECT_ID,
        resource_id=RESOURCE_ID,
        expected_version=0,
        target_state=target,
    )


def _intent() -> IntentCommand:
    schedule = "2026-08-22T02:00:00.000Z"
    fingerprint = publish_request_fingerprint(
        PublishRequestFingerprintInputV1(
            candidate_hash="11" * 32,
            platform="mock",
            account_id=UUID("44444444-4444-4444-8444-444444444444"),
            normalized_schedule_slot=datetime(2026, 8, 22, 2, tzinfo=UTC),
        )
    ).sha256
    return IntentCommand(
        project_id=PROJECT_ID,
        candidate_id=RESOURCE_ID,
        approval_snapshot_id="33333333-3333-4333-8333-333333333333",
        account_id="44444444-4444-4444-8444-444444444444",
        intent_id="55555555-5555-4555-8555-555555555555",
        outbox_id="66666666-6666-4666-8666-666666666666",
        request_fingerprint=fingerprint,
        normalized_schedule_slot=schedule,
    )


def test_boundary_parsers_and_activity_registry() -> None:
    assert str(_uuid(PROJECT_ID)) == PROJECT_ID
    assert _digest("ab" * 32) == bytes.fromhex("ab" * 32)
    assert _timestamp("2026-08-22T02:00:00.000Z").utcoffset() is not None
    with pytest.raises(ValueError, match="64 lowercase"):
        _digest("ab")
    with pytest.raises(ValueError):
        _digest("zz" * 32)
    with pytest.raises(ValueError, match="UTC offset"):
        _timestamp("2026-08-22T02:00:00")
    with pytest.raises(ValueError, match="UTC offset"):
        _parse_timestamp("2026-08-22T02:00:00")
    with pytest.raises(ValueError, match="must not be blank"):
        PostgresWorkflowActivities(" ")

    instance = PostgresWorkflowActivities("postgresql://test")
    assert len(activity_functions(instance)) == 5
    assert asyncio.run(mock_publish(_intent())) == PublishOutcome.SUCCEEDED.value
    with pytest.raises(ValueError):
        asyncio.run(mock_publish(_intent().__class__(**{**_intent().__dict__, "intent_id": "bad"})))


def test_state_activity_success_retry_and_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = PostgresWorkflowActivities("postgresql://test")

    success = FakeConnection([(1,)])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection, "connect", _connect_factory(success)
    )
    assert asyncio.run(instance.advance_content_state(_transition())) == 1

    retry = FakeConnection([None, ("FACT_CHECK", 1)])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection, "connect", _connect_factory(retry)
    )
    assert asyncio.run(instance.advance_candidate_state(_transition())) == 1

    conflict = FakeConnection([None, ("RIGHTS_CHECK", 2)])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection, "connect", _connect_factory(conflict)
    )
    with pytest.raises(ApplicationError, match="compare-and-swap"):
        asyncio.run(instance.advance_candidate_state(_transition()))


def test_intent_activity_is_atomic_idempotent_and_conflict_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = PostgresWorkflowActivities("postgresql://test")
    command = _intent()
    expected = (
        _uuid(command.intent_id),
        _uuid(command.outbox_id),
        _uuid(command.outbox_id),
        _uuid(command.intent_id),
        _uuid(command.candidate_id),
        _uuid(command.approval_snapshot_id),
        _uuid(command.account_id),
        _digest(command.request_fingerprint),
        _timestamp(command.normalized_schedule_slot),
    )

    existing = FakeConnection([None, expected])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection, "connect", _connect_factory(existing)
    )
    assert asyncio.run(instance.create_publish_intent_and_outbox(command)) == command
    assert len(existing.executions) == 2

    conflict = FakeConnection([None, (expected[0], expected[0], expected[2], expected[3])])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection, "connect", _connect_factory(conflict)
    )
    with pytest.raises(ApplicationError, match="bound differently"):
        asyncio.run(instance.create_publish_intent_and_outbox(command))

    candidate_hash = bytes.fromhex("11" * 32)
    account_hash = bytes.fromhex("22" * 32)
    gate = (
        candidate_hash,
        "mock",
        "policy-v1",
        "APPROVED",
        candidate_hash,
        "policy-v1",
        account_hash,
        datetime(2099, 1, 1, tzinfo=UTC),
        "APPROVED",
        "ACTIVE",
        account_hash,
        "APPROVED",
        False,
    )
    inserted = FakeConnection([None, None, None, gate, None, None, None])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection, "connect", _connect_factory(inserted)
    )
    assert asyncio.run(instance.create_publish_intent_and_outbox(command)) == command
    assert len(inserted.executions) == 7

    equivalent_row = (expected[0], expected[1], *expected[4:])
    equivalent = FakeConnection([None, None, equivalent_row])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection, "connect", _connect_factory(equivalent)
    )
    assert asyncio.run(instance.create_publish_intent_and_outbox(command)) == command

    equivalent_conflict = FakeConnection(
        [None, None, (*equivalent_row[:-1], datetime(2099, 1, 1, tzinfo=UTC))]
    )
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection,
        "connect",
        _connect_factory(equivalent_conflict),
    )
    with pytest.raises(ApplicationError, match="fingerprint is already bound"):
        asyncio.run(instance.create_publish_intent_and_outbox(command))

    missing_gate = FakeConnection([None, None, None, None])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection,
        "connect",
        _connect_factory(missing_gate),
    )
    with pytest.raises(ApplicationError, match="boundary is missing"):
        asyncio.run(instance.create_publish_intent_and_outbox(command))

    invalid_gate = FakeConnection([None, None, None, (*gate[:-1], True)])
    monkeypatch.setattr(
        activities_module.psycopg.AsyncConnection,
        "connect",
        _connect_factory(invalid_gate),
    )
    with pytest.raises(ApplicationError, match="failed revalidation"):
        asyncio.run(instance.create_publish_intent_and_outbox(command))


def test_publish_and_stop_activity_methods_delegate_to_dispatcher() -> None:
    instance = PostgresWorkflowActivities("postgresql://test")

    class FakeDispatcher:
        async def set_stop(self, _: StopCommand) -> int:
            return 7

        async def dispatch(self, command: IntentCommand, publisher: object) -> PublishOutcome:
            assert command == _intent()
            assert publisher is activities_module._mock_publisher
            return PublishOutcome.UNKNOWN

    instance._dispatcher = FakeDispatcher()  # type: ignore[assignment]
    stop = StopCommand(
        control_id="77777777-7777-4777-8777-777777777777",
        project_id=PROJECT_ID,
        scope=StopScope.GLOBAL,
        account_id=None,
        stopped=True,
        reason="test",
        expected_version=-1,
        updated_by_subject_id="88888888-8888-4888-8888-888888888888",
    )
    assert asyncio.run(instance.set_publish_stop(stop)) == 7
    assert asyncio.run(instance.dispatch_mock_publish(_intent())) == PublishOutcome.UNKNOWN.value
    assert asyncio.run(activities_module._mock_publisher(_intent())) is PublishOutcome.SUCCEEDED
