from pathlib import Path

from scripts.check_repo import migration_issues, secret_issues


def test_secret_check_rejects_private_environment_file(tmp_path: Path) -> None:
    environment = tmp_path / ".env"
    environment.write_text("SAFE=false\n", encoding="utf-8")

    assert secret_issues([environment], root=tmp_path) == ["forbidden sensitive filename: .env"]


def test_secret_check_rejects_token_shaped_assignment(tmp_path: Path) -> None:
    config = tmp_path / "config.txt"
    secret_fixture = "api_" + "key=" + ("x" * 32) + "\n"
    config.write_text(secret_fixture, encoding="utf-8")

    issues = secret_issues([config], root=tmp_path)

    assert len(issues) == 1
    assert issues[0].startswith("secret-like content matched in config.txt")


def test_migration_check_accepts_forward_names_and_rejects_duplicates(tmp_path: Path) -> None:
    (tmp_path / "0001_create_projects.sql").touch()
    (tmp_path / "0001_create_audit.py").touch()
    (tmp_path / "bad-name.sql").touch()

    assert migration_issues(tmp_path) == [
        "duplicate migration sequence: 0001",
        "invalid migration filename: bad-name.sql",
    ]
