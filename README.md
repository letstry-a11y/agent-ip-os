# Agent IP OS

Agent IP OS is a local-first, auditable operating system for a two-founder AI-assisted content company. It separates deterministic workflow state, Agent cognition, controlled tools, and versioned assets so external actions remain reviewable and reversible where possible.

## Current status

M0-00 through M0-03 are complete and accepted. M0-04 now provides the pinned Python/Node workspace, a minimal API and web shell, locked dependencies, local quality gates, and a GitHub Actions workflow. M0-05 remains blocked by the missing Docker/WSL2 prerequisites and unconfirmed virtualization.

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
- [AI portrait authorization template](docs/rights/身份衍生虚拟AI肖像授权与撤回清单_v1.md): scoped consent, Provider, security, approval, and revocation checklist.
- [Architecture decisions](docs/adr/README.md): accepted technical decisions.
- [M0 acceptance record](docs/acceptance/m0.md): evidence and remaining gate.

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

The project pins uv `0.12.3`, uv-managed CPython `3.12.13`, Node `24` LTS, and npm `11`. The host's global Python 3.14 is not used by project commands. Docker, WSL2, FFmpeg, and ffprobe remain unavailable, and virtualization is unconfirmed. Full evidence and required follow-up are in the [environment inventory](docs/environment/m0-inventory.md).

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

For local development, start the current shells separately:

```powershell
npm run dev:api
npm run dev:web
```

The API health endpoint is `http://127.0.0.1:8000/healthz`; the web shell uses `http://127.0.0.1:3000`. One-command full-stack startup is deliberately deferred to M0-05 because the database, object storage, and Temporal containers do not exist yet.

## Safety

Never put credentials in chat or repository files. Use `.env.example` only as a key-name template. Real publishing, paid calls, cloud creation, production deployment, destructive migrations, and platform authorization require separate explicit human approval.
