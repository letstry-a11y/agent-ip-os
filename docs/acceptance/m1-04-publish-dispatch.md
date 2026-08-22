# M1-04 publish dispatch evidence

- Captured: 2026-08-22 (Asia/Shanghai)
- Result: **IN PROGRESS — local PostgreSQL acceptance passed**
- Safety boundary: isolated PostgreSQL databases and a network-free Mock publisher only

## Implemented

- Forward migration `0005_publish_dispatch_controls.sql` adds global/account stop controls,
  publish jobs, short lease ownership, and traceable publish attempts, and backfills earlier
  intents without rewriting migration history.
- Request fingerprints now bind candidate hash, platform, account, and normalized schedule
  through canonical JSON v1.
- Intent creation serializes equal fingerprints and atomically creates intent, outbox, and
  job rows.
- Dispatch rechecks approval, account, lease, and stop state immediately before the Mock
  boundary. Ambiguous responses become `RECONCILIATION_REQUIRED` and cannot auto-retry.

## Local verification

1. Migration `0005` applied successfully to the persistent local PostgreSQL database.
2. All 38 unit plus isolated PostgreSQL integration tests passed when run without the local
   Temporal dev-server test.
3. The 100-submit concurrency test produced exactly one matching intent and one publish job.
4. Both project-global and account stop race tests raised the stop after lease acquisition;
   each produced zero adapter calls and zero publish attempts.
5. The UNKNOWN test called the publisher once, recorded one `UNKNOWN` attempt, moved the job
   to `RECONCILIATION_REQUIRED`, and returned the same state without a second call.
6. The publish Activity and dispatcher modules reached 100% statement/branch coverage; Ruff
   and strict mypy passed.

## Remaining before READY_FOR_REVIEW

- The pre-existing persistent Temporal restart test currently cannot start its downloaded
  Windows dev server because that executable exits during resource detection. PostgreSQL
  acceptance is unaffected, but the complete repository gate must be rerun in hosted Linux
  CI or after the local Temporal executable issue is resolved.
- Run the web/format/repository gates, inspect the final diff, then create a protected PR.
- Human review must confirm the stop linearization point and that UNKNOWN always requires
  reconciliation. This work does not authorize a Provider, platform login, or publication.
