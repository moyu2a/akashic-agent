from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def build_system_path_failure_attribution(
    payload: dict[str, object],
    *,
    baseline_mode: str = "current",
    candidate_mode: str = "safe_version_replace",
) -> dict[str, object]:
    cases = [row for row in payload.get("cases", []) if isinstance(row, dict)]
    by_key: dict[tuple[str, int, str], dict[str, object]] = {}
    for row in cases:
        by_key[
            (
                str(row.get("case_id") or ""),
                int(row.get("repeat_index", 0) or 0),
                str(row.get("mode") or ""),
            )
        ] = dict(row)

    matrix: list[dict[str, object]] = []
    buckets: Counter[str] = Counter()
    movement: Counter[str] = Counter()
    keys = sorted({(case_id, repeat) for case_id, repeat, _mode in by_key})
    for case_id, repeat_index in keys:
        baseline = by_key.get((case_id, repeat_index, baseline_mode))
        candidate = by_key.get((case_id, repeat_index, candidate_mode))
        if baseline is None or candidate is None:
            movement["unpaired"] += 1
            continue

        base_answer = bool(baseline.get("answer_rule_passed"))
        cand_answer = bool(candidate.get("answer_rule_passed"))
        if base_answer and cand_answer:
            movement["baseline_passed_candidate_passed"] += 1
        elif (not base_answer) and cand_answer:
            movement["baseline_failed_candidate_passed"] += 1
        elif base_answer and not cand_answer:
            movement["baseline_passed_candidate_failed"] += 1
        else:
            movement["baseline_failed_candidate_failed"] += 1

        bucket = _candidate_failure_bucket(candidate)
        buckets[bucket] += 1
        matrix.append(
            {
                "case_id": case_id,
                "repeat_index": repeat_index,
                "category": str(
                    candidate.get("category") or baseline.get("category") or ""
                ),
                "baseline_answer_rule_passed": base_answer,
                "candidate_answer_rule_passed": cand_answer,
                "baseline_forbidden_violation": int(
                    baseline.get("forbidden_contains_violation_count", 0) or 0
                )
                > 0,
                "candidate_forbidden_violation": int(
                    candidate.get("forbidden_contains_violation_count", 0) or 0
                )
                > 0,
                "candidate_failure_bucket": bucket,
            }
        )

    metrics = {
        "evaluation_level": "system_path_failure_attribution",
        "failure_bucket_semantics": "sanitized_heuristic",
        "baseline_mode": baseline_mode,
        "candidate_mode": candidate_mode,
        "paired_run_count": len(matrix),
        "unpaired_run_count": int(movement["unpaired"]),
        "baseline_passed_candidate_passed_count": int(
            movement["baseline_passed_candidate_passed"]
        ),
        "baseline_failed_candidate_passed_count": int(
            movement["baseline_failed_candidate_passed"]
        ),
        "baseline_passed_candidate_failed_count": int(
            movement["baseline_passed_candidate_failed"]
        ),
        "baseline_failed_candidate_failed_count": int(
            movement["baseline_failed_candidate_failed"]
        ),
        "candidate_failure_bucket_counts": dict(sorted(buckets.items())),
        "raw_query_included": False,
        "prompt_included": False,
        "conversation_log_included": False,
        "complete_response_included": False,
        "memory_payload_included": False,
    }
    return {"metrics": metrics, "case_repeat_matrix": matrix}


def write_system_path_failure_attribution_json(
    report: dict[str, object],
    path: Path,
) -> None:
    _validate_private(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_system_path_failure_attribution_markdown(
    report: dict[str, object],
    path: Path,
) -> None:
    _validate_private(report)
    metrics = report["metrics"]
    assert isinstance(metrics, dict)
    lines = [
        "# System Path Failure Attribution",
        "",
        (
            "本报告只包含脱敏 case id、repeat id、pass/fail 和 heuristic "
            "failure bucket；不包含原始问题、提示词、记忆正文或完整回答。"
        ),
        "",
        f"- paired_run_count: `{metrics['paired_run_count']}`",
        f"- unpaired_run_count: `{metrics['unpaired_run_count']}`",
        f"- failure_bucket_semantics: `{metrics['failure_bucket_semantics']}`",
        "",
        "| bucket | count |",
        "| --- | ---: |",
    ]
    buckets = metrics.get("candidate_failure_bucket_counts", {})
    if isinstance(buckets, dict):
        for bucket, count in buckets.items():
            lines.append(f"| {bucket} | {count} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _candidate_failure_bucket(row: dict[str, object]) -> str:
    if bool(row.get("provider_error")):
        return "infra_provider_error"
    if bool(row.get("timeout")):
        return "infra_timeout"
    if not bool(row.get("memory_grounding_passed")):
        return "grounding_failure"
    if int(row.get("forbidden_contains_violation_count", 0) or 0) > 0:
        return "forbidden_answer_failure"
    failures = {str(item) for item in row.get("failures", []) if item}
    if "answer_language_not_chinese" in failures or row.get("language_passed") is False:
        return "language_failure"
    if int(row.get("expected_contains_miss_count", 0) or 0) > 0:
        return "answer_rule_miss_required_terms"
    if int(row.get("expected_any_miss_count", 0) or 0) > 0:
        return "answer_rule_miss_any_group"
    if bool(row.get("answer_rule_passed")):
        return "passed"
    if int(row.get("answer_length", 0) or 0) < 12:
        return "answer_too_short_or_generic"
    return "evidence_present_answer_missed"


def _validate_private(report: dict[str, object]) -> None:
    text = json.dumps(report, ensure_ascii=False)
    blocked = (
        "raw_prompt",
        "full_answer",
        "session_text",
        "memory_summary",
        "raw_memory_summary",
        "api_key",
        "Authorization",
    )
    found = [term for term in blocked if term in text]
    if found:
        raise ValueError(f"forbidden report content: {found}")
