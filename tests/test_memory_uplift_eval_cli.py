from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_memory_uplift_eval_cli_writes_reports(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_uplift_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--out-dir",
            str(out_dir),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_uplift_eval.json" in completed.stdout
    json_path = out_dir / "memory_uplift_eval.json"
    md_path = out_dir / "memory_uplift_eval.md"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["phase6c_level"] == "offline_uplift_proxy"
    assert payload["metrics"]["llm_calls_enabled"] is False
    assert payload["metrics"]["real_memory_db_enabled"] is False
    assert payload["metrics"]["case_count"] == 9
    assert "phase2" in payload["phase_summaries"]
    assert md_path.exists()


def test_memory_uplift_eval_cli_limit_is_deterministic(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_uplift_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--out-dir",
            str(out_dir),
            "--limit",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (out_dir / "memory_uplift_eval.json").read_text(encoding="utf-8")
    )
    assert payload["metrics"]["case_count"] == 2
