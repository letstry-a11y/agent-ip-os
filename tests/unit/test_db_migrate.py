from pathlib import Path

import pytest

from scripts.db_migrate import MigrationError, load_migrations, resolve_database_url


def test_load_migrations_orders_files_and_hashes_bytes(tmp_path: Path) -> None:
    (tmp_path / "0002_second.sql").write_text("SELECT 2;\n", encoding="utf-8")
    (tmp_path / "0001_first.sql").write_text("SELECT 1;\n", encoding="utf-8")

    migrations = load_migrations(tmp_path)

    assert [migration.sequence for migration in migrations] == [1, 2]
    assert [migration.name for migration in migrations] == ["0001_first.sql", "0002_second.sql"]
    assert all(len(migration.checksum) == 64 for migration in migrations)


def test_load_migrations_rejects_invalid_and_duplicate_sequences(tmp_path: Path) -> None:
    (tmp_path / "bad-name.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(MigrationError, match="invalid SQL migration"):
        load_migrations(tmp_path)

    (tmp_path / "bad-name.sql").unlink()
    (tmp_path / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0001_second.sql").write_text("SELECT 2;", encoding="utf-8")
    with pytest.raises(MigrationError, match="duplicate migration sequence"):
        load_migrations(tmp_path)


def test_database_url_prefers_environment_and_fails_without_local_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")
    assert resolve_database_url() == "postgresql://configured"

    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setattr("scripts.db_migrate.LOCAL_ENV_FILE", tmp_path / "missing.env")
    with pytest.raises(MigrationError, match="credential file does not exist"):
        resolve_database_url()


def test_database_url_reads_ignored_local_password_without_printing_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    local_env = tmp_path / "compose.env"
    local_env.write_text("POSTGRES_PASSWORD=a/b+c\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_PORT", "15432")
    monkeypatch.setattr("scripts.db_migrate.LOCAL_ENV_FILE", local_env)

    assert resolve_database_url() == ("postgresql://agent_ip:a%2Fb%2Bc@127.0.0.1:15432/agent_ip")

    local_env.write_text("GARAGE_RPC_SECRET=placeholder\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="missing POSTGRES_PASSWORD"):
        resolve_database_url()
