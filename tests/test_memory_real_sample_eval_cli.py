from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.test_memory_eval_real_samples import _create_memory_db


def test_run_memory_real_sample_eval_cli_writes_reports(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "reports"
    _create_memory_db(workspace / "memory" / "memory2.db")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_real_sample_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--limit-per-category",
            "5",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_real_sample_eval.json" in completed.stdout
    payload = json.loads((out_dir / "memory_real_sample_eval.json").read_text())
    assert payload["sample_count"] >= 1
    assert (out_dir / "memory_real_sample_eval.md").exists()


def test_run_memory_real_sample_eval_cli_allows_explicit_zero_limit_dry_run(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "reports"
    _create_memory_db(workspace / "memory" / "memory2.db")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_real_sample_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--limit-per-category",
            "0",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    payload = json.loads((out_dir / "memory_real_sample_eval.json").read_text())
    assert payload["sample_count"] == 0
    assert payload["missing_table_count"] == 0
    assert (out_dir / "memory_real_sample_eval.md").exists()


def test_run_memory_real_sample_eval_cli_returns_one_for_missing_memory_db(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_real_sample_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--limit-per-category",
            "5",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    payload = json.loads((out_dir / "memory_real_sample_eval.json").read_text())
    assert payload["sample_count"] == 0
    assert payload["missing_table_count"] == 1
    assert (out_dir / "memory_real_sample_eval.md").exists()
