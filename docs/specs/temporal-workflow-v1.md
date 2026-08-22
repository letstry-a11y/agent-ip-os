# Temporal content workflow v1

- Status: Implemented and accepted for M1-02
- Version: 1.0
- Queue: `agent-ip-content-v1`
- Safety boundary: Mock publish only; no Provider or platform network call

## Ownership and identity

Temporal owns durable orchestration while PostgreSQL remains the authoritative business
state. One `ContentWorkflow` owns a `ContentUnit`; it starts one
`PlatformCandidateWorkflow` child per immutable platform candidate. IDs are stable:

```text
parent: supplied content workflow ID
child:  <parent-workflow-id>/candidate/<candidate-id>
```

Stable child IDs make approval routing explicit and make replay/restart independent of an
in-memory handle cache. Workflow inputs carry the current PostgreSQL `state_version`; every
persisted transition uses compare-and-swap and returns the new version.

## Parent progression

The parent advances `PLATFORM_ADAPTATION → CANDIDATES_ACTIVE`, waits for every child result,
and then advances to `LEARNING`. It returns every child terminal result in input order. A
successful child cannot overwrite or hide a rejected, quarantined, expired, unknown, or
failed sibling.

## Child progression and approval

Each child advances through `FACT_CHECK → RIGHTS_CHECK → COMPLIANCE_CHECK → RISK_ROUTING →
WAITING_APPROVAL` and waits on a durable Temporal signal. The signal contract accepts one
of `APPROVED`, `REJECTED`, or `REVISION_REQUESTED`; malformed decisions and approval without
an intent fail closed to `QUARANTINED`. One authorized human decision is sufficient for the
early/MVP policy. The first accepted resolution wins and duplicate signals are no-ops.

Authentication, authorization, candidate/snapshot revalidation, and actor audit belong to
the M1-06 control-plane endpoint before it sends this signal. Calling the Temporal signal
directly is an internal service capability, not a human-facing approval interface. T3
production operations remain disabled and are not enabled by this workflow.

Terminal paths are:

| Condition | Final candidate state |
|---|---|
| Approval timer expires | `APPROVAL_EXPIRED` |
| Human rejects | `REJECTED` |
| Human requests revision | `REVISION_REQUESTED → SUPERSEDED` |
| Invalid/missing approval intent | `QUARANTINED` |
| Mock confirms success | `PUBLISHED` |
| Mock result is unknown | `RECONCILIATION_REQUIRED` |
| Mock Activity fails permanently or exhausts retries | `PUBLISH_FAILED` |

## Activities and retry semantics

Workflow code is deterministic and performs no database or network I/O. PostgreSQL
Activities perform versioned state transitions and create the publish intent, outbox
message, and ready publish job in one transaction. Exact Activity retries return the prior
commit. Concurrent commands for the same recomputed request fingerprint converge on the
first committed intent only when candidate, approval snapshot, account, and schedule are
semantically identical; any mismatch fails closed.

Activities use at most three attempts with bounded exponential backoff. The current
`mock_publish` obtains a five-second job lease, revalidates approval/account bindings and
global/account stop controls immediately before the network-free Mock boundary, and records
one attempt. `UNKNOWN` consumes the outbox message into `RECONCILIATION_REQUIRED`; later
dispatch calls return that state without resending. M1-05 expands the behavioral Mock
failure matrix.

## Runtime boundary

The `workflow-worker` Compose service runs as a non-root user with a read-only filesystem
and a temporary ready file. Startup refuses any environment other than `DRY_RUN=true` and
`EXTERNAL_SIDE_EFFECTS_ENABLED=false`. PostgreSQL and Temporal must be healthy before the
worker starts.

## Verification contract

The workflow suite must prove persistent Temporal restart during approval wait, independent
siblings, first-signal-wins, one-human approval, revision/rejection/expiry/quarantine,
transient retry, permanent failure, unknown-outcome reconciliation, and empty-child parent
completion. PostgreSQL integration tests must prove compare-and-swap retry and atomic
intent/outbox retry against a real isolated database. The six-service Compose stack must
pass start, independent verification, and restart with external side effects disabled.
