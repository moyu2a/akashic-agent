from __future__ import annotations

import json
from pathlib import Path

from memory2 import eval_layered_scoring as layered


def test_memory_layered_scoring_cli_writes_reports(tmp_path: Path) -> None:
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_layered_scoring_eval.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_layered_scoring_eval.json" in completed.stdout
    assert "memory_layered_scoring_eval.md" in completed.stdout
    payload = json.loads(
        (tmp_path / "memory_layered_scoring_eval.json").read_text(encoding="utf-8")
    )
    markdown = (tmp_path / "memory_layered_scoring_eval.md").read_text(encoding="utf-8")

    assert payload["metrics"]["measurement_mode"] == "offline_trace_layered_scoring"
    assert payload["metrics"]["case_count"] == 80
    assert payload["metrics"]["layer_count"] == 3
    assert "# 记忆系统三层评分评测报告" in markdown
    assert "## 总览" in markdown
    assert "写入治理评分" in markdown
    assert "记忆库卫生评分" in markdown


def test_memory_layered_scoring_cli_handles_common_subset(tmp_path: Path) -> None:
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_layered_scoring_eval.py",
            "--out-dir",
            str(tmp_path),
            "--case-set",
            "common",
            "--limit",
            "8",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "memory_layered_scoring_eval.json").read_text(encoding="utf-8")
    )
    markdown = (tmp_path / "memory_layered_scoring_eval.md").read_text(encoding="utf-8")

    assert payload["metrics"]["common_case_count"] == 8
    assert payload["metrics"]["hard_case_count"] == 0
    assert payload["metrics"]["hard_total_layered_score"] == "unavailable"
    assert "hard 0 个" in markdown


def test_memory_layered_scoring_cli_handles_hard_subset(tmp_path: Path) -> None:
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_layered_scoring_eval.py",
            "--out-dir",
            str(tmp_path),
            "--case-set",
            "hard",
            "--limit",
            "8",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "memory_layered_scoring_eval.json").read_text(encoding="utf-8")
    )
    assert payload["metrics"]["common_case_count"] == 0
    assert payload["metrics"]["hard_case_count"] == 8
    assert payload["metrics"]["common_total_layered_score"] == "unavailable"


def test_memory_layered_scoring_cli_cleans_up_on_failure(tmp_path: Path) -> None:
    out_dir = tmp_path / "failed_reports"

    original = layered.build_layered_scoring_report

    def boom(cases):  # type: ignore[no-untyped-def]
        raise RuntimeError("layered eval failed")

    layered.build_layered_scoring_report = boom  # type: ignore[assignment]
    try:
        exit_code = layered.main(["--out-dir", str(out_dir)])
    finally:
        layered.build_layered_scoring_report = original  # type: ignore[assignment]

    assert exit_code != 0
    assert not out_dir.exists() or not any(out_dir.iterdir())
