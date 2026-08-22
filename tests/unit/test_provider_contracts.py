from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from agent_ip_agent_runtime import (
    MockAudioProvider,
    MockImageProvider,
    MockTextModelProvider,
    MockVideoProvider,
    Provider,
)
from agent_ip_data_models import (
    ProviderErrorCode,
    ProviderFailureV1,
    ProviderJobStatus,
    ProviderJobV1,
    ProviderKind,
    ProviderProvenanceV1,
    ProviderRateLimitV1,
    ProviderRequestV1,
    ProviderUsageV1,
)
from pydantic import ValidationError

REQUEST_ID = UUID("30000000-0000-0000-0000-000000000003")
TRACE_ID = UUID("40000000-0000-0000-0000-000000000004")
SOURCE_ID = UUID("50000000-0000-0000-0000-000000000005")
NOW = datetime(2026, 8, 22, 16, 0, tzinfo=UTC)


def _request(kind: ProviderKind, *, topic: str = "synthetic-fixture") -> ProviderRequestV1:
    return ProviderRequestV1(
        request_id=REQUEST_ID,
        trace_id=TRACE_ID,
        provider_kind=kind,
        operation="generate",
        input={"topic": topic, "identity_data": False},
        requested_model=None,
        source_ids=(SOURCE_ID,),
        timeout_seconds=30,
        max_cost_microunits=0,
    )


def _deny_network(*args: object, **kwargs: object) -> None:
    raise AssertionError("M2-01 Provider Mock attempted network access")


