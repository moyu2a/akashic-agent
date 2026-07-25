from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memory2.eval_real_candidates import CandidateEvalResult
from memory2.eval_real_samples import RealSampleSet
from memory2.eval_runner import EvalRunReport


def build_real_eval_summary(
    sample_set: RealSampleSet,
    report: EvalRunReport,
    candidate_result: CandidateEvalResult,
) -> dict[str, object]:
    category_counts: dict[str, int] = {}
    for sample in sample_set.samples:
        category_counts[sample.category] = category_counts.get(sample.category, 0) + 1
    summary: dict[str, object] = {
        "sample_count": len(sample_set.samples),
        "memory_item_count": sample_set.metrics.get("memory_item_count", 0),
        "replacement_count": sample_set.metrics.get("replacement_count", 0),
        "invalid_extra_json_count": sample_set.metrics.get("invalid_extra_json_count", 0),
        "missing_scope_count": sample_set.metrics.get("missing_scope_count", 0),
        "missing_table_count": sample_set.metrics.get("missing_table_count", 0),
        "cross_scope_sample_unavailable": sample_set.metrics.get(
            "cross_scope_sample_unavailable",
            0,
        ),
        "category_counts": category_counts,
        "phase6b_level": "real_sample_retrieval",
        "llm_calls_enabled": False,
        "answer_quality_available": False,
        "sensitive_text_included": False,
        "label_forced_recall": False,
    }
    for key in (
        "case_count",
        "profile_count",
        "passed_case_count",
        "failed_case_count",
        "failed_profile_count",
        "trace_count",
        "trace_count_by_feature",
        "profile_pass_rate",
    ):
        summary[key] = report.metrics.get(key, 0)
    summary["labelled_contract_pass_rate"] = report.metrics.get("profile_pass_rate", 0.0)
    summary["labelled_should_not_violation_count"] = _should_not_violation_count(report)
    for key, value in candidate_result.metrics.items():
        summary[key] = value
    summary["sample_records"] = _sample_records(sample_set)
    summary["profile_records"] = _profile_records(report)
    summary["candidate_records"] = list(candidate_result.sample_results)
    summary["failure_records"] = _failure_records(report)
    return summary


def write_real_eval_json(summary: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_real_eval_markdown(summary: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Memory Real Sample Evaluation Report",
        "",
        "本报告来自真实 memory 数据样本，但未调用 LLM，不代表最终回答质量。",
        "报告默认不包含真实 memory summary 或 session 原文。",
        "",
        "## Summary",
        "",
    ]
    for key in sorted(summary):
        value = summary[key]
        if isinstance(value, dict | list):
            lines.append(f"- `{key}`: `{json.dumps(value, ensure_ascii=False, sort_keys=True)}`")
        else:
            lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _sample_records(sample_set: RealSampleSet) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for sample in sample_set.samples:
        records.append(
            {
                "sample_id": sample.sample_id,
                "category": sample.category,
                "session_key": sample.session_key,
                "channel": sample.channel,
                "chat_id": sample.chat_id,
                "should_recall_ids": list(sample.should_recall_ids),
                "should_not_recall_ids": list(sample.should_not_recall_ids),
                "memory_ids": [
                    str(item.get("id") or "")
                    for item in sample.memory_items
                    if str(item.get("id") or "").strip()
                ],
                "replacement_edges": [
                    {
                        "old_item_id": str(edge.get("old_item_id") or ""),
                        "new_item_id": str(edge.get("new_item_id") or ""),
                        "relation_type": str(edge.get("relation_type") or ""),
                    }
                    for edge in sample.memory_replacements
                ],
            }
        )
    return records


def _profile_records(report: EvalRunReport) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for case in report.cases:
        for profile_name, profile in case.profiles.items():
            records.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "profile": profile_name,
                    "enabled": profile.enabled,
                    "passed": profile.passed,
                    "trace_features": list(profile.trace_features),
                    "recalled_ids": list(profile.recalled_ids),
                    "injected_ids": list(profile.injected_ids),
                    "metrics": profile.metrics,
                    "trace_metrics": {
                        name: trace.metrics
                        for name, trace in profile.traces.items()
                    },
                    "failures": list(profile.failures),
                }
            )
    return records


def _failure_records(report: EvalRunReport) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for case in report.cases:
        for failure in case.failures:
            records.append(
                {
                    "case_id": case.case_id,
                    "profile": "",
                    "failure": failure,
                }
            )
        for profile_name, profile in case.profiles.items():
            for failure in profile.failures:
                records.append(
                    {
                        "case_id": case.case_id,
                        "profile": profile_name,
                        "failure": failure,
                    }
                )
    return records


def _should_not_violation_count(report: EvalRunReport) -> int:
    count = 0
    for case in report.cases:
        for failure in case.failures:
            if "should not recall id" in failure or "was injected" in failure:
                count += 1
    return count
