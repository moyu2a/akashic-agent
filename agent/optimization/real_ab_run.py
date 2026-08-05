from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

from agent.optimization.stage1_fake_run import DEFAULT_STAGE1_CASES, Stage1Case

__all__ = [
    "REAL_AB_PHASES",
    "RealABPhase",
    "RealABRecord",
    "RealABReport",
    "expected_fast_path_for_profile",
    "phase_profiles",
    "sanitize_preview",
    "select_cost_latency_cases",
    "select_real_ab_cases",
    "select_suite_cases",
    "summarize_real_ab_records",
    "write_real_ab_json",
    "write_real_ab_markdown",
]

_PREVIEW_MAX_CHARS = 240
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
)


@dataclass(frozen=True)
class RealABPhase:
    name: str
    profiles: tuple[str, ...]
    categories: tuple[str, ...]
    purpose: str


@dataclass(frozen=True)
class RealABRecord:
    run_id: str
    phase: str
    profile: str
    case_id: str
    category: str
    prompt_preview: str
    reply_preview: str
    correctness: str
    simple_fast_path: bool
    expected_fast_path: bool
    tool_error_count: int
    actual_prompt_tokens_sum: int | None
    actual_total_tokens_sum: int | None
    turn_duration_ms: int | None
    llm_duration_ms_sum: int | None
    react_iteration_count: int | None
    actual_tools: tuple[str, ...]
    expected_tools: tuple[str, ...]
    denied_tool_attempt_count: int
    unregistered_tool_count: int
    forbidden_reply_pattern_count: int
    expected_tool_missing_count: int
    note: str


@dataclass(frozen=True)
class RealABReport:
    metrics: dict[str, Any]
    profile_summaries: dict[str, dict[str, Any]]
    category_summaries: dict[str, dict[str, Any]]
    paired_deltas: dict[str, dict[str, Any]]
    records: list[RealABRecord]


REAL_AB_PHASES: dict[str, RealABPhase] = {
    "A": RealABPhase(
        name="A",
        profiles=("baseline", "simple_fast_path"),
        categories=("simple_no_tool", "tool_task", "memory_task", "proactive_task"),
        purpose="Validate simple_fast_path routing and correctness on mixed tasks.",
    ),
    "B": RealABPhase(
        name="B",
        profiles=("baseline", "combined_p1"),
        categories=("simple_no_tool", "tool_task", "memory_task", "proactive_task"),
        purpose="Validate combined_p1 against baseline after phase A passes.",
    ),
    "C": RealABPhase(
        name="C",
        profiles=("baseline", "context20"),
        categories=("memory_task",),
        purpose="Validate context20 against baseline on memory/history cases.",
    ),
    "D": RealABPhase(
        name="D",
        profiles=("baseline", "tool_result_limit"),
        categories=("tool_task",),
        purpose="Validate tool_result_limit against baseline on tool-oriented cases.",
    ),
}


def phase_profiles(phase: str) -> tuple[str, ...]:
    return _phase(phase).profiles


def expected_fast_path_for_profile(profile: str, case: Stage1Case) -> bool:
    return profile in {"simple_fast_path", "combined_p1"} and bool(
        case.expected_fast_path
    )


def select_real_ab_cases(phase: str) -> tuple[Stage1Case, ...]:
    spec = _phase(phase)
    return tuple(
        case for case in DEFAULT_STAGE1_CASES if case.category in spec.categories
    )


def select_cost_latency_cases(phase: str) -> tuple[Stage1Case, ...]:
    return tuple(case for case in select_real_ab_cases(phase) if case.allow_in_cost_latency)


def select_suite_cases(phase: str, suite: str) -> tuple[Stage1Case, ...]:
    name = str(suite or "").strip()
    if name == "cost_latency":
        return select_cost_latency_cases(phase)
    return tuple(case for case in select_real_ab_cases(phase) if case.suite == name)


