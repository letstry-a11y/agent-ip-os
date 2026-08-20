# M0-00 read-only environment inventory

- Captured: 2026-08-19 (Asia/Shanghai)
- Host: `LAPTOP-03A2LN8Q`
- Method: read-only PowerShell/.NET/tool version queries
- Change policy: no install, feature enablement, service start, registry write, or network call was performed

## Summary

The host has enough preliminary CPU, memory, and workspace disk capacity for local MVP development, but it is not ready for the planned container/media stack. Docker, WSL2, FFmpeg, and ffprobe are unavailable. A 2026-08-20 read-only follow-up confirmed that Windows detects an active hypervisor and virtualization-based security is running. The installed Python 3.14 is not the project target (Python 3.12).

| Area | Observed result | Classification | Required follow-up |
|---|---|---|---|
| Operating system | Microsoft Windows build `10.0.26200`, x64 OS/process | Present | Confirm supported Docker/WSL path during M0-04/05. |
| WSL2 | `wsl --status`, `--version`, and `--list --verbose` report that Windows Subsystem for Linux is not installed/enabled | Missing | Human-authorized Windows feature/distro installation if Docker/Temporal toolchain requires it. |
| Docker / Compose | `docker` command not found | Missing | Human-authorized Docker Desktop or approved alternative installation; do not install in this task. |
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

This is a capacity signal, not a load test. M0-05 must measure actual container memory and disk consumption after the stack exists.

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

1. Enable/install the approved Windows WSL2 prerequisites.
2. Install Docker Desktop or explicitly approve a different local container runtime.
3. Install FFmpeg/ffprobe before the video-template task.

No Provider SDK, platform credential, cloud resource, database service, or media binary was installed or contacted.

## M0-04 toolchain amendment

With founder authorization for local M0-04 setup, the repository now uses a project-isolated uv-managed CPython `3.12.13` runtime and uv `0.12.3`; the global Python 3.14 installation remains untouched. The existing Node `24.15.0` and npm `11.12.1` satisfy the pinned Node 24/npm 11 lines. Dependency state is captured by `uv.lock` and `package-lock.json` and restored with locked-install commands.

This amendment originally changed only the Python/Node development toolchain classification. A second read-only check on 2026-08-20 changed virtualization from unconfirmed to present. Docker, WSL2, FFmpeg/ffprobe, Provider credentials, and external platform access remain missing or unauthorized.

## Limitations

- The original restricted-account capture could not confirm virtualization. The later
  `systeminfo` result confirms an active hypervisor but does not separately inventory each
  optional Windows feature.
- WSL output was UTF-16/mojibake in the capture shell, but all three queries consistently returned the standard “WSL is not installed; run `wsl.exe --install`” message. No install command was run.
- Tool discovery reflects the current sandbox `PATH`; a binary installed elsewhere but not exposed to this account would remain classified as unavailable.
