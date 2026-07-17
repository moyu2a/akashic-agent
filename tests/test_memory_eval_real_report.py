from __future__ import annotations

import json
from pathlib import Path

from memory2.eval_real_candidates import evaluate_unforced_candidates
from memory2.eval_real_report import (
    build_real_eval_summary,
    write_real_eval_json,
    write_real_eval_markdown,
)
from memory2.eval_real_samples import (
    collect_real_memory_samples,
    real_sample_to_eval_case,
)
from memory2.eval_runner import run_eval_cases
from tests.test_memory_eval_real_samples import _create_memory_db


def test_build_real_eval_summary_contains_quantitative_fields(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")
    sample_set = collect_real_memory_samples(workspace, limit_per_category=5)
    report = run_eval_cases([real_sample_to_eval_case(s) for s in sample_set.samples])
    candidate_result = evaluate_unforced_candidates(sample_set)

    summary = build_real_eval_summary(sample_set, report, candidate_result)

    assert summary["sample_count"] == len(sample_set.samples)
    assert summary["memory_item_count"] == 3
    assert summary["replacement_count"] == 1
    assert "profile_pass_rate" in summary
    assert summary["label_forced_recall"] is False
    assert "candidate_hit_rate_without_label_forcing" in summary
    assert "trace_count_by_feature" in summary
    assert "category_counts" in summary
    assert summary["sample_records"]
    assert summary["profile_records"]
    assert summary["candidate_records"]
    assert summary["failure_records"] == []
    sample_record = summary["sample_records"][0]
    assert "sample_id" in sample_record
    assert "session_key" in sample_record
    assert "memory_ids" in sample_record
    assert "query" not in sample_record


def test_real_eval_writers_emit_json_and_markdown(tmp_path: Path) -> None:
    summary = {
        "sample_count": 2,
        "memory_item_count": 3,
        "replacement_count": 1,
        "profile_pass_rate": 1.0,
        "category_counts": {"preference": 1, "procedure": 1},
        "trace_count_by_feature": {"tri_retrieval": 2},
        "label_forced_recall": False,
        "answer_quality_available": False,
        "sample_records": [
            {
                "sample_id": "real_preference_m_pref",
                "session_key": "cli:local",
                "memory_ids": ["m_pref"],
            }
        ],
    }
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    write_real_eval_json(summary, json_path)
    write_real_eval_markdown(summary, md_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["sample_count"] == 2
    text = md_path.read_text(encoding="utf-8")
    assert "# Memory Real Sample Evaluation Report" in text
    assert "profile_pass_rate" in text
    assert "本报告来自真实 memory 数据样本" in text


def test_real_eval_report_does_not_emit_raw_memory_text_by_default(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")
    sample_set = collect_real_memory_samples(workspace, limit_per_category=5)
    report = run_eval_cases([real_sample_to_eval_case(s) for s in sample_set.samples])
    candidate_result = evaluate_unforced_candidates(sample_set)
    summary = build_real_eval_summary(sample_set, report, candidate_result)
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    write_real_eval_json(summary, json_path)
    write_real_eval_markdown(summary, md_path)

    assert "用户偏好中文回答" not in json_path.read_text(encoding="utf-8")
    assert "用户偏好中文回答" not in md_path.read_text(encoding="utf-8")
