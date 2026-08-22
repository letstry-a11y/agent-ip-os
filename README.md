# Agent IP OS

Agent IP OS is a local-first, auditable operating system for a two-founder AI-assisted content company. It separates deterministic workflow state, Agent cognition, controlled tools, and versioned assets so external actions remain reviewable and reversible where possible.

## Current status

M0-00 through M0-05 and M1-01 through M1-04 are complete; M1-05 is ready for review. The repository has a pinned Python/Node workspace, minimal API and web shells, locked dependencies, local quality gates, hosted CI, a verified six-service Docker Compose development stack, shared versioned domain contracts, forward-only PostgreSQL migrations, a cross-runtime canonical-hash contract, durable Temporal parent/child workflows backed by PostgreSQL Activities, accepted guarded Mock publish dispatch, and deterministic network-free Agent/media/platform fault fixtures. The public [`letstry-a11y/agent-ip-os`](https://github.com/letstry-a11y/agent-ip-os) repository protects `main` with pull requests, an up-to-date passing `quality` check, resolved conversations, and linear history. M1-04 acceptance and M1-05 implementation have not authorized any real external action.

The current default is Mock-only, `DRY_RUN=true`, no cloud resources, no real Provider, and no real platform action.

## MVP boundary

The 12-week MVP delivers six combined Agent runtime units, image/text and one 30-second video workflow, mandatory human final approval, and either one officially authorized platform adapter or a publish-package fallback. It does not automate replies, contracts, payments, or unrestricted R1 publishing. See the [MVP PRD](docs/product/prd-mvp.md) for testable requirements.

## Start here

1. Read [AGENTS.md](AGENTS.md).
2. Review the [baseline manifest](docs/baseline/README.md).
3. Resolve or explicitly defer items in [DECISIONS.md](DECISIONS.md).
4. Select one ready item from [BACKLOG.md](BACKLOG.md).
5. Read the linked specification and ADRs before changing files.

## Documentation map

- [Environment inventory](docs/environment/m0-inventory.md): read-only host facts and missing prerequisites.
- [MVP PRD](docs/product/prd-mvp.md): users, scope, functional requirements, non-goals, and release measures.
- [System context](docs/architecture/system-context.md): boundaries, components, trust zones, and dependencies.
- [Core data model](docs/architecture/data-model.md): authoritative aggregates and relationships.
- [Content lifecycle](docs/specs/content-lifecycle.md): parent/child state machines and invariants.
- [Temporal workflow v1](docs/specs/temporal-workflow-v1.md): durable parent/child IDs, signals, Activities, retries, and Mock boundary.
- [Canonical JSON v1](docs/specs/canonical-json-v1.md): exact candidate/snapshot bytes, hashes, and invalidation bindings.
- [AI portrait authorization template](docs/rights/身份衍生虚拟AI肖像授权与撤回清单_v1.md): scoped consent, Provider, security, approval, and revocation checklist.
- [Architecture decisions](docs/adr/README.md): accepted technical decisions.
- [Local development stack](docs/runbooks/local-development.md): one-command Compose operations and acceptance procedure.
- [M0 acceptance record](docs/acceptance/m0.md): evidence and remaining gate.
- [M1-01 schema evidence](docs/acceptance/m1-01-core-schema.md): migrations, invariants, and real-PostgreSQL verification.
- [M1-02 Temporal evidence](docs/acceptance/m1-02-temporal-workflow.md): restart recovery, terminal/retry matrix, real Activities, and six-service runtime.
- [M1-03 canonical-hash evidence](docs/acceptance/m1-03-canonical-hash.md): cross-runtime vectors, invalidation tests, and database guard.
- [M1-04 publish-dispatch evidence](docs/acceptance/m1-04-publish-dispatch.md): request deduplication, short leases, stop races, and UNKNOWN reconciliation.
- [M1-05 Mock evidence](docs/acceptance/m1-05-mock-boundaries.md): deterministic Agent/media/platform failures, network guard, and cost reporting.
- [Mock boundaries v1](docs/specs/mock-boundaries-v1.md): deterministic Agent/media/platform success, failure, and cost semantics with no network.

## Planned repository layout

```text
apps/                     deployable API, console, and media worker
packages/                 domain, workflow, Agent, policy, adapter, media, and eval modules
config/                   versioned contracts, policies, platforms, and templates
migrations/               forward database migrations
infra/                    local Compose and later deployment definitions
tests/                    unit, integration, workflow, and platform-sandbox tests
docs/                     durable product and operational memory
```

Placeholder files preserve boundaries that have not yet entered implementation. The API and web placeholders were replaced by their M0-04 project shells; business workflows remain out of scope until M1.

## Local prerequisites

The project pins uv `0.12.3`, CPython `3.12.13`, Node `24` LTS, and npm `11`. The host's global Python 3.14 is not used by project commands. WSL2 and Docker Desktop are installed and the Linux-container development stack is verified; FFmpeg and ffprobe remain unavailable and will require separate authorization before M3-03. Full evidence and required follow-up are in the [environment inventory](docs/environment/m0-inventory.md).

## Commands

Install the pinned tools, then restore the locked dependencies from the repository root:

```powershell
uv python install
uv sync --locked --all-groups
npm ci --ignore-scripts
```

Run every M0-04 quality gate and the production web build:

```powershell
npm run check
npm run build
```

Apply the forward-only migrations to the local development database, then run the isolated
real-PostgreSQL migration and constraint suite:

```powershell
npm run db:migrate
npm run check:integration
```

With Docker Desktop running, start and verify the full local stack:

```powershell
npm run stack:up
npm run stack:verify
```

The command starts the API, web console, PostgreSQL 16, Garage S3-compatible local storage, Temporal development server/UI, and the Mock-only Temporal workflow worker. See the [local development runbook](docs/runbooks/local-development.md) for endpoints, restart/stop commands, port overrides, credential handling, and runtime evidence.

## Safety

Never put credentials in chat or repository files. Use `.env.example` only as a key-name template. Real publishing, paid calls, cloud creation, production deployment, destructive migrations, and platform authorization require separate explicit human approval.
