# Publish dispatch control v1

- Status: M1-04 implementation in progress
- Version: 1.0
- Safety boundary: Mock publisher only; no Provider or platform network call

## Logical action and transaction

The service recomputes `request_fingerprint` from candidate hash, platform, account ID, and
normalized schedule slot. A PostgreSQL transaction-level advisory lock serializes equivalent
submissions. The winning transaction creates one immutable `publish_intent`, one outbox
message, and one `READY` publish job. Equivalent concurrent submissions return the winning
binding; any semantic mismatch fails closed.

## Lease and final gate

A worker locks the job/outbox row and obtains a five-second lease identified by worker and
token UUIDs. Before the Mock request boundary it repeats all available authoritative checks:

- candidate, approval snapshot, policy, and account hashes still match;
- approval request and snapshot are approved and unexpired;
- account status is `ACTIVE`;
- neither the project-global nor account stop control is active;
- the job lease belongs to this worker and has not expired.

A stop that commits before this final gate changes the job to `STOPPED` and produces no
publish attempt or external call. The final gate is the stop linearization point: a request
already past it has begun, while a later stop governs subsequent requests and reconciliation.

## Terminal outcomes

| Outcome | Job state | Outbox | Automatic resend |
|---|---|---|---|
| Confirmed success | `SUCCEEDED` | delivered | No |
| Known failure | `FAILED` | delivered | No in M1-04 |
| Lost/ambiguous response | `RECONCILIATION_REQUIRED` | delivered | Never |
| Stop before request | `STOPPED` | pending with stop reason | No while stopped |
| Another active lease | unchanged `LEASED` | claimed | No |

`publish_attempts` records `STARTED` before the boundary and the terminal result afterward.
An adapter exception is treated as `UNKNOWN`, because absence of a response cannot prove
that the external side did nothing.
