# MVP product requirements

- Status: Ready for founder review
- Version: 0.1
- Date: 2026-08-19
- Derived from: [business baseline](../baseline/AI超级IP双人公司商业计划书_v1.md), [technical baseline](../baseline/AI超级IP全Agent公司技术方案_v1.md), and [execution plan](../baseline/AI超级IP系统_Codex开发执行计划_v1.md)

## 1. Product statement

Agent IP OS lets two founders plan, generate, verify, approve, package, optionally publish through one officially authorized test-platform integration, and learn from short-form IP content while preserving evidence for facts, rights, consent, risk, cost, versions, and every external attempt.

The product is an auditable content operating system, not a group chat of autonomous bots. Deterministic code controls state and side effects; Agents propose structured outputs; humans retain final content and high-risk authority.

## 2. Users and jobs

| User | Primary job | Non-delegable authority |
|---|---|---|
| Creative founder / rights holder | Define IP, review visual/voice/persona use, compare candidates, approve/revise/reject content | Veto personal portrayal, portrait/voice use, intimacy, identity changes, and final public expression |
| Technical/operations founder | Configure approved workflows, review costs/risk, schedule, reconcile, and respond to incidents | Pause unsafe automation, approve budget/operations within written authority, manage platform qualification |
| Second registered T3 approver | Independently review funds/contracts/personality-right actions | Distinct MFA approval; cannot be replaced by initiator or Agent |
| Operator (may be a founder) | Inspect queues, download packages, enter permitted manual post/metric evidence | Cannot alter an approved immutable candidate or bypass policy |

The public audience is the subject of content strategy, not a direct console user in the MVP.

## 3. Goals

1. Prove one source content unit can traverse research/planning → creation → media → immutable platform candidates → final checks → human approval → transactional publish intent → Mock/authorized test publish or complete publish package → metrics, without losing state or duplicating an attempt.
2. Preserve a verifiable chain from every final byte and claim to sources, derivations, rights/consent, Agent/prompt/model versions, cost, approval, and platform result.
3. Fail closed on missing/unknown rights, facts, policy, approval, budget, authorization, webhook validity, or publish outcome.
4. Keep Provider and platform choices replaceable and allow development to continue with Mock/packaging branches when external approvals are absent.
5. Reduce repetitive work while all MVP external content remains subject to human final approval.

## 4. MVP scope

### Included

- Six combined runtime units: planning/research, creation, media production, final verification, platform candidate/publishing, basic analytics.
- Versioned IP bible references and synthetic/authorized asset input.
- Image/text publish packages and one template-based 30-second video workflow.
- Douyin, Bilibili, and Xiaohongshu package adaptation; at most one officially authorized test-platform adapter.
- Per-platform immutable candidates, fact/rights/risk/AI-disclosure checks, R0–R4 routing, and mandatory final approval.
- Candidate/report/policy/account/expiry-bound approval snapshots.
- Global and account stop flags, outbox, publish lease, idempotency, unknown-result reconciliation, and audit chain.
- Downloadable packages and permitted manual post ID / 24h, 72h, 7d metric evidence when APIs are unavailable.
- Comment collection/classification and reply drafts only if the authorized platform supports collection; no sending.
- Cost, trace, operational state, and release-gate views.

### Explicitly excluded through week 16

- 20 independently deployed Agents, long fiction/film, complete song generation, second production platform.
- Automatic comments, private messages, sales promises, quotations, contracts, payments, invoices, or sensitive-material intake.
- Non-official publishing via Cookie, simulated click, undocumented endpoint, or region-rule circumvention.
- R1 automatic publishing before 100 gold cases, four independent stable weeks, required drills, and explicit G5 approval.
- Kubernetes, Kafka, separate warehouse, microservices, and authoritative vector memory.
- Production face/voice clone use without D-003 scope and all required consent/storage/revocation controls.

## 5. Functional requirements

