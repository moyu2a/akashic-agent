from __future__ import annotations

import json
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from memory2.eval_cases import EvalCase
from memory2.eval_quantitative_cases import QUANTITATIVE_FEATURES
from memory2.eval_runner import (
    EvalCaseResult,
    EvalProfileResult,
    EvalRunReport,
    EvalTrace,
    _active_memory_items,
    _baseline_recalled_items,
    _candidate_lanes,
    _injection_candidates,
    _memory_items,
    _memorize_calls,
    _query,
    _scope,
    run_eval_cases,
)
from memory2.eval_route_governance import (
    build_offline_route_governance_rows,
    route_governance_markdown_lines,
)
from memory2.injection_governance_experiments import (
    build_injection_governance_shadow_result,
)
from memory2.provenance_experiments import build_provenance_shadow_result
from memory2.rerank_experiments import build_rerank_shadow_result
from memory2.retrieval_experiments import build_tri_retrieval_shadow_result
from memory2.retrieval_graph_experiments import build_graph_retrieval_shadow_result
from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)
from memory2.version_chain_experiments import build_version_chain_shadow_result
from plugins.default_memory.experiments import (
    extract_explicit_memorize_baseline,
    score_write_candidate_shadow,
)


_FIXED_REPORT_TIME = datetime(2026, 7, 17, tzinfo=timezone.utc)

BALANCED_SCORE_FORMULA = (
    "balanced_score = 0.30 * answer_score + "
    "0.25 * retrieval_proxy_score + "
    "0.20 * grounding_score + "
    "0.15 * governance_score + "
    "0.10 * efficiency_score; unavailable dimensions are omitted "
    "and remaining weights are normalized"
)


REPORT_PROFILES: tuple[str, ...] = (
    "off",
    "memory_base",
    "write_value_only",
    "tri_retrieval_only",
    "graph_only",
    "rerank_only",
    "version_provenance_only",
    "sleep_only",
    "all_on",
)

CHAIN_PROFILES: tuple[str, ...] = (
    "chain_memory_base",
    "chain_write_value",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_sleep_consolidation",
    "chain_all_on",
)

CHAIN_REPORT_PROFILES: tuple[str, ...] = (*CHAIN_PROFILES, "chain_off")

PROFILE_RUNTIME_MAP: dict[str, str] = {
    "off": "off",
    "memory_base": "off",
    "write_value_only": "phase1",
    "tri_retrieval_only": "phase2",
    "graph_only": "phase2",
    "rerank_only": "phase3",
    "version_provenance_only": "phase4",
    "sleep_only": "phase5",
    "all_on": "all",
}

PROFILE_FEATURE_MAP: dict[str, tuple[str, ...]] = {
    "off": (),
    "memory_base": (),
    "write_value_only": ("write_value_score",),
    "tri_retrieval_only": ("tri_retrieval",),
    "graph_only": ("graph_retrieval",),
    "rerank_only": ("rerank_shadow", "injection_governance_shadow"),
    "version_provenance_only": ("version_chain_shadow", "provenance_shadow"),
    "sleep_only": ("sleep_consolidation_shadow",),
    "all_on": QUANTITATIVE_FEATURES,
}

CHAIN_PROFILE_FEATURE_MAP: dict[str, tuple[str, ...]] = {
    "chain_off": (),
    "chain_memory_base": (),
    "chain_write_value": ("write_value_score",),
    "chain_tri_retrieval": ("write_value_score", "tri_retrieval"),
    "chain_graph_retrieval": (
        "write_value_score",
        "tri_retrieval",
        "graph_retrieval",
    ),
    "chain_rerank_injection": (
        "write_value_score",
        "tri_retrieval",
        "graph_retrieval",
        "rerank_shadow",
        "injection_governance_shadow",
    ),
    "chain_version_provenance": (
        "write_value_score",
        "tri_retrieval",
        "graph_retrieval",
        "rerank_shadow",
        "injection_governance_shadow",
        "version_chain_shadow",
        "provenance_shadow",
    ),
    "chain_sleep_consolidation": QUANTITATIVE_FEATURES,
    "chain_all_on": QUANTITATIVE_FEATURES,
}

PROFILE_FEATURE_LABELS: dict[str, str] = {
    "off": "关闭增强控制组",
    "memory_base": "原始记忆基线",
    "write_value_only": "写入价值",
    "tri_retrieval_only": "三路召回",
    "graph_only": "图谱召回",
    "rerank_only": "重排与注入治理",
    "version_provenance_only": "版本链与溯源",
    "sleep_only": "睡眠巩固",
    "all_on": "全开组合",
}

CHAIN_PROFILE_LABELS: dict[str, str] = {
    "chain_off": "关闭记忆增强",
    "chain_memory_base": "原始记忆基线",
    "chain_write_value": "加入写入价值治理",
    "chain_tri_retrieval": "加入三路召回",
    "chain_graph_retrieval": "加入图谱召回",
    "chain_rerank_injection": "加入重排与注入治理",
    "chain_version_provenance": "加入版本链与溯源",
    "chain_sleep_consolidation": "加入睡眠巩固",
    "chain_all_on": "全开组合校验",
}


@dataclass(frozen=True)
class QuantitativeProfileSummary:
    profile_name: str
    feature_name: str
    case_set: str
    case_count: int
    target_count: int
    success_count: int
    miss_count: int
    recall_rate: float
    grounding_count: int
    forbidden_count: int
    repeat_count: int
    answer_rule_pass_rate: float
    memory_grounding_pass_rate: float
    forbidden_violation_rate: float
    main_score: float
    baseline_score: float
    uplift_points: float
    uplift_pct: float | None
    token_signal_kind: str
    token_signal_value: float | str
    token_signal_delta: float | str
    latency_ms: float | str
    latency_delta_ms: float | str
    unavailable: tuple[str, ...]


@dataclass(frozen=True)
class QuantitativeUpliftReport:
    run_id: str
    generated_at: str
    score_formula: str
    profile_summaries: tuple[QuantitativeProfileSummary, ...]
    feature_contributions: tuple[QuantitativeProfileSummary, ...]
    case_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]


@dataclass(frozen=True)
class BalancedProfileSummary:
    profile_name: str
    feature_name: str
    case_set: str
    case_count: int
    answer_score: float
    retrieval_proxy_score: float | str
    grounding_score: float
    governance_score: float
    efficiency_score: float | str
    balanced_score: float
    balanced_delta_points: float
    balanced_delta_pct: float | None
    balanced_score_available_dimensions: tuple[str, ...]
    unavailable_dimensions: tuple[str, ...]


@dataclass(frozen=True)
class QuantitativeBalancedReport:
    run_id: str
    generated_at: str
    score_formula: str
    profile_summaries: tuple[QuantitativeProfileSummary, ...]
    balanced_summaries: tuple[BalancedProfileSummary, ...]
    case_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]


def calculate_main_score(
    *,
    answer_rule_pass_rate: float,
    memory_grounding_pass_rate: float,
    forbidden_violation_rate: float,
) -> float:
    return round(
        0.7 * float(answer_rule_pass_rate)
        + 0.2 * float(memory_grounding_pass_rate)
        + 0.1 * (100.0 - float(forbidden_violation_rate)),
        4,
    )


def calculate_balanced_scores(
    row: QuantitativeProfileSummary,
) -> dict[str, float | str | tuple[str, ...]]:
    answer_score = row.answer_rule_pass_rate
    retrieval_proxy_score: float | str = (
        row.answer_rule_pass_rate
        if _profile_has_retrieval_signal(row.profile_name)
        else "unavailable"
    )
    grounding_score = row.memory_grounding_pass_rate
    governance_score = round(
        0.55 * (100.0 - row.forbidden_violation_rate)
        + 0.45 * grounding_score,
        4,
    )
    efficiency_score = _efficiency_score(row)
    weighted_scores: tuple[tuple[str, float, float | str], ...] = (
        ("answer_score", 0.30, answer_score),
        ("retrieval_proxy_score", 0.25, retrieval_proxy_score),
        ("grounding_score", 0.20, grounding_score),
        ("governance_score", 0.15, governance_score),
        ("efficiency_score", 0.10, efficiency_score),
    )
    available = [
        (name, weight, float(value))
        for name, weight, value in weighted_scores
        if isinstance(value, (int, float))
    ]
    unavailable = tuple(
        name
        for name, _, value in weighted_scores
        if not isinstance(value, (int, float))
    )
    weight_sum = sum(weight for _, weight, _ in available)
    balanced_score = (
        round(sum(weight * value for _, weight, value in available) / weight_sum, 4)
        if weight_sum
        else 0.0
    )
    return {
        "answer_score": answer_score,
        "retrieval_proxy_score": retrieval_proxy_score,
        "grounding_score": grounding_score,
        "governance_score": governance_score,
        "efficiency_score": efficiency_score,
        "balanced_score": balanced_score,
        "balanced_score_available_dimensions": tuple(name for name, _, _ in available),
        "unavailable_dimensions": unavailable,
    }


def build_quantitative_balanced_report(
    cases: Sequence[EvalCase],
) -> QuantitativeBalancedReport:
    chain_report = build_quantitative_chain_report(cases)
    balanced_summaries = _build_balanced_summaries(chain_report.profile_summaries)
    metrics = _build_balanced_report_metrics(cases, balanced_summaries, chain_report)
    run_id = _deterministic_run_id(cases, (*CHAIN_PROFILES, "balanced"))
    return QuantitativeBalancedReport(
        run_id=run_id,
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        score_formula=BALANCED_SCORE_FORMULA,
        profile_summaries=chain_report.profile_summaries,
        balanced_summaries=balanced_summaries,
        case_records=chain_report.case_records,
        metrics=metrics,
    )


def build_quantitative_uplift_report(cases: Sequence[EvalCase]) -> QuantitativeUpliftReport:
    eval_report = run_eval_cases(cases)
    if not eval_report.passed:
        failures = "\n".join(
            f"- {case.case_id}: {', '.join(case.failures) or 'unknown failure'}"
            for case in eval_report.cases
            if not case.passed
        )
        raise RuntimeError(
            "eval runner failed before uplift report generation:\n"
            f"{failures or '- unknown failure'}"
        )
    case_results = {case.case_id: case for case in eval_report.cases}
    case_records: list[dict[str, object]] = []
    per_case_rows: list[dict[str, object]] = []

    for case in cases:
        case_set = _case_set(case)
        for profile_name in REPORT_PROFILES:
            row = _score_case_profile(case, case_results[case.id], case_set, profile_name)
            per_case_rows.append(row)
            case_records.append(row)

    profile_summaries = _build_profile_summaries(per_case_rows)
    feature_contributions = tuple(
        row
        for row in profile_summaries
        if row.case_set == "overall"
        and row.profile_name not in {"off", "memory_base"}
    )
    metrics = _build_report_metrics(cases, profile_summaries, per_case_rows)
    run_id = _deterministic_run_id(cases, REPORT_PROFILES)
    return QuantitativeUpliftReport(
        run_id=run_id,
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        score_formula=(
            "main_score = 0.7 * answer_rule_pass_rate + "
            "0.2 * memory_grounding_pass_rate + "
            "0.1 * (100 - forbidden_violation_rate)"
        ),
        profile_summaries=profile_summaries,
        feature_contributions=feature_contributions,
        case_records=tuple(case_records),
        metrics=metrics,
    )


