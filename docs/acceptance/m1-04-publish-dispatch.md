# M1-04 publish dispatch evidence

- Captured: 2026-08-22 (Asia/Shanghai)
- Result: **PASS / ACCEPTED**
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

[Pull request #7](https://github.com/letstry-a11y/agent-ip-os/pull/7) ran the complete Linux
quality gate, including persistent Temporal restart, PostgreSQL integration, 100% workspace
coverage, repository/web checks, Compose validation, and the production web build. The
implementation [hosted CI run #18](https://github.com/letstry-a11y/agent-ip-os/actions/runs/32569912896)
completed successfully in 1 minute 30 seconds.

## Human acceptance

On 2026-08-22 the founder confirmed that the final pre-request gate is the stop
linearization point, that UNKNOWN always requires reconciliation with no automatic retry,
and that the five-second lease is acceptable for the Mock/MVP load. PR #7 was then merged
as commit `8907878`; [post-merge main CI #20](https://github.com/letstry-a11y/agent-ip-os/actions/runs/32570307908)
passed in 1 minute 31 seconds.

The downloaded Temporal dev server still has a Windows-only startup issue on this host;
the same persistent-restart scenario passed in hosted Linux CI. Acceptance does not
authorize a Provider, platform login, or publication.
