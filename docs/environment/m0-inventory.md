# M0-00 read-only environment inventory

- Captured: 2026-08-19 (Asia/Shanghai)
- Host: `LAPTOP-03A2LN8Q`
- Method: read-only PowerShell/.NET/tool version queries
- Change policy: no install, feature enablement, service start, registry write, or network call was performed

## Summary

The host has sufficient preliminary CPU, memory, and workspace disk capacity for local MVP development. After explicit founder authorization on 2026-08-20, WSL2 and Docker Desktop were installed and the local five-service container stack passed M0-05 acceptance. FFmpeg and ffprobe remain unavailable. The installed global Python 3.14 is not the project target (Python 3.12).

| Area | Observed result | Classification | Required follow-up |
|---|---|---|---|
| Operating system | Microsoft Windows build `10.0.26200`, x64 OS/process | Present | Confirm supported Docker/WSL path during M0-04/05. |
| WSL2 | WSL `2.7.12.0`, kernel `6.18.33.2-2`; default version 2 | Present | Keep the Docker WSL2 backend current; no general-purpose Linux distribution was required for M0-05. |
| Docker / Compose | Docker Desktop `4.87.0`, Engine/CLI `29.7.2`, Compose `v5.4.0`, Linux containers via WSL2 | Present | Keep Docker Desktop running for stack commands. |
| Virtualization | 2026-08-20 `systeminfo` reports that a hypervisor is detected; virtualization-based security is running | Present | The base virtualization prerequisite is satisfied; WSL2/Docker installation still requires explicit machine-change authority. |
| Python | Global `3.14.5`; project-isolated uv-managed `3.12.13` | Present | Use only the pinned project runtime for repository commands. |
| Node.js | `v24.15.0`; repository pins Node 24 LTS | Present | Keep within the pinned Node 24 engine range. |
| npm | `11.12.1`; repository pins npm 11 | Present | Restore with the committed lockfile. |
| FFmpeg / ffprobe | Commands not found | Missing | Human-authorized installation before M3-03; record exact version after install. |
| Git | `2.54.0.windows.1` | Present | Sufficient for local Git/worktree operations. |
| Repository | Local Git repository on `main`, no commits when inventory began | Present | M0 content is ready to become the initial reviewed commit; remote creation is D-009. |

## Resources

| Resource | Observed | Assessment |
|---|---:|---|
| Logical processors visible | 32 | Preliminary capacity is sufficient. |
| Physical memory | 63.63 GiB total, 33.92 GiB available, 46% load | Preliminary capacity is sufficient for the planned local services. |
| `C:` | 581.13 GiB total, 379.78 GiB free | Sufficient. |
| `D:` | 500.00 GiB total, 61.61 GiB free | Constrained relative to other drives; avoid container/media data here. |
| `E:` (workspace) | 500.00 GiB total, 468.76 GiB free | Sufficient for development and synthetic media fixtures. |
| `F:` | 300.00 GiB total, 299.85 GiB free | Sufficient but outside the current workspace scope. |

This is a capacity signal, not a load test. M0-05 subsequently measured approximately 177 MiB across the five idle containers, 49.9 MB in four local volumes, and 1.392 GB across the five active images; see [runtime evidence](../acceptance/m0-05-runtime.md).

## Planned local ports

At capture time the following TCP listen ports were available:

| Port | Planned use | Result |
|---:|---|---|
| 3000 | Web console | Available |
| 8000 | FastAPI | Available |
| 5432 | PostgreSQL | Available |
| 7233 | Temporal frontend | Available |
| 8233 | Temporal UI | Available |
| 3900 | Garage S3-compatible API | Not present in the original capture; M0-05 startup rechecks it |

Port availability is time-sensitive. M0-05 must recheck before binding and allow documented overrides rather than killing unrelated listeners.

## Missing items that require human authorization

1. Install FFmpeg/ffprobe before the video-template task.

No Provider SDK, platform credential, cloud resource, database service, or media binary was installed or contacted.

## M0-04 toolchain amendment

With founder authorization for local M0-04 setup, the repository now uses a project-isolated uv-managed CPython `3.12.13` runtime and uv `0.12.3`; the global Python 3.14 installation remains untouched. The existing Node `24.15.0` and npm `11.12.1` satisfy the pinned Node 24/npm 11 lines. Dependency state is captured by `uv.lock` and `package-lock.json` and restored with locked-install commands.

This amendment originally changed only the Python/Node development toolchain classification. A second read-only check on 2026-08-20 changed virtualization from unconfirmed to present. A later founder-authorized machine change installed WSL2 and Docker Desktop for M0-05. FFmpeg/ffprobe, Provider credentials, and external platform access remain missing or unauthorized.

## Limitations

- The original restricted-account capture could not confirm virtualization. The later
  `systeminfo` result confirms an active hypervisor but does not separately inventory each
  optional Windows feature.
- The original WSL queries reported that WSL was absent. The later authorized installation supersedes that observation; some `wsl.exe` output still renders as UTF-16/mojibake in the capture shell, so numeric versions were cross-checked separately.
- Tool discovery reflects the current sandbox `PATH`; a binary installed elsewhere but not exposed to this account would remain classified as unavailable.