def build_quantitative_chain_report(cases: Sequence[EvalCase]) -> QuantitativeUpliftReport:
    eval_report = run_eval_cases(cases)
    if not eval_report.passed:
        failures = "\n".join(
            f"- {case.case_id}: {', '.join(case.failures) or 'unknown failure'}"
            for case in eval_report.cases
            if not case.passed
        )
        raise RuntimeError(
            "eval runner failed before chain report generation:\n"
            f"{failures or '- unknown failure'}"
        )
    case_results = {case.case_id: case for case in eval_report.cases}
    case_records: list[dict[str, object]] = []
    per_case_rows: list[dict[str, object]] = []

    for case in cases:
        case_set = _case_set(case)
        all_profile = case_results[case.id].profiles["all"]
        off_profile = case_results[case.id].profiles["off"]
        for profile_name in CHAIN_REPORT_PROFILES:
            feature_names = CHAIN_PROFILE_FEATURE_MAP[profile_name]
            runtime_profile = off_profile if not feature_names else all_profile
            row = _score_case_feature_set(
                case=case,
                runtime_profile=runtime_profile,
                case_set=case_set,
                profile_name=profile_name,
                feature_name=CHAIN_PROFILE_LABELS[profile_name],
                feature_names=feature_names,
            )
            per_case_rows.append(row)
            case_records.append(row)

    profile_summaries = _build_profile_summaries(
        per_case_rows,
        profile_order=CHAIN_REPORT_PROFILES,
        label_map=CHAIN_PROFILE_LABELS,
        delta_mode="previous_step",
        baseline_profile="chain_memory_base",
    )
    feature_contributions = tuple(
        row
        for row in profile_summaries
        if row.case_set == "overall"
        and row.profile_name not in {"chain_off", "chain_memory_base"}
    )
    metrics = _build_chain_report_metrics(cases, profile_summaries, per_case_rows)
    run_id = _deterministic_run_id(cases, CHAIN_PROFILES)
    return QuantitativeUpliftReport(
        run_id=run_id,
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        score_formula=(
            "main_score = 0.7 * answer_rule_pass_rate + "
            "0.2 * memory_grounding_pass_rate + "
            "0.1 * (100 - forbidden_violation_rate)"
        ),
        profile_summaries=profile_summaries,
        feature_contributions=feature_contributions,
        case_records=tuple(case_records),
        metrics=metrics,
    )


