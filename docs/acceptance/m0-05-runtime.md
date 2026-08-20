# M0-05 runtime evidence

- Captured: 2026-08-20 (Asia/Shanghai)
- Host: `LAPTOP-03A2LN8Q`
- Result: **PASS / DONE**
- Safety boundary: local Mock/package-only behavior, `DRY_RUN=true`, external side effects disabled, and every published port bound to `127.0.0.1`

## Runtime versions

| Component | Verified version / mode |
|---|---|
| WSL | `2.7.12.0`; kernel `6.18.33.2-2`; default version 2 |
| Docker Desktop | `4.87.0`, WSL2 Linux-container backend |
| Docker Engine / CLI | `29.7.2` / `29.7.2` |
| Docker Compose | `v5.4.0` |

## Command evidence

The following repository commands completed successfully on the target host:

1. `npm run stack:up` built the API and web images, started PostgreSQL, Garage,
   Temporal, API, and Web, waited for health checks, and completed the independent
   verification routine.
2. `npm run stack:verify` confirmed all five running services, PostgreSQL readiness,
   Garage node health, Temporal cluster health, API `status=ok`, the disabled external
   side-effect boundary, the Web response, and the Temporal UI response.
3. `npm run stack:restart` restarted all five containers and then repeated the same
   verification successfully.

The first API image exposed a container-only permission defect: uv had linked the virtual
environment interpreter into root's private directory. The Dockerfile now selects
`/usr/local/bin/python3.12` explicitly and disables managed interpreter downloads during
image construction. A rebuilt image ran successfully as the non-root `agent-ip` user.

## Clean-checkout reproduction

An ignored temporary clone of the feature branch was created beneath the repository runtime
directory. It had no `.venv`, runtime credential file, containers, or volumes. `stack:up`:

- created a new CPython 3.12 environment from the lockfile;
- generated a new ignored `.runtime/compose.env` without displaying its values;
- rebuilt both application images;
- used project name `agent-ip-os-clean` and alternate loopback ports to remain isolated;
- reported all five services healthy and external side effects disabled.

After verification, only the isolated test containers, volumes, images, network, and clone
were removed. The primary development stack and its named volumes were preserved.

## Resource snapshot

An idle post-restart `docker stats --no-stream` snapshot reported:

| Service | Memory |
|---|---:|
| API | 37.98 MiB |
| Web | 51.94 MiB |
| Garage | 9.762 MiB |
| PostgreSQL | 21.51 MiB |
| Temporal | 55.63 MiB |
| **Approximate total** | **176.82 MiB** |

At capture time, Docker reported five active images using 1.392 GB, four active local
volumes using 49.9 MB, and 2.052 GB of build cache. Image and cache totals are engine-wide
snapshots rather than strict per-service allocations.

## Remaining host prerequisite

FFmpeg/ffprobe remain absent. They do not block M1 or M2, but M3-03 stays blocked until a
separately authorized installation and version capture are complete.