def sanitize_preview(text: str, *, max_chars: int = _PREVIEW_MAX_CHARS) -> str:
    value = " ".join(str(text or "").split())
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(_redact_match, value)
    if len(value) > max_chars:
        return value[: max(0, max_chars - 3)] + "..."
    return value


def summarize_real_ab_records(records: Sequence[RealABRecord]) -> RealABReport:
    record_list = list(records)
    profiles = tuple(dict.fromkeys(record.profile for record in record_list))
    categories = tuple(dict.fromkeys(record.category for record in record_list))
    profile_summaries = {
        profile: _summarize_real_records(
            [record for record in record_list if record.profile == profile]
        )
        for profile in profiles
    }
    category_summaries = {
        category: _summarize_real_records(
            [record for record in record_list if record.category == category]
        )
        for category in categories
    }
    paired_deltas = _paired_deltas(record_list)
    gate_pass = bool(record_list) and all(_record_gate_pass(record) for record in record_list)
    metrics = {
        "mode": "real_llm",
        "real_llm": True,
        "turn_count": len(record_list),
        "profile_count": len(profiles),
        "case_count": len({record.case_id for record in record_list}),
        "gate_pass": gate_pass,
        "profiles": list(profiles),
        "categories": list(categories),
        "run_ids": list(dict.fromkeys(record.run_id for record in record_list)),
    }
    return RealABReport(
        metrics=metrics,
        profile_summaries=profile_summaries,
        category_summaries=category_summaries,
        paired_deltas=paired_deltas,
        records=record_list,
    )


