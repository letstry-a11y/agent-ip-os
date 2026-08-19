# Architecture decision records

ADRs capture technical decisions that are expensive to reverse. Product/provider/platform/account/budget choices requiring founder authority remain in [DECISIONS.md](../../DECISIONS.md).

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-deterministic-durable-workflows.md) | Accepted | Temporal/code owns durable workflow; Agents do not. |
| [0002](0002-modular-monolith-and-provider-neutrality.md) | Accepted | Start as a modular monolith behind Provider-neutral contracts. |
| [0003](0003-official-platform-api-or-publish-package.md) | Accepted | Use official authorized APIs or degrade to publish packages; never bypass. |
| [0004](0004-postgresql-authority-and-deferred-vectors.md) | Accepted | PostgreSQL is business truth; vector retrieval is deferred from MVP core. |
| [0005](0005-pinned-toolchain-and-ci-gates.md) | Accepted | Pin uv/Python and Node/npm, commit lockfiles, and use one local/CI quality gate. |

Statuses: Proposed, Accepted, Superseded, Rejected. Never edit an accepted ADR to reverse its outcome; add a new ADR that supersedes it.
