# Local development stack

## Boundary

This runbook starts the local M0-05/M1 development stack. It uses Mock/package-only behavior,
sets `DRY_RUN=true`, keeps external side effects disabled, and binds every published port to
`127.0.0.1`. It does not authorize Provider calls, platform publishing, portrait processing,
or production deployment.

The six services are:

| Service | Default URL/port | Purpose |
|---|---:|---|
| Web | `http://127.0.0.1:3000` | Minimal local console |
| API | `http://127.0.0.1:8000/healthz` | Control-plane health boundary |
| PostgreSQL | `127.0.0.1:5432` | Authoritative transactional domain data |
| Garage | `http://127.0.0.1:3900` | Local S3-compatible object storage |
| Temporal | `127.0.0.1:7233`; UI `http://127.0.0.1:8233` | Local durable-workflow development server |
| Workflow worker | Internal queue `agent-ip-content-v1` | Durable parent/child orchestration with PostgreSQL Activities and network-free Mock publish |

PostgreSQL, Garage, and Temporal use named volumes. `stack:down` preserves them. The worker
uses a read-only filesystem, runs as non-root, and refuses to start unless dry-run is enabled
and external side effects are disabled.

## Prerequisites

- Windows virtualization/hypervisor support enabled.
- WSL2 and a current Docker Desktop installation using Linux containers.
- The repository's pinned uv/Python and Node/npm toolchain.
- Docker Desktop running before a stack command is invoked.

The one-command startup performs a Docker daemon check, checks unused loopback ports,
generates random local-only credentials under ignored `.runtime/compose.env`, validates
Compose, builds the API/web/workflow-worker images, waits for health checks, and runs the independent
verification suite:

```powershell
npm run stack:up
```

Verify again without rebuilding:

```powershell
npm run stack:verify
```

Apply all pending forward-only database migrations to the local development database:

```powershell
npm run db:migrate
```

The migrator records each filename and SHA-256 checksum in `schema_migrations`, takes a
PostgreSQL advisory lock, and refuses changed or missing history. It never runs a down
migration. Production execution remains a separately reviewed and explicitly authorized
operation.

Run the migration, integrity, project-isolation, immutability, and idempotency suite against
short-lived databases on the local PostgreSQL service:

```powershell
npm run check:integration
```

Failure reports redact the database URL. The suite creates uniquely named test databases,
terminates their remaining sessions, and removes the test databases when complete.

Inspect, restart with persisted data, or stop while preserving volumes:

```powershell
npm run stack:status
npm run stack:restart
npm run stack:down
```

Do not commit or share `.runtime/compose.env`. Delete it only together with the associated
local volumes; otherwise the stored database/object data will retain credentials the next
startup no longer knows.

## Port conflicts

The startup script reports conflicts and never kills the owning process. Override a port in
the current shell when needed, then use the same override for later verification:

```powershell
$env:API_PORT = "18000"
$env:WEB_PORT = "13000"
npm run stack:up
npm run stack:verify
```

Supported overrides are `API_PORT`, `WEB_PORT`, `POSTGRES_PORT`,
`OBJECT_STORAGE_PORT`, `TEMPORAL_PORT`, and `TEMPORAL_UI_PORT`.

## Acceptance evidence

M0-05 was verified on the target host on 2026-08-20. The durable command results,
clean-checkout reproduction, versions, and resource snapshot are recorded in
[the M0-05 runtime evidence](../acceptance/m0-05-runtime.md).

Repeat `stack:up`, `stack:verify`, and `stack:restart` after changes to Compose, images,
health checks, or the host container runtime. Never copy the generated credential file
between checkouts.
