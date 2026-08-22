from __future__ import annotations

import asyncio
import socket
from uuid import UUID, uuid4

import pytest
from agent_ip_agent_runtime import (
    MockTextModelProvider,
    ProviderRouter,
    SecondaryMockProvider,
    SecondaryMockScenario,
)
from agent_ip_data_models import (
    ProviderErrorCode,
    ProviderJobStatus,
    ProviderKind,
    ProviderRequestV1,
)

TRACE_ID = UUID("70000000-0000-0000-0000-000000000007")


def _request(kind: ProviderKind, request_id: UUID | None = None) -> ProviderRequestV1:
    return ProviderRequestV1(
        request_id=request_id or uuid4(),
        trace_id=TRACE_ID,
        provider_kind=kind,
        operation="generate",
        input={"fixture": "synthetic-secondary"},
        timeout_seconds=30,
        max_cost_microunits=0,
    )


def _deny_network(*args: object, **kwargs: object) -> None:
    raise AssertionError("M2B secondary Mock attempted network access")


@pytest.mark.parametrize("kind", list(ProviderKind))
def test_secondary_mock_has_distinct_two_poll_success_and_output_format(
    kind: ProviderKind, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "create_connection", _deny_network)
    provider = SecondaryMockProvider(kind)
    request = _request(kind)

    submitted = asyncio.run(provider.submit(request))
    replayed = asyncio.run(provider.submit(request))
    first_poll = asyncio.run(provider.get_status(submitted.job_id))
    completed = asyncio.run(provider.get_status(submitted.job_id))
    completed_again = asyncio.run(provider.get_status(submitted.job_id))

    assert submitted == replayed == first_poll
    assert submitted.provenance.provider_id == "mock-secondary"
    assert completed == completed_again
    assert completed.status is ProviderJobStatus.SUCCEEDED
    assert completed.output is not None
    if kind is ProviderKind.TEXT:
        assert completed.output["segments"] == [
            {"kind": "paragraph", "value": "Alternate Mock text."}
        ]
    else:
        assert "mock/alternate/" in str(completed.output["artifacts"])


@pytest.mark.parametrize(
    ("scenario", "code", "retryable", "retry_after"),
    [
        (SecondaryMockScenario.RATE_LIMIT, ProviderErrorCode.RATE_LIMIT, True, 30),
        (SecondaryMockScenario.TRANSIENT, ProviderErrorCode.TRANSIENT, True, None),
        (SecondaryMockScenario.INVALID_OUTPUT, ProviderErrorCode.INVALID_OUTPUT, False, None),
    ],
)
def test_secondary_mock_emits_typed_failure_samples(
    scenario: SecondaryMockScenario,
    code: ProviderErrorCode,
    retryable: bool,
    retry_after: int | None,
) -> None:
    provider = SecondaryMockProvider(ProviderKind.TEXT, scenario=scenario)
    submitted = asyncio.run(provider.submit(_request(ProviderKind.TEXT)))
    assert asyncio.run(provider.get_status(submitted.job_id)).status is ProviderJobStatus.RUNNING

    failed = asyncio.run(provider.get_status(submitted.job_id))
    failed_again = asyncio.run(provider.get_status(submitted.job_id))
    assert failed == failed_again
    assert failed.status is ProviderJobStatus.FAILED
    assert failed.failure is not None
    assert failed.failure.code is code
    assert failed.failure.retryable is retryable
    assert failed.failure.retry_after_seconds == retry_after
    assert failed.output is None


def test_secondary_cancel_before_second_poll_stays_cancelled() -> None:
    provider = SecondaryMockProvider(ProviderKind.VIDEO)
    submitted = asyncio.run(provider.submit(_request(ProviderKind.VIDEO)))
    cancelled = asyncio.run(provider.cancel(submitted.job_id))
    assert asyncio.run(provider.get_status(submitted.job_id)) == cancelled


def test_router_switches_explicit_providers_and_fails_closed() -> None:
    primary = MockTextModelProvider()
    secondary = SecondaryMockProvider(ProviderKind.TEXT)
    router = ProviderRouter((primary, secondary))

    assert router.resolve(ProviderKind.TEXT, "mock-primary") is primary
    assert router.resolve(ProviderKind.TEXT, "mock-secondary") is secondary
    with pytest.raises(KeyError, match="Provider is not registered"):
        router.resolve(ProviderKind.IMAGE, "mock-secondary")

    with pytest.raises(ValueError, match="duplicate Provider registration"):
        ProviderRouter((primary, MockTextModelProvider()))
