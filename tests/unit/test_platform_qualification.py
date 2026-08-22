from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from scripts.platform_qualification import (
    DEFAULT_RECORD,
    QualificationError,
    load_record,
    main,
    select_branch,
    validate_record,
)


def current_payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(DEFAULT_RECORD.read_text(encoding="utf-8")))


def test_current_record_selects_safe_fallback(capsys: pytest.CaptureFixture[str]) -> None:
    record = load_record(DEFAULT_RECORD)

    assert select_branch(record) == "M5B"
    assert main([str(DEFAULT_RECORD)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "platform": "xiaohongshu",
        "probe_result": "NOT_RUN_NO_AUTHORIZED_SCOPE",
        "selected_branch": "M5B",
        "valid": True,
    }


def test_m5a_requires_every_grant_and_one_successful_probe() -> None:
    record = current_payload()
    evidence = cast(dict[str, object], record["account_evidence"])
    for field in (
        "test_account_evidenced",
        "developer_app_evidenced",
        "callback_domain_evidenced",
        "api_approval_evidenced",
        "explicit_probe_authorization_evidenced",
    ):
        evidence[field] = True
    evidence["exact_scopes"] = ["generic_note_publish"]
    probe = cast(dict[str, object], record["minimal_probe"])
    probe.update({"mode": "AUTHORIZED_OFFICIAL_API", "result": "PASS", "external_requests": 1})
    record["selected_branch"] = "M5A"

    assert select_branch(validate_record(record)) == "M5A"


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda record: cast(list[dict[str, object]], record["official_sources"])[0].update(
                {"url": "https://example.com/not-official"}
            ),
            "not an approved host",
        ),
        (
            lambda record: record.update({"selected_branch": "M5A"}),
            "selected_branch must be M5B",
        ),
        (
            lambda record: record.update({"access_token": "never-store-this"}),
            "forbidden sensitive field",
        ),
    ],
)
def test_invalid_or_overstated_records_fail_closed(
    mutator: Callable[[dict[str, object]], object], message: str
) -> None:
    record = copy.deepcopy(current_payload())
    mutator(record)

    with pytest.raises(QualificationError, match=message):
        validate_record(record)


def test_cli_reports_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")

    assert main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["valid"] is False