@pytest.mark.parametrize(
    ("kind", "provider_type", "artifact_fragment"),
    [
        (ProviderKind.TEXT, MockTextModelProvider, None),
        (ProviderKind.IMAGE, MockImageProvider, "mock/image/"),
        (ProviderKind.VIDEO, MockVideoProvider, "mock/video/"),
        (ProviderKind.AUDIO, MockAudioProvider, "mock/audio/"),
    ],
)
def test_primary_mocks_submit_poll_and_replay_without_network(
    kind: ProviderKind,
    provider_type: type[
        MockTextModelProvider | MockImageProvider | MockVideoProvider | MockAudioProvider
    ],
    artifact_fragment: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(socket, "create_connection", _deny_network)
    provider = provider_type()
    request = _request(kind)

    submitted = asyncio.run(provider.submit(request))
    replayed = asyncio.run(provider.submit(request))
    completed = asyncio.run(provider.get_status(submitted.job_id))
    completed_again = asyncio.run(provider.get_status(submitted.job_id))

    assert isinstance(provider, Provider)
    assert submitted == replayed
    assert submitted.status is ProviderJobStatus.RUNNING
    assert completed == completed_again
    assert completed.status is ProviderJobStatus.SUCCEEDED
    assert completed.output is not None
    assert completed.output_hash is not None
    assert completed.usage.input_units > 0
    assert completed.usage.output_units > 0
    assert completed.usage.cost_microunits == 0
    assert completed.provenance.synthetic is True
    assert completed.provenance.provider_id == "mock-primary"
    assert completed.provenance.source_ids == (SOURCE_ID,)
    assert completed.rate_limit.remaining == 99
    if artifact_fragment is None:
        assert completed.output["text"] == "Mock-only structured text; no Provider was called."
    else:
        assert artifact_fragment in str(completed.output["artifact_key"])


def test_cancel_is_idempotent_and_does_not_change_success() -> None:
    provider = MockVideoProvider()
    submitted = asyncio.run(provider.submit(_request(ProviderKind.VIDEO)))

    cancelled = asyncio.run(provider.cancel(submitted.job_id))
    cancelled_again = asyncio.run(provider.cancel(submitted.job_id))
    after_poll = asyncio.run(provider.get_status(submitted.job_id))

    assert cancelled.status is ProviderJobStatus.CANCELLED
    assert cancelled == cancelled_again == after_poll

    second = MockAudioProvider()
    running = asyncio.run(second.submit(_request(ProviderKind.AUDIO)))
    succeeded = asyncio.run(second.get_status(running.job_id))
    assert asyncio.run(second.cancel(running.job_id)) == succeeded


def test_mock_rejects_wrong_kind_changed_replay_and_unknown_job() -> None:
    provider = MockTextModelProvider()
    with pytest.raises(ValueError, match="does not match TEXT"):
        asyncio.run(provider.submit(_request(ProviderKind.IMAGE)))

    submitted = asyncio.run(provider.submit(_request(ProviderKind.TEXT)))
    with pytest.raises(ValueError, match="cannot be reused"):
        asyncio.run(provider.submit(_request(ProviderKind.TEXT, topic="changed")))

    unknown = UUID("60000000-0000-0000-0000-000000000006")
    with pytest.raises(KeyError, match="unknown provider job"):
        asyncio.run(provider.get_status(unknown))
    with pytest.raises(KeyError, match="unknown provider job"):
        asyncio.run(provider.cancel(unknown))
    assert submitted.request_id == REQUEST_ID


def test_rate_limit_and_boundary_schemas_fail_closed() -> None:
    valid_limit = ProviderRateLimitV1(limit=10, remaining=0, reset_at=NOW)
    usage = ProviderUsageV1(input_units=1, output_units=0, cost_microunits=0, currency="CNY")
    failure = ProviderFailureV1(
        code=ProviderErrorCode.RATE_LIMIT,
        message="synthetic limit",
        retryable=True,
        request_accepted=False,
        retry_after_seconds=5,
        usage=usage,
        rate_limit=valid_limit,
    )
    assert failure.code is ProviderErrorCode.RATE_LIMIT
    assert set(ProviderErrorCode) == {
        ProviderErrorCode.INVALID_REQUEST,
        ProviderErrorCode.INVALID_OUTPUT,
        ProviderErrorCode.AUTHORIZATION,
        ProviderErrorCode.CONTENT_POLICY,
        ProviderErrorCode.RATE_LIMIT,
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.TRANSIENT,
        ProviderErrorCode.CANCELLED,
        ProviderErrorCode.INTERNAL,
    }

    with pytest.raises(ValidationError, match="remaining must not exceed limit"):
        ProviderRateLimitV1(limit=10, remaining=11, reset_at=NOW)

    values = _request(ProviderKind.TEXT).model_dump()
    values["credential"] = "forbidden"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProviderRequestV1.model_validate(values)


def test_job_schema_rejects_inconsistent_terminal_evidence() -> None:
    usage = ProviderUsageV1(input_units=1, output_units=1, cost_microunits=0, currency="CNY")
    rate_limit = ProviderRateLimitV1(limit=10, remaining=9, reset_at=NOW)
    provenance = ProviderProvenanceV1(
        provider_id="mock",
        model_id="mock-text",
        model_version="v1",
        request_hash="a" * 64,
        synthetic=True,
    )
    base: dict[str, object] = {
        "job_id": REQUEST_ID,
        "request_id": REQUEST_ID,
        "trace_id": TRACE_ID,
        "provider_kind": ProviderKind.TEXT,
        "usage": usage,
        "provenance": provenance,
        "rate_limit": rate_limit,
        "updated_at": NOW + timedelta(seconds=1),
    }

    with pytest.raises(ValidationError, match="successful job requires"):
        ProviderJobV1(status=ProviderJobStatus.SUCCEEDED, **base)

    failure = ProviderFailureV1(
        code=ProviderErrorCode.INTERNAL,
        message="synthetic failure",
        retryable=False,
        request_accepted=True,
        usage=usage,
    )
    failed = ProviderJobV1(status=ProviderJobStatus.FAILED, failure=failure, **base)
    assert failed.failure == failure

    with pytest.raises(ValidationError, match="failed job requires"):
        ProviderJobV1(
            status=ProviderJobStatus.FAILED,
            failure=failure,
            output={"unexpected": True},
            **base,
        )

    with pytest.raises(ValidationError, match="non-result job"):
        ProviderJobV1(
            status=ProviderJobStatus.RUNNING,
            output={"too_early": True},
            **base,
        )
