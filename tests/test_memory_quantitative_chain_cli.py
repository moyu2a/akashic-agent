from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_memory_quantitative_chain_cli_writes_reports(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_quantitative_chain_eval.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_quantitative_chain_eval.json" in completed.stdout
    assert "memory_quantitative_chain_eval.md" in completed.stdout
    json_path = tmp_path / "memory_quantitative_chain_eval.json"
    md_path = tmp_path / "memory_quantitative_chain_eval.md"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert payload["metrics"]["measurement_mode"] == "offline_trace_quantitative_chain"
    assert payload["metrics"]["case_count"] == 80
    assert payload["metrics"]["chain_step_count"] == 8
    overall = [
        row for row in payload["profile_summaries"] if row["case_set"] == "overall"
    ]
    assert [row["profile_name"] for row in overall] == [
        "chain_memory_base",
        "chain_write_value",
        "chain_tri_retrieval",
        "chain_graph_retrieval",
        "chain_rerank_injection",
        "chain_version_provenance",
        "chain_sleep_consolidation",
        "chain_all_on",
        "chain_off",
    ]
    assert overall[0]["uplift_points"] == 0.0
    assert overall[1]["uplift_points"] == round(
        overall[1]["main_score"] - overall[0]["main_score"],
        4,
    )
    assert "## 链路主要结果" in markdown
    assert "targets | success | miss | recall_rate" in markdown
    assert "不是单项分数相加" in markdown


def test_memory_quantitative_chain_cli_handles_common_subset(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_quantitative_chain_eval.py",
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
        (tmp_path / "memory_quantitative_chain_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (tmp_path / "memory_quantitative_chain_eval.md").read_text(
        encoding="utf-8"
    )
    assert payload["metrics"]["common_case_count"] == 8
    assert payload["metrics"]["hard_case_count"] == 0
    assert payload["metrics"]["hard_final_main_score"] == "unavailable"
    assert "hard 0 个" in markdown
