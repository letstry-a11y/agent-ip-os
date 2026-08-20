# Local development stack

## Boundary

This runbook starts the M0-05 development stack only. It uses Mock/package-only behavior,
sets `DRY_RUN=true`, keeps external side effects disabled, and binds every published port to
`127.0.0.1`. It does not authorize Provider calls, platform publishing, portrait processing,
or production deployment.

The five services are:

| Service | Default URL/port | Purpose |
|---|---:|---|
| Web | `http://127.0.0.1:3000` | Minimal local console |
| API | `http://127.0.0.1:8000/healthz` | Control-plane health boundary |
| PostgreSQL | `127.0.0.1:5432` | Future authoritative domain data |
| Garage | `http://127.0.0.1:3900` | Local S3-compatible object storage |
| Temporal | `127.0.0.1:7233`; UI `http://127.0.0.1:8233` | Local durable-workflow development server |

PostgreSQL, Garage, and Temporal use named volumes. `stack:down` preserves them.

## Prerequisites

- Windows virtualization/hypervisor support enabled.
- WSL2 and a current Docker Desktop installation using Linux containers.
- The repository's pinned uv/Python and Node/npm toolchain.
- Docker Desktop running before a stack command is invoked.

The one-command startup performs a Docker daemon check, checks unused loopback ports,
generates random local-only credentials under ignored `.runtime/compose.env`, validates
Compose, builds the API/web images, waits for health checks, and runs the independent
verification suite:

```powershell
npm run stack:up
```

Verify again without rebuilding:

```powershell
npm run stack:verify
```

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

## Acceptance evidence still required

M0-05 is not complete merely because the files exist. On the target host, record:

1. successful `npm run stack:up` and `npm run stack:verify` output;
2. successful `npm run stack:restart` followed by verification;
3. a clean-checkout reproduction with newly generated local credentials;
4. the Docker/WSL2 versions and approximate container memory/disk footprint.
