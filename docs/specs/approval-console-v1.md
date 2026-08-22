# Approval console and API v1

- Status: implemented for M1-06 review
- Scope: local Mock-only human review of one immutable platform candidate
- External effects: none

## Purpose

The M1-06 approval surface lets an authorized human inspect the exact candidate and bound
evidence, then approve, reject, or request revision. It does not create a publish intent,
call a Provider, process a portrait, log into a platform, or publish.

## Identity boundary

Actor identity is resolved by a server-side dependency and is never accepted in the
decision body. M1-06 supports only the explicitly enabled local Mock identity mode:

- `APPROVAL_MOCK_MODE=true` must be set;
- `APPROVAL_MOCK_SUBJECT_ID` identifies the synthetic human;
- `APPROVAL_MOCK_PROJECT_ID` limits that human to one project;
- the actor type is `HUMAN` and the role is `APPROVER`.

Missing, malformed, disabled, non-human, unscoped, or non-approver identity fails closed.
The human who created a request cannot resolve that same request. A service or Agent may
create a request, but cannot provide the human decision. M4-02 will replace this Mock
identity dependency with production RBAC/ABAC and MFA; M1-06 does not claim production
authentication.

One authorized human decision is sufficient for early/MVP R0/R1/R2 operation. This does
not enable real T3 actions or change the separate two-human production gate.

## Versioned API

```text
GET  /api/v1/projects/{project_id}/approvals/{approval_request_id}
POST /api/v1/projects/{project_id}/approvals/{approval_request_id}/decisions
```

The POST body contains only:

```json
{"schema_version": 1, "decision": "APPROVED", "expected_version": 0}
```

`decision` is `APPROVED`, `REJECTED`, or `REVISION_REQUESTED`. The expected version is a
compare-and-swap guard. Duplicate or stale decisions return a conflict and never create a
second snapshot.

## Authoritative data and transaction

Migration `0006` adds a request state version and immutable `approval_request_bindings`.
The binding freezes candidate, account, fact, rights, risk, policy, and action hashes at
request creation. Decision handling runs in one PostgreSQL transaction:

1. lock the request and verify actor/project/role/initiator separation;
2. verify pending status, expected version, expiry, candidate state, and R4 prohibition;
3. recompute the canonical approval snapshot hash with the server-side actor and UTC time;
4. insert exactly one immutable snapshot;
5. resolve the request and advance candidate state with compare-and-swap semantics.

Expiry advances the request to `EXPIRED` and the candidate to `APPROVAL_EXPIRED`; no
snapshot is fabricated. R4 cannot be approved. Rejection and revision are immutable human
decisions, not approvals for publication.

## View and invalidation

The response includes candidate title, caption, tags, disclosure, platform/account,
request status/version, candidate state/version, risk/action/expiry, all bound hashes, the
server-resolved viewer identity, and snapshot validity when a snapshot exists.

The page displays invalidation reasons produced by canonical approval evaluation. At M1-06
the directly observable invalidation path is expiry; later fact/rights/risk sources will
provide their current hashes without changing this response contract. Any invalid result is
visually blocking and disables decision controls.

## UI contract

The console route is:

```text
/approvals/{project_id}/{approval_request_id}
```

The page shows the letter content, five evidence bindings, viewer identity, request version,
expiry, and three explicit actions. Approval additionally requires the human to check the
on-screen acknowledgement that the exact version and bindings were reviewed. Loading,
empty, stale, expired, forbidden, and upstream-unavailable states give actionable text.
