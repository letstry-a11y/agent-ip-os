# Core data model

- Status: M1-01 physical model, M1-03 canonical bindings, and M1-06 approval binding implemented
- Version: 1.1
- Related: [MVP PRD](../product/prd-mvp.md), [content lifecycle](../specs/content-lifecycle.md), [canonical JSON v1](../specs/canonical-json-v1.md), [ADR-0004](../adr/0004-postgresql-authority-and-deferred-vectors.md)

## Modeling rules

- IDs are stable opaque identifiers; implementation chooses UUIDv7 only after runtime/library compatibility tests.
- Stored timestamps are UTC; schedules also store the intended IANA time zone.
- Mutable business concepts use explicit versions. A published/approved candidate is never updated in place.
- Hashes identify canonical content/snapshots; they are not substitutes for primary keys or authorization.
- Large bytes live in object storage; PostgreSQL stores metadata, immutable object version/key, size, media type, and cryptographic digest.
- Every tenant-bound row includes the single MVP project ID even though the MVP is single-tenant, preventing accidental cross-project access patterns later.

## Main aggregates

```mermaid
erDiagram
    IP_PROJECT ||--o{ CONTENT_UNIT : owns
    IP_PROJECT ||--o{ IP_BIBLE_VERSION : defines
    CONTENT_UNIT ||--o{ CONTENT_VERSION : versions
    CONTENT_UNIT ||--o{ CONTENT_TASK : executes
    CONTENT_TASK ||--o{ AGENT_RUN : invokes
    AGENT_RUN ||--o{ TOOL_CALL : records
    CONTENT_VERSION ||--o{ ARTIFACT : produces
    ARTIFACT ||--o{ ARTIFACT_DERIVATION : parent
    ARTIFACT ||--o{ ARTIFACT_DERIVATION : child
    ARTIFACT ||--o{ ASSET_RIGHT : requires
    CONSENT_GRANT ||--o{ ASSET_RIGHT : supports
    CONTENT_UNIT ||--o{ PLATFORM_CANDIDATE : adapts
    PLATFORM_CANDIDATE }o--o{ ARTIFACT : includes
    PLATFORM_CANDIDATE ||--o{ FACT_CLAIM : contains
    PLATFORM_CANDIDATE ||--o{ RISK_REPORT : checked_by
    PLATFORM_CANDIDATE ||--o{ APPROVAL_REQUEST : requests
    APPROVAL_REQUEST ||--o{ APPROVAL_SNAPSHOT : resolves
    PLATFORM_CANDIDATE ||--o{ PUBLISH_INTENT : authorizes
    PUBLISH_INTENT ||--o{ PUBLISH_JOB : dispatches
    PUBLISH_JOB ||--o{ PUBLISH_ATTEMPT : attempts
    PUBLISH_INTENT ||--o| PLATFORM_POST : confirms
    PLATFORM_POST ||--o{ METRIC_SNAPSHOT : measures
    PLATFORM_POST ||--o{ TAKEDOWN_JOB : may_require
    IP_PROJECT ||--o{ DECISION_LOG : records
    IP_PROJECT ||--o{ AUDIT_EVENT : audits
    CONTENT_UNIT ||--o{ COST_LEDGER : costs
```

## Aggregate responsibilities

| Aggregate / table family | Required concepts and invariants |
|---|---|
| `ip_projects`, `ip_bible_versions` | Project identity; versioned positioning, voice, prohibited areas, and effective approval. Agent may propose a bible change but cannot make it effective. |
| `content_units`, `content_versions`, `content_tasks` | Parent business lifecycle, immutable content revisions, current task/state, expected version, trace, and failure category. |
| `agent_configs`, `agent_runs`, `tool_calls` | Versioned role contract/prompt/tool allowlist/budget; run input/output hashes, Provider/model, source IDs, latency, status, cost; tool authorization and redacted result metadata. |
| `artifacts`, `artifact_derivations` | Immutable object digest/version and directed acyclic derivation edge with transformation/version. A final asset cannot pass if its dependency closure is incomplete or cyclic. |
| `asset_rights`, `consent_grants` | Rights owner/evidence, purpose, platform, territory, term, Provider, commercial/derivative/relicense scope, revocation and retention. These relational records are authoritative. |
| `platform_candidates` + candidate-artifact join | Platform/account/policy-specific immutable title, caption, normalized/sorted tags, ordered asset list, AI disclosure, schedule, canonical payload/hash, supersession relation. |
| `fact_claims`, rights manifest, `risk_reports` | Claims mapped to evidence snapshots/time/confidence/result; final asset-closure result; risk rule version/hits/R0–R4/block reason. Reports are immutable and hashable. |
| `approval_requests`, `approval_snapshots` | Requested action/risk/required roles, expiry/status; resolution binds candidate and all report/policy/account hashes plus distinct human actor(s). Revision never reuses an old approval. |
| `platform_accounts` | Platform, environment/test marker, subject/Scope/status, encrypted credential reference (not token), revoked/paused state, capabilities version. |
| `publish_intents`, outbox, `publish_jobs`, `publish_attempts` | Intent ID, request fingerprint, repost reason, atomic outbox, lease, attempt number/error class/request/response hashes, platform upload/draft references, known/unknown result and reconciliation owner. |
| `platform_posts`, `takedown_jobs` | Confirmed platform post identity and candidate/intent; revocation/removal workflow per post with platform-limitation evidence. |
| `comment_events`, `metric_snapshots` | Deduplicated platform events; source is API or manual. MVP reply text remains a draft and no send intent exists. Manual metrics store evidence and actor. |
| `cost_ledger`, `experiments` | Provider/media/storage/platform/human cost with currency and source; predeclared experiment variable/hypothesis/window so results cannot rewrite criteria retroactively. |
| `decision_log`, `audit_events` | In-product approved decisions; append-only actor/action/resource/time/trace/previous-hash/event-hash chain. Agent has no update/delete permission. |

