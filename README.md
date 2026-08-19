# Agent IP OS

Agent IP OS is a local-first, auditable operating system for a two-founder AI-assisted content company. It separates deterministic workflow state, Agent cognition, controlled tools, and versioned assets so external actions remain reviewable and reversible where possible.

## Current status

M0-00 through M0-02 are complete. M0-03 specifications are ready for founder review. This repository intentionally contains no application implementation or installed dependencies yet; the next engineering task is `M0-04` after M0-03 is accepted.

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

Placeholder files preserve the planned boundaries in fresh clones. They are replaced by real package/app files only as their Backlog task begins.

## Local prerequisites

The read-only M0 inventory found Windows x64, Git, Node 24, and Python 3.14, but no Docker, WSL2, FFmpeg, or ffprobe. Virtualization could not be confirmed with current permissions. Python 3.14 is not the approved backend runtime; Python 3.12 remains the target. Do not install or change the machine as part of M0-00 through M0-03. Full evidence and required follow-up are in the [environment inventory](docs/environment/m0-inventory.md).

## Commands

Canonical one-command startup and one-command quality checks do not exist yet because `M0-04` (Python/Node project and CI) and `M0-05` (Docker Compose) have not been executed. Claiming one-command reproducibility before those tasks would be false. These commands must be documented here as part of those tasks and verified on a clean checkout.

## Safety

Never put credentials in chat or repository files. Use `.env.example` only as a key-name template. Real publishing, paid calls, cloud creation, production deployment, destructive migrations, and platform authorization require separate explicit human approval.
