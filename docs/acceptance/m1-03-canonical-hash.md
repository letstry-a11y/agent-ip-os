# M1-03 canonical hash and approval evidence

- Captured: 2026-08-22 (Asia/Shanghai)
- Result: **PASS locally / READY FOR HOSTED REVIEW**
- Safety boundary: deterministic local code and isolated local PostgreSQL databases only;
  no Provider, platform account, cloud resource, outbox action, or publication was contacted

## Delivered scope

M1-03 establishes [canonical JSON and approval binding v1](../specs/canonical-json-v1.md)
as the byte contract shared by Python domain services and the TypeScript web boundary.

| Area | Evidence |
|---|---|
| Canonical bytes | Compact UTF-8, Unicode NFC, unsigned UTF-8 key ordering, array-order preservation, safe integers, null/absence separation, and strict UTC milliseconds |
| Candidate identity | Final title, caption, normalized/sorted tags, ordered asset hashes, disclosure, platform, account, and policy version produce an immutable SHA-256 identity |
| Approval identity | Snapshot self-hash binds project/request/candidate/account identities, decision/action, all candidate/report/account hashes, policy, approver identity, decision time, and expiry; one authorized human is sufficient in early/MVP operation |
| Invalidation | Deterministic evaluation returns explicit reasons for tamper, non-approval, expiry, and candidate/fact/rights/risk/policy/account/action changes |
| Database guard | Forward migration `0004_require_distinct_approvers.sql` still permits one approver and rejects a repeated subject only if a future policy supplies two entries |

The candidate hash intentionally excludes schedule. M1-04 will bind the normalized schedule
slot into the request fingerprint, so rescheduling cannot reuse the same external-action
identity while content identity remains stable.

## Verification results

1. Python formatting, Ruff lint, and strict mypy passed.
2. Twenty Python unit tests passed with 100% statement and branch coverage across 378
   statements and 56 branches. The canonical/approval module itself has 173 statements and
   52 branches at 100%.
3. The validity suite explicitly proves that a correctly bound single-human snapshot is
   sufficient. TypeScript formatting, ESLint, `tsc --noEmit`, and Vitest passed. Both runtimes consume
   `tests/fixtures/canonical-json-v1.json` and reproduce the same candidate and approval
   SHA-256 values.
4. Four isolated real-PostgreSQL integration tests passed, including staged forward
   migration through `0004`, repeat-migration idempotency, persistence of canonical payloads
   and real computed hashes, acceptance of one approver, and rejection of a duplicated
   optional second approver.
5. The persistent local development database reported current on two consecutive migration
   runs, and the Next.js production build passed.
6. The local Compose verification reported PostgreSQL, Garage, Temporal, API, and Web all
   healthy; external side effects remained disabled.

Hosted CI and protected-branch merge evidence will be added before this item is marked
`DONE`.

## Human review boundary

Founder review should confirm that (1) one authorized human is sufficient during early/MVP
operation, while real T3 remains disabled, (2) schedule belongs to the M1-04 request
fingerprint rather than candidate content identity, (3) safe-integer-only JSON is an
acceptable cross-runtime fail-closed rule, and (4) these candidate/report/policy/account/
action/expiry fields are the complete approval binding set. This review does not authorize a
Provider, real platform login, production migration, or publication.