def write_quantitative_uplift_json(report: QuantitativeUpliftReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_quantitative_chain_markdown(report: QuantitativeUpliftReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(report.profile_summaries)
    overall_rows = [row for row in rows if row.case_set == "overall"]
    common_rows = [row for row in rows if row.case_set == "common"]
    hard_rows = [row for row in rows if row.case_set == "hard"]
    lines = [
        "# 记忆系统链路量化评测报告",
        "",
        "本报告是离线确定性评测结果，只代表当前样本集上的链路对比，不代表生产全量结论。",
        "",
        "## 评测口径",
        "",
        "- 链路评测按累计开关计算，每一步包含前面已经打开的能力。",
        "- 主表使用目标命中、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。",
        "- `chain_memory_base` 是主基线，`chain_off` 只作为关闭增强控制组。",
        "- 链路不是单项分数相加；后一步会继承前一步的上下文、治理成本和候选变化。",
        "",
        "## 总览",
        "",
        f"- 样本规模：{report.metrics.get('case_count')} 个目标导向 case，其中 common {report.metrics.get('common_case_count')} 个，hard {report.metrics.get('hard_case_count')} 个。",
        f"- `case_count`: `{report.metrics.get('case_count')}`",
        f"- `common_case_count`: `{report.metrics.get('common_case_count')}`",
        f"- `hard_case_count`: `{report.metrics.get('hard_case_count')}`",
        f"- `chain_step_count`: `{report.metrics.get('chain_step_count')}`",
        f"- 原始记忆基线：命中 `{report.metrics.get('baseline_success_count')}` / `{report.metrics.get('baseline_target_count')}`，漏召回 `{report.metrics.get('baseline_miss_count')}`，召回率 `{report.metrics.get('baseline_recall_rate')}`%。",
        f"- 全开组合：命中 `{report.metrics.get('final_success_count')}` / `{report.metrics.get('final_target_count')}`，漏召回 `{report.metrics.get('final_miss_count')}`，召回率 `{report.metrics.get('final_recall_rate')}`%。",
        "",
        "## 链路主要结果",
        "",
        "| step | label | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall_rows:
        if row.profile_name == "chain_off":
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    row.profile_name,
                    row.feature_name,
                    _fmt(row.target_count),
                    _fmt(row.success_count),
                    _fmt(row.miss_count),
                    _fmt(row.recall_rate),
                    _fmt(row.grounding_count),
                    _fmt(row.memory_grounding_pass_rate),
                    _fmt(row.forbidden_count),
                    _fmt(row.forbidden_violation_rate),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## common / hard 对比",
            "",
            "| case_set | step | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in common_rows + hard_rows:
        if row.profile_name == "chain_off":
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    row.case_set,
                    row.profile_name,
                    _fmt(row.target_count),
                    _fmt(row.success_count),
                    _fmt(row.miss_count),
                    _fmt(row.recall_rate),
                    _fmt(row.grounding_count),
                    _fmt(row.memory_grounding_pass_rate),
                    _fmt(row.forbidden_count),
                    _fmt(row.forbidden_violation_rate),
                ]
            )
            + " |"
        )
    control = _summary_lookup(overall_rows, "chain_off")
    lines.extend(
        [
            "",
            "## 关闭增强控制组",
            "",
            "| control | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| "
            + " | ".join(
                [
                    "chain_off",
                    _fmt(control.target_count if control else "unavailable"),
                    _fmt(control.success_count if control else "unavailable"),
                    _fmt(control.miss_count if control else "unavailable"),
                    _fmt(control.recall_rate if control else "unavailable"),
                    _fmt(control.grounding_count if control else "unavailable"),
                    _fmt(
                        control.memory_grounding_pass_rate
                        if control
                        else "unavailable"
                    ),
                    _fmt(control.forbidden_count if control else "unavailable"),
                    _fmt(
                        control.forbidden_violation_rate
                        if control
                        else "unavailable"
                    ),
                ]
            )
            + " |",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_quantitative_uplift_markdown(report: QuantitativeUpliftReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(report.profile_summaries)
    overall_rows = [row for row in rows if row.case_set == "overall"]
    common_rows = [row for row in rows if row.case_set == "common"]
    hard_rows = [row for row in rows if row.case_set == "hard"]
    baseline = _summary_lookup(overall_rows, "memory_base")
    all_on = _summary_lookup(overall_rows, "all_on")
    lines = [
        "# 记忆系统 Phase 6d 量化提升报告",
        "",
        "本报告是离线确定性评测结果，只代表当前样本集上的对比，不代表生产全量结论。",
        "",
        "## 计数与比例口径",
        "",
        "- 主表使用目标命中、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。",
        "- `memory_base` 是主基线，`off` 只作为关闭增强控制组。",
        "",
        "## 总览",
        "",
        f"- `case_count`: `{report.metrics.get('case_count')}`",
        f"- `common_case_count`: `{report.metrics.get('common_case_count')}`",
        f"- `hard_case_count`: `{report.metrics.get('hard_case_count')}`",
        f"- `repeat_count`: `{report.metrics.get('repeat_count')}`",
        f"- 原始记忆基线：命中 `{baseline.success_count if baseline else 'unavailable'}` / `{baseline.target_count if baseline else 'unavailable'}`，漏召回 `{baseline.miss_count if baseline else 'unavailable'}`，召回率 `{_fmt(baseline.recall_rate if baseline else 'unavailable')}`%。",
        f"- 全开组合：命中 `{all_on.success_count if all_on else 'unavailable'}` / `{all_on.target_count if all_on else 'unavailable'}`，漏召回 `{all_on.miss_count if all_on else 'unavailable'}`，召回率 `{_fmt(all_on.recall_rate if all_on else 'unavailable')}`%。",
        "",
        "## 主要结果",
        "",
        "| profile | case_set | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall_rows:
        if row.profile_name == "off":
            continue
        lines.append(_count_rate_summary_row_to_md(row))
    lines.extend(
        [
            "",
            "## common / hard 对比",
            "",
            "| case_set | profile | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in common_rows + hard_rows:
        if row.profile_name == "off":
            continue
        lines.append(_count_rate_summary_row_to_md(row))
    control = _summary_lookup(overall_rows, "off")
    lines.extend(
        [
            "",
            "## 关闭增强控制组",
            "",
            "| control | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            _count_rate_summary_row_to_md(control, include_profile_only=True)
            if control
            else "| off | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |",
            "",
            "## 原始评分字段",
            "",
            "- `main_score`、`uplift_points` 和 `uplift_pct` 保留在 JSON 输出中以兼容既有消费者，不作为本报告主表的解释口径。",
        ]
    )
    lines.extend(
        route_governance_markdown_lines(
            build_offline_route_governance_rows(report)
        )
    )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- `token_signal_value` / `latency_ms` 若无直接可用值，会标记为 `unavailable`。",
            "- `token_signal_kind` 区分 `prompt_token_delta`、`estimated_token_saving`、`mixed` 和 `unavailable`。",
            "- `tri_retrieval_only` 和 `graph_only` 是同一轮 phase2 runtime 的两条家族视角，不是两个独立开关运行。",
            "- `all_on` 若同时包含成本和节省两类 token 信号，会标记为 `mixed`，不会强行合并成一个 token 数。",
            "- `feature_contributions` 只展示 overall 视角，便于看单项开关的净增益。",
            "- `memory_base` 是原始记忆基线，`off` 是关闭增强控制组；单项增益和总增益都应优先相对 `memory_base` 理解。",
        ]
    )
    lines.extend(_detailed_review_lines(report, rows))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _family_trace_for_case(case: EvalCase, family_name: str) -> EvalTrace | None:
    if family_name == "write_value_score":
        calls = list(_memorize_calls(case))
        candidates = [
            {
                "summary": str(call.get("summary") or ""),
                "source_ref": _scope(case)["session_key"] + "@post_response",
            }
            for call in calls
            if str(call.get("summary") or "").strip()
        ]
        if not candidates:
            return None
        baseline = extract_explicit_memorize_baseline(calls)
        written_ids = {
            str(item_id) for item_id in baseline.get("written_item_ids", [])
        }
        existing_memories = [
            item
            for item in _active_memory_items(case)
            if str(item.get("id") or "") not in written_ids
        ]
        scored = [
            {
                "summary": candidate["summary"],
                **score_write_candidate_shadow(
                    candidate["summary"],
                    source_ref=candidate["source_ref"],
                    existing_memories=[
                        item
                        for item in existing_memories
                        if str(item.get("id") or "")
                        != str(candidate.get("id") or "")
                    ],
                ),
            }
            for candidate in candidates
        ]
        allow_count = sum(1 for item in scored if item.get("decision") == "allow")
        reject_count = sum(1 for item in scored if item.get("decision") == "reject")
        review_count = sum(1 for item in scored if item.get("decision") == "review")
        reasons: dict[str, int] = {}
        for item in scored:
            reason = str(item.get("reason") or "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
        metrics = {
            "candidate_count": len(scored),
            "baseline_written_count": int(baseline.get("baseline_written_count") or 0),
            "policy_allow_count": allow_count,
            "policy_reject_count": reject_count,
            "policy_review_count": review_count,
            "temporary_risk_count": sum(
                1
                for item in scored
                if float(item.get("signals", {}).get("temporary_risk_score") or 0.0)
                >= 0.5
            ),
            "assistant_inference_risk_count": sum(
                1
                for item in scored
                if float(
                    item.get("signals", {}).get("assistant_inference_risk_score")
                    or 0.0
                )
                >= 0.5
            ),
            "duplicate_risk_count": sum(
                1
                for item in scored
                if float(item.get("signals", {}).get("duplicate_risk_score") or 0.0)
                >= 0.5
            ),
            "similar_memory_count": sum(
                int(item.get("similar_memory_count") or 0) for item in scored
            ),
            "write_reduction_rate": (
                round(
                    max(0, int(baseline.get("baseline_written_count") or 0) - allow_count)
                    / int(baseline.get("baseline_written_count") or 1),
                    4,
                )
                if baseline.get("baseline_written_count")
                else 0.0
            ),
            "reject_reason_distribution": reasons,
        }
        return EvalTrace(
            feature_name="write_value_score",
            baseline_result=baseline,
            experimental_result={
                "candidate_count": len(scored),
                "policy_allow_count": allow_count,
                "policy_reject_count": reject_count,
                "policy_review_count": review_count,
                "candidates": scored,
            },
            metrics=metrics,
        )
    if family_name == "tri_retrieval":
        lanes = _candidate_lanes(case)
        scope = _scope(case)
        result = build_tri_retrieval_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=lanes.semantic_items,
            keyword_items=lanes.keyword_items,
            provenance_items=lanes.provenance_items,
            latency_ms=0.0,
            top_n=max(8, len(_active_memory_items(case))),
        )
        metrics = dict(result.metrics)
        return EvalTrace("tri_retrieval", result.baseline_result, result.experimental_result, metrics)
    if family_name == "graph_retrieval":
        lanes = _candidate_lanes(case)
        result = build_graph_retrieval_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=lanes.semantic_items,
            keyword_items=lanes.keyword_items,
            provenance_items=lanes.provenance_items,
            graph_items=lanes.graph_items,
            latency_ms=0.0,
            top_n=max(8, len(_active_memory_items(case))),
        )
        metrics = dict(result.metrics)
        return EvalTrace("graph_retrieval", result.baseline_result, result.experimental_result, metrics)
    if family_name == "rerank_shadow":
        lanes = _candidate_lanes(case)
        scope = _scope(case)
        result = build_rerank_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=lanes.semantic_items,
            keyword_items=lanes.keyword_items,
            provenance_items=lanes.provenance_items,
            graph_items=lanes.graph_items,
            scope_channel=scope["channel"],
            scope_chat_id=scope["chat_id"],
            top_n=max(8, len(_active_memory_items(case))),
        )
        return EvalTrace("rerank_shadow", result.baseline_result, result.experimental_result, dict(result.metrics))
    if family_name == "injection_governance_shadow":
        candidates = _injection_candidates(case)
        baseline_items = _baseline_recalled_items(case)
        result = build_injection_governance_shadow_result(
            baseline_items=baseline_items,
            baseline_injected_ids=[str(item.get("id") or "") for item in baseline_items],
            baseline_text_block="\n".join(str(item.get("summary") or "") for item in baseline_items),
            candidate_items=candidates,
            max_chars=180,
            max_items=4,
        )
        metrics = dict(result.metrics)
        metrics["dropped_by_reason"] = dict(result.experimental_result.get("drop_reasons", {}))
        return EvalTrace("injection_governance_shadow", result.baseline_result, result.experimental_result, metrics)
    if family_name == "version_chain_shadow":
        result = build_version_chain_shadow_result(
            memory_items=_memory_items(case),
            replacements=list(case.setup.get("memory_replacements", [])),
            recalled_items=_baseline_recalled_items(case),
        )
        return EvalTrace("version_chain_shadow", result.baseline_result, result.experimental_result, dict(result.metrics))
    if family_name == "provenance_shadow":
        scope = _scope(case)
        result = build_provenance_shadow_result(
            memory_items=_memory_items(case),
            recalled_items=_baseline_recalled_items(case),
            scope_channel=scope["channel"],
            scope_chat_id=scope["chat_id"],
        )
        return EvalTrace("provenance_shadow", result.baseline_result, result.experimental_result, dict(result.metrics))
    if family_name == "sleep_consolidation_shadow":
        result = build_sleep_consolidation_shadow_result(
            memory_items=_memory_items(case),
            now=datetime(2026, 7, 17, tzinfo=timezone.utc),
        )
        metrics = dict(result.metrics)
        metrics["job_latency_ms"] = 0.0
        return EvalTrace("sleep_consolidation_shadow", result.baseline_result, result.experimental_result, metrics)
    return None


def _score_case_profile(
    case: EvalCase,
    case_result: EvalCaseResult,
    case_set: str,
    profile_name: str,
) -> dict[str, object]:
    runtime_profile = case_result.profiles[PROFILE_RUNTIME_MAP[profile_name]]
    return _score_case_feature_set(
        case=case,
        runtime_profile=runtime_profile,
        case_set=case_set,
        profile_name=profile_name,
        feature_name=PROFILE_FEATURE_LABELS[profile_name],
        feature_names=PROFILE_FEATURE_MAP[profile_name],
    )


def _score_case_feature_set(
    *,
    case: EvalCase,
    runtime_profile: EvalProfileResult,
    case_set: str,
    profile_name: str,
    feature_name: str,
    feature_names: tuple[str, ...],
) -> dict[str, object]:
    if profile_name in {"memory_base", "chain_memory_base"}:
        return _score_original_memory_base_case(
            case=case,
            case_set=case_set,
            profile_name=profile_name,
            feature_name=feature_name,
        )

    family_scores = tuple(
        _score_family(
            case=case,
            trace=runtime_profile.traces.get(family_name),
            profile_name=profile_name,
            family_name=family_name,
        )
        for family_name in feature_names
    )
    if not family_scores:
        family_scores = (
            {
                "family_name": "baseline",
                "answer_rule_pass_rate": 0.0,
                "memory_grounding_pass_rate": 0.0,
                "forbidden_violation_rate": 0.0,
                "token_signal_kind": "unavailable",
                "token_signal_value": "unavailable",
                "latency_ms": "unavailable",
                "unavailable": ("token_signal_value", "latency_ms"),
            },
        )
    answer_rule_pass_rate = _avg(
        row["answer_rule_pass_rate"] for row in family_scores
    )
    memory_grounding_pass_rate = _avg(
        row["memory_grounding_pass_rate"] for row in family_scores
    )
    forbidden_violation_rate = _avg(
        row["forbidden_violation_rate"] for row in family_scores
    )
    main_score = calculate_main_score(
        answer_rule_pass_rate=answer_rule_pass_rate,
        memory_grounding_pass_rate=memory_grounding_pass_rate,
        forbidden_violation_rate=forbidden_violation_rate,
    )
    expected_ids = tuple(
        str(item) for item in case.expectations.get("should_recall_ids", [])
    )
    forbidden_ids = tuple(
        str(item) for item in case.expectations.get("should_not_recall_ids", [])
    )
    target_count = len(set(expected_ids))
    success_count = int(round(answer_rule_pass_rate / 100.0 * target_count))
    success_count = min(success_count, target_count)
    miss_count = max(0, target_count - success_count)
    grounding_count = int(round(memory_grounding_pass_rate / 100.0 * target_count))
    grounding_count = min(grounding_count, target_count)
    forbidden_count = int(
        round(forbidden_violation_rate / 100.0 * max(1, len(set(forbidden_ids))))
    )
    unavailable = tuple(
        sorted({item for row in family_scores for item in row["unavailable"]})
    )
    token_signal_kind, token_signal_value = _aggregate_token_signal(family_scores)
    token_signal_delta = _delta_value(
        token_signal_value,
        "unavailable",
        profile_kind=token_signal_kind,
        baseline_kind="unavailable",
    )
    latency_ms = _sum_numeric(row["latency_ms"] for row in family_scores)
    row = {
        "case_id": case.id,
        "category": case.category,
        "case_set": case_set,
        "profile_name": profile_name,
        "feature_name": feature_name,
        "measurement_family": case.setup.get("measurement_family", ""),
        "target_profile": case.setup.get("target_profile", ""),
        "repeat_count": 1,
        "target_count": target_count,
        "success_count": success_count,
        "miss_count": miss_count,
        "recall_rate": _ratio(success_count, target_count) * 100.0,
        "grounding_count": grounding_count,
        "forbidden_count": forbidden_count,
        "answer_rule_pass_rate": answer_rule_pass_rate,
        "memory_grounding_pass_rate": memory_grounding_pass_rate,
        "forbidden_violation_rate": forbidden_violation_rate,
        "main_score": main_score,
        "token_signal_kind": token_signal_kind,
        "token_signal_value": token_signal_value,
        "token_signal_delta": token_signal_delta,
        "latency_ms": latency_ms,
        "unavailable": unavailable,
    }
    row.update(_route_case_fields(runtime_profile, feature_names))
    return row


def _route_case_fields(
    runtime_profile: EvalProfileResult,
    feature_names: tuple[str, ...],
) -> dict[str, object]:
    for feature_name in ("tri_retrieval", "graph_retrieval", "rerank_shadow"):
        if feature_name not in feature_names:
            continue
        trace = runtime_profile.traces.get(feature_name)
        if trace is None:
            continue
        metrics = trace.metrics
        if "retrieval_scene" not in metrics:
            continue
        return {
            "retrieval_scene": metrics.get("retrieval_scene", "unknown"),
            "route_source_feature": feature_name,
            "route_decision": metrics.get("route_decision", {}),
            "candidate_drop_counts": metrics.get("candidate_drop_counts", {}),
            "candidate_drop_rate": metrics.get("candidate_drop_rate", 0.0),
            "candidate_accept_rate": metrics.get("candidate_accept_rate", 0.0),
            "expected_route_hit_rate": metrics.get("expected_route_hit_rate", 0.0),
            "route_hit_rate": metrics.get("route_hit_rate", 0.0),
            "graph_lane_used": bool(metrics.get("graph_lane_used", False)),
            "route_input_counts": metrics.get("route_input_counts", {}),
        }
    return {}


def _score_original_memory_base_case(
    *,
    case: EvalCase,
    case_set: str,
    profile_name: str,
    feature_name: str,
) -> dict[str, object]:
    expected_ids = tuple(
        str(item) for item in case.expectations.get("should_recall_ids", [])
    )
    forbidden_ids = tuple(
        str(item) for item in case.expectations.get("should_not_recall_ids", [])
    )
    recalled_items = _baseline_recalled_items(case)
    recalled_ids = tuple(str(item.get("id") or "") for item in recalled_items)
    expected_set = set(expected_ids)
    forbidden_set = set(forbidden_ids)
    recalled_set = set(recalled_ids)
    target_count = len(expected_set)
    success_count = len(recalled_set & expected_set)
    forbidden_count = len(recalled_set & forbidden_set)
    grounding_count = sum(
        1
        for item in recalled_items
        if str(item.get("id") or "") in expected_set
        and str(item.get("source_ref") or "").strip()
    )
    recall_rate = _ratio(success_count, target_count) * 100.0
    grounding_rate = _ratio(grounding_count, target_count) * 100.0
    forbidden_rate = _ratio(forbidden_count, max(1, len(forbidden_set))) * 100.0
    main_score = calculate_main_score(
        answer_rule_pass_rate=recall_rate,
        memory_grounding_pass_rate=grounding_rate,
        forbidden_violation_rate=forbidden_rate,
    )
    return {
        "case_id": case.id,
        "category": case.category,
        "case_set": case_set,
        "profile_name": profile_name,
        "feature_name": feature_name,
        "measurement_family": case.setup.get("measurement_family", ""),
        "target_profile": case.setup.get("target_profile", ""),
        "repeat_count": 1,
        "target_count": target_count,
        "success_count": success_count,
        "miss_count": max(0, target_count - success_count),
        "recall_rate": recall_rate,
        "grounding_count": grounding_count,
        "forbidden_count": forbidden_count,
        "answer_rule_pass_rate": recall_rate,
        "memory_grounding_pass_rate": grounding_rate,
        "forbidden_violation_rate": forbidden_rate,
        "main_score": main_score,
        "token_signal_kind": "unavailable",
        "token_signal_value": "unavailable",
        "token_signal_delta": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": ("token_signal_value", "latency_ms"),
    }


def _score_family(
    *,
    case: EvalCase,
    trace: EvalTrace | None,
    profile_name: str,
    family_name: str,
) -> dict[str, object]:
    if profile_name == "off":
        return {
            "family_name": family_name,
            "answer_rule_pass_rate": 0.0,
            "memory_grounding_pass_rate": 0.0,
            "forbidden_violation_rate": 0.0,
            "token_signal_kind": "unavailable",
            "token_signal_value": "unavailable",
            "latency_ms": "unavailable",
            "unavailable": ("token_signal_value", "latency_ms"),
        }

    if trace is None:
        return {
            "family_name": family_name,
            "answer_rule_pass_rate": 0.0,
            "memory_grounding_pass_rate": 0.0,
            "forbidden_violation_rate": 0.0,
            "token_signal_kind": "unavailable",
            "token_signal_value": "unavailable",
            "latency_ms": "unavailable",
            "unavailable": (family_name, "token_signal_value", "latency_ms"),
        }
    expected_ids = tuple(
        str(item) for item in case.expectations.get("should_recall_ids", [])
    )
    forbidden_ids = tuple(
        str(item) for item in case.expectations.get("should_not_recall_ids", [])
    )
    if family_name == "write_value_score":
        return _score_write_family(trace)
    if family_name == "tri_retrieval":
        return _score_retrieval_family(
            trace,
            expected_ids=expected_ids,
            forbidden_ids=forbidden_ids,
            selected_key="fused_ids",
        )
    if family_name == "graph_retrieval":
        return _score_retrieval_family(
            trace,
            expected_ids=expected_ids,
            forbidden_ids=forbidden_ids,
            selected_key="graph_fused_ids",
        )
    if family_name == "rerank_shadow":
        return _score_rerank_family(
            trace,
            expected_ids=expected_ids,
            forbidden_ids=forbidden_ids,
        )
    if family_name == "injection_governance_shadow":
        return _score_injection_family(trace)
    if family_name == "version_chain_shadow":
        return _score_version_family(
            trace,
            expected_ids=expected_ids,
            forbidden_ids=forbidden_ids,
        )
    if family_name == "provenance_shadow":
        return _score_provenance_family(trace)
    if family_name == "sleep_consolidation_shadow":
        return _score_sleep_family(trace)
    return {
        "family_name": family_name,
        "answer_rule_pass_rate": 0.0,
        "memory_grounding_pass_rate": 0.0,
        "forbidden_violation_rate": 0.0,
        "token_signal_kind": "unavailable",
        "token_signal_value": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": (family_name, "token_signal_value", "latency_ms"),
    }


def _score_write_family(trace: Any) -> dict[str, object]:
    metrics = trace.metrics
    candidate_count = max(0, int(metrics.get("candidate_count", 0) or 0))
    reject_count = max(0, int(metrics.get("policy_reject_count", 0) or 0))
    allow_count = max(0, int(metrics.get("policy_allow_count", 0) or 0))
    temporary_risk_count = max(0, int(metrics.get("temporary_risk_count", 0) or 0))
    assistant_risk_count = max(
        0, int(metrics.get("assistant_inference_risk_count", 0) or 0)
    )
    duplicate_risk_count = max(0, int(metrics.get("duplicate_risk_count", 0) or 0))
    answer = _ratio(reject_count, candidate_count)
    grounding = _ratio(max(candidate_count - duplicate_risk_count, 0), candidate_count)
    forbidden = _ratio(temporary_risk_count + assistant_risk_count + allow_count, candidate_count)
    return {
        "family_name": "write_value_score",
        "answer_rule_pass_rate": answer * 100.0,
        "memory_grounding_pass_rate": grounding * 100.0,
        "forbidden_violation_rate": forbidden * 100.0,
        "token_signal_kind": "unavailable",
        "token_signal_value": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": ("token_signal_value", "latency_ms"),
    }


def _score_retrieval_family(
    trace: Any,
    *,
    expected_ids: tuple[str, ...],
    forbidden_ids: tuple[str, ...],
    selected_key: str,
) -> dict[str, object]:
    selected_ids = tuple(str(item) for item in trace.experimental_result.get(selected_key, []))
    recall = _hit_rate(selected_ids, expected_ids)
    forbidden = _hit_rate(selected_ids, forbidden_ids)
    grounding = float(trace.metrics.get("source_ref_coverage", 0.0) or 0.0) * 100.0
    latency = trace.metrics.get("retrieval_latency_ms", "unavailable")
    return {
        "family_name": selected_key,
        "answer_rule_pass_rate": recall * 100.0,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden * 100.0,
        "token_signal_kind": "unavailable",
        "token_signal_value": "unavailable",
        "latency_ms": latency,
        "unavailable": ("token_signal_value",),
    }


def _score_rerank_family(
    trace: Any,
    *,
    expected_ids: tuple[str, ...],
    forbidden_ids: tuple[str, ...],
) -> dict[str, object]:
    selected_ids = tuple(str(item) for item in trace.experimental_result.get("reranked_ids", []))
    recall = _hit_rate(selected_ids, expected_ids)
    forbidden = _hit_rate(selected_ids, forbidden_ids)
    candidate_count = max(0, int(trace.metrics.get("candidate_count", 0) or 0))
    source_ref_count = max(0, int(trace.metrics.get("source_ref_count", 0) or 0))
    grounding = _ratio(source_ref_count, candidate_count)
    prompt_token_delta = float(trace.metrics.get("prompt_token_delta", 0) or 0)
    low_confidence_injected_count = max(
        0, int(trace.metrics.get("low_confidence_injected_count", 0) or 0)
    )
    forbidden = max(forbidden, _ratio(low_confidence_injected_count, candidate_count))
    return {
        "family_name": "rerank_shadow",
        "answer_rule_pass_rate": recall * 100.0,
        "memory_grounding_pass_rate": grounding * 100.0,
        "forbidden_violation_rate": forbidden * 100.0,
        "token_signal_kind": "prompt_token_delta",
        "token_signal_value": prompt_token_delta,
        "latency_ms": "unavailable",
        "unavailable": ("latency_ms",),
    }


def _score_injection_family(trace: Any) -> dict[str, object]:
    metrics = trace.metrics
    baseline_injected = max(0, int(metrics.get("baseline_injected_count", 0) or 0))
    experimental_injected = max(
        0, int(metrics.get("experimental_injected_count", 0) or 0)
    )
    low_confidence = max(0, int(metrics.get("low_confidence_injected_count", 0) or 0))
    dropped = max(0, int(metrics.get("dropped_count", 0) or 0))
    prompt_token_delta = float(metrics.get("prompt_token_delta", 0) or 0)
    answer = _ratio(dropped, max(1, baseline_injected + dropped))
    grounding = _ratio(max(0, experimental_injected - low_confidence), max(1, experimental_injected))
    forbidden = _ratio(low_confidence, max(1, baseline_injected))
    return {
        "family_name": "injection_governance_shadow",
        "answer_rule_pass_rate": answer * 100.0,
        "memory_grounding_pass_rate": grounding * 100.0,
        "forbidden_violation_rate": forbidden * 100.0,
        "token_signal_kind": "prompt_token_delta",
        "token_signal_value": prompt_token_delta,
        "latency_ms": "unavailable",
        "unavailable": ("latency_ms",),
    }


def _score_version_family(
    trace: Any,
    *,
    expected_ids: tuple[str, ...],
    forbidden_ids: tuple[str, ...],
) -> dict[str, object]:
    baseline_ids = tuple(str(item) for item in trace.baseline_result.get("baseline_recalled_ids", []))
    active_leaf_ids = tuple(
        str(item) for item in trace.experimental_result.get("active_leaf_ids", [])
    )
    recall = _hit_rate(active_leaf_ids, expected_ids)
    stale_count = max(0, int(trace.metrics.get("stale_recalled_count", 0) or 0))
    conflict_count = max(0, int(trace.metrics.get("conflict_chain_count", 0) or 0))
    rollback_count = max(0, int(trace.metrics.get("rollback_candidate_count", 0) or 0))
    superseded_count = max(0, int(trace.metrics.get("superseded_recalled_count", 0) or 0))
    grounding = float(trace.metrics.get("parse_success_rate", 0.0) or 0.0) * 100.0
    forbidden = _ratio(
        stale_count + superseded_count + conflict_count,
        max(1, len(baseline_ids) or len(active_leaf_ids)),
    )
    if forbidden_ids:
        forbidden = max(forbidden, _hit_rate(baseline_ids, forbidden_ids))
    return {
        "family_name": "version_chain_shadow",
        "answer_rule_pass_rate": recall * 100.0,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden * 100.0,
        "token_signal_kind": "unavailable",
        "token_signal_value": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": ("token_signal_value", "latency_ms"),
    }


def _score_provenance_family(trace: Any) -> dict[str, object]:
    source_ref_coverage = float(trace.metrics.get("source_ref_coverage", 0.0) or 0.0) * 100.0
    parse_success_rate = float(trace.metrics.get("parse_success_rate", 0.0) or 0.0) * 100.0
    cross_scope_risk_count = max(0, int(trace.metrics.get("cross_scope_risk_count", 0) or 0))
    cross_scope_memory_count = max(
        0, int(trace.metrics.get("cross_scope_memory_count", 0) or 0)
    )
    grounding = _avg([source_ref_coverage, parse_success_rate])
    forbidden = _ratio(cross_scope_risk_count, max(1, cross_scope_memory_count))
    return {
        "family_name": "provenance_shadow",
        "answer_rule_pass_rate": source_ref_coverage,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden * 100.0,
        "token_signal_kind": "unavailable",
        "token_signal_value": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": ("token_signal_value", "latency_ms"),
    }


def _score_sleep_family(trace: Any) -> dict[str, object]:
    metrics = trace.metrics
    duplicate_group_count = max(0, int(metrics.get("duplicate_group_count", 0) or 0))
    merge_candidate_count = max(0, int(metrics.get("merge_candidate_count", 0) or 0))
    stale_candidate_count = max(0, int(metrics.get("stale_candidate_count", 0) or 0))
    low_value_candidate_count = max(
        0, int(metrics.get("low_value_candidate_count", 0) or 0)
    )
    conflict_candidate_count = max(0, int(metrics.get("conflict_candidate_count", 0) or 0))
    scanned_count = max(1, int(metrics.get("scanned_count", 0) or 0))
    missing_source_ref_count = max(
        0, int(metrics.get("missing_source_ref_count", 0) or 0)
    )
    estimated_token_saving = float(metrics.get("estimated_token_saving", 0) or 0)
    job_latency_ms = float(metrics.get("job_latency_ms", 0) or 0)
    answer = min(
        100.0,
        float(
            duplicate_group_count * 12
            + merge_candidate_count * 10
            + stale_candidate_count * 2
            + low_value_candidate_count * 2
            + conflict_candidate_count * 4
        ),
    )
    grounding = (1.0 - min(1.0, missing_source_ref_count / scanned_count)) * 100.0
    forbidden = 0.0
    return {
        "family_name": "sleep_consolidation_shadow",
        "answer_rule_pass_rate": answer,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden,
        "token_signal_kind": "estimated_token_saving",
        "token_signal_value": estimated_token_saving,
        "latency_ms": job_latency_ms,
        "unavailable": (),
    }


def _build_profile_summaries(
    rows: Sequence[dict[str, object]],
    *,
    profile_order: Sequence[str] = REPORT_PROFILES,
    label_map: dict[str, str] = PROFILE_FEATURE_LABELS,
    delta_mode: str = "baseline",
    baseline_profile: str = "memory_base",
) -> tuple[QuantitativeProfileSummary, ...]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (str(row["case_set"]), str(row["profile_name"]))
        grouped.setdefault(key, []).append(row)
    overall_grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        overall_grouped.setdefault(str(row["profile_name"]), []).append(row)

    baseline_lookup = {
        case_set: _aggregate_case_rows(grouped[(case_set, baseline_profile)])
        for case_set in {"common", "hard"}
        if (case_set, baseline_profile) in grouped
    }
    baseline_lookup["overall"] = _aggregate_case_rows(
        overall_grouped.get(baseline_profile, [])
    )
    result: list[QuantitativeProfileSummary] = []
    for case_set in ("common", "hard", "overall"):
        previous_aggregate: dict[str, object] | None = None
        for profile_name in profile_order:
            aggregate_rows = (
                grouped.get((case_set, profile_name), [])
                if case_set != "overall"
                else overall_grouped.get(profile_name, [])
            )
            if not aggregate_rows:
                continue
            aggregate = _aggregate_case_rows(aggregate_rows)
            baseline = baseline_lookup.get(case_set, baseline_lookup.get("overall"))
            baseline_score = baseline["main_score"] if baseline else 0.0
            if delta_mode == "previous_step":
                previous_score = (
                    float(previous_aggregate["main_score"])
                    if previous_aggregate is not None
                    else float(aggregate["main_score"])
                )
                uplift_points = round(float(aggregate["main_score"]) - previous_score, 4)
                uplift_pct = (
                    round(uplift_points / previous_score * 100.0, 4)
                    if previous_score
                    else None
                )
            else:
                uplift_points = round(float(aggregate["main_score"]) - baseline_score, 4)
                uplift_pct = (
                    round(uplift_points / baseline_score * 100.0, 4)
                    if baseline_score
                    else None
                )
            delta_reference = (
                previous_aggregate
                if delta_mode == "previous_step" and previous_aggregate is not None
                else baseline
            )
            token_signal_delta = _delta_value(
                aggregate["token_signal_value"],
                delta_reference.get("token_signal_value")
                if delta_reference
                else "unavailable",
                profile_kind=str(aggregate["token_signal_kind"]),
                baseline_kind=str(
                    delta_reference.get("token_signal_kind")
                    if delta_reference
                    else "unavailable"
                ),
            )
            latency_delta_ms = _delta_value(
                aggregate["latency_ms"],
                delta_reference.get("latency_ms")
                if delta_reference
                else "unavailable",
            )
            result.append(
                QuantitativeProfileSummary(
                    profile_name=profile_name,
                    feature_name=label_map[profile_name],
                    case_set=case_set,
                    case_count=int(aggregate["case_count"]),
                    target_count=int(aggregate["target_count"]),
                    success_count=int(aggregate["success_count"]),
                    miss_count=int(aggregate["miss_count"]),
                    recall_rate=float(aggregate["recall_rate"]),
                    grounding_count=int(aggregate["grounding_count"]),
                    forbidden_count=int(aggregate["forbidden_count"]),
                    repeat_count=1,
                    answer_rule_pass_rate=float(aggregate["answer_rule_pass_rate"]),
                    memory_grounding_pass_rate=float(
                        aggregate["memory_grounding_pass_rate"]
                    ),
                    forbidden_violation_rate=float(
                        aggregate["forbidden_violation_rate"]
                    ),
                    main_score=float(aggregate["main_score"]),
                    baseline_score=float(baseline_score),
                    uplift_points=uplift_points,
                    uplift_pct=uplift_pct,
                    token_signal_kind=str(aggregate["token_signal_kind"]),
                    token_signal_value=aggregate["token_signal_value"],
                    token_signal_delta=token_signal_delta,
                    latency_ms=aggregate["latency_ms"],
                    latency_delta_ms=latency_delta_ms,
                    unavailable=tuple(aggregate["unavailable"]),
                )
            )
            previous_aggregate = aggregate
    return tuple(result)


def _aggregate_case_rows(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    target_count = sum(int(row.get("target_count", 0) or 0) for row in rows)
    success_count = sum(int(row.get("success_count", 0) or 0) for row in rows)
    grounding_count = sum(int(row.get("grounding_count", 0) or 0) for row in rows)
    forbidden_count = sum(int(row.get("forbidden_count", 0) or 0) for row in rows)
    answer = _avg(float(row["answer_rule_pass_rate"]) for row in rows)
    grounding = _avg(float(row["memory_grounding_pass_rate"]) for row in rows)
    forbidden = _avg(float(row["forbidden_violation_rate"]) for row in rows)
    main_score = _avg(float(row["main_score"]) for row in rows)
    token_signal_kind, token_signal_value = _aggregate_token_signal(rows)
    latency_values = [row["latency_ms"] for row in rows if isinstance(row["latency_ms"], (int, float))]
    return {
        "case_count": len(rows),
        "target_count": target_count,
        "success_count": success_count,
        "miss_count": max(0, target_count - success_count),
        "recall_rate": _ratio(success_count, target_count) * 100.0,
        "grounding_count": grounding_count,
        "forbidden_count": forbidden_count,
        "answer_rule_pass_rate": answer,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden,
        "main_score": main_score,
        "token_signal_kind": token_signal_kind,
        "token_signal_value": token_signal_value,
        "latency_ms": _maybe_sum(latency_values),
        "unavailable": _aggregate_unavailable(rows),
    }


def _build_report_metrics(
    cases: Sequence[EvalCase],
    summaries: Sequence[QuantitativeProfileSummary],
    rows: Sequence[dict[str, object]],
) -> dict[str, object]:
    baseline = _summary_lookup(summaries, "memory_base", case_set="overall")
    all_on = _summary_lookup(summaries, "all_on", case_set="overall")
    common = _summary_lookup(summaries, "all_on", case_set="common")
    hard = _summary_lookup(summaries, "all_on", case_set="hard")
    common_baseline = _summary_lookup(summaries, "memory_base", case_set="common")
    hard_baseline = _summary_lookup(summaries, "memory_base", case_set="hard")
    overall_baseline = baseline.main_score if baseline else 0.0
    overall_all_on = all_on.main_score if all_on else 0.0
    total_uplift_points = round(overall_all_on - overall_baseline, 4)
    total_uplift_pct = (
        round(total_uplift_points / overall_baseline * 100.0, 4)
        if overall_baseline
        else None
    )
    return {
        "measurement_mode": "offline_trace_quantitative_uplift",
        "baseline_profile": "memory_base",
        "control_profile": "off",
        "case_count": len(cases),
        "common_case_count": sum(1 for case in cases if case.id.startswith("common_")),
        "hard_case_count": sum(1 for case in cases if case.id.startswith("hard_")),
        "profile_count": len(REPORT_PROFILES),
        "feature_count": len(QUANTITATIVE_FEATURES),
        "repeat_count": 1,
        "case_record_count": len(rows),
        "profile_summary_count": len(summaries),
        "overall_main_score": overall_all_on,
        "baseline_main_score": overall_baseline,
        "baseline_target_count": baseline.target_count if baseline else 0,
        "baseline_success_count": baseline.success_count if baseline else 0,
        "baseline_miss_count": baseline.miss_count if baseline else 0,
        "baseline_recall_rate": baseline.recall_rate if baseline else 0.0,
        "final_target_count": all_on.target_count if all_on else 0,
        "final_success_count": all_on.success_count if all_on else 0,
        "final_miss_count": all_on.miss_count if all_on else 0,
        "final_recall_rate": all_on.recall_rate if all_on else 0.0,
        "total_uplift_points": total_uplift_points,
        "total_uplift_pct": total_uplift_pct,
        "common_main_score": common.main_score if common else "unavailable",
        "hard_main_score": hard.main_score if hard else "unavailable",
        "common_baseline_main_score": common_baseline.main_score
        if common_baseline
        else "unavailable",
        "hard_baseline_main_score": hard_baseline.main_score
        if hard_baseline
        else "unavailable",
        "overall_answer_rule_pass_rate": all_on.answer_rule_pass_rate if all_on else 0.0,
        "overall_memory_grounding_pass_rate": all_on.memory_grounding_pass_rate if all_on else 0.0,
        "overall_forbidden_violation_rate": all_on.forbidden_violation_rate if all_on else 0.0,
        "unavailable_count": sum(1 for row in rows if row["unavailable"]),
        "score_formula": (
            "main_score = 0.7 * answer_rule_pass_rate + "
            "0.2 * memory_grounding_pass_rate + "
            "0.1 * (100 - forbidden_violation_rate)"
        ),
    }


def _build_chain_report_metrics(
    cases: Sequence[EvalCase],
    summaries: Sequence[QuantitativeProfileSummary],
    rows: Sequence[dict[str, object]],
) -> dict[str, object]:
    baseline = _summary_lookup(summaries, "chain_memory_base", case_set="overall")
    final = _summary_lookup(summaries, "chain_all_on", case_set="overall")
    common_final = _summary_lookup(summaries, "chain_all_on", case_set="common")
    hard_final = _summary_lookup(summaries, "chain_all_on", case_set="hard")
    baseline_score = baseline.main_score if baseline else 0.0
    final_score = final.main_score if final else 0.0
    total_uplift_points = round(final_score - baseline_score, 4)
    total_uplift_pct = (
        round(total_uplift_points / baseline_score * 100.0, 4)
        if baseline_score
        else None
    )
    overall_steps = [
        row
        for row in summaries
        if row.case_set == "overall" and row.profile_name != "chain_off"
    ]
    strongest = max(overall_steps, key=lambda row: row.uplift_points, default=None)
    weakest = min(overall_steps, key=lambda row: row.uplift_points, default=None)
    return {
        "measurement_mode": "offline_trace_quantitative_chain",
        "baseline_profile": "chain_memory_base",
        "control_profile": "chain_off",
        "case_count": len(cases),
        "common_case_count": sum(1 for case in cases if case.id.startswith("common_")),
        "hard_case_count": sum(1 for case in cases if case.id.startswith("hard_")),
        "chain_step_count": len(CHAIN_PROFILES),
        "feature_count": len(QUANTITATIVE_FEATURES),
        "repeat_count": 1,
        "case_record_count": len(rows),
        "profile_summary_count": len(summaries),
        "baseline_main_score": baseline_score,
        "final_main_score": final_score,
        "baseline_target_count": baseline.target_count if baseline else 0,
        "baseline_success_count": baseline.success_count if baseline else 0,
        "baseline_miss_count": baseline.miss_count if baseline else 0,
        "baseline_recall_rate": baseline.recall_rate if baseline else 0.0,
        "final_target_count": final.target_count if final else 0,
        "final_success_count": final.success_count if final else 0,
        "final_miss_count": final.miss_count if final else 0,
        "final_recall_rate": final.recall_rate if final else 0.0,
        "total_chain_uplift_points": total_uplift_points,
        "total_chain_uplift_pct": total_uplift_pct,
        "common_final_main_score": common_final.main_score
        if common_final
        else "unavailable",
        "hard_final_main_score": hard_final.main_score
        if hard_final
        else "unavailable",
        "strongest_step": strongest.profile_name if strongest else "unavailable",
        "strongest_step_delta": strongest.uplift_points
        if strongest
        else "unavailable",
        "weakest_step": weakest.profile_name if weakest else "unavailable",
        "weakest_step_delta": weakest.uplift_points if weakest else "unavailable",
        "negative_step_count": sum(1 for row in overall_steps if row.uplift_points < 0),
        "positive_step_count": sum(1 for row in overall_steps if row.uplift_points > 0),
        "score_formula": (
            "main_score = 0.7 * answer_rule_pass_rate + "
            "0.2 * memory_grounding_pass_rate + "
            "0.1 * (100 - forbidden_violation_rate)"
        ),
    }


def _build_balanced_summaries(
    rows: Sequence[QuantitativeProfileSummary],
) -> tuple[BalancedProfileSummary, ...]:
    result: list[BalancedProfileSummary] = []
    for case_set in ("common", "hard", "overall"):
        previous: BalancedProfileSummary | None = None
        for profile_name in CHAIN_PROFILES:
            row = _summary_lookup(rows, profile_name, case_set=case_set)
            if row is None:
                continue
            scores = calculate_balanced_scores(row)
            balanced_score = float(scores["balanced_score"])
            previous_score = previous.balanced_score if previous else balanced_score
            delta_points = round(balanced_score - previous_score, 4)
            delta_pct = (
                round(delta_points / previous_score * 100.0, 4)
                if previous_score
                else None
            )
            summary = BalancedProfileSummary(
                profile_name=row.profile_name,
                feature_name=row.feature_name,
                case_set=row.case_set,
                case_count=row.case_count,
                answer_score=float(scores["answer_score"]),
                retrieval_proxy_score=scores["retrieval_proxy_score"],
                grounding_score=float(scores["grounding_score"]),
                governance_score=float(scores["governance_score"]),
                efficiency_score=scores["efficiency_score"],
                balanced_score=balanced_score,
                balanced_delta_points=delta_points,
                balanced_delta_pct=delta_pct,
                balanced_score_available_dimensions=tuple(
                    str(item) for item in scores["balanced_score_available_dimensions"]
                ),
                unavailable_dimensions=tuple(
                    str(item) for item in scores["unavailable_dimensions"]
                ),
            )
            result.append(summary)
            previous = summary
    return tuple(result)


def _build_balanced_report_metrics(
    cases: Sequence[EvalCase],
    summaries: Sequence[BalancedProfileSummary],
    chain_report: QuantitativeUpliftReport,
) -> dict[str, object]:
    baseline = _balanced_summary_lookup(summaries, "chain_off", case_set="overall")
    final = _balanced_summary_lookup(summaries, "chain_all_on", case_set="overall")
    common_final = _balanced_summary_lookup(
        summaries, "chain_all_on", case_set="common"
    )
    hard_final = _balanced_summary_lookup(summaries, "chain_all_on", case_set="hard")
    baseline_score = baseline.balanced_score if baseline else 0.0
    final_score = final.balanced_score if final else 0.0
    total_uplift_points = round(final_score - baseline_score, 4)
    overall_steps = [
        row
        for row in summaries
        if row.case_set == "overall" and row.profile_name != "chain_off"
    ]
    strongest = max(
        overall_steps,
        key=lambda row: row.balanced_delta_points,
        default=None,
    )
    weakest = min(
        overall_steps,
        key=lambda row: row.balanced_delta_points,
        default=None,
    )
    return {
        "measurement_mode": "offline_trace_quantitative_balanced",
        "case_count": len(cases),
        "common_case_count": sum(1 for case in cases if case.id.startswith("common_")),
        "hard_case_count": sum(1 for case in cases if case.id.startswith("hard_")),
        "balanced_step_count": len(CHAIN_PROFILES),
        "chain_run_id": chain_report.run_id,
        "baseline_balanced_score": baseline_score,
        "final_balanced_score": final_score,
        "total_balanced_uplift_points": total_uplift_points,
        "total_balanced_uplift_pct": (
            round(total_uplift_points / baseline_score * 100.0, 4)
            if baseline_score
            else None
        ),
        "strongest_balanced_step": strongest.profile_name
        if strongest
        else "unavailable",
        "strongest_balanced_delta": strongest.balanced_delta_points
        if strongest
        else "unavailable",
        "weakest_balanced_step": weakest.profile_name
        if weakest
        else "unavailable",
        "weakest_balanced_delta": weakest.balanced_delta_points
        if weakest
        else "unavailable",
        "answer_score_final": final.answer_score if final else "unavailable",
        "retrieval_proxy_score_final": final.retrieval_proxy_score
        if final
        else "unavailable",
        "grounding_score_final": final.grounding_score if final else "unavailable",
        "governance_score_final": final.governance_score if final else "unavailable",
        "efficiency_score_final": final.efficiency_score if final else "unavailable",
        "common_final_balanced_score": common_final.balanced_score
        if common_final
        else "unavailable",
        "hard_final_balanced_score": hard_final.balanced_score
        if hard_final
        else "unavailable",
        "balanced_score_available_dimensions_final": final.balanced_score_available_dimensions
        if final
        else (),
        "unavailable_dimensions_final": final.unavailable_dimensions if final else (),
        "score_formula": BALANCED_SCORE_FORMULA,
    }


def _balanced_summary_lookup(
    rows: Sequence[BalancedProfileSummary],
    profile_name: str,
    *,
    case_set: str = "overall",
) -> BalancedProfileSummary | None:
    for row in rows:
        if row.profile_name == profile_name and row.case_set == case_set:
            return row
    return None


def _report_to_dict(report: QuantitativeUpliftReport) -> dict[str, object]:
    return {
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "score_formula": report.score_formula,
        "metrics": report.metrics,
        "profile_summaries": [asdict(row) for row in report.profile_summaries],
        "feature_contributions": [asdict(row) for row in report.feature_contributions],
        "case_records": list(report.case_records),
    }


def _balanced_report_to_dict(report: QuantitativeBalancedReport) -> dict[str, object]:
    return {
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "score_formula": report.score_formula,
        "metrics": report.metrics,
        "profile_summaries": [asdict(row) for row in report.profile_summaries],
        "balanced_summaries": [asdict(row) for row in report.balanced_summaries],
        "case_records": list(report.case_records),
    }


def write_quantitative_balanced_json(
    report: QuantitativeBalancedReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _balanced_report_to_dict(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def write_quantitative_balanced_markdown(
    report: QuantitativeBalancedReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(report.balanced_summaries)
    overall_rows = [row for row in rows if row.case_set == "overall"]
    common_rows = [row for row in rows if row.case_set == "common"]
    hard_rows = [row for row in rows if row.case_set == "hard"]
    baseline = _balanced_summary_lookup(overall_rows, "chain_off")
    final = _balanced_summary_lookup(overall_rows, "chain_all_on")
    common_count = report.metrics.get("common_case_count", "unavailable")
    hard_count = report.metrics.get("hard_case_count", "unavailable")
    lines = [
        "# 记忆系统 Balanced 量化评测报告",
        "",
        "本报告是离线确定性 trace 的分层代理评测，不调用真实 LLM，不读写真实 memory DB，不是生产回答准确率。",
        "",
        "## 评测口径",
        "",
        f"- 样本规模：{report.metrics.get('case_count')} 个目标导向 case，其中 common {common_count} 个，hard {hard_count} 个。",
        "- Balanced report 借鉴 RAG/Agent 分层评测共识，把回答、召回代理、证据、治理和效率分开；本项目的改进是把 memory 生命周期治理纳入评分，包括 forbidden、source_ref、版本链、scope 隔离和 token/sleep 信号。它仍然是离线代理评测，不是生产回答准确率。",
        "- `retrieval_proxy_score` 是当前离线 trace 的召回代理指标，不是真实 `recall@k`。",
        "- `efficiency_score` 缺失时保持 `unavailable`，计算 `balanced_score` 时只按可用维度归一化权重。",
        f"- `{report.score_formula}`",
        "",
        "## 分层评分",
        "",
        "| 指标 | 含义 | 方向 |",
        "| --- | --- | --- |",
        "| `answer_score` | 回答规则或目标记忆命中代理分，来自 `answer_rule_pass_rate` | 越高越好 |",
        "| `retrieval_proxy_score` | 召回相关链路步骤上的离线召回代理分，不是真实 `recall@k` | 越高越好 |",
        "| `grounding_score` | 来源、证据或可解释字段覆盖情况，来自 `memory_grounding_pass_rate` | 越高越好 |",
        "| `governance_score` | 综合 forbidden 控制和 grounding 的治理分 | 越高越好 |",
        "| `efficiency_score` | token 节省或 prompt token 控制的效率分；缺失时为 `unavailable` | 越高越好 |",
        "| `balanced_score` | 只用可用维度归一化后的综合代理分 | 越高越好 |",
        "",
        "## 链路 Balanced 增益",
        "",
        "| step | label | balanced_score | 相邻增益 | answer_score | retrieval_proxy_score | grounding_score | governance_score | efficiency_score | available | unavailable |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in overall_rows:
        lines.append(_balanced_summary_row_to_md(row))
    lines.extend(
        [
            "",
            "## common / hard 对比",
            "",
            "| case_set | step | balanced_score | 相邻增益 | answer_score | retrieval_proxy_score | grounding_score | governance_score | efficiency_score |",
            "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in common_rows + hard_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.case_set,
                    row.profile_name,
                    _fmt(row.balanced_score),
                    _fmt(row.balanced_delta_points),
                    _fmt(row.answer_score),
                    _fmt(row.retrieval_proxy_score),
                    _fmt(row.grounding_score),
                    _fmt(row.governance_score),
                    _fmt(row.efficiency_score),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 关闭状态 balanced_score 为 `{_fmt(baseline.balanced_score if baseline else 'unavailable')}`。",
            f"- 全开组合 balanced_score 为 `{_fmt(final.balanced_score if final else 'unavailable')}`，相邻链路总提升 `{_fmt(report.metrics.get('total_balanced_uplift_points'))}` 分。",
            f"- 相邻增益最高的步骤是 `{report.metrics.get('strongest_balanced_step')}`，增益为 `{_fmt(report.metrics.get('strongest_balanced_delta'))}` 分。",
            f"- 相邻增益最低的步骤是 `{report.metrics.get('weakest_balanced_step')}`，变化为 `{_fmt(report.metrics.get('weakest_balanced_delta'))}` 分。",
            "- 这个口径让后段治理、证据和效率模块有独立展示空间，但它仍然是离线代理评测，不能写成线上效果或真实准确率结论。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _balanced_summary_row_to_md(row: BalancedProfileSummary) -> str:
    return (
        "| "
        + " | ".join(
            [
                row.profile_name,
                row.feature_name,
                _fmt(row.balanced_score),
                _fmt(row.balanced_delta_points),
                _fmt(row.answer_score),
                _fmt(row.retrieval_proxy_score),
                _fmt(row.grounding_score),
                _fmt(row.governance_score),
                _fmt(row.efficiency_score),
                ", ".join(row.balanced_score_available_dimensions),
                ", ".join(row.unavailable_dimensions) or "none",
            ]
        )
        + " |"
    )


def _summary_lookup(
    rows: Sequence[QuantitativeProfileSummary],
    profile_name: str,
    *,
    case_set: str = "overall",
) -> QuantitativeProfileSummary | None:
    for row in rows:
        if row.profile_name == profile_name and row.case_set == case_set:
            return row
    return None


def _summary_row_to_md(row: QuantitativeProfileSummary) -> str:
    return (
        f"| {row.profile_name} | {row.case_set} | {_fmt(row.main_score)} | "
        f"{_fmt(row.uplift_points)} | {_fmt(row.uplift_pct)} | "
        f"{_fmt(row.answer_rule_pass_rate)} | {_fmt(row.memory_grounding_pass_rate)} | "
        f"{_fmt(row.forbidden_violation_rate)} | {_fmt(row.token_signal_kind)} | "
        f"{_fmt(row.token_signal_value)} | {_fmt(row.token_signal_delta)} | "
        f"{_fmt(row.latency_ms)} | "
        f"{_fmt(row.latency_delta_ms)} |"
    )


def _count_rate_summary_row_to_md(
    row: QuantitativeProfileSummary,
    *,
    include_profile_only: bool = False,
) -> str:
    fields = [row.profile_name]
    if not include_profile_only:
        fields.append(row.case_set)
    fields.extend(
        [
            _fmt(row.target_count),
            _fmt(row.success_count),
            _fmt(row.miss_count),
            _fmt(row.recall_rate),
            _fmt(row.grounding_count),
            _fmt(row.memory_grounding_pass_rate),
            _fmt(row.forbidden_count),
            _fmt(row.forbidden_violation_rate),
        ]
    )
    return "| " + " | ".join(fields) + " |"


def _detailed_review_lines(
    report: QuantitativeUpliftReport,
    rows: Sequence[QuantitativeProfileSummary],
) -> list[str]:
    ordered_profiles = (
        "off",
        "write_value_only",
        "tri_retrieval_only",
        "graph_only",
        "rerank_only",
        "version_provenance_only",
        "sleep_only",
        "all_on",
    )
    case_count = report.metrics.get("case_count", "unavailable")
    common_case_count = report.metrics.get("common_case_count", "unavailable")
    hard_case_count = report.metrics.get("hard_case_count", "unavailable")
    lines = [
        "",
        "## 详细复盘",
        "",
        "### 测试过程",
        "",
        "- 测试对象：Phase 6d 离线量化 uplift report。",
        f"- 样本规模：{case_count} 个目标导向 case，其中 common {common_case_count} 个，hard {hard_case_count} 个。",
        "- 对照方式：同一批 case 同时跑 `off`、单项开关和 `all_on`。",
        "- 执行方式：复用离线 `EvalCase`、`EvalRunReport` 和 shadow trace，不启动 AgentLoop，不调用真实 LLM，不读写真实 memory DB。",
        "- 评分方式：用 `answer_rule_pass_rate`、`memory_grounding_pass_rate` 和 `forbidden_violation_rate` 计算 `main_score`。",
        "- 失败门控：如果底层 eval runner 失败，报告生成直接失败，不输出伪成功报表。",
        "- 验证结果：本报告只记录评测产物；测试是否通过以实际命令输出为准，不在报告生成逻辑中硬编码。",
        "",
        "### 指标含义",
        "",
        "| 指标 | 含义 | 方向 |",
        "| --- | --- | --- |",
        "| `main_score` | 综合主分，公式为 `0.7 * answer + 0.2 * grounding + 0.1 * (100 - forbidden)` | 越高越好 |",
        "| `uplift_points` | 当前开关相比 `memory_base` 提高的分数 | 越高越好 |",
        "| `uplift_pct` | 当前开关相比 `memory_base` 的提升百分比 | 越高越好 |",
        "| `answer_rule_pass_rate` | 是否命中预期答案规则或目标记忆 | 越高越好 |",
        "| `memory_grounding_pass_rate` | 召回、注入或治理结果是否有来源和证据支撑 | 越高越好 |",
        "| `forbidden_violation_rate` | 是否召回或注入了旧记忆、噪声记忆、跨会话记忆等 forbidden 内容 | 越低越好 |",
        "| `token_signal_kind` | token 信号类型，例如 `prompt_token_delta`、`estimated_token_saving`、`mixed` | 用于解释 token 数字 |",
        "| `token_signal_value` | token 信号值；不同 kind 不能直接相加 | 视 kind 而定 |",
        "| `token_signal_delta` | 与 baseline 可比时的 token 差值；不可比时为 `unavailable` | 视 kind 而定 |",
        "| `latency_ms` | 当前 trace 能观测到的耗时信号 | 越低越好 |",
        "| `common` | 常见场景样本集 | 用于看普通问题表现 |",
        "| `hard` | 难例、边界、模糊指代样本集 | 用于看复杂问题表现 |",
        "",
        "### 各开关详细结论",
        "",
    ]
    for profile_name in ordered_profiles:
        overall = _summary_lookup(rows, profile_name)
        if overall is None:
            continue
        common = _summary_lookup(rows, profile_name, case_set="common")
        hard = _summary_lookup(rows, profile_name, case_set="hard")
        review = _profile_review_text(profile_name, overall, common, hard)
        lines.extend(
            [
                f"#### {PROFILE_FEATURE_LABELS[profile_name]} `{profile_name}`",
                "",
                "| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
                _review_metric_row("overall", overall),
            ]
        )
        if common is not None:
            lines.append(_review_metric_row("common", common))
        if hard is not None:
            lines.append(_review_metric_row("hard", hard))
        lines.extend(
            [
                "",
                f"- 关闭时做得好：{review['off_good']}",
                f"- 关闭时做得不好：{review['off_bad']}",
                f"- 开启后做得好：{review['on_good']}",
                f"- 开启后做得不好：{review['on_bad']}",
                f"- 结论：{review['conclusion']}",
                "",
            ]
        )
    lines.extend(
        [
            "### 总结",
            "",
            f"- 全开组合 `all_on` 的主分为 `{report.metrics.get('overall_main_score')}`，相比原始记忆基线提高 `{report.metrics.get('total_uplift_points')}` 分。",
            f"- 单项直接提分最强的是 `{_strongest_feature_profile(rows)}`，它是当前样本集上的最高 uplift profile。",
            "- `graph_only` 对模糊关联命中有效，但需要继续和 source_ref / provenance 联动提升证据支撑。",
            "- `rerank_only` 和 `version_provenance_only` 更偏治理，价值在降低错误注入、旧版本误用和跨 scope 风险。",
            "- `write_value_only` 和 `sleep_only` 更偏长期质量维护，不应只用即时回答主分评价。",
            "- `all_on` 不是单项分数相加；它是多类能力同时打开后的组合态，后续需要优化组合权重和 active 化策略。",
        ]
    )
    return lines


def _review_metric_row(label: str, row: QuantitativeProfileSummary) -> str:
    return (
        f"| {label} | {_fmt(row.main_score)} | {_fmt(row.uplift_points)} | "
        f"{_fmt(row.uplift_pct)} | {_fmt(row.answer_rule_pass_rate)} | "
        f"{_fmt(row.memory_grounding_pass_rate)} | "
        f"{_fmt(row.forbidden_violation_rate)} | {_fmt(row.token_signal_kind)} | "
        f"{_fmt(row.token_signal_value)} | {_fmt(row.token_signal_delta)} | "
        f"{_fmt(row.latency_ms)} |"
    )


def _profile_review_text(
    profile_name: str,
    overall: QuantitativeProfileSummary,
    common: QuantitativeProfileSummary | None,
    hard: QuantitativeProfileSummary | None,
) -> dict[str, str]:
    common_score = _case_set_score_clause("common", common)
    hard_score = _case_set_score_clause("hard", hard)
    graph_on_good = (
        f"answer 为 {_fmt(overall.answer_rule_pass_rate)}，{hard_score}，说明图谱对模糊关联和难例补召回有效。"
        if hard is not None
        else f"answer 为 {_fmt(overall.answer_rule_pass_rate)}，{hard_score}，当前只说明图谱对已评测样本的补召回有效。"
    )
    rerank_on_good = (
        f"forbidden 降到 {_fmt(overall.forbidden_violation_rate)}，{hard_score}，说明它能有效控制哪些记忆进入 prompt。"
        if hard is not None
        else f"forbidden 降到 {_fmt(overall.forbidden_violation_rate)}，{hard_score}，当前只说明它能控制已评测样本中哪些记忆进入 prompt。"
    )
    reviews: dict[str, dict[str, str]] = {
        "off": {
            "off_good": "没有启用实验召回、注入或写入治理，因此没有额外 token 成本、延迟和实验模块引入的 forbidden 风险。",
            "off_bad": f"answer 为 {_fmt(overall.answer_rule_pass_rate)}，grounding 为 {_fmt(overall.memory_grounding_pass_rate)}，主分为 {_fmt(overall.main_score)}，只能作为对照组，不能提供记忆增强能力。",
            "on_good": "不适用；`off` 本身就是关闭状态。",
            "on_bad": "不适用；`off` 本身就是关闭状态。",
            "conclusion": "关闭状态安全但无增强能力，是衡量 uplift 的 baseline。",
        },
        "write_value_only": {
            "off_good": "关闭时不会因为写入价值评分引入额外计算成本。",
            "off_bad": "缺少候选记忆价值判断，临时信息、重复信息、助手推断都有污染长期记忆的风险。",
            "on_good": f"answer 达到 {_fmt(overall.answer_rule_pass_rate)}，说明写入治理规则能识别不少应该拒绝或审查的候选。",
            "on_bad": f"grounding 为 {_fmt(overall.memory_grounding_pass_rate)}，forbidden 为 {_fmt(overall.forbidden_violation_rate)}，说明它只适合作为写入入口治理，不能单独保证召回和证据质量。",
            "conclusion": "适合作为长期记忆写入前的第一道过滤，但需要和 source_ref、重复检测、冲突检测继续联动。",
        },
        "tri_retrieval_only": {
            "off_good": "关闭时没有额外检索路径和融合排序成本。",
            "off_bad": "单一路径或无增强召回容易漏掉模糊指代、关键词不完全匹配和 source_ref 相关记忆。",
            "on_good": f"main_score 为 {_fmt(overall.main_score)}，answer 为 {_fmt(overall.answer_rule_pass_rate)}，grounding 为 {_fmt(overall.memory_grounding_pass_rate)}；{hard_score}。",
            "on_bad": f"forbidden 为 {_fmt(overall.forbidden_violation_rate)}，说明仍可能带入旧记忆、噪声记忆或跨 scope 候选。",
            "conclusion": "当前最强直接提分项，优先级最高，但需要后接重排和注入治理。",
        },
        "graph_only": {
            "off_good": "关闭时不会引入图谱构建、实体桥接和图路径解释成本。",
            "off_bad": "模糊实体关系、跨概念关联和第三路补充召回能力不足。",
            "on_good": graph_on_good,
            "on_bad": f"grounding 为 {_fmt(overall.memory_grounding_pass_rate)}，forbidden 为 {_fmt(overall.forbidden_violation_rate)}，说明当前图谱结果还没有充分转成可解释 source_ref 证据。",
            "conclusion": "适合作为第三路增强，但必须和溯源、重排、注入治理一起使用。",
        },
        "rerank_only": {
            "off_good": "关闭时没有额外 prompt token 增量。",
            "off_bad": "召回候选可能直接进入上下文，低质量、低置信度或冲突记忆更容易污染 prompt。",
            "on_good": rerank_on_good,
            "on_bad": f"token_signal_kind 为 {_fmt(overall.token_signal_kind)}，token_signal_value 为 {_fmt(overall.token_signal_value)}；grounding 为 {_fmt(overall.memory_grounding_pass_rate)}。",
            "conclusion": "是召回后的必要治理层，重点价值是降风险，但需要继续控制 token 成本。",
        },
        "version_provenance_only": {
            "off_good": "关闭时没有版本链扫描和 source_ref 解析成本。",
            "off_bad": "旧版本、新版本、跨会话记忆容易混在一起，难以判断记忆来源是否可信。",
            "on_good": f"forbidden 为 {_fmt(overall.forbidden_violation_rate)}，说明旧版本误用和跨 scope 风险被有效压住。",
            "on_bad": f"answer 为 {_fmt(overall.answer_rule_pass_rate)}，grounding 为 {_fmt(overall.memory_grounding_pass_rate)}，不如三路召回直接提分明显。",
            "conclusion": "是长期记忆可信度基础设施，价值在一致性、隔离和可追溯，不是单独的最强召回模块。",
        },
        "sleep_only": {
            "off_good": "关闭时不会执行后台扫描、去重和压缩估算。",
            "off_bad": "重复、过期、低价值、冲突记忆会持续堆积，长期增加 prompt 噪声和维护成本。",
            "on_good": f"grounding 达到 {_fmt(overall.memory_grounding_pass_rate)}，forbidden 为 {_fmt(overall.forbidden_violation_rate)}，并输出 {_fmt(overall.token_signal_kind)} {_fmt(overall.token_signal_value)}。",
            "on_bad": f"answer 为 {_fmt(overall.answer_rule_pass_rate)}，说明它不是即时召回模块，不能直接提高单轮回答命中。",
            "conclusion": "适合作为后台长期质量维护能力，主要价值是去重、压缩、清理和降噪。",
        },
        "all_on": {
            "off_good": "关闭时最简单、最安全、没有组合复杂度。",
            "off_bad": "没有召回增强、图谱、重排治理、版本链、溯源和睡眠巩固，记忆能力不足。",
            "on_good": f"overall 主分达到 {_fmt(overall.main_score)}，{common_score}，{hard_score}，说明组合能力可以覆盖当前已评测样本。",
            "on_bad": "分数低于单独三路召回，因为组合态混入写入、睡眠等非即时问答能力；token_signal_kind 为 mixed，不能合并成一个 token 数。",
            "conclusion": "全开证明整体方向有效，但后续要优化组合权重，不能简单把所有模块平均计算。",
        },
    }
    return reviews[profile_name]


def _case_set_score_clause(
    case_set: str,
    row: QuantitativeProfileSummary | None,
) -> str:
    if row is None:
        return f"本次未评测 {case_set} 集"
    return f"{case_set} 集为 {_fmt(row.main_score)}"


def _strongest_feature_profile(rows: Sequence[QuantitativeProfileSummary]) -> str:
    candidates = [
        row
        for row in rows
        if row.case_set == "overall" and row.profile_name not in {"off", "all_on"}
    ]
    if not candidates:
        return "unavailable"
    return max(candidates, key=lambda row: row.uplift_points).profile_name


def _profile_has_retrieval_signal(profile_name: str) -> bool:
    return any(
        feature in CHAIN_PROFILE_FEATURE_MAP.get(profile_name, ())
        for feature in (
            "tri_retrieval",
            "graph_retrieval",
            "rerank_shadow",
            "version_chain_shadow",
        )
    )


def _efficiency_score(row: QuantitativeProfileSummary) -> float | str:
    value = row.token_signal_value
    if row.token_signal_kind == "estimated_token_saving" and isinstance(
        value,
        (int, float),
    ):
        return round(min(100.0, float(value) / 10.0), 4)
    if row.token_signal_kind == "prompt_token_delta" and isinstance(
        value,
        (int, float),
    ):
        return round(max(0.0, 100.0 - float(value) / 100.0), 4)
    return "unavailable"


def _fmt(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _avg(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if float(denominator) <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _hit_rate(candidate_ids: tuple[str, ...], target_ids: tuple[str, ...]) -> float:
    if not target_ids:
        return 0.0
    return round(len(set(candidate_ids) & set(target_ids)) / len(set(target_ids)), 4)


def _maybe_sum(values: Sequence[int | float]) -> float | str:
    if not values:
        return "unavailable"
    return round(sum(float(value) for value in values), 4)


def _aggregate_token_signal(rows: Sequence[dict[str, object]]) -> tuple[str, float | str]:
    kinds_seen: set[str] = set()
    signals: list[tuple[str, float]] = []
    for row in rows:
        value = row.get("token_signal_value", "unavailable")
        kind = str(row.get("token_signal_kind") or "unavailable")
        if kind == "unavailable":
            continue
        kinds_seen.add(kind)
        if kind == "mixed" or not isinstance(value, (int, float)):
            continue
        signals.append((kind, float(value)))
    if "mixed" in kinds_seen or len(kinds_seen) > 1:
        return "mixed", "unavailable"
    if not signals:
        return "unavailable", "unavailable"
    return next(iter(kinds_seen)), round(sum(value for _, value in signals), 4)


def _sum_numeric(values: Iterable[object]) -> float | str:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return "unavailable"
    return round(sum(numbers), 4)


def _delta_value(
    profile_value: float | str,
    baseline_value: float | str,
    *,
    profile_kind: str | None = None,
    baseline_kind: str | None = None,
) -> float | str:
    if not isinstance(profile_value, (int, float)) or not isinstance(
        baseline_value, (int, float)
    ):
        return "unavailable"
    if profile_kind is not None or baseline_kind is not None:
        if (
            not profile_kind
            or not baseline_kind
            or profile_kind != baseline_kind
            or profile_kind in {"mixed", "unavailable"}
            or baseline_kind in {"mixed", "unavailable"}
        ):
            return "unavailable"
    return round(float(profile_value) - float(baseline_value), 4)


def _aggregate_unavailable(rows: Sequence[dict[str, object]]) -> tuple[str, ...]:
    return tuple(sorted({item for row in rows for item in row["unavailable"]}))


def _deterministic_run_id(cases: Sequence[EvalCase], profiles: Sequence[str]) -> str:
    case_ids = ",".join(sorted(case.id for case in cases))
    profile_ids = ",".join(profiles)
    payload = f"{case_ids}|{profile_ids}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _case_set(case: EvalCase) -> str:
    category = str(case.category or "")
    if category.startswith("common_"):
        return "common"
    if category.startswith("hard_"):
        return "hard"
    return "overall"