def write_real_ab_json(report: RealABReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metrics": report.metrics,
        "profile_summaries": report.profile_summaries,
        "category_summaries": report.category_summaries,
        "paired_deltas": report.paired_deltas,
        "records": [asdict(record) for record in report.records],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_real_ab_markdown(report: RealABReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Optimization Real LLM Gated A/B",
        "",
        "本报告使用真实 LLM usage 字段记录 token 与时延；prompt/reply 仅保存脱敏预览。",
        "",
        "## Summary",
        "",
        f"- gate_pass: `{str(report.metrics['gate_pass']).lower()}`",
        f"- turns: `{report.metrics['turn_count']}`",
        f"- profiles: `{', '.join(report.metrics['profiles'])}`",
        f"- run_ids: `{', '.join(report.metrics['run_ids'])}`",
        "",
        "## Profile Summary",
        "",
        "| profile | turns | pass | warn | fail | missing/zero usage | unexpected fast path | expected tool missing | denied tools | unregistered tools | forbidden text | tool errors | avg prompt | avg total | avg turn |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for profile, row in report.profile_summaries.items():
        lines.append(
            "| {profile} | {turn_count} | {pass_count} | {warn_count} | "
            "{fail_count} | {missing_or_zero_usage_count} | "
            "{unexpected_fast_path_count} | {expected_tool_missing_count} | "
            "{denied_tool_attempt_count} | {unregistered_tool_count} | "
            "{forbidden_reply_pattern_count} | {tool_errors} | "
            "{avg_prompt_tokens} | {avg_total_tokens} | {avg_turn_ms}ms |".format(
                profile=profile, **row
            )
        )
    lines.extend(
        [
            "",
            "## Paired Delta",
            "",
            "| profile | paired cases | total token delta | turn latency delta |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for profile, row in report.paired_deltas.items():
        lines.append(
            "| {profile} | {paired_case_count} | {total_tokens_delta_pct}% | "
            "{turn_latency_delta_pct}% |".format(profile=profile, **row)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _phase(name: str) -> RealABPhase:
    key = name.strip().upper()
    try:
        return REAL_AB_PHASES[key]
    except KeyError as exc:
        raise ValueError(f"unknown real A/B phase: {name}") from exc


def _record_gate_pass(record: RealABRecord) -> bool:
    if record.correctness == "FAIL":
        return False
    if not _positive_int(record.actual_prompt_tokens_sum):
        return False
    if not _positive_int(record.actual_total_tokens_sum):
        return False
    if record.tool_error_count:
        return False
    if record.simple_fast_path != record.expected_fast_path:
        return False
    if record.expected_tool_missing_count:
        return False
    if record.denied_tool_attempt_count:
        return False
    if record.unregistered_tool_count:
        return False
    if record.forbidden_reply_pattern_count:
        return False
    return True


def _summarize_real_records(records: Sequence[RealABRecord]) -> dict[str, Any]:
    values = list(records)
    prompt_values = [
        int(record.actual_prompt_tokens_sum)
        for record in values
        if _positive_int(record.actual_prompt_tokens_sum)
    ]
    total_values = [
        int(record.actual_total_tokens_sum)
        for record in values
        if _positive_int(record.actual_total_tokens_sum)
    ]
    turn_values = [
        int(record.turn_duration_ms)
        for record in values
        if _positive_int(record.turn_duration_ms)
    ]
    return {
        "turn_count": len(values),
        "pass_count": sum(1 for record in values if record.correctness == "PASS"),
        "warn_count": sum(1 for record in values if record.correctness == "WARN"),
        "fail_count": sum(1 for record in values if record.correctness == "FAIL"),
        "missing_or_zero_usage_count": sum(
            1
            for record in values
            if not _positive_int(record.actual_prompt_tokens_sum)
            or not _positive_int(record.actual_total_tokens_sum)
        ),
        "unexpected_fast_path_count": sum(
            1
            for record in values
            if record.simple_fast_path != record.expected_fast_path
        ),
        "expected_tool_missing_count": sum(
            record.expected_tool_missing_count for record in values
        ),
        "denied_tool_attempt_count": sum(
            record.denied_tool_attempt_count for record in values
        ),
        "unregistered_tool_count": sum(record.unregistered_tool_count for record in values),
        "forbidden_reply_pattern_count": sum(
            record.forbidden_reply_pattern_count for record in values
        ),
        "tool_errors": sum(record.tool_error_count for record in values),
        "avg_prompt_tokens": round(mean(prompt_values), 1) if prompt_values else None,
        "avg_total_tokens": round(mean(total_values), 1) if total_values else None,
        "avg_turn_ms": round(mean(turn_values), 1) if turn_values else None,
    }


def _paired_deltas(records: Sequence[RealABRecord]) -> dict[str, dict[str, Any]]:
    baselines = {
        record.case_id: record
        for record in records
        if record.profile == "baseline" and _record_gate_pass(record)
    }
    profiles = tuple(
        profile for profile in dict.fromkeys(record.profile for record in records)
        if profile != "baseline"
    )
    result: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        pairs = [
            (baselines[record.case_id], record)
            for record in records
            if record.profile == profile
            and record.case_id in baselines
            and _record_gate_pass(record)
        ]
        result[profile] = {
            "paired_case_count": len(pairs),
            "total_tokens_delta_pct": _delta_pct(
                [base.actual_total_tokens_sum for base, _ in pairs],
                [candidate.actual_total_tokens_sum for _, candidate in pairs],
            ),
            "turn_latency_delta_pct": _delta_pct(
                [base.turn_duration_ms for base, _ in pairs],
                [candidate.turn_duration_ms for _, candidate in pairs],
            ),
        }
    return result


def _delta_pct(base_values: Sequence[int | None], candidate_values: Sequence[int | None]) -> float | None:
    base = [int(value) for value in base_values if _positive_int(value)]
    candidate = [int(value) for value in candidate_values if _positive_int(value)]
    if not base or not candidate or len(base) != len(candidate):
        return None
    base_sum = sum(base)
    if base_sum <= 0:
        return None
    return round(((sum(candidate) - base_sum) / base_sum) * 100, 2)


def _positive_int(value: int | None) -> bool:
    return isinstance(value, int) and value > 0


def _redact_match(match: re.Match[str]) -> str:
    if len(match.groups()) >= 2:
        return f"{match.group(1)}=[REDACTED]"
    return "[REDACTED]"
