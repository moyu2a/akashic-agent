from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_memory_quantitative_balanced_cli_writes_reports(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_quantitative_balanced_eval.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_quantitative_balanced_eval.json" in completed.stdout
    payload = json.loads(
        (tmp_path / "memory_quantitative_balanced_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (tmp_path / "memory_quantitative_balanced_eval.md").read_text(
        encoding="utf-8"
    )
    assert payload["metrics"]["measurement_mode"] == "offline_trace_quantitative_balanced"
    assert payload["metrics"]["case_count"] == 80
    first = payload["balanced_summaries"][0]
    assert "answer_score" in first
    assert "retrieval_proxy_score" in first
    assert "grounding_score" in first
    assert "governance_score" in first
    assert "efficiency_score" in first
    assert "balanced_score" in first
    assert "balanced_delta_points" in first
    assert "balanced_delta_pct" in first
    assert "balanced_score_available_dimensions" in first
    assert "unavailable_dimensions" in first
    assert "## 分层评分" in markdown
    assert "answer_score" in markdown
    assert "retrieval_proxy_score" in markdown
    assert "governance_score" in markdown
    assert "efficiency_score" in markdown
    assert "不是生产回答准确率" in markdown


def test_memory_quantitative_balanced_cli_handles_common_subset(
    tmp_path: Path,
) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_quantitative_balanced_eval.py",
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
        (tmp_path / "memory_quantitative_balanced_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (tmp_path / "memory_quantitative_balanced_eval.md").read_text(
        encoding="utf-8"
    )
    assert payload["metrics"]["common_case_count"] == 8
    assert payload["metrics"]["hard_case_count"] == 0
    assert payload["metrics"]["hard_final_balanced_score"] == "unavailable"
    assert "hard 0 个" in markdown


def test_memory_quantitative_balanced_cli_handles_hard_subset(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_quantitative_balanced_eval.py",
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
        (tmp_path / "memory_quantitative_balanced_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (tmp_path / "memory_quantitative_balanced_eval.md").read_text(
        encoding="utf-8"
    )
    assert payload["metrics"]["common_case_count"] == 0
    assert payload["metrics"]["hard_case_count"] == 8
    assert payload["metrics"]["common_final_balanced_score"] == "unavailable"
    assert "common 0 个" in markdown
