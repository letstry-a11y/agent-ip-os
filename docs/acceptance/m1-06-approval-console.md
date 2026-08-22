# M1-06 minimal approval API and page evidence

- Captured: 2026-08-22 (Asia/Shanghai)
- Result: **PASS / ACCEPTED**
- Safety boundary: local Mock identity and PostgreSQL only; no real Provider, platform,
  portrait, publication, credential, or external side effect

## Implemented

- Project-scoped GET and decision APIs expose one bound candidate without accepting actor
  identity in the URL or request body.
- The server resolves an explicitly enabled Mock human identity and requires `APPROVER`,
  project membership, and separation from the request initiator.
- Migration `0006` freezes candidate, fact, rights, risk, account, policy, and action evidence
  in an immutable request-binding row and adds request compare-and-swap versioning.
- Approve, reject, and request-revision each create a canonical immutable snapshot and advance
  request plus candidate state in one PostgreSQL transaction. Early/MVP requires one authorized
  human; two-person production routing and all real T3 actions remain disabled.
- Expired, stale, terminal, non-waiting, R4 approval, unsupported two-person, and concurrent
  state changes fail closed. The read model recomputes approval validity and exposes the exact
  invalidation reasons.
- The responsive review desk presents the letter beside its five evidence hashes, viewer
  identity, expiry, risk, version, approval snapshot, and invalidation state. All decisions
  require an explicit human acknowledgement first.

## Verification

1. Ruff formatting/lint and strict mypy passed for the changed Python boundaries.
2. Eight approval API/unit tests cover strict bodies, server identity, stable HTTP errors,
   fail-closed configuration, schema round trip, and compare-and-swap race detection.
3. Eight real-PostgreSQL integration tests cover all decisions, immutable migration behavior,
   actor/project/role/initiator isolation, stale/terminal/R4/two-person guards, expiry,
   account-change invalidation, and canonical timestamp rejection.
4. Prettier, ESLint, TypeScript, eight Vitest tests, and the Next.js production build passed.
5. Browser verification at desktop and 390-pixel mobile widths confirmed readable responsive
   layout. The approve action was disabled before acknowledgement, enabled afterward, then
   changed the authoritative result from `PENDING / V0` to `APPROVED / V1` and displayed the
   generated approval snapshot hash.

6. [PR #9](https://github.com/letstry-a11y/agent-ip-os/pull/9) passed its protected quality
   check and reported no conflict with `main` before acceptance was recorded.

## Human acceptance

On 2026-08-22 the founder completed three independent local review requests through the
responsive desk. The authoritative API and PostgreSQL state recorded `APPROVED`,
`REVISION_REQUESTED`, and `REJECTED` respectively, each at state version 1. The founder then
confirmed the review was complete, accepting the displayed evidence boundary and the three
Chinese decision paths for early Mock-only operation.

Acceptance does not enable a real identity provider, paid generation, portrait processing,
platform login, publication, or any other external side effect.
