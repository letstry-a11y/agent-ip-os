"""Apply checksum-verified, forward-only PostgreSQL migrations."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"
LOCAL_ENV_FILE = ROOT / ".runtime" / "compose.env"
MIGRATION_PATTERN = re.compile(r"^(?P<sequence>\d{4})_[a-z0-9_]+\.sql$")


class MigrationError(RuntimeError):
    """Raised when migration history is invalid or cannot safely advance."""


@dataclass(frozen=True)
class Migration:
    """One immutable forward migration."""

    sequence: int
    name: str
    sql: str
    checksum: str


def load_migrations(directory: Path = MIGRATIONS_DIR) -> tuple[Migration, ...]:
    """Load ordered SQL migrations and reject unsupported files or duplicate sequences."""

    migrations: list[Migration] = []
    sequences: set[int] = set()
    for path in sorted(directory.iterdir()):
        if path.name == ".gitkeep":
            continue
        match = MIGRATION_PATTERN.fullmatch(path.name)
        if not path.is_file() or match is None:
            raise MigrationError(f"invalid SQL migration: {path.name}")
        sequence = int(match.group("sequence"))
        if sequence in sequences:
            raise MigrationError(f"duplicate migration sequence: {sequence:04d}")
        sequences.add(sequence)
        raw = path.read_bytes()
        migrations.append(
            Migration(
                sequence=sequence,
                name=path.name,
                sql=raw.decode("utf-8"),
                checksum=hashlib.sha256(raw).hexdigest(),
            )
        )
    return tuple(migrations)


def resolve_database_url() -> str:
    """Read a supplied URL or build the ignored local-Compose URL without logging it."""

    configured = os.environ.get("DATABASE_URL")
    if configured:
        return configured
    if not LOCAL_ENV_FILE.is_file():
        raise MigrationError(
            "DATABASE_URL is unset and the local Compose credential file does not exist; "
            "start the local stack or provide a test database URL"
        )
    values = dict(
        line.split("=", maxsplit=1)
        for line in LOCAL_ENV_FILE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    password = values.get("POSTGRES_PASSWORD")
    if not password:
        raise MigrationError("local Compose credential file is missing POSTGRES_PASSWORD")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    return f"postgresql://agent_ip:{quote(password, safe='')}@127.0.0.1:{port}/agent_ip"


def migrate(
    database_url: str,
    *,
    directory: Path = MIGRATIONS_DIR,
    target_sequence: int | None = None,
) -> tuple[str, ...]:
    """Apply unapplied migrations in independent transactions and return their names."""

    all_migrations = load_migrations(directory)
    known_migrations = {migration.sequence: migration for migration in all_migrations}
    migrations = all_migrations
    if target_sequence is not None:
        migrations = tuple(item for item in migrations if item.sequence <= target_sequence)
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("SELECT pg_advisory_lock(hashtext(%s))", ("agent-ip-os",))
        try:
            with connection.transaction():
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        sequence integer PRIMARY KEY CHECK (sequence > 0),
                        name text NOT NULL UNIQUE,
                        checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
                        applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                history = connection.execute(
                    "SELECT sequence, name, checksum FROM schema_migrations ORDER BY sequence"
                ).fetchall()
                for sequence, name, checksum in history:
                    expected = known_migrations.get(sequence)
                    if expected is None or (name, checksum) != (
                        expected.name,
                        expected.checksum,
                    ):
                        raise MigrationError(
                            f"migration history mismatch at sequence {sequence:04d}"
                        )
            for migration in migrations:
                with connection.transaction():
                    existing = connection.execute(
                        "SELECT name, checksum FROM schema_migrations WHERE sequence = %s",
                        (migration.sequence,),
                    ).fetchone()
                    if existing is not None:
                        continue
                    connection.execute(migration.sql)
                    connection.execute(
                        "INSERT INTO schema_migrations (sequence, name, checksum) "
                        "VALUES (%s, %s, %s)",
                        (migration.sequence, migration.name, migration.checksum),
                    )
                    applied.append(migration.name)
        finally:
            connection.execute("SELECT pg_advisory_unlock(hashtext(%s))", ("agent-ip-os",))
    return tuple(applied)


def main() -> int:
    """Apply all migrations to the configured database without exposing its URL."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    applied = migrate(resolve_database_url())
    if applied:
        print(f"Applied {len(applied)} forward migration(s): {', '.join(applied)}")
    else:
        print("Database schema is current; no migrations applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
