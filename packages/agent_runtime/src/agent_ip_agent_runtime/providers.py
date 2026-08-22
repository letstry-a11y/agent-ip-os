"""Provider protocols and a deterministic, network-free primary Mock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol, cast, runtime_checkable
from uuid import NAMESPACE_URL, UUID, uuid5

from agent_ip_data_models import (
    ProviderJobStatus,
    ProviderJobV1,
    ProviderKind,
    ProviderProvenanceV1,
    ProviderRateLimitV1,
    ProviderRequestV1,
    ProviderUsageV1,
    hash_canonical_json,
)
from agent_ip_data_models.hashing import CanonicalValue
from pydantic import JsonValue


@runtime_checkable
class Provider(Protocol):
    """Portable asynchronous generation provider."""

    kind: ProviderKind

    async def submit(self, request: ProviderRequestV1) -> ProviderJobV1:
        """Accept an idempotent request and return its running job."""

    async def get_status(self, job_id: UUID) -> ProviderJobV1:
        """Return the current job and advance deterministic Mock work."""

    async def cancel(self, job_id: UUID) -> ProviderJobV1:
        """Cancel unfinished work; terminal jobs remain unchanged."""


class TextModelProvider(Provider, Protocol):
    """Provider interface for structured text or multimodal understanding."""


class ImageProvider(Provider, Protocol):
    """Provider interface for image generation or editing."""


class VideoProvider(Provider, Protocol):
    """Provider interface for asynchronous video generation."""


class AudioProvider(Provider, Protocol):
    """Provider interface for transcription or licensed synthetic audio."""


class PrimaryMockProvider:
    """In-memory provider with deterministic IDs, outputs, cost, and provenance."""

    provider_id = "mock-primary"
    model_version = "m2-01-v1"

    def __init__(self, kind: ProviderKind) -> None:
        self.kind = kind
        self.model_id = f"mock-{kind.value.lower()}-v1"
        self._jobs: dict[UUID, ProviderJobV1] = {}
        self._request_hashes: dict[UUID, str] = {}

    async def submit(self, request: ProviderRequestV1) -> ProviderJobV1:
        """Create one running job, or return the prior job for an exact replay."""

        if request.provider_kind is not self.kind:
            raise ValueError(
                f"request kind {request.provider_kind.value} does not match {self.kind.value}"
            )
        request_hash = hash_canonical_json(
            cast(CanonicalValue, request.model_dump(mode="json"))
        ).sha256
        existing_hash = self._request_hashes.get(request.request_id)
        if existing_hash is not None:
            if existing_hash != request_hash:
                raise ValueError("request_id cannot be reused with different input")
            return self._jobs[self._job_id(request.request_id)]

        job_id = self._job_id(request.request_id)
        now = datetime.now(UTC)
        job = ProviderJobV1(
            job_id=job_id,
            request_id=request.request_id,
            trace_id=request.trace_id,
            provider_kind=self.kind,
            status=ProviderJobStatus.RUNNING,
            usage=self._usage(request, output_units=0),
            provenance=ProviderProvenanceV1(
                provider_id=self.provider_id,
                model_id=self.model_id,
                model_version=self.model_version,
                request_hash=request_hash,
                source_ids=request.source_ids,
                synthetic=True,
            ),
            rate_limit=self._rate_limit(now),
            updated_at=now,
        )
        self._request_hashes[request.request_id] = request_hash
        self._jobs[job_id] = job
        return job

    async def get_status(self, job_id: UUID) -> ProviderJobV1:
        """Complete a running job immediately without sleeping or external work."""

        job = self._required_job(job_id)
        if job.status is not ProviderJobStatus.RUNNING:
            return job
        output = self._output(job.provenance.request_hash)
        completed = job.model_copy(
            update={
                "status": ProviderJobStatus.SUCCEEDED,
                "output": output,
                "output_hash": hash_canonical_json(cast(CanonicalValue, output)).sha256,
                "usage": job.usage.model_copy(update={"output_units": len(str(output))}),
                "updated_at": datetime.now(UTC),
            }
        )
        validated = ProviderJobV1.model_validate(completed.model_dump())
        self._jobs[job_id] = validated
        return validated

    async def cancel(self, job_id: UUID) -> ProviderJobV1:
        """Cancel running work idempotently and preserve terminal job evidence."""

        job = self._required_job(job_id)
        if job.status is not ProviderJobStatus.RUNNING:
            return job
        cancelled = ProviderJobV1.model_validate(
            job.model_copy(
                update={
                    "status": ProviderJobStatus.CANCELLED,
                    "updated_at": datetime.now(UTC),
                }
            ).model_dump()
        )
        self._jobs[job_id] = cancelled
        return cancelled

    def _required_job(self, job_id: UUID) -> ProviderJobV1:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise KeyError(f"unknown provider job: {job_id}") from error

    def _job_id(self, request_id: UUID) -> UUID:
        return uuid5(NAMESPACE_URL, f"agent-ip-os:{self.provider_id}:{self.kind}:{request_id}")

    @staticmethod
    def _usage(request: ProviderRequestV1, *, output_units: int) -> ProviderUsageV1:
        input_units = len(str(request.input))
        return ProviderUsageV1(
            input_units=input_units,
            output_units=output_units,
            cost_microunits=0,
            currency="CNY",
        )

    @staticmethod
    def _rate_limit(now: datetime) -> ProviderRateLimitV1:
        return ProviderRateLimitV1(limit=100, remaining=99, reset_at=now + timedelta(minutes=1))

    def _output(self, request_hash: str) -> dict[str, JsonValue]:
        prefix = request_hash[:16]
        if self.kind is ProviderKind.TEXT:
            return {"text": "Mock-only structured text; no Provider was called.", "id": prefix}
        if self.kind is ProviderKind.IMAGE:
            return {"artifact_key": f"mock/image/{request_hash}.png", "id": prefix}
        if self.kind is ProviderKind.VIDEO:
            return {"artifact_key": f"mock/video/{request_hash}.mp4", "id": prefix}
        return {"artifact_key": f"mock/audio/{request_hash}.wav", "id": prefix}


class MockTextModelProvider(PrimaryMockProvider):
    """Primary text Mock."""

    def __init__(self) -> None:
        super().__init__(ProviderKind.TEXT)


class MockImageProvider(PrimaryMockProvider):
    """Primary image Mock."""

    def __init__(self) -> None:
        super().__init__(ProviderKind.IMAGE)


class MockVideoProvider(PrimaryMockProvider):
    """Primary video Mock."""

    def __init__(self) -> None:
        super().__init__(ProviderKind.VIDEO)


class MockAudioProvider(PrimaryMockProvider):
    """Primary audio Mock."""

    def __init__(self) -> None:
        super().__init__(ProviderKind.AUDIO)
