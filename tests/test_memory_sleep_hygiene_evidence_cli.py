from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_sleep_hygiene_evidence_cli_writes_reports(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_sleep_hygiene_evidence_eval.py",
            "--output-dir",
            str(output_dir),
            "--duplicate-groups",
            "3",
            "--stale-count",
            "4",
            "--low-value-count",
            "5",
            "--retained-count",
            "6",
            "--missing-source-count",
            "2",
            "--write-target-metrics",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    evidence_path = output_dir / "memory_sleep_hygiene_evidence.jsonl"
    summary_path = output_dir / "memory_sleep_hygiene_evidence_eval.json"
    summary_md_path = output_dir / "memory_sleep_hygiene_evidence_eval.md"
    target_json_path = output_dir / "memory_target_metric_sleep_hygiene.json"
    target_md_path = output_dir / "memory_target_metric_sleep_hygiene.md"

    assert evidence_path.exists()
    assert summary_path.exists()
    assert summary_md_path.exists()
    assert target_json_path.exists()
    assert target_md_path.exists()

    records = [
        json.loads(line)
        for line in evidence_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    target = json.loads(target_json_path.read_text(encoding="utf-8"))
    online_hygiene_rows = [
        row
        for row in target["memory_hygiene_rows"]
        if row["measurement_layer"] == "online_evidence"
    ]

    assert len(records) == 18
    assert summary["metrics"]["scanned_active_item_count"] == 21
    assert summary["metrics"]["evaluated_evidence_row_count"] == 18
    assert summary["metrics"]["duplicate_merge_rate"] == 100.0
    assert summary["metrics"]["false_positive_cleanup_rate"] == 0.0
    assert online_hygiene_rows


def test_sleep_hygiene_cli_supports_all_case_set_with_group_tables(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_sleep_hygiene_evidence_eval.py",
            "--output-dir",
            str(output_dir),
            "--case-set",
            "all",
            "--duplicate-groups",
            "3",
            "--stale-count",
            "4",
            "--low-value-count",
            "5",
            "--retained-count",
            "6",
            "--hard-per-scenario",
            "2",
            "--missing-source-count",
            "2",
            "--write-target-metrics",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(
        (output_dir / "memory_sleep_hygiene_evidence_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (output_dir / "memory_sleep_hygiene_evidence_eval.md").read_text(
        encoding="utf-8"
    )
    target = json.loads(
        (output_dir / "memory_target_metric_sleep_hygiene.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary["metrics"]["group_metrics"]["standard"]["case_count"] == 18
    assert summary["metrics"]["group_metrics"]["hard"]["case_count"] == 16
    assert summary["metrics"]["group_metrics"]["hard"]["evaluated_item_count"] > 16
    assert "standard / hard / overall" in markdown
    assert "candidate precision" in markdown
    online_rows = [
        row
        for row in target["memory_hygiene_rows"]
        if row["measurement_layer"] == "online_evidence"
    ]
    assert online_rows


def test_sleep_hygiene_cli_rejects_session_store_mode_without_db(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_sleep_hygiene_evidence_eval.py",
            "--output-dir",
            str(tmp_path / "reports"),
            "--source-fetch-mode",
            "session-store",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--session-db is required" in result.stderr


def test_sleep_hygiene_cli_can_run_source_backed_fixture_mode(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "reports"
    fixture_db = tmp_path / "fixture" / "sessions.db"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_sleep_hygiene_evidence_eval.py",
            "--output-dir",
            str(output_dir),
            "--source-fixture-mode",
            "balanced",
            "--source-fixture-db",
            str(fixture_db),
            "--write-dry-run-patch",
            "--write-target-metrics",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert fixture_db.exists()
    summary = json.loads(
        (output_dir / "memory_sleep_hygiene_evidence_eval.json").read_text(
            encoding="utf-8"
        )
    )
    source = summary["metrics"]["source_evidence_metrics"]

    assert source["source_fetch_mode"] == "session-store"
    assert source["source_fetch_success_rate"] < 100.0
    assert source["source_support_rate"] < 100.0
    assert source["missing_source_count"] > 0
    assert source["unsupported_source_count"] > 0
    assert "source evidence metrics" in (
        output_dir / "memory_sleep_hygiene_evidence_eval.md"
    ).read_text(encoding="utf-8")


def test_sleep_hygiene_cli_does_not_mark_non_fixture_session_store_as_fixture(
    tmp_path: Path,
) -> None:
    from session.store import SessionStore

    session_db = tmp_path / "sessions.db"
    store = SessionStore(session_db)
    store.create_session(key="cli:local")
    store.close()
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_sleep_hygiene_evidence_eval.py",
            "--output-dir",
            str(output_dir),
            "--duplicate-groups",
            "1",
            "--stale-count",
            "1",
            "--low-value-count",
            "1",
            "--retained-count",
            "1",
            "--source-fetch-mode",
            "session-store",
            "--session-db",
            str(session_db),
            "--write-target-metrics",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    target = json.loads(
        (output_dir / "memory_target_metric_sleep_hygiene.json").read_text(
            encoding="utf-8"
        )
    )
    online_hygiene_rows = [
        row
        for row in target["memory_hygiene_rows"]
        if row["measurement_layer"] == "online_evidence"
    ]
    assert online_hygiene_rows
    assert {
        row["checkpoint_source"] for row in online_hygiene_rows
    } == {"sleep_hygiene_session_store"}


def test_sleep_hygiene_cli_can_write_dry_run_patch(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_sleep_hygiene_evidence_eval.py",
            "--output-dir",
            str(output_dir),
            "--case-set",
            "hard",
            "--hard-per-scenario",
            "2",
            "--write-dry-run-patch",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    patch = json.loads(
        (output_dir / "memory_sleep_hygiene_dry_run_patch.json").read_text(
            encoding="utf-8"
        )
    )
    assert patch["applied_change_count"] == 0
    assert patch["would_remove_low_value"]
    assert patch["requires_review"]
