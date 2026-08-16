from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

GOVERNANCE_FAILURE_BUCKETS: tuple[str, ...] = (
    "retrieval_miss",
    "low_rank",
    "governance_drop",
    "missing_expected_answer_term",
    "missing_expected_answer_term_group",
    "found_forbidden_answer_term",
    "grounding_missing",
    "semantic_ambiguity",
    "needs_human_review",
    "provider_error",
    "timeout",
    "language_detection_noise",
    "infra_noise",
    "semantic_absurdity_dataset_gate",
)


def governance_failure_buckets(failures: list[str]) -> tuple[str, ...]:
    buckets: list[str] = []
    for failure in failures:
        bucket = _governance_failure_bucket(failure)
        if bucket not in buckets:
            buckets.append(bucket)
    return tuple(buckets)


def _governance_failure_bucket(failure: str) -> str:
    if failure in GOVERNANCE_FAILURE_BUCKETS:
        return failure
    if failure.startswith("missing expected answer term group"):
        return "missing_expected_answer_term_group"
    if failure.startswith("missing expected answer term"):
        return "missing_expected_answer_term"
    if failure.startswith("found forbidden answer term"):
        return "found_forbidden_answer_term"
    if failure.startswith("missing expected memory ids"):
        return "grounding_missing"
    if failure in {"provider_error", "timeout"}:
        return failure
    return "infra_noise" if "infra" in failure else "governance_drop"


BASELINE_PROFILE = "chain_memory_base"


@dataclass(frozen=True)
class OnlineFailureAttributionProfileRow:
    profile_name: str
    case_count: int
    answer_failure_count: int
    grounding_failure_count: int
    forbidden_failure_count: int
    grounded_but_answer_failed_count: int
    answer_pass_but_grounding_failed_count: int
    infra_failure_count: int
    avg_used_memory_id_count: float
    avg_total_token_count: float
    avg_latency_ms: float
    answer_failure_rate: float
    grounding_failure_rate: float
    forbidden_failure_rate: float
    baseline_answer_pass_profile_fail_count: int
    baseline_answer_fail_profile_pass_count: int
    forbidden_introduced_vs_baseline_count: int
    forbidden_removed_vs_baseline_count: int
    avg_token_delta_vs_baseline: float | None
    avg_latency_delta_vs_baseline: float | None
    failure_code_counts: dict[str, int]
    top_failure_examples: tuple[str, ...]
    primary_issue: str


@dataclass(frozen=True)
class OnlineFailureAttributionReport:
    case_count: int
    profile_rows: dict[str, OnlineFailureAttributionProfileRow]
    metrics: dict[str, object]


def build_online_failure_attribution_report(
    payload: Mapping[str, object],
) -> OnlineFailureAttributionReport:
    records = [
        row
        for row in payload.get("case_records", [])
        if isinstance(row, Mapping)
    ]
    return _build_report_from_records(
        records,
        source_metrics=payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else {},
    )


def build_online_failure_attribution_report_from_checkpoint_rows(
    rows: Sequence[Mapping[str, object]],
) -> OnlineFailureAttributionReport:
    records: list[Mapping[str, object]] = []
    for row in rows:
        result = row.get("result")
        if isinstance(result, Mapping):
            records.append(result)
    return _build_report_from_records(records, source_metrics={})


