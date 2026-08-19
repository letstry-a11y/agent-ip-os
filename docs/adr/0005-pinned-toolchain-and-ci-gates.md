# ADR-0005: Pin the toolchain and share quality gates with CI

- Status: Accepted
- Date: 2026-08-19
- Source authority: M0-04 execution plan and accepted M0 specifications

## Context

The host exposes Python 3.14 and Node 24, while the backend target is Python 3.12 and framework compatibility changes over time. Reproducible local and CI results require a declared runtime, deterministic dependency resolution, and one set of commands rather than environment-specific checklists.

## Decision

Use uv `0.12.3` with uv-managed CPython `3.12.13`. Use the Node `24` LTS line with npm `11`; pin direct production framework dependencies and commit `package-lock.json`. Commit `uv.lock` for the complete Python workspace. Locked installation is mandatory in CI and clean-checkout verification; Node lifecycle scripts stay disabled unless a later reviewed dependency explicitly requires one.

The root `npm run check` command is the canonical quality gate. It runs:

- repository link, baseline-integrity, high-confidence secret, and migration-name checks;
- Ruff formatting and linting, strict mypy, and pytest with branch coverage;
- Prettier, ESLint, TypeScript, and Vitest for the web workspace.

`npm run build` separately verifies the production Next.js build. GitHub Actions runs locked restores, the same quality gate, and the build on pull requests and pushes to `main` with read-only repository permissions.

## Consequences

- Positive: the host's global Python version cannot silently alter backend results, and local/CI commands stay aligned.
- Positive: lockfile review makes transitive dependency changes explicit.
- Cost: runtime and tool upgrades require intentional changes to version files, manifests, lockfiles, tests, and this decision's successor if the supported line changes.
- Constraint: no task may claim hosted CI evidence until a private remote and workflow run exist under D-009.
- Constraint: M0-04 does not authorize Docker, Provider SDKs, credentials, cloud resources, platform calls, or production actions.

## Rejected alternatives

- Reuse global Python 3.14: outside the approved backend target and vulnerable to host drift.
- Unlocked installs or floating runtime tags: cannot demonstrate clean-checkout reproducibility.
- Separate local and CI scripts: creates divergence and makes acceptance evidence ambiguous.
