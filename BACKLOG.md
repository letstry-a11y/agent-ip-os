# Delivery Backlog

The critical path is M0 → M1 → selected M2 branch → M3 → M4 → selected M5 branch → M6 → M7 stabilization. External approvals select a documented branch; they do not justify bypassing safety controls.

Status values: `DONE`, `READY_FOR_REVIEW`, `READY`, `BLOCKED`, `NOT_STARTED`. `DONE` means the completion evidence exists and all applicable Definition of Done checks passed. Human milestone acceptance is recorded separately in `docs/acceptance/`.

## M0 — baseline and decisions

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M0-00 | Read-only host and resource inventory | None | DONE | Windows/WSL2, Docker, virtualization, Python, Node, FFmpeg, Git, memory, disks, and planned ports are classified as present, missing, or unconfirmed in [inventory](docs/environment/m0-inventory.md); no installation performed. |
| M0-01 | Initialize Git, directories, and ignore rules | None | DONE | Local `main` repository exists; planned boundaries and placeholders are present; `.gitignore` excludes secrets/build/runtime data; no credential is tracked. |
| M0-02 | Add working agreement, README, decisions, Backlog, and baselines | M0-01 | DONE | `AGENTS.md`, `README.md`, `DECISIONS.md`, this Backlog, three immutable baseline copies, manifest dates, and SHA-256 values exist; repository-relative links pass the link check. |
| M0-03 | MVP PRD, system context, lifecycle, data model, and first ADRs | M0-02 | DONE | [PRD](docs/product/prd-mvp.md), [context](docs/architecture/system-context.md), [data model](docs/architecture/data-model.md), [lifecycle](docs/specs/content-lifecycle.md), and accepted-baseline ADRs are internally consistent; founder acceptance is recorded in [acceptance](docs/acceptance/m0.md) and D-010. |
| M0-04 | Python/Node workspace and CI gates | M0-01, M0-03 accepted | DONE | uv/Python and Node/npm are pinned; lockfiles, API/web shells, repository/Python/web gates, and CI workflow exist; locked restore, `npm run check`, and `npm run build` pass locally, in a fresh clone, and in [hosted CI run #3](https://github.com/letstry-a11y/agent-ip-os/actions/runs/32333631269); the API smoke test passes. |
| M0-05 | Docker Compose local environment | M0-04, Docker/WSL2 prerequisites | DONE | WSL2 and Docker Desktop are installed; Compose generates ignored random local credentials and all five services pass start, independent verify, restart, and isolated clean-checkout reproduction. Versions and resource measurements are recorded in [runtime evidence](docs/acceptance/m0-05-runtime.md). |

## M1 — local vertical slice

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M1-01 | Core schemas and migrations | M0-03 accepted, M0-04 | DONE | Content, version, artifact, rights, candidate, approval, publish-intent/outbox, and audit schemas have shared versioned contracts, forward-only migrations, project-scoped constraints, immutable evidence guards, checksum enforcement, and real-PostgreSQL forward-upgrade tests recorded in [M1-01 evidence](docs/acceptance/m1-01-core-schema.md). |
| M1-02 | Temporal parent/child workflow | M1-01, M0-05 | DONE | Durable parent/independent children, one-human approval wait, PostgreSQL CAS Activities, atomic intent/outbox replay, terminal/retry paths, persistent Temporal restart, and a healthy six-service Mock-only stack passed protected PR and post-merge CI. See [M1-02 evidence](docs/acceptance/m1-02-temporal-workflow.md). |
| M1-03 | Canonical JSON, candidate hash, and approval snapshot | M1-01 | DONE | Python/TypeScript share versioned golden vectors for ordering, Unicode, time, null, tags, and ordered assets; one authorized human approval is sufficient in early/MVP operation; approval self-hash plus candidate/report/policy/account/action/expiry bindings fail closed. See [M1-03 evidence](docs/acceptance/m1-03-canonical-hash.md). |
| M1-04 | Outbox, idempotency, and stop flags | M1-02, M1-03 | DONE | Transactional outbox plus five-second lease prevents duplicates under 100 concurrent repeats; global/account stop blocks in-flight worker at the final pre-request gate; UNKNOWN requires reconciliation with no automatic retry. Founder acceptance, protected PR #7, and post-merge main CI #20 pass. |
| M1-05 | Mock Agent, media, and platform adapters | M1-02 | DONE | Deterministic, network-free Agent/media/platform fixtures cover success, invalid schema, timeout, transient/permanent failure, cancellation, platform-only non-retryable lost response, and integer cost reporting. Local quality, focused 100% coverage, complete hosted Linux CI, and founder acceptance pass. |
| M1-06 | Minimal approval API/page | M1-03, M1-04 | DONE | Server-resolved Mock human identity, immutable evidence binding, one-human approve/reject/revision transaction, expiry/CAS/R4/self-bypass guards, responsive review desk, passing protected CI, and founder acceptance of all three decision paths are recorded in [M1-06 evidence](docs/acceptance/m1-06-approval-console.md). |
| M1-07 | Read-only platform qualification probe | D-001, D-007 input | DONE | Official Xiaohongshu Share SDK and mini-program sources, absent project app/test-account/callback/Scope/API approval, zero external requests, and deterministic M5B selection are recorded in [M1-07 evidence](docs/acceptance/m1-07-platform-qualification.md); no browser/Cookie publishing automation was used. |

## M2 — Provider-neutral Agent runtime

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M2-01 | Provider interfaces and primary Mock | M1-05 | DONE | Text/image/video/audio Protocols share strict request, async status, cancellation, cost, provenance, error, and rate-limit contracts; deterministic zero-network primary Mocks pass replay/cancel/fail-closed contract tests. See [M2-01 evidence](docs/acceptance/m2-01-provider-contracts.md). |
| M2-00 | Select M2A or M2B from G1 | M2-01, D-004, D-005, D-006 | DONE | Deployment region, legally approved Providers, and paid budget remain unapproved; the explicit local-Mock instruction and safe fallback select M2B without claiming real integration. See [M2B/M2-03 evidence](docs/acceptance/m2b-01-agent-contracts.md). |
| M2A-01 | One approved text Provider | M2-00 selects M2A | NOT_STARTED | Sandbox invocation produces validated structured output, provenance, errors, latency, and cost; Mock remains usable; secrets stay brokered and redacted. |
| M2B-01 | Second behavioral Mock/contract Provider | M2-00 selects M2B | DONE | Alternate two-poll Mock output/error behavior and explicit routing prove text/image/video/audio Provider switching without business-contract changes or real-integration claims. See [evidence](docs/acceptance/m2b-01-agent-contracts.md). |
| M2-03 | Six runtime contracts and schemas | M0-03 accepted | DONE | One strict versioned config contains exactly the six MVP units with schemas, tools, scopes, global forbidden actions, zero-cost budget, timeout, bounded safe retries, escalation, and prompt versions. See [specification](docs/specs/agent-contracts-v1.md). |
| M2-04 | AgentRuntime permissions, retries, cancellation, and trace | M2-03 and M2A-01 or M2B-01 | NOT_STARTED | Server-side authorization rejects forbidden tools; invalid output cannot advance state; bounded retries/cancellation/cost/source/prompt/model versions are traceable. |

## M3 — content and media factory

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M3-01 | Topic → script → platform-candidate version chain | M2-04 | NOT_STARTED | Immutable versions retain parent/source/prompt/model lineage; revision creates a new version and cannot mutate an approved candidate. |
| M3-02 | Image/text template and OCR checks | M3-01 | NOT_STARTED | Synthetic or authorized inputs produce original, publish image, thumbnail, disclosure, font/source record, and OCR/technical report; failure blocks candidate. |
| M3-03 | FFmpeg 30-second video template | M3-01, FFmpeg prerequisite | BLOCKED | Shot JSON renders master/platform media, subtitle and cover; ffprobe verifies duration/resolution/frame/audio/file limits; failed shot can rerun alone. |
| M3-04 | Artifact lineage and rights closure | M1-01 | NOT_STARTED | Directed derivation graph has no orphan final asset; every leaf has valid rights; revocation cancels unpublished descendants and creates per-post takedown tasks. |
| M3-05 | Douyin/Bilibili/Xiaohongshu publish packages | M3-02, M3-03 | NOT_STARTED | Three packages validate platform-specific title/caption/tag/media/disclosure metadata and can be downloaded without any external action. |
| M3-06 | Console comparison, revision, rejection, and batch approval | M1-06, M3-05 | NOT_STARTED | Browser E2E covers version comparison and all approval outcomes; batching never mixes hashes/accounts/expired snapshots; all outputs remain human-final-approved. |

## M4 — safety, approval, and reliable publishing

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M4-01 | Final fact, rights, and risk reports | M3-04, M3-05 | NOT_STARTED | Final per-platform bytes/text are checked; claims map to timestamped evidence; missing/unknown/expired evidence fails closed; report hashes are bound. |
| M4-02 | RBAC/ABAC and T3 dual approval | M1-03, D-008 for production enablement | NOT_STARTED | Human/service/Agent identities and resource/workflow scopes are enforced server-side; distinct MFA humans and no initiator self-approval are tested; production T3 stays disabled until D-008. |
| M4-03 | Publish lease, reconciliation, and audit hash chain | M1-04 | NOT_STARTED | Lease rechecks hash/approval/stop/budget; unknown publish result cannot auto-retry; tamper tests detect audit-chain modification; WORM export contract exists. |
| M4-04 | Threat model and security tests | M4-01, M4-02, M4-03 | NOT_STARTED | Prompt injection, SSRF/file isolation, privilege escalation, secret leakage, duplicate, stop race, revocation, and webhook-signature tests pass with zero R3/R4 release. |

## M5 — selected platform branch

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M5-00 | Select M5A or M5B from G2 | M4-03, D-001, D-007 | NOT_STARTED | Exact platform account/Scope/authorization evidence selects official API or publish-package fallback; no unsupported success is claimed. |
| M5A-01 | OAuth and Token Broker | M5-00 selects M5A | NOT_STARTED | Test-account OAuth, encrypted broker, refresh/revocation, redaction, least Scope, and Agent no-token access are demonstrated. |
| M5A-02 | Upload, create, query, and reconcile | M5A-01 | NOT_STARTED | Authorized test account proves declared capabilities, error/rate-limit mapping, stable request fingerprint, unknown-outcome reconciliation, and no duplicates. |
| M5B-01 | Publish package, Mock contracts, manual metrics/reconciliation | M5-00 selects M5B | NOT_STARTED | Complete packages, error samples, manual platform-post ID and 24h/72h/7d evidence entry, and reconciliation drill run locally; API access remains explicitly blocked. |

## M6 — release candidate

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M6-01 | Metrics, cost, and operations dashboard | M3-06 | NOT_STARTED | E2E shows per-content trace, state, blocks, latency, model/media/human cost, approval time, and manual/API metrics with acceptable query performance. |
| M6-02 | 100 gold cases and release gate | M2-03, M4-04 | NOT_STARTED | 20 brand, 20 fact, 20 rights/risk, 20 platform, 10 injection, and 10 recovery/idempotency cases are versioned; humans confirm labels; schema ≥99%, key safety misses 0, duplicates 0. |
| M6-03 | Disaster drills and runbooks | M6-02 and M5A-02 or M5B-01 | NOT_STARTED | Backup restore, token leak, rights revocation, takedown, platform outage, stop race, and mistaken publish drills have timestamps, evidence, owners, results, and follow-up tasks. |
| M6-04 | Release-candidate review and freeze | M0–M4, chosen M2/M5 branches, M6-01..03 | NOT_STARTED | Full applicable quality/eval/security gates pass; main features/prompts/rules/schemas freeze; release notes, deployment and on-call docs exist; no unapproved external action occurs. |

## M7 — four-week independent stabilization

| ID | Task | Dependencies | Status | Completion definition / evidence |
|---|---|---|---|---|
| M7-01 | Stabilization run | M6-04 accepted | NOT_STARTED | Four weeks add no major features; at least 30 ContentUnits, 20 test/API or Mock/package reconciliations, 5 injected failures, 2 stop drills, 2 revocation drills, and 1 full restore are evidenced; no duplicate/unauthorized publish. |
| M7-02 | G5 automation decision package | M7-01, 100 gold cases, SLO evidence | NOT_STARTED | Founder receives exact proposed R1 templates/accounts/windows/daily limit and residual risk. System remains human-final-approved unless explicit G5 approval is recorded. |
