# Deterministic Mock boundaries v1

- Status: implemented for M1-05 review
- External effects: none
- Network: prohibited

## Purpose

M1-05 supplies deterministic stand-ins for Agent, media, and platform boundaries so the
local vertical slice can exercise failures without a real Provider, asset service, account,
or platform request. These Mocks are test infrastructure and do not claim production
Provider compatibility; M2-01 owns the provider-neutral production contracts.

## Request and result

Every invocation uses `MockRequestV1` with a UUID invocation ID, UUID trace ID, boundary,
scenario, and JSON payload. A successful invocation returns `MockResultV1` containing a
canonical output hash and `MockUsageV1` with integer input/output units and integer USD
microunits. Integer microunits avoid floating-point accounting drift.

The same request always produces the same output, hash, usage, and cost. Mocks must not
read environment credentials, open sockets, sleep to simulate latency, or write external
state.

## Failure matrix

| Scenario | Retryable | Request accepted | Result uncertain | Required behavior |
|---|---:|---:|---:|---|
| `SUCCESS` | No | Boundary-specific | No | Return a validated, hash-addressed result and cost. |
| `INVALID_SCHEMA` | No | No | No | Reject malformed structured output before workflow advancement. |
| `TIMEOUT` | Yes | No | No | Return an immediate deterministic timeout classification; do not sleep. |
| `TRANSIENT_FAILURE` | Yes | No | No | Permit only a later bounded runtime retry. |
| `PERMANENT_FAILURE` | No | No | No | Fail terminally until input/configuration changes. |
| `CANCELLED` | No | No | No | Stop without retry or external effect. |
| `LOST_RESPONSE` | No | Yes | Yes | Platform only: enter reconciliation; never treat as a retryable failure. |

`LOST_RESPONSE` is invalid for Agent and media boundaries because they have no platform
publication effect to reconcile. The Mock platform returns only synthetic IDs and never
contacts Xiaohongshu or another platform.

## Deterministic success payloads

- Agent: a structured proposal ID, fixed launch column, and Mock-only body.
- Media: synthetic object metadata and content hash; no image, portrait, voice, or bytes.
- Platform: synthetic post ID, `PUBLISHED` Mock status, and request fingerprint.

Identity-derived portrait processing remains blocked by D-003. All M1-05 fixtures are
non-identifying and synthetic.
