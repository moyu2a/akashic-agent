from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_memory_answer_retrieval_counts_cli_writes_answer_only_report(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_answer_retrieval_counts_eval.py",
            "--out-dir",
            str(tmp_path),
            "--limit",
            "50",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_answer_retrieval_counts_eval.json" in completed.stdout
    payload = json.loads(
        (tmp_path / "memory_answer_retrieval_counts_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (tmp_path / "memory_answer_retrieval_counts_eval.md").read_text(
        encoding="utf-8"
    )
    assert payload["metrics"]["measurement_mode"] == (
        "offline_answer_retrieval_count_eval"
    )
    assert payload["metrics"]["disabled_controls_excluded"] is True
    assert payload["metrics"]["write_governance_excluded"] is True
    assert payload["metrics"]["sleep_consolidation_excluded"] is True
    assert "write_value_only" not in markdown
    assert "sleep_only" not in markdown
    assert "main_score" not in markdown
    assert "## 单模块启动测试" in markdown
    assert "## 组合链路测试" in markdown
    assert "召回率提升百分点" in markdown
    assert "相邻召回率提升百分点" in markdown
