"""Validate a network-free platform qualification evidence record."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = ROOT / "config" / "platforms" / "xiaohongshu-qualification-v1.json"
OFFICIAL_HOSTS = frozenset({"agora.xiaohongshu.com", "miniapp.xiaohongshu.com"})
SENSITIVE_KEY_PARTS = ("cookie", "password", "secret", "token", "credential")
REQUIRED_EVIDENCE_FLAGS = (
    "test_account_evidenced",
    "developer_app_evidenced",
    "callback_domain_evidenced",
    "api_approval_evidenced",
    "explicit_probe_authorization_evidenced",
)


class QualificationError(ValueError):
    """Raised when a qualification record is malformed or overstates authorization."""


def require_mapping(value: object, label: str) -> dict[str, object]:
    """Return a string-keyed mapping or raise a stable validation error."""

    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise QualificationError(f"{label} must be an object with string keys")
    return cast(dict[str, object], value)


def require_string_list(value: object, label: str) -> tuple[str, ...]:
    """Return an immutable string list or raise a stable validation error."""

    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise QualificationError(f"{label} must be an array of strings")
    return tuple(cast(list[str], value))


def reject_sensitive_fields(value: object, path: str = "record") -> None:
    """Reject secret-bearing field names recursively before any record is accepted."""

    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise QualificationError(f"{path} contains a non-string key")
            lowered = raw_key.lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                raise QualificationError(f"{path}.{raw_key} is a forbidden sensitive field")
            reject_sensitive_fields(child, f"{path}.{raw_key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive_fields(child, f"{path}[{index}]")


def select_branch(record: Mapping[str, object]) -> str:
    """Select M5A only for a complete, explicitly authorized official probe."""

    evidence = require_mapping(record.get("account_evidence"), "account_evidence")
    flags_complete = all(evidence.get(field) is True for field in REQUIRED_EVIDENCE_FLAGS)
    scopes = require_string_list(evidence.get("exact_scopes"), "account_evidence.exact_scopes")
    probe = require_mapping(record.get("minimal_probe"), "minimal_probe")
    probe_passed = probe.get("result") == "PASS" and probe.get("external_requests") == 1
    return "M5A" if flags_complete and "generic_note_publish" in scopes and probe_passed else "M5B"


def validate_record(payload: object) -> dict[str, object]:
    """Validate sources, safety fields, and branch truthfulness."""

    record = require_mapping(payload, "record")
    reject_sensitive_fields(record)
    if record.get("schema_version") != 1:
        raise QualificationError("schema_version must equal 1")
    if record.get("platform") != "xiaohongshu":
        raise QualificationError("platform must equal xiaohongshu")

    sources = record.get("official_sources")
    if not isinstance(sources, list) or not sources:
        raise QualificationError("official_sources must be a non-empty array")
    for index, source_value in enumerate(sources):
        source = require_mapping(source_value, f"official_sources[{index}]")
        url = source.get("url")
        if not isinstance(url, str):
            raise QualificationError(f"official_sources[{index}].url must be a string")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
            raise QualificationError(f"official_sources[{index}].url is not an approved host")

    branch = select_branch(record)
    if record.get("selected_branch") != branch:
        raise QualificationError(f"selected_branch must be {branch} for the recorded evidence")
    probe = require_mapping(record.get("minimal_probe"), "minimal_probe")
    if probe.get("mode") == "DOCUMENTATION_ONLY" and probe.get("external_requests") != 0:
        raise QualificationError("documentation-only probe must record zero external requests")
    return record


def load_record(path: Path) -> dict[str, object]:
    """Load and validate one UTF-8 JSON evidence record."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    return validate_record(payload)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the configured snapshot and print a non-sensitive result."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, default=DEFAULT_RECORD)
    args = parser.parse_args(argv)
    try:
        record = load_record(args.record)
    except (OSError, json.JSONDecodeError, QualificationError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "valid": True,
                "platform": record["platform"],
                "selected_branch": record["selected_branch"],
                "probe_result": require_mapping(record["minimal_probe"], "minimal_probe")["result"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
