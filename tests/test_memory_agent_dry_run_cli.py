from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_memory_agent_dry_run_cli_writes_reports(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_agent_dry_run_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--limit",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_agent_dry_run_eval.json" in completed.stdout
    payload = json.loads((out_dir / "memory_agent_dry_run_eval.json").read_text())
    assert payload["metrics"]["phase6b_level"] == "agent_dry_run"
    assert payload["metrics"]["case_count"] == 2
    assert payload["metrics"]["passed_case_count"] == 2
    assert (out_dir / "memory_agent_dry_run_eval.md").exists()


def test_memory_agent_dry_run_cli_returns_one_for_empty_cases(
    tmp_path: Path,
) -> None:
    case_root = tmp_path / "empty_cases"
    case_root.mkdir()
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_agent_dry_run_eval.py",
            "--case-root",
            str(case_root),
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    payload = json.loads((out_dir / "memory_agent_dry_run_eval.json").read_text())
    assert payload["metrics"]["case_count"] == 0
    assert (out_dir / "memory_agent_dry_run_eval.md").exists()
