# M1-02 Temporal workflow evidence

- Captured: 2026-08-22 (Asia/Shanghai)
- Result: **PASS locally / READY FOR HOSTED REVIEW**
- Safety boundary: local Temporal/PostgreSQL and network-free Mock publish only; no Provider,
  platform account, cloud resource, browser automation, or publication was contacted

## Delivered scope

[Temporal workflow v1](../specs/temporal-workflow-v1.md) implements one durable content
parent with independent platform-candidate children on queue `agent-ip-content-v1`. Children
wait for one authorized human resolution, preserve distinct terminal outcomes, and use
PostgreSQL compare-and-swap Activities for authoritative state.

Publish-intent and outbox rows are committed atomically. Activity replay recognizes only a
complete identical binding; conflicting candidate, snapshot, account, fingerprint, schedule,
or outbox identity fails closed. The publish boundary is a deterministic, network-free Mock.

## Verification results

1. Twenty-seven unit/workflow tests passed with 100% statement and branch coverage across
   618 statements and 90 branches.
2. The persistent Temporal test stopped the Worker and Temporal dev server while two child
   workflows waited for approval, restarted both against the same SQLite history, then
   completed one child as `PUBLISHED` and its sibling as `REJECTED`.
3. The workflow matrix passed first-signal-wins, single-human approval, revision,
   rejection, expiry, invalid/missing intent quarantine, transient retry on attempt three,
   permanent failure, unknown-outcome reconciliation, and an empty-child parent.
4. Four isolated real-PostgreSQL integration tests passed. They include state CAS commit
   replay and exact intent/outbox transaction replay through the actual async Activities.
5. API and workflow-worker container images built with locked dependencies. The local
   Compose stack reported PostgreSQL, Garage, Temporal, API, Web, and workflow-worker all
   healthy before and after a full restart; external side effects remained disabled.
6. The Web container now receives only the shared canonical-hash golden JSON fixture needed
   by its build-time type check, closing the M1-03 clean-container build gap.

Hosted CI and protected-branch merge evidence will be added before M1-02 is marked `DONE`.

## Human review boundary

Review should confirm that (1) one authorized human decision is sufficient for early/MVP
content while T3 production actions remain disabled, (2) the API must authenticate,
authorize, revalidate, and audit before signaling Temporal, (3) `RECONCILIATION_REQUIRED`
never auto-retries a possibly accepted external action, and (4) M1-04 remains responsible
for stop flags, leases, and 100-way concurrent deduplication. This review does not authorize
real publishing or any external account action.