def write_online_failure_attribution_json(
    report: OnlineFailureAttributionReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_online_failure_attribution_markdown(
    report: OnlineFailureAttributionReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Online Failure Attribution",
        "",
        "本报告用于解释真实/线上回答质量评测中每个 profile 的失败类型，不重新评分历史 checkpoint。",
        "",
        "## Overview",
        "",
        f"- `case_record_count`: `{report.case_count}`",
        f"- `profile_count`: `{report.metrics.get('profile_count')}`",
        f"- `source_real_llm_enabled`: `{report.metrics.get('source_real_llm_enabled')}`",
        "",
        "## Profile Attribution",
        "",
        "| profile | cases | answer_fail | grounding_fail | forbidden_fail | grounded_but_answer_failed | answer_pass_but_grounding_failed | primary_issue | avg_token_delta_vs_base | avg_latency_delta_vs_base |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in report.profile_rows.values():
        lines.append(
            "| "
            + " | ".join(
                [
                    row.profile_name,
                    str(row.case_count),
                    str(row.answer_failure_count),
                    str(row.grounding_failure_count),
                    str(row.forbidden_failure_count),
                    str(row.grounded_but_answer_failed_count),
                    str(row.answer_pass_but_grounding_failed_count),
                    row.primary_issue,
                    _fmt_nullable(row.avg_token_delta_vs_baseline),
                    _fmt_nullable(row.avg_latency_delta_vs_baseline),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Failure Codes", ""])
    for row in report.profile_rows.values():
        if not row.failure_code_counts:
            continue
        codes = ", ".join(
            f"`{code}`={count}"
            for code, count in sorted(row.failure_code_counts.items())
        )
        lines.append(f"- `{row.profile_name}`: {codes}")
    lines.extend(["", "## Representative Failure Examples", ""])
    for row in report.profile_rows.values():
        if not row.top_failure_examples:
            continue
        examples = " ; ".join(f"`{item}`" for item in row.top_failure_examples)
        lines.append(f"- `{row.profile_name}`: {examples}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_report_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    source_metrics: Mapping[str, object],
) -> OnlineFailureAttributionReport:
    by_profile: dict[str, list[Mapping[str, object]]] = {}
    baseline_by_key: dict[tuple[str, str, int], Mapping[str, object]] = {}
    for row in records:
        profile = str(row.get("profile_name") or "unknown")
        by_profile.setdefault(profile, []).append(row)
        if profile == BASELINE_PROFILE:
            baseline_by_key[_case_key(row)] = row

    profile_rows = {
        profile: _build_profile_row(profile, rows, baseline_by_key)
        for profile, rows in sorted(by_profile.items())
    }
    metrics = {
        "case_record_count": len(records),
        "profile_count": len(profile_rows),
        "source_real_llm_enabled": source_metrics.get("real_llm_enabled"),
    }
    return OnlineFailureAttributionReport(
        case_count=len(records),
        profile_rows=profile_rows,
        metrics=metrics,
    )


def _build_profile_row(
    profile_name: str,
    rows: Sequence[Mapping[str, object]],
    baseline_by_key: Mapping[tuple[str, str, int], Mapping[str, object]],
) -> OnlineFailureAttributionProfileRow:
    count = len(rows)
    answer_failures = [
        row for row in rows if not _bool(row.get("answer_rule_passed"))
    ]
    grounding_failures = [
        row for row in rows if not _bool(row.get("memory_grounding_passed"))
    ]
    forbidden_failures = [
        row for row in rows if _int(row.get("forbidden_contains_violation_count")) > 0
    ]
    infra_failures = [
        row
        for row in rows
        if _bool(row.get("provider_error")) or _bool(row.get("timeout"))
    ]
    grounded_but_answer_failed = [
        row
        for row in rows
        if _bool(row.get("memory_grounding_passed"))
        and not _bool(row.get("answer_rule_passed"))
    ]
    answer_pass_but_grounding_failed = [
        row
        for row in rows
        if _bool(row.get("answer_rule_passed"))
        and not _bool(row.get("memory_grounding_passed"))
    ]
    paired = [
        (baseline_by_key[_case_key(row)], row)
        for row in rows
        if profile_name != BASELINE_PROFILE and _case_key(row) in baseline_by_key
    ]
    token_deltas = [
        _float(row.get("total_token_count")) - _float(base.get("total_token_count"))
        for base, row in paired
    ]
    latency_deltas = [
        _float(row.get("latency_ms")) - _float(base.get("latency_ms"))
        for base, row in paired
    ]
    failure_code_counts = _failure_code_counts(rows)
    return OnlineFailureAttributionProfileRow(
        profile_name=profile_name,
        case_count=count,
        answer_failure_count=len(answer_failures),
        grounding_failure_count=len(grounding_failures),
        forbidden_failure_count=len(forbidden_failures),
        grounded_but_answer_failed_count=len(grounded_but_answer_failed),
        answer_pass_but_grounding_failed_count=len(answer_pass_but_grounding_failed),
        infra_failure_count=len(infra_failures),
        avg_used_memory_id_count=_avg(_int(row.get("used_memory_id_count")) for row in rows),
        avg_total_token_count=_avg(_float(row.get("total_token_count")) for row in rows),
        avg_latency_ms=_avg(_float(row.get("latency_ms")) for row in rows),
        answer_failure_rate=_rate(len(answer_failures), count),
        grounding_failure_rate=_rate(len(grounding_failures), count),
        forbidden_failure_rate=_rate(len(forbidden_failures), count),
        baseline_answer_pass_profile_fail_count=sum(
            1
            for base, row in paired
            if _bool(base.get("answer_rule_passed"))
            and not _bool(row.get("answer_rule_passed"))
        ),
        baseline_answer_fail_profile_pass_count=sum(
            1
            for base, row in paired
            if not _bool(base.get("answer_rule_passed"))
            and _bool(row.get("answer_rule_passed"))
        ),
        forbidden_introduced_vs_baseline_count=sum(
            1
            for base, row in paired
            if _int(base.get("forbidden_contains_violation_count")) == 0
            and _int(row.get("forbidden_contains_violation_count")) > 0
        ),
        forbidden_removed_vs_baseline_count=sum(
            1
            for base, row in paired
            if _int(base.get("forbidden_contains_violation_count")) > 0
            and _int(row.get("forbidden_contains_violation_count")) == 0
        ),
        avg_token_delta_vs_baseline=_avg_or_none(token_deltas),
        avg_latency_delta_vs_baseline=_avg_or_none(latency_deltas),
        failure_code_counts=failure_code_counts,
        top_failure_examples=_top_failure_examples(rows),
        primary_issue=_primary_issue(
            infra_failure_count=len(infra_failures),
            grounded_but_answer_failed_count=len(grounded_but_answer_failed),
            answer_pass_but_grounding_failed_count=len(answer_pass_but_grounding_failed),
            grounding_failure_count=len(grounding_failures),
            answer_failure_count=len(answer_failures),
            forbidden_failure_count=len(forbidden_failures),
        ),
    )


def _primary_issue(
    *,
    infra_failure_count: int,
    grounded_but_answer_failed_count: int,
    answer_pass_but_grounding_failed_count: int,
    grounding_failure_count: int,
    answer_failure_count: int,
    forbidden_failure_count: int,
) -> str:
    if infra_failure_count > 0:
        return "infra_failure"
    if grounded_but_answer_failed_count > 0:
        return "grounded_but_answer_failed"
    if answer_pass_but_grounding_failed_count > 0:
        return "grounding_only_failure"
    if forbidden_failure_count > 0:
        return "forbidden_failure"
    if grounding_failure_count > 0:
        return "grounding_failure"
    if answer_failure_count > 0:
        return "answer_failure"
    return "none"


def _failure_code_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for failure in _iter_failures(rows):
        code = _failure_code(str(failure))
        counts[code] = counts.get(code, 0) + 1
    return counts


def _top_failure_examples(
    rows: Sequence[Mapping[str, object]],
    *,
    limit: int = 5,
) -> tuple[str, ...]:
    examples: list[str] = []
    seen: set[str] = set()
    for failure in _iter_failures(rows):
        text = str(failure)
        if text in seen:
            continue
        seen.add(text)
        examples.append(text)
        if len(examples) >= limit:
            break
    return tuple(examples)


def _iter_failures(rows: Sequence[Mapping[str, object]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        raw = row.get("failures")
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            failures.extend(str(item) for item in raw)
    return failures


def _failure_code(failure: str) -> str:
    known_prefixes = {
        "found forbidden answer term": "found_forbidden_answer_term",
        "missing expected memory ids": "missing_expected_memory_ids",
        "missing expected answer term group": "missing_expected_answer_term_group",
        "missing expected answer term": "missing_expected_answer_term",
    }
    for prefix, code in known_prefixes.items():
        if failure.startswith(prefix):
            return code
    code = re.sub(r"[^a-zA-Z0-9]+", "_", failure.strip().lower()).strip("_")
    return code or "unknown_failure"


def _case_key(row: Mapping[str, object]) -> tuple[str, str, int]:
    return (
        str(row.get("case_id") or ""),
        str(row.get("prompt_variant") or ""),
        _int(row.get("repeat_index")),
    )


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 4)


def _avg(values) -> float:
    collected = [float(value) for value in values]
    if not collected:
        return 0.0
    return round(sum(collected) / len(collected), 4)


def _avg_or_none(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _bool(value: object) -> bool:
    return bool(value)


def _int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_nullable(value: float | None) -> str:
    if value is None:
        return "N/A"
    return str(round(float(value), 4))
