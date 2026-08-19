# AGENTS.md

This file is the binding working agreement for every task in this repository.

## Source of truth

Read this file before making changes. Then read the task-specific specification and the immutable baseline documents listed in [docs/baseline/README.md](docs/baseline/README.md). If sources conflict, stop before implementation and record the conflict in `DECISIONS.md`; do not silently choose a broader or less safe interpretation.

Priority order:

1. Explicit human instruction for the current task;
2. This file and any narrower descendant `AGENTS.md`;
3. Accepted ADRs and versioned specifications;
4. MVP PRD and Backlog;
5. Baseline documents.

## Product scope

The 12-week MVP contains only:

- six combined runtime units: planning/research, creation, media production, final verification, platform candidate/publishing, and basic analytics;
- image/text packages and one kind of 30-second video;
- mandatory human final approval for every external content item;
- one officially authorized platform adapter if credentials and Scope are granted, otherwise complete publish packages and Mock reconciliation;
- comments collected/classified with reply drafts only; no automatic replies;
- four additional weeks of stabilization before any limited R1 automation is considered.

Do not add 20 physical Agents, long-form fiction or films, a complete music pipeline, a second production platform, automatic comments/private messages, CRM, Kubernetes, Kafka, a data warehouse, or microservice decomposition during the 16-week scope.

## Architecture invariants

- Temporal owns durable workflow progression; model conversations never own business state.
- PostgreSQL is the transactional source of truth. Redis, caches, search indexes, and vectors are never authoritative.
- Agents produce structured proposals and cannot directly publish, pay, sign, delete protected data, or read secrets.
- Side effects pass through a server-side tool gateway with identity, scope, resource, workflow-state, candidate-hash, approval, budget, and stop-flag checks.
- Every platform candidate is immutable. Approval binds the candidate hash and the hashes/versions of fact, rights, risk, policy, account, and expiry data.
- Publishing uses an outbox, idempotency key, short-lived publish lease, and reconciliation before any retry of an unknown result.
- Provider interfaces remain vendor-neutral. Business state must not contain a provider conversation identifier as its only durable reference.
- MVP vector retrieval is deferred. Rights, consent, budget, publication, and policy truth stay in relational tables.

## Repository boundaries

- `apps/`: deployable API, web console, and media worker entry points.
- `packages/`: reusable domain, workflow, provider, policy, platform, media, and evaluation modules.
- `config/`: version-controlled Agent contracts, platform capabilities, policies, and templates. Never store secrets here.
- `migrations/`: forward database migrations. Destructive production changes require separate human approval.
- `docs/`: product memory, specifications, ADRs, acceptance evidence, and runbooks.
- `tests/`: unit, integration, workflow, platform sandbox, security, and end-to-end coverage.

Keep dependency direction toward domain contracts: apps may depend on packages; domain/data contracts must not depend on app frameworks. Shared schemas live in `packages/data_models`, not duplicated across apps.

## Engineering conventions

- Use UTF-8, LF line endings where tools permit, English identifiers, and descriptive snake_case Python modules / kebab-case documentation filenames.
- Target Python 3.12 for backend code. The exact patch version and Node runtime are pinned in M0-04 after toolchain review; do not infer compatibility from the currently installed Python 3.14 or Node 24.
- Use typed Pydantic schemas at boundaries and version public schemas, prompts, policy rules, and Agent contracts.
- Use UTC for stored timestamps and explicit IANA time zones for schedules; never rely on a host-local implicit time.
- Add or update tests with every behavior change. A bug fix starts with a failing regression test where practicable.
- Schema/API changes update the specification first and include migration plus compatibility tests.
- Prompt, model, tool, or policy changes run the applicable evaluation suite before release.

M0-04 will establish canonical format, lint, type-check, test, secret-scan, and migration-check commands. Until then, do not invent commands or claim those gates ran.

## Security and external effects

- Never read, print, transmit, commit, or place production keys, tokens, cookies, raw face data, or raw voiceprints in prompts, logs, traces, fixtures, or ordinary storage.
- Commit only `.env.example`; real `.env` files are ignored.
- Default local operation is Mock-only, `DRY_RUN=true`, and external side effects disabled.
- Do not use Cookie automation, browser simulation, region circumvention, or undocumented platform endpoints for publishing.
- Do not perform real publishing, production deployment, paid calls, cloud-resource creation, destructive migration, risk-threshold changes, or authorization changes without explicit human approval naming the target environment and action.
- T3 production actions require two distinct registered humans with MFA; initiators cannot self-approve. Without a second qualified approver, T3 remains disabled.
- Unknown facts, missing rights, expired consent, unverified webhooks, uncertain publish results, and policy conflicts fail closed.

## Definition of Done

A task is Done only when all applicable items are complete:

1. Scope and acceptance criteria are satisfied without unrelated expansion.
2. Code, structured schemas, migrations, configuration, and documentation agree.
3. Formatting, lint, type checks, relevant unit/integration/workflow/E2E/security/evaluation tests pass.
4. Logs and traces are checked for secret and sensitive-data leakage.
5. Failure, retry, cancellation, idempotency, observability, and rollback/forward-fix behavior are covered in proportion to risk.
6. `BACKLOG.md`, acceptance evidence, and affected runbooks are updated.
7. The final report states result, changed files/behavior, exact verification evidence, remaining risks, at most three human decisions, and one recommended next task.

If a required check cannot run, report the missing dependency or permission; code inspection is not a substitute for verification.
