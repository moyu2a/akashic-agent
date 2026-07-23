from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_source_ref_quality_cli_writes_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "report"
    fixture_db = tmp_path / "fixture" / "sessions.db"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_source_ref_quality_eval.py",
            "--output-dir",
            str(output_dir),
            "--fixture-db",
            str(fixture_db),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert fixture_db.exists()
    assert "source ref quality eval complete" in result.stdout
    payload = json.loads(
        (output_dir / "memory_source_ref_quality_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (output_dir / "memory_source_ref_quality_eval.md").read_text(
        encoding="utf-8"
    )

    assert payload["metadata"]["evaluation_mode"] == "synthetic_fixture_shadow"
    assert payload["metadata"]["production_uplift"] is False
    assert payload["metrics"]["normalized_fetch_success_rate"] > payload["metrics"]["baseline_fetch_success_rate"]
    assert payload["metrics"]["normalized_source_backed_eligible_rate"] > payload["metrics"]["baseline_source_backed_eligible_rate"]
    assert "shadow normalized_source_ref" in markdown
    assert "不是线上真实提升结论" in markdown


def test_source_ref_quality_cli_writes_expanded_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "expanded-report"
    fixture_db = tmp_path / "fixture" / "sessions.db"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_source_ref_quality_eval.py",
            "--output-dir",
            str(output_dir),
            "--fixture-db",
            str(fixture_db),
            "--case-pack",
            "expanded",
            "--common-per-scenario",
            "20",
            "--hard-per-scenario",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(
        (output_dir / "memory_source_ref_quality_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (output_dir / "memory_source_ref_quality_eval.md").read_text(
        encoding="utf-8"
    )

    assert payload["metadata"]["case_pack"] == "expanded"
    assert payload["metrics"]["candidate_count"] == 200
    assert payload["group_metrics"]["case_sets"]["common"]["candidate_count"] == 100
    assert payload["group_metrics"]["case_sets"]["hard"]["candidate_count"] == 100
    assert "Scenario Metrics" in markdown
    assert "source ref quality eval complete" in result.stdout


def test_source_ref_quality_cli_expanded_rejects_unmarked_session_db(
    tmp_path: Path,
) -> None:
    from session.store import SessionStore

    output_dir = tmp_path / "expanded-report"
    fixture_db = tmp_path / "sessions.db"
    store = SessionStore(fixture_db)
    try:
        store.create_session(key="telegram:123")
        store.insert_message(
            "telegram:123",
            role="user",
            content="CLI 不应该覆盖这个普通 sessions.db",
            ts="2026-07-22T00:00:00+08:00",
            seq=0,
        )
    finally:
        store.close()

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_source_ref_quality_eval.py",
            "--output-dir",
            str(output_dir),
            "--fixture-db",
            str(fixture_db),
            "--case-pack",
            "expanded",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "refusing to overwrite existing non-fixture session db" in result.stderr

    store = SessionStore(fixture_db)
    try:
        messages = store.fetch_session_messages("telegram:123")
    finally:
        store.close()
    assert [message["content"] for message in messages] == [
        "CLI 不应该覆盖这个普通 sessions.db"
    ]
