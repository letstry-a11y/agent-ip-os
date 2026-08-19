# ADR-0002: modular monolith with Provider-neutral contracts

- Status: Accepted
- Date: 2026-08-19
- Source authority: approved technical baseline V1.1

## Context

One technical founder must deliver and operate the MVP. Provider availability depends on deployment region, contract terms, account approval, and budget. Premature microservices would multiply deployment and consistency work, while vendor-bound business state would make a later compliant switch expensive.

## Decision

Build a modular monolith with separately runnable web, API, workflow worker, and media worker processes sharing versioned domain packages. Define `TextModelProvider`, `EmbeddingProvider`, `ImageProvider`, `VideoProvider`, and `AudioProvider` contracts; implement only the providers required by the selected M2 branch.

Persist normalized requests/results, source/provenance, Provider/model ID, prompt version, cost, and error class. Provider conversation/job IDs may support polling but cannot define business state. Six combined runtime units are logical roles, not 20 always-on services.

## Consequences

- Positive: simpler local operation, transactional consistency, lower single-maintainer burden, replaceable Provider implementations.
- Cost: module boundaries require enforcement without network separation; adapters must normalize different Provider semantics.
- Deferred: microservices, Kafka, Kubernetes, separate warehouse, complete multi-Provider production failover.
- Verification: M2 contract/switch tests must not modify workflow code or persisted business semantics.

## Rejected alternatives

- One microservice per Agent: excessive operational and consistency cost for MVP scale.
- Direct Provider SDK calls scattered through workflows: locks business logic to vendor errors, schemas, and conversation IDs.
