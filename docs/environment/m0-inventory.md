# M0-00 read-only environment inventory

- Captured: 2026-08-19 (Asia/Shanghai)
- Host: `LAPTOP-03A2LN8Q`
- Method: read-only PowerShell/.NET/tool version queries
- Change policy: no install, feature enablement, service start, registry write, or network call was performed

## Summary

The host has enough preliminary CPU, memory, and workspace disk capacity for local MVP development, but it is not ready for the planned container/media stack. Docker, WSL2, FFmpeg, and ffprobe are unavailable. Hardware/firmware virtualization could not be confirmed under the current restricted account. The installed Python 3.14 is not the project target (Python 3.12).

| Area | Observed result | Classification | Required follow-up |
|---|---|---|---|
| Operating system | Microsoft Windows build `10.0.26200`, x64 OS/process | Present | Confirm supported Docker/WSL path during M0-04/05. |
| WSL2 | `wsl --status`, `--version`, and `--list --verbose` report that Windows Subsystem for Linux is not installed/enabled | Missing | Human-authorized Windows feature/distro installation if Docker/Temporal toolchain requires it. |
| Docker / Compose | `docker` command not found | Missing | Human-authorized Docker Desktop or approved alternative installation; do not install in this task. |
| Virtualization | CIM and `systeminfo` queries returned Access Denied; registry signals were absent/inconclusive | Unconfirmed | A human/admin must confirm BIOS/UEFI virtualization, Hyper-V/Virtual Machine Platform/WSL features before M0-05. |
| Python | `python --version` = `3.14.5`; executable under the user's local Python314 directory. `py --version` said no installed Python in the sandbox context | Present but incompatible/unreliable | Provision a project-isolated Python 3.12 runtime in M0-04 after approval; do not reuse 3.14 without compatibility decision. |
| Node.js | `v24.15.0` | Present, target not yet pinned | M0-04 selects and pins the supported Node line after Next.js compatibility review. |
| npm | `11.12.1` | Present | Pin package manager/version in M0-04. |
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
| 9000 | S3-compatible API | Available |
| 9001 | S3-compatible console | Available |

Port availability is time-sensitive. M0-05 must recheck before binding and allow documented overrides rather than killing unrelated listeners.

## Missing items that require human authorization

1. Confirm/enable virtualization and the approved Windows container/WSL prerequisites.
2. Install Docker Desktop or explicitly approve a different local container runtime.
3. Provision an isolated Python 3.12 toolchain.
4. Install FFmpeg/ffprobe before the video-template task.
5. Decide the supported Node/package-manager versions in M0-04; installation is needed only if the installed line is rejected.

No Provider SDK, platform credential, cloud resource, database service, or media binary was installed or contacted.

## M0-04 toolchain amendment

With founder authorization for local M0-04 setup, the repository now uses a project-isolated uv-managed CPython `3.12.13` runtime and uv `0.12.3`; the global Python 3.14 installation remains untouched. The existing Node `24.15.0` and npm `11.12.1` satisfy the pinned Node 24/npm 11 lines. Dependency state is captured by `uv.lock` and `package-lock.json` and restored with locked-install commands.

This amendment changes only the Python/Node development toolchain classification. Docker, WSL2, virtualization, FFmpeg/ffprobe, Provider credentials, and external platform access remain in their original missing, unconfirmed, or unauthorized states.

## Limitations

- Restricted-account CIM and `systeminfo` access prevented a definitive virtualization/firmware result.
- WSL output was UTF-16/mojibake in the capture shell, but all three queries consistently returned the standard “WSL is not installed; run `wsl.exe --install`” message. No install command was run.
- Tool discovery reflects the current sandbox `PATH`; a binary installed elsewhere but not exposed to this account would remain classified as unavailable.
