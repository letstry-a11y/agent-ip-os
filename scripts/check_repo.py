"""Check repository links, baselines, migrations, and obvious secret leaks."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATTERN = re.compile(r"^(?P<sequence>\d{4})_[a-z0-9_]+\.(?:py|sql)$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*"
        r"['\"]?[A-Za-z0-9_./+=-]{16,}",
        re.IGNORECASE,
    ),
)
BASELINE_HASHES = {
    "docs/baseline/AI超级IP双人公司商业计划书_v1.md": (
        "9B4CD455C682FEA18913D66777E5A2DA7311F4A902B422A11921BDC0E025D585"
    ),
    "docs/baseline/AI超级IP全Agent公司技术方案_v1.md": (
        "24E7A48B3E5305F2B2497BE9819B4051CD5F647188D7643471A62DAB5B7F66D5"
    ),
    "docs/baseline/AI超级IP系统_Codex开发执行计划_v1.md": (
        "34848C390329E9DBA66C090EDFCD1A854BF4A76433A31A3FFB9D05465CF82630"
    ),
}


def repository_files(root: Path = ROOT) -> list[Path]:
    """Return present tracked and untracked, non-ignored files without a shell."""

    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    return [path for path in paths if path.is_file()]


def secret_issues(paths: Iterable[Path], root: Path = ROOT) -> list[str]:
    """Return forbidden filenames and high-confidence secret-like matches."""

    issues: list[str] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.name == ".env" or path.suffix.lower() in {".pem", ".p12", ".pfx"}:
            issues.append(f"forbidden sensitive filename: {relative}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                issues.append(f"secret-like content matched in {relative}: {pattern.pattern}")
    return issues


def migration_issues(directory: Path) -> list[str]:
    """Validate forward migration names and unique numeric sequences."""

    issues: list[str] = []
    sequences: set[str] = set()
    for path in sorted(directory.iterdir()):
        if path.name == ".gitkeep":
            continue
        if not path.is_file():
            issues.append(f"unexpected migration directory: {path.name}")
            continue
        match = MIGRATION_PATTERN.fullmatch(path.name)
        if match is None:
            issues.append(f"invalid migration filename: {path.name}")
            continue
        sequence = match.group("sequence")
        if sequence in sequences:
            issues.append(f"duplicate migration sequence: {sequence}")
        sequences.add(sequence)
    return issues


def baseline_issues(root: Path = ROOT) -> list[str]:
    """Verify byte-preserved baseline files against their approved hashes."""

    issues: list[str] = []
    for relative, expected in BASELINE_HASHES.items():
        path = root / relative
        if not path.is_file():
            issues.append(f"missing baseline: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if actual != expected:
            issues.append(f"baseline hash mismatch: {relative}: {actual}")
    return issues


def markdown_link_issues(paths: Iterable[Path], root: Path = ROOT) -> list[str]:
    """Validate repository-relative Markdown links without network access."""

    issues: list[str] = []
    for path in paths:
        if path.suffix.lower() != ".md":
            continue
        content = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_PATTERN.finditer(content):
            target = match.group(1).strip().strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_without_anchor = target.split("#", maxsplit=1)[0]
            if not target_without_anchor:
                continue
            resolved = (path.parent / target_without_anchor).resolve()
            if not resolved.exists():
                relative = path.relative_to(root).as_posix()
                issues.append(f"broken Markdown link: {relative} -> {target}")
    return issues


def main() -> int:
    """Run every deterministic repository check."""

    paths = repository_files()
    issues = [
        *secret_issues(paths),
        *migration_issues(ROOT / "migrations"),
        *baseline_issues(),
        *markdown_link_issues(paths),
    ]
    if issues:
        print("Repository checks failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(
        f"Repository checks passed: {len(paths)} present tracked/untracked files, "
        f"{len(BASELINE_HASHES)} baselines, migrations and Markdown links verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