| ID | Requirement | Acceptance signal |
|---|---|---|
| FR-001 | Create a `ContentUnit` with project, target column, schedule, budget, and source goals. | Invalid/missing identifiers, budget, or project scope are rejected; creation is audited. |
| FR-002 | Produce versioned structured outputs from each of six runtime units with source, prompt, model/Provider, cost, and trace metadata. | Invalid schema cannot advance workflow; retry is bounded and visible. |
| FR-003 | Create a separate immutable `PlatformCandidate` per platform/account. | Editing any title, caption, tag, ordered asset, disclosure, platform, account, or policy creates a new candidate/hash. |
| FR-004 | Compute canonical candidate/report hashes consistently. | Golden vectors cover key ordering, Unicode, time, nulls, sorted tags, and ordered asset hashes across relevant runtimes. |
| FR-005 | Check the final platform candidate for claims, evidence, asset-rights closure, consent, disclosure, policy, and brand risk. | Missing, expired, unreachable, or unknown evidence blocks rather than guesses. |
| FR-006 | Route R0–R4 and create a human-readable approval snapshot. | R3/R4 cannot reach publishing; MVP R0/R1/R2 still require final human approval. |
| FR-007 | Bind approval to candidate, fact, rights, risk, policy version, account, approver, and expiry. | Any bound input change or expiry makes the approval unusable. |
| FR-008 | Enforce human/service/Agent RBAC plus resource/workflow ABAC in the tool gateway. | Agent requests for forbidden publish/delete/pay/secret tools are rejected and audited server-side. |
| FR-009 | Create publish intent and outbox atomically after rechecking hash, approval, stop flags, budget, and account. | Transaction failure creates neither an executable outbox item nor a partial intent. |
| FR-010 | Recheck a short-lived publish lease immediately before external request. | Stop/revocation/approval expiry before send blocks the request within the SLO path. |
| FR-011 | Prevent duplicate external attempts with intent ID and request fingerprint. | 100 concurrent identical submissions produce no second publish; legitimate repost uses a new intent and reason. |
| FR-012 | Reconcile “request may have succeeded but response was lost.” | System queries official capability or enters manual reconciliation; it never automatically republishes an unknown result. |
| FR-013 | Continue durable workflow after process restart and support bounded retry/cancel/quarantine. | Restart tests preserve state and waiting approvals; permanent failures do not loop. |
| FR-014 | Record append-only audit events with actor, action, resource, before/after references, trace, and hash chain. | A modified/deleted/reordered event is detectable; Agent has no mutation permission. |
| FR-015 | Generate complete platform packages without any network call. | Operator can download validated media/text/disclosure/manifest files for all three target platforms. |
| FR-016 | Use official test platform only when exact Scope and human authorization exist. | Test-account allowlist and dry-run/environment gates prevent production-account or unsupported calls. |
| FR-017 | Support manual post/metric evidence where platform APIs are absent. | Entry records actor, timestamp, platform post ID, source screenshot/value, and `manual_metric`; it never appears as API collection. |
| FR-018 | Show queue, approval, state, blocks, cost, trace, and outcome in the console. | E2E user can explain why an item is waiting/blocked and what exact approved version would be sent. |
| FR-019 | Propagate portrait/voice rights revocation. | Unpublished descendants cancel; each published platform post gets a takedown/review job; source access is revoked per retention rules. |
| FR-020 | Run release gates for schema, safety, idempotency, secrets, and evaluations. | Schema success ≥99%, duplicate publish 0, R3/R4 leakage 0, and any critical safety miss blocks release. |

## 6. Non-functional requirements

- **Safety:** R3/R4 unauthorized publish = 0; external action defaults disabled. Early/MVP review requires one authorized human final approval. Real T3 actions remain disabled; if later enabled under D-008, their production policy may require two distinct MFA humans.
- **Reliability:** workflow state loss = 0; duplicate publish = 0; every attempt traceable; retries categorized and bounded.
- **Stop SLO:** stop signal to blocking a not-yet-submitted new publish request has P95 ≤5 seconds under measured MVP load. Already accepted platform work follows reconciliation/cancel/takedown rather than an impossible instant guarantee.
- **Security/privacy:** no plaintext platform token in logs/database business fields/Agent context; raw face/voice data is isolated and omitted from ordinary trace/vector/test data.
- **Auditability:** every generated artifact and external attempt has stable IDs, hashes, versions, sources, actors, and timestamps.
- **Portability:** Provider switching does not alter business workflow or persisted business semantics.
- **Operability:** operator can identify retryable/permanent/unknown failures, cost, responsible queue, and required human action.
- **Reproducibility:** after M0-04/05, documented commands start the local stack and run quality gates on a clean checkout.

## 7. Primary workflow

1. A schedule or authorized operator creates a batch and ContentUnits.
2. Planning/research proposes sourced topics; creation produces structured scripts; media produces versioned assets.
3. Platform adaptation freezes one immutable candidate per platform/account.
4. Fact, rights, and risk checks inspect the final candidate and asset dependency closure.
5. Risk routing creates a hash-bound human approval request; any revision restarts affected checks.
6. Approved candidate enters transactional outbox only after policy, budget, stop, account, and approval validation.
7. Worker reacquires a publish lease and either invokes the officially authorized test adapter, performs Mock publish, or emits a downloadable package.
8. Results become confirmed, failed, or unknown/reconciliation; unknown never means retry-as-new.
9. Metrics and cost produce analysis while strategy/IP-bible changes remain proposals requiring their own approval.

The normative states and transition guards are in [content lifecycle](../specs/content-lifecycle.md).

## 8. External gates and fallback branches

| Gate | Approved path | Safe fallback |
|---|---|---|
| G0 scope/platform | Configure selected first platform and columns | Generic fixtures and package-only local demonstration |
| G1 deployment/Provider/budget | M2A with one legally approved text Provider | M2B with two behavioral Mock Providers |
| G2 platform Scope | M5A official API against allowlisted test account | M5B packages, Mock contracts, and manual reconciliation |
| G3 product acceptance | Continue toward API branch | Remain in manual package publishing |
| G4 test publish permission | Explicitly execute named test-account operation | Upload simulation and contract tests only |
| G5 automation | Limited named R1 scope after all evidence | Continue mandatory final approval |

Open choices are tracked in [DECISIONS.md](../../DECISIONS.md).

## 9. MVP release definition

The 12-week MVP is complete only when all applicable Backlog tasks through M6 pass, one M2 and one M5 branch are truthfully selected, 100 gold cases meet the release gate, every external content item remains human-final-approved, required failure drills pass, and no secret/rights/approval/idempotency critical defect is open. Four-week M7 stabilization is separate and cannot overlap feature completion.

Business outcomes such as followers, revenue, or the 90-day content experiment are measured by the business plan and are not fabricated as technical acceptance results.