## Authority by data type

| Question | Authoritative source | Never authoritative |
|---|---|---|
| May this asset/persona be used now? | `asset_rights` + `consent_grants` and current revocation/term | Vector search, prompt text, artifact filename |
| Is this exact candidate approved? | Valid `approval_snapshot` bound to hashes/account/expiry | UI checkbox cache, Agent answer |
| Was an external request made/succeeded? | Publish attempt plus reconciled `platform_post`/official or human evidence | Temporal retry count alone, missing response interpreted as failure |
| Is publishing stopped? | Transactional global/account stop state checked at intent and lease | Cached dashboard state |
| What did the Agent know/use? | Run/tool/source/prompt/model version records and redacted trace | Provider conversation ID alone |
| Is a policy effective? | Versioned policy record with source/effective date/approval | Latest web search result |

## Migration constraints for M1-01

M1-01 turns the conceptual model into the smallest authoritative schema needed for the M1
vertical slice. The implemented physical tables are:

| Family | M1-01 tables | Boundary |
|---|---|---|
| Project and content | `ip_projects`, `content_units`, `content_versions` | The unit holds mutable lifecycle/version counters; version payloads are immutable. |
| Assets and rights | `artifacts`, `consent_grants`, `asset_rights` | PostgreSQL stores metadata and authority only; object bytes remain outside the database. |
| Candidate | `platform_accounts`, `platform_candidates`, `platform_candidate_states`, `candidate_artifacts` | Frozen payload binds one immutable content version and ordered assets; lifecycle state has an independent compare-and-swap version. |
| Approval | `approval_requests`, `approval_snapshots` | Requests may resolve; snapshots bind candidate/report/policy/account hashes and are immutable. |
| Publish and audit | `publish_intents`, `outbox_messages`, `audit_events` | Fingerprints are unique, intent/outbox rows must coexist at transaction commit, and evidence rows are append-only. |

Every tenant-bound primary entity carries `project_id`. Composite foreign keys prevent a
row from referring to an entity in another project even when an opaque ID is known. UUIDs
are application-supplied so M1-01 does not select a UUIDv7 extension prematurely. All
stored timestamps use `timestamptz`; application schemas reject naive datetimes.

`content_versions`, `artifacts`, `platform_candidates`, `candidate_artifacts`,
`approval_snapshots`, `publish_intents`, and `audit_events` reject update and delete after
M1-01 migration `0002`. Mutable lifecycle/status fields live on their owning request/state
rows instead of mutating frozen payloads.

Migration `0003` adds the explicit content-version binding that every platform candidate
requires. It refuses to infer a version if a pre-release database already contains a
candidate, because silently guessing the source version would create false approval evidence.

M1-03 gives candidate and approval hashes one cross-runtime byte contract. One authorized
human approval is sufficient during early/MVP operation. Migration `0004` does not require
two approvers; it only prevents the same subject from being counted twice if a future policy
adds a second approver. Runtime evaluation fails closed when the snapshot hash, decision,
expiry, candidate/report/policy/account binding, or approved action no longer matches current
authoritative values.

Migration `0006` adds a compare-and-swap version to each approval request and an immutable
`approval_request_bindings` row. The binding freezes the candidate, fact, rights, risk,
account, policy, and requested-action evidence before the request is shown to a human. The
M1-06 API resolves actor identity on the server, prevents the request initiator from deciding
their own request, and creates the existing canonical approval snapshot in the same database
transaction that advances both request and candidate state.

`publish_intents.outbox_message_id` and `outbox_messages.publish_intent_id` form deferred,
unique, project-scoped foreign keys. Both rows can be inserted in either order inside one
transaction, but a transaction containing only one side cannot commit. The outbox delivery
columns remain mutable for M1-04 dispatch/retry behavior.

The audit table stores a per-project previous/event hash chain. Database constraints enforce
one genesis event, an existing predecessor, no chain fork, and immutable rows. M4-03 remains
responsible for recomputing hashes, access control, and WORM export.

M1-01 deliberately defers agent/tool runs, derivation closure, fact/risk report bodies,
platform attempts/posts, stop flags, metrics, comments, costs, and experiments to their
own Backlog tasks. Approval snapshots reserve the final report hashes without treating
unimplemented report tables as authoritative evidence.
