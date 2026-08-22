# Provider contracts v1

- Status: accepted for M2-01
- Scope: provider-neutral text, image, video, and audio boundaries plus primary Mock
- Safety boundary: local memory only, zero network, zero credentials, zero paid calls
- Baseline: [technical plan](../baseline/AI超级IP全Agent公司技术方案_v1.md) and
  [Codex execution plan](../baseline/AI超级IP系统_Codex开发执行计划_v1.md)

## Contract

All four Provider families implement the same asynchronous lifecycle:

1. `submit(ProviderRequestV1)` accepts an idempotent request and returns a `RUNNING` job.
2. `get_status(job_id)` returns the durable job snapshot and may advance it to a terminal state.
3. `cancel(job_id)` cancels unfinished work and leaves terminal evidence unchanged.

`TextModelProvider`, `ImageProvider`, `VideoProvider`, and `AudioProvider` are distinct public
interfaces so applications can depend on the capability they need. Business state stores the
portable request/job/provenance data, never a vendor conversation identifier as its only durable
reference. Embeddings remain deferred by the accepted MVP architecture.

## Versioned evidence

Every request binds a UUID request ID, trace ID, Provider kind, operation, JSON input, optional
model preference, source IDs, timeout, and maximum cost. Every accepted job reports:

- `RUNNING`, `SUCCEEDED`, `FAILED`, or `CANCELLED`;
- validated JSON output and its canonical hash on success;
- input/output units, integer microunit cost, and currency;
- Provider/model/version, request hash, source IDs, optional content credential, and whether the
  result is synthetic;
- rate-limit limit, remaining count, and offset-aware reset timestamp;
- structured failure evidence when failed.

The error taxonomy is `INVALID_REQUEST`, `INVALID_OUTPUT`, `AUTHORIZATION`, `CONTENT_POLICY`,
`RATE_LIMIT`, `TIMEOUT`, `TRANSIENT`, `CANCELLED`, and `INTERNAL`. Retryability is explicit on the
failure rather than inferred solely from the code. Later runtime policy may retry only bounded,
explicitly retryable failures and must honor `retry_after_seconds`.

Schema invariants fail closed: success requires output and a hash with no failure; failure requires
failure evidence with no output; running/cancelled jobs cannot contain a result; rate-limit
remaining cannot exceed its limit; boundary payloads reject extra fields.

## Primary Mock

The primary Mock has one implementation per Provider family and deliberately uses no SDK,
network, file bytes, credential, sleep, or paid resource. It:

- derives a stable job UUID from Provider kind and request ID;
- rejects the same request ID with changed input;
- returns the same job for an exact replay;
- completes deterministically when polled;
- cancels running work idempotently;
- returns kind-specific synthetic text or artifact metadata;
- records `mock-primary`, model/version evidence, zero CNY cost, and a deterministic limit snapshot.

The Mock proves the application boundary only. It is not evidence that any real Provider, region,
model, media capability, price, or account has been approved.
