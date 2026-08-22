"""Operate and verify the local Docker Compose development stack."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "infra" / "docker-compose.yml"
RUNTIME_DIR = ROOT / ".runtime"
ENV_FILE = RUNTIME_DIR / "compose.env"
EXPECTED_SERVICES = {"api", "object-storage", "postgres", "temporal", "web", "workflow-worker"}
PORT_DEFAULTS = {
    "API_PORT": 8000,
    "OBJECT_STORAGE_PORT": 3900,
    "POSTGRES_PORT": 5432,
    "TEMPORAL_PORT": 7233,
    "TEMPORAL_UI_PORT": 8233,
    "WEB_PORT": 3000,
}


def ensure_runtime_env(path: Path | None = None) -> Path:
    """Create local-only random development credentials once."""

    path = ENV_FILE if path is None else path
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "GARAGE_ADMIN_TOKEN": secrets.token_urlsafe(32),
        "GARAGE_DEFAULT_ACCESS_KEY": f"GK{secrets.token_hex(16)}",
        "GARAGE_DEFAULT_SECRET_KEY": secrets.token_hex(32),
        "GARAGE_METRICS_TOKEN": secrets.token_urlsafe(32),
        "GARAGE_RPC_SECRET": secrets.token_hex(32),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    }
    content = "".join(f"{key}={value}\n" for key, value in sorted(values.items()))
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o600)
    return path


def compose_command(*arguments: str) -> list[str]:
    """Build the stable Compose command used by every stack operation."""

    return [
        "docker",
        "compose",
        "--env-file",
        str(ensure_runtime_env()),
        "-f",
        str(COMPOSE_FILE),
        *arguments,
    ]


def run_compose(*arguments: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    """Run Docker Compose from the repository root."""

    return subprocess.run(
        compose_command(*arguments),
        cwd=ROOT,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def require_docker() -> None:
    """Fail with an actionable message when Docker Desktop is unavailable."""

    if shutil.which("docker") is None:
        raise RuntimeError(
            "Docker is not installed or not on PATH. Complete the documented WSL2/Docker "
            "Desktop prerequisite before starting M0-05."
        )
    subprocess.run(
        ["docker", "info"],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def configured_ports() -> dict[str, int]:
    """Return validated loopback port overrides."""

    ports: dict[str, int] = {}
    for name, default in PORT_DEFAULTS.items():
        value = int(os.environ.get(name, default))
        if not 1 <= value <= 65535:
            raise ValueError(f"{name} must be between 1 and 65535")
        ports[name] = value
    if len(set(ports.values())) != len(ports):
        raise ValueError("stack port overrides must be unique")
    return ports


def port_is_available(port: int) -> bool:
    """Check a loopback TCP port without stopping another process."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def stack_has_containers() -> bool:
    """Return whether this Compose project already has containers."""

    result = run_compose("ps", "-q", capture_output=True)
    return bool(result.stdout.strip())


def assert_ports_available() -> None:
    """Report conflicts instead of killing unrelated listeners."""

    conflicts = [
        f"{name}={port}" for name, port in configured_ports().items() if not port_is_available(port)
    ]
    if conflicts:
        raise RuntimeError(
            "The following loopback ports are already in use: "
            + ", ".join(conflicts)
            + ". Stop the owning process or set a documented port override."
        )


def wait_for_http(url: str, *, expected_json: bool = False, timeout: float = 60.0) -> None:
    """Wait for an HTTP endpoint and enforce the API safety boundary when requested."""

    deadline = time.monotonic() + timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if not 200 <= response.status < 400:
                    raise RuntimeError(f"HTTP {response.status}")
                if expected_json:
                    payload = json.load(response)
                    if payload.get("status") != "ok":
                        raise RuntimeError("API did not report status=ok")
                    if payload.get("external_side_effects_enabled") is not False:
                        raise RuntimeError("API external side effects are not disabled")
                return
        except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as error:
            last_error = str(error)
            time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def verify() -> None:
    """Verify container state, infrastructure CLIs, UIs, and the API boundary."""

    running = set(
        run_compose("ps", "--services", "--filter", "status=running", capture_output=True)
        .stdout.strip()
        .splitlines()
    )
    missing = EXPECTED_SERVICES - running
    if missing:
        raise RuntimeError(f"Compose services are not running: {', '.join(sorted(missing))}")

    run_compose("exec", "-T", "postgres", "pg_isready", "-U", "agent_ip", "-d", "agent_ip")
    run_compose("exec", "-T", "object-storage", "/garage", "status")
    run_compose(
        "exec",
        "-T",
        "temporal",
        "temporal",
        "operator",
        "cluster",
        "health",
        "--address",
        "127.0.0.1:7233",
    )

    ports = configured_ports()
    wait_for_http(f"http://127.0.0.1:{ports['API_PORT']}/healthz", expected_json=True)
    wait_for_http(f"http://127.0.0.1:{ports['WEB_PORT']}/")
    wait_for_http(f"http://127.0.0.1:{ports['TEMPORAL_UI_PORT']}/")
    print("Local stack verified: 6 services healthy; external side effects remain disabled.")


def main(arguments: list[str] | None = None) -> int:
    """Dispatch a stable stack command."""

    command_arguments = sys.argv[1:] if arguments is None else arguments
    command = command_arguments[0] if len(command_arguments) == 1 else ""
    try:
        if command not in {"config", "down", "restart", "status", "up", "verify"}:
            raise ValueError("usage: dev_stack.py {config|up|verify|restart|status|down}")
        require_docker()
        if command == "config":
            run_compose("config", "--quiet")
            print("Compose configuration is valid.")
        elif command == "up":
            if not stack_has_containers():
                assert_ports_available()
            run_compose("up", "-d", "--build", "--wait")
            verify()
        elif command == "verify":
            verify()
        elif command == "restart":
            run_compose("restart")
            run_compose("up", "-d", "--wait")
            verify()
        elif command == "status":
            run_compose("ps")
        else:
            run_compose("down", "--remove-orphans")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Stack command failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
