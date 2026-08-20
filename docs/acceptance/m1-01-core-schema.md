# M1-01 core schema evidence

- Captured: 2026-08-20 (Asia/Shanghai)
- Result: **PASS / DONE**
- Safety boundary: local development and ephemeral test databases only; no production
  database, cloud resource, Provider, platform account, or external publishing action was
  contacted

## Delivered scope

M1-01 implements the smallest authoritative PostgreSQL core needed by the next vertical
slice. The physical model and its boundaries are recorded in the
[core data model](../architecture/data-model.md).

| Area | Evidence |
|---|---|
| Shared contracts | Strict, frozen Pydantic v1 contracts for content, versions, artifacts, rights, candidates, approval snapshots, publish intents, outbox messages, and audit events in `packages/data_models` |
| Initial schema | `migrations/0001_core_domain.sql` creates project-scoped core records and transactional intent/outbox relationships |
| Forward fixes | `migrations/0002_enforce_immutable_evidence.sql` adds append-only database triggers; `0003_bind_candidate_content_version.sql` adds an explicit immutable source-version binding and refuses unsafe inference for pre-existing candidates |
| Migrator | `scripts/db_migrate.py` discovers ordered migrations, hashes exact bytes, serializes application with an advisory lock, and rejects missing, renamed, or changed applied history |
| Hosted gate | PostgreSQL 16.13 is a required CI service and the `quality` job runs the real integration suite |

## Enforced invariants

- Composite foreign keys prevent a record from binding a content unit, candidate, approval,
  account, artifact, or audit predecessor from another project.
- Content versions, artifacts, platform candidates, candidate-artifact bindings, approval
  snapshots, publish intents, and audit events reject update and delete operations.
- A candidate binds the immutable content version, package JSON, candidate hash, account
  reference/hash, and trace identity used by later approval work.
- Each approval snapshot binds candidate, report, policy, account, and expiry hashes/values;
  later work may add invalidation behavior without mutating the snapshot.
- A publish intent and its outbox message are created as a deferred, one-to-one pair inside
  one transaction. A unique request fingerprint prevents duplicate intent creation.
- Each project has at most one audit genesis event; predecessor hashes cannot fork or cross
  project boundaries.

## Verification results

The following repository commands completed successfully on the target host:

1. `npm run check`: repository/baseline/migration checks, Ruff format and lint, strict mypy,
   14 unit tests, 100% coverage across 199 Python statements and 2 branches, Prettier,
   ESLint, TypeScript, and Vitest all passed.
2. `npm run check:integration`: 4 real-PostgreSQL tests passed. They exercised staged
   `0001` → `0002` → `0003` upgrade with data preservation, repeat migration idempotency, append-only
   rejection, project isolation, candidate bindings, duplicate request fingerprints,
   deferred intent/outbox pairing, audit genesis/fork rules, and checksum tamper rejection.
   A pre-0003 candidate also proved the version-binding forward fix fails atomically instead
   of inventing authoritative lineage.
3. `npm run db:migrate`: the persistent local development database reported current with no
   pending migration after both migrations had been applied.
4. `npm run build`: the Next.js production build passed.
5. `npm run stack:up`: API and Web images rebuilt, including the shared data-model package;
   PostgreSQL, Garage, Temporal, API, and Web all reported healthy, while external side
   effects remained disabled.

## Security and operational notes

- Generated local credentials remain only in ignored `.runtime/compose.env`; tests and the
  migrator do not print the database URL.
- Database migrations are forward-only. A defect is corrected by a new reviewed migration,
  not by destructive rollback.
- PostgreSQL holds transactional truth and immutable metadata. Large artifact bytes remain
  in versioned object storage, and vector retrieval remains deferred under ADR-0004.
- M1-01 does not authorize production migration, real platform access, paid Provider calls,
  or autonomous publication.

## Human review boundary

Before M1-02/M1-03 are treated as accepted on top of this model, a founder should review the
physical table map, the intentionally deferred tables, and the append-only/transactional
invariants in the core data model. This is a model acceptance decision, not permission for
production execution.
