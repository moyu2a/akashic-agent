from __future__ import annotations

import argparse
import json
import hashlib
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from memory2.eval_cases import EvalCase
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_quantitative_uplift import (
    CHAIN_PROFILE_FEATURE_MAP,
    CHAIN_PROFILES,
    CHAIN_PROFILE_LABELS,
    QuantitativeProfileSummary,
    build_quantitative_chain_report,
    calculate_main_score,
)
from memory2.eval_runner import EvalCaseResult, EvalRunReport, run_eval_cases


ANSWER_LAYER_FORMULA = (
    "answer_layer_score = 0.70 * answer_rule_pass_rate + "
    "0.20 * memory_grounding_pass_rate + "
    "0.10 * (100 - forbidden_violation_rate)"
)

LAYERED_TOTAL_FORMULA = (
    "layered_total_score = 0.45 * answer_layer_score + "
    "0.30 * write_governance_score + "
    "0.25 * memory_hygiene_score; "
    "unavailable layers are omitted and remaining weights are normalized"
)

WRITE_COMPONENT_NAMES: tuple[str, ...] = (
    "useful_write_precision_score",
    "pollution_block_score",
    "duplicate_control_score",
    "review_safety_score",
    "write_reduction_score",
)

HYGIENE_COMPONENT_NAMES: tuple[str, ...] = (
    "source_ref_health_score",
    "stale_cleanup_signal_score",
    "duplicate_merge_signal_score",
    "conflict_resolution_signal_score",
    "low_value_cleanup_signal_score",
    "token_saving_score",
)


@dataclass(frozen=True)
class LayeredComponentBreakdown:
    layer_name: str
    score: float | str
    components: dict[str, float | str]
    unavailable_reasons: tuple[str, ...]


@dataclass(frozen=True)
class LayeredProfileSummary:
    profile_name: str
    feature_name: str
    case_set: str
    case_count: int
    answer_layer_score: float
    write_governance_score: float | str
    write_components: dict[str, float | str]
    memory_hygiene_score: float | str
    hygiene_components: dict[str, float | str]
    layer_breakdowns: tuple[LayeredComponentBreakdown, ...]
    layered_total_score: float
    adjacent_total_delta_points: float
    total_uplift_points: float
    available_layers: tuple[str, ...]
    unavailable_layers: tuple[str, ...]


@dataclass(frozen=True)
class LayeredScoringReport:
    run_id: str
    generated_at: str
    score_formulas: dict[str, str]
    layer_summaries: tuple[LayeredProfileSummary, ...]
    case_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]


def calculate_answer_layer_score(row: QuantitativeProfileSummary) -> float:
    return calculate_main_score(
        answer_rule_pass_rate=row.answer_rule_pass_rate,
        memory_grounding_pass_rate=row.memory_grounding_pass_rate,
        forbidden_violation_rate=row.forbidden_violation_rate,
    )


def calculate_write_governance_score(
    trace_metrics: dict[str, object],
) -> tuple[float | str, dict[str, float | str]]:
    breakdown = _build_write_breakdown(trace_metrics)
    return breakdown.score, breakdown.components


def calculate_memory_hygiene_score(
    trace_metrics: dict[str, object],
) -> tuple[float | str, dict[str, float | str]]:
    breakdown = _build_hygiene_breakdown(trace_metrics)
    return breakdown.score, breakdown.components


def calculate_layered_total_score(
    answer_score: float | str,
    write_score: float | str,
    hygiene_score: float | str,
) -> float:
    score, _, _ = _weighted_available(
        (
            ("answer_layer", 0.45, answer_score),
            ("write_governance", 0.30, write_score),
            ("memory_hygiene", 0.25, hygiene_score),
        )
    )
    return score


def build_layered_scoring_report(cases: Sequence[EvalCase]) -> LayeredScoringReport:
    run_report = run_eval_cases(cases)
    chain_report = build_quantitative_chain_report(cases)
    run_case_results = {case.case_id: case for case in run_report.cases}
    chain_case_records = {
        (str(row["case_id"]), str(row["profile_name"])): row
        for row in chain_report.case_records
    }

    case_records: list[dict[str, object]] = []
    for case in cases:
        case_set = _case_set(case)
        run_case = run_case_results[case.id]
        all_profile = _preferred_profile(run_case)
        for profile_name in CHAIN_PROFILES:
            profile_feature_names = CHAIN_PROFILE_FEATURE_MAP[profile_name]
            chain_row = chain_case_records[(case.id, profile_name)]
            answer_row = _summary_from_record(chain_row, case_set, profile_name)
            answer_layer_score = calculate_answer_layer_score(answer_row)

            write_breakdown = _build_profile_layer_breakdown(
                layer_name="write_governance",
                trace=_trace_for_layer(all_profile, "write_value_score")
                if "write_value_score" in profile_feature_names
                else None,
                breakdown_fn=_build_write_breakdown,
                component_names=WRITE_COMPONENT_NAMES,
            )
            hygiene_breakdown = _build_profile_layer_breakdown(
                layer_name="memory_hygiene",
                trace=_trace_for_layer(all_profile, "sleep_consolidation_shadow")
                if "sleep_consolidation_shadow" in profile_feature_names
                else None,
                breakdown_fn=_build_hygiene_breakdown,
                component_names=HYGIENE_COMPONENT_NAMES,
            )

            layer_breakdowns = (
                LayeredComponentBreakdown(
                    layer_name="answer_layer",
                    score=answer_layer_score,
                    components={
                        "answer_rule_pass_rate": float(answer_row.answer_rule_pass_rate),
                        "memory_grounding_pass_rate": float(
                            answer_row.memory_grounding_pass_rate
                        ),
                        "forbidden_violation_rate": float(
                            answer_row.forbidden_violation_rate
                        ),
                    },
                    unavailable_reasons=(),
                ),
                write_breakdown,
                hygiene_breakdown,
            )

            write_score = write_breakdown.score
            hygiene_score = hygiene_breakdown.score
            layered_total_score = calculate_layered_total_score(
                answer_layer_score,
                write_score,
                hygiene_score,
            )
            available_layers = tuple(
                name
                for name, value in (
                    ("answer_layer", answer_layer_score),
                    ("write_governance", write_score),
                    ("memory_hygiene", hygiene_score),
                )
                if isinstance(value, (int, float))
            )
            unavailable_layers = tuple(
                name
                for name, value in (
                    ("answer_layer", answer_layer_score),
                    ("write_governance", write_score),
                    ("memory_hygiene", hygiene_score),
                )
                if not isinstance(value, (int, float))
            )
            case_records.append(
                {
                    "case_id": case.id,
                    "case_set": case_set,
                    "profile_name": profile_name,
                    "feature_name": CHAIN_PROFILE_LABELS[profile_name],
                    "answer_layer_score": answer_layer_score,
                    "write_governance_score": write_score,
                    "write_components": write_breakdown.components,
                    "write_unavailable_reasons": write_breakdown.unavailable_reasons,
                    "memory_hygiene_score": hygiene_score,
                    "hygiene_components": hygiene_breakdown.components,
                    "hygiene_unavailable_reasons": hygiene_breakdown.unavailable_reasons,
                    "layer_breakdowns": tuple(asdict(item) for item in layer_breakdowns),
                    "layered_total_score": layered_total_score,
                    "trace_metrics": {
                        "write_value_score": _trace_metrics(all_profile, "write_value_score"),
                        "sleep_consolidation_shadow": _trace_metrics(
                            all_profile, "sleep_consolidation_shadow"
                        ),
                    },
                }
            )

    layer_summaries = _build_layer_summaries(
        cases=cases,
        chain_report=chain_report,
        case_records=case_records,
    )
    metrics = _build_report_metrics(cases, layer_summaries, case_records)
    run_id = _deterministic_run_id(cases, CHAIN_PROFILES)
    return LayeredScoringReport(
        run_id=run_id,
        generated_at="2026-07-17T00:00:00+00:00",
        score_formulas={
            "answer_layer": ANSWER_LAYER_FORMULA,
            "write_governance": (
                "write_governance_score = "
                "0.35 * useful_write_precision_score + "
                "0.25 * pollution_block_score + "
                "0.15 * duplicate_control_score + "
                "0.15 * review_safety_score + "
                "0.10 * write_reduction_score"
            ),
            "memory_hygiene": (
                "memory_hygiene_score = "
                "0.25 * source_ref_health_score + "
                "0.20 * stale_cleanup_signal_score + "
                "0.20 * duplicate_merge_signal_score + "
                "0.15 * conflict_resolution_signal_score + "
                "0.10 * low_value_cleanup_signal_score + "
                "0.10 * token_saving_score"
            ),
            "layered_total": LAYERED_TOTAL_FORMULA,
        },
        layer_summaries=layer_summaries,
        case_records=tuple(case_records),
        metrics=metrics,
    )


def write_layered_scoring_json(report: LayeredScoringReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_layered_scoring_markdown(report: LayeredScoringReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(report.layer_summaries)
    overall_rows = [row for row in rows if row.case_set == "overall"]
    common_rows = [row for row in rows if row.case_set == "common"]
    hard_rows = [row for row in rows if row.case_set == "hard"]
    lines = [
        "# 记忆系统三层评分评测报告",
        "",
        "本报告是离线确定性代理结果，只代表当前样本集上的分层对比，不代表生产全量结论。",
        "",
        "## 评分口径",
        "",
        f"- `{report.score_formulas['answer_layer']}`",
        f"- `{report.score_formulas['write_governance']}`",
        f"- `{report.score_formulas['memory_hygiene']}`",
        f"- `{report.score_formulas['layered_total']}`",
        "- 三层分开评估：即时回答、写入治理、记忆库卫生。",
        "- 总分只是概览，不是生产准确率，也不是最终上线排序。",
        "",
        "## 总览",
        "",
        f"- 样本规模：{report.metrics.get('case_count')} 个目标导向 case，其中 common {report.metrics.get('common_case_count')} 个，hard {report.metrics.get('hard_case_count')} 个。",
        f"- `case_count`: `{report.metrics.get('case_count')}`",
        f"- `common_case_count`: `{report.metrics.get('common_case_count')}`",
        f"- `hard_case_count`: `{report.metrics.get('hard_case_count')}`",
        f"- `layer_count`: `{report.metrics.get('layer_count')}`",
        f"- `baseline_total_layered_score`: `{report.metrics.get('baseline_total_layered_score')}`",
        f"- `final_total_layered_score`: `{report.metrics.get('final_total_layered_score')}`",
        f"- `total_layered_uplift_points`: `{report.metrics.get('total_layered_uplift_points')}`",
        "",
        "## 链路阶段对比",
        "",
        "| step | label | answer_layer | write_governance | memory_hygiene | layered_total | 相邻增益 | 总增益 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.profile_name,
                    row.feature_name,
                    _fmt(row.answer_layer_score),
                    _fmt(row.write_governance_score),
                    _fmt(row.memory_hygiene_score),
                    _fmt(row.layered_total_score),
                    _fmt(row.adjacent_total_delta_points),
                    _fmt(row.total_uplift_points),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 写入治理评分",
            "",
            "| step | useful_write_precision | pollution_block | duplicate_control | review_safety | write_reduction | score |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in overall_rows:
        breakdown = _breakdown_by_layer(row, "write_governance")
        lines.append(
            "| "
            + " | ".join(
                [
                    row.profile_name,
                    _fmt(breakdown.components.get("useful_write_precision_score")),
                    _fmt(breakdown.components.get("pollution_block_score")),
                    _fmt(breakdown.components.get("duplicate_control_score")),
                    _fmt(breakdown.components.get("review_safety_score")),
                    _fmt(breakdown.components.get("write_reduction_score")),
                    _fmt(breakdown.score),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 记忆库卫生评分",
            "",
            "| step | source_ref_health | stale_cleanup | duplicate_merge | conflict_resolution | low_value_cleanup | token_saving | score |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in overall_rows:
        breakdown = _breakdown_by_layer(row, "memory_hygiene")
        lines.append(
            "| "
            + " | ".join(
                [
                    row.profile_name,
                    _fmt(breakdown.components.get("source_ref_health_score")),
                    _fmt(breakdown.components.get("stale_cleanup_signal_score")),
                    _fmt(breakdown.components.get("duplicate_merge_signal_score")),
                    _fmt(breakdown.components.get("conflict_resolution_signal_score")),
                    _fmt(breakdown.components.get("low_value_cleanup_signal_score")),
                    _fmt(breakdown.components.get("token_saving_score")),
                    _fmt(breakdown.score),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## common / hard 对比",
            "",
            "| case_set | step | layered_total | answer_layer | write_governance | memory_hygiene |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in common_rows + hard_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.case_set,
                    row.profile_name,
                    _fmt(row.layered_total_score),
                    _fmt(row.answer_layer_score),
                    _fmt(row.write_governance_score),
                    _fmt(row.memory_hygiene_score),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 最终链路 `{report.metrics.get('final_profile_name')}` 的三层总分为 `{report.metrics.get('final_total_layered_score')}`。",
            f"- 相邻增益最高的步骤是 `{report.metrics.get('strongest_step')}`，增益为 `{report.metrics.get('strongest_step_delta')}` 分。",
            f"- 相邻增益最低的步骤是 `{report.metrics.get('weakest_step')}`，变化为 `{report.metrics.get('weakest_step_delta')}` 分。",
            "- 写入治理和记忆库卫生不再被单独的回答分数吞掉，但它们仍然属于离线代理指标，不是生产准确率。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--case-set", choices=("all", "common", "hard"), default="all")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(list(argv) if argv is not None else None)

    cases = build_quantitative_eval_cases(case_set=args.case_set, limit=args.limit)
    if not cases:
        print("No quantitative cases available.")
        return 1

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_layered_scoring_eval.json"
    md_path = out_dir / "memory_layered_scoring_eval.md"
    tmp_json = out_dir / "memory_layered_scoring_eval.json.tmp"
    tmp_md = out_dir / "memory_layered_scoring_eval.md.tmp"

    try:
        report = build_layered_scoring_report(cases)
        out_dir.mkdir(parents=True, exist_ok=True)
        write_layered_scoring_json(report, tmp_json)
        write_layered_scoring_markdown(report, tmp_md)
        tmp_json.replace(json_path)
        tmp_md.replace(md_path)
        print(json_path)
        print(md_path)
        return 0
    except Exception as exc:  # pragma: no cover - exercised via CLI failure tests
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for tmp_path in (tmp_json, tmp_md):
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except FileNotFoundError:
                pass


def _build_profile_layer_breakdown(
    *,
    layer_name: str,
    trace: Any | None,
    breakdown_fn: Any,
    component_names: tuple[str, ...],
) -> LayeredComponentBreakdown:
    if trace is None:
        return LayeredComponentBreakdown(
            layer_name=layer_name,
            score="unavailable",
            components={name: "unavailable" for name in component_names},
            unavailable_reasons=("trace_missing",),
        )
    return breakdown_fn(trace.metrics)


def _build_write_breakdown(trace_metrics: dict[str, object]) -> LayeredComponentBreakdown:
    candidate_count = _required_metric(trace_metrics, "candidate_count")
    policy_reject_count = _required_metric(trace_metrics, "policy_reject_count")
    policy_review_count = _required_metric(trace_metrics, "policy_review_count")
    duplicate_risk_count = _required_metric(trace_metrics, "duplicate_risk_count")
    temporary_risk_count = _required_metric(trace_metrics, "temporary_risk_count")
    assistant_risk_count = _required_metric(
        trace_metrics, "assistant_inference_risk_count"
    )
    write_reduction_rate = _required_metric(trace_metrics, "write_reduction_rate")
    reasons: list[str] = []
    required_values = [
        candidate_count,
        policy_reject_count,
        policy_review_count,
        duplicate_risk_count,
        temporary_risk_count,
        assistant_risk_count,
        write_reduction_rate,
    ]
    if any(value is None for value in required_values) or candidate_count is None or candidate_count <= 0:
        reasons.extend(_missing_reasons(
            trace_metrics,
            (
                "candidate_count",
                "policy_reject_count",
                "policy_review_count",
                "duplicate_risk_count",
                "temporary_risk_count",
                "assistant_inference_risk_count",
                "write_reduction_rate",
            ),
        ))
        if candidate_count is not None and candidate_count <= 0:
            reasons.append("candidate_count:zero")
        return LayeredComponentBreakdown(
            layer_name="write_governance",
            score="unavailable",
            components={name: "unavailable" for name in WRITE_COMPONENT_NAMES},
            unavailable_reasons=tuple(dict.fromkeys(reasons)),
        )

    assert candidate_count is not None
    assert policy_reject_count is not None
    assert policy_review_count is not None
    assert duplicate_risk_count is not None
    assert temporary_risk_count is not None
    assert assistant_risk_count is not None
    assert write_reduction_rate is not None
    any_risk = temporary_risk_count > 0 or assistant_risk_count > 0
    components = {
        "useful_write_precision_score": _clamp_0_100(
            100.0 * policy_reject_count / candidate_count
        ),
        "pollution_block_score": _clamp_0_100(
            100.0 * policy_review_count / candidate_count
        ),
        "duplicate_control_score": _clamp_0_100(
            100.0 * max(candidate_count - duplicate_risk_count, 0.0)
            / candidate_count
        ),
        "review_safety_score": _clamp_0_100(
            100.0
            * (
                policy_review_count / candidate_count
                if any_risk
                else policy_reject_count / candidate_count
            )
        ),
        "write_reduction_score": _clamp_0_100(100.0 * write_reduction_rate),
    }
    score, _, _ = _weighted_available(
        (
            ("useful_write_precision_score", 0.35, components["useful_write_precision_score"]),
            ("pollution_block_score", 0.25, components["pollution_block_score"]),
            ("duplicate_control_score", 0.15, components["duplicate_control_score"]),
            ("review_safety_score", 0.15, components["review_safety_score"]),
            ("write_reduction_score", 0.10, components["write_reduction_score"]),
        )
    )
    return LayeredComponentBreakdown(
        layer_name="write_governance",
        score=score,
        components=components,
        unavailable_reasons=(),
    )


def _build_hygiene_breakdown(trace_metrics: dict[str, object]) -> LayeredComponentBreakdown:
    scanned_count = _required_metric(trace_metrics, "scanned_count")
    missing_source_ref_count = _required_metric(trace_metrics, "missing_source_ref_count")
    stale_candidate_count = _required_metric(trace_metrics, "stale_candidate_count")
    duplicate_group_count = _required_metric(trace_metrics, "duplicate_group_count")
    merge_candidate_count = _required_metric(trace_metrics, "merge_candidate_count")
    conflict_candidate_count = _required_metric(trace_metrics, "conflict_candidate_count")
    low_value_candidate_count = _required_metric(trace_metrics, "low_value_candidate_count")
    estimated_token_saving = _required_metric(trace_metrics, "estimated_token_saving")
    required_values = [
        scanned_count,
        missing_source_ref_count,
        stale_candidate_count,
        duplicate_group_count,
        merge_candidate_count,
        conflict_candidate_count,
        low_value_candidate_count,
        estimated_token_saving,
    ]
    if any(value is None for value in required_values) or scanned_count is None or scanned_count <= 0:
        reasons = _missing_reasons(
            trace_metrics,
            (
                "scanned_count",
                "missing_source_ref_count",
                "stale_candidate_count",
                "duplicate_group_count",
                "merge_candidate_count",
                "conflict_candidate_count",
                "low_value_candidate_count",
                "estimated_token_saving",
            ),
        )
        if scanned_count is not None and scanned_count <= 0:
            reasons.append("scanned_count:zero")
        return LayeredComponentBreakdown(
            layer_name="memory_hygiene",
            score="unavailable",
            components={name: "unavailable" for name in HYGIENE_COMPONENT_NAMES},
            unavailable_reasons=tuple(dict.fromkeys(reasons)),
        )

    assert scanned_count is not None
    assert missing_source_ref_count is not None
    assert stale_candidate_count is not None
    assert duplicate_group_count is not None
    assert merge_candidate_count is not None
    assert conflict_candidate_count is not None
    assert low_value_candidate_count is not None
    assert estimated_token_saving is not None
    components = {
        "source_ref_health_score": _clamp_0_100(
            100.0 * (1.0 - missing_source_ref_count / scanned_count)
        ),
        "stale_cleanup_signal_score": _clamp_0_100(
            100.0 * stale_candidate_count / scanned_count
        ),
        "duplicate_merge_signal_score": _clamp_0_100(
            100.0
            * min(duplicate_group_count, merge_candidate_count)
            / scanned_count
        ),
        "conflict_resolution_signal_score": _clamp_0_100(
            100.0 * conflict_candidate_count / scanned_count
        ),
        "low_value_cleanup_signal_score": _clamp_0_100(
            100.0 * low_value_candidate_count / scanned_count
        ),
        "token_saving_score": _clamp_0_100(
            100.0 * estimated_token_saving / max(1.0, scanned_count)
        ),
    }
    score, _, _ = _weighted_available(
        (
            ("source_ref_health_score", 0.25, components["source_ref_health_score"]),
            ("stale_cleanup_signal_score", 0.20, components["stale_cleanup_signal_score"]),
            ("duplicate_merge_signal_score", 0.20, components["duplicate_merge_signal_score"]),
            ("conflict_resolution_signal_score", 0.15, components["conflict_resolution_signal_score"]),
            ("low_value_cleanup_signal_score", 0.10, components["low_value_cleanup_signal_score"]),
            ("token_saving_score", 0.10, components["token_saving_score"]),
        )
    )
    return LayeredComponentBreakdown(
        layer_name="memory_hygiene",
        score=score,
        components=components,
        unavailable_reasons=(),
    )


def _build_layer_summaries(
    *,
    cases: Sequence[EvalCase],
    chain_report: Any,
    case_records: Sequence[dict[str, object]],
) -> tuple[LayeredProfileSummary, ...]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    overall_grouped: dict[str, list[dict[str, object]]] = {}
    for row in case_records:
        grouped.setdefault((str(row["case_set"]), str(row["profile_name"])), []).append(row)
        overall_grouped.setdefault(str(row["profile_name"]), []).append(row)

    answer_lookup = {
        (row.case_set, row.profile_name): row
        for row in chain_report.profile_summaries
    }
    summaries: list[LayeredProfileSummary] = []
    for case_set in ("common", "hard", "overall"):
        previous_score: float | None = None
        for profile_name in CHAIN_PROFILES:
            rows = (
                overall_grouped.get(profile_name, [])
                if case_set == "overall"
                else grouped.get((case_set, profile_name), [])
            )
            if not rows:
                continue
            answer_row = answer_lookup[(case_set, profile_name)]
            answer_layer_score = calculate_answer_layer_score(answer_row)
            write_summary = _aggregate_layer(rows, "write_governance", WRITE_COMPONENT_NAMES)
            hygiene_summary = _aggregate_layer(
                rows,
                "memory_hygiene",
                HYGIENE_COMPONENT_NAMES,
            )
            total_layered_score = calculate_layered_total_score(
                answer_layer_score,
                write_summary.score,
                hygiene_summary.score,
            )
            available_layers = tuple(
                name
                for name, value in (
                    ("answer_layer", answer_layer_score),
                    ("write_governance", write_summary.score),
                    ("memory_hygiene", hygiene_summary.score),
                )
                if isinstance(value, (int, float))
            )
            unavailable_layers = tuple(
                name
                for name, value in (
                    ("answer_layer", answer_layer_score),
                    ("write_governance", write_summary.score),
                    ("memory_hygiene", hygiene_summary.score),
                )
                if not isinstance(value, (int, float))
            )
            adjacent_delta = (
                round(total_layered_score - previous_score, 4)
                if previous_score is not None
                else 0.0
            )
            total_uplift = round(
                total_layered_score
                - _summary_total_for_profile(answer_lookup, case_set, "chain_memory_base"),
                4,
            )
            summaries.append(
                LayeredProfileSummary(
                    profile_name=profile_name,
                    feature_name=CHAIN_PROFILE_LABELS[profile_name],
                    case_set=case_set,
                    case_count=len(rows),
                    answer_layer_score=answer_layer_score,
                    write_governance_score=write_summary.score,
                    write_components=write_summary.components,
                    memory_hygiene_score=hygiene_summary.score,
                    hygiene_components=hygiene_summary.components,
                    layer_breakdowns=(
                        LayeredComponentBreakdown(
                            layer_name="answer_layer",
                            score=answer_layer_score,
                            components={
                                "answer_rule_pass_rate": answer_row.answer_rule_pass_rate,
                                "memory_grounding_pass_rate": answer_row.memory_grounding_pass_rate,
                                "forbidden_violation_rate": answer_row.forbidden_violation_rate,
                            },
                            unavailable_reasons=(),
                        ),
                        write_summary,
                        hygiene_summary,
                    ),
                    layered_total_score=total_layered_score,
                    adjacent_total_delta_points=adjacent_delta,
                    total_uplift_points=total_uplift,
                    available_layers=available_layers,
                    unavailable_layers=unavailable_layers,
                )
            )
            previous_score = total_layered_score
    return tuple(summaries)


def _aggregate_layer(
    rows: Sequence[dict[str, object]],
    layer_name: str,
    component_names: Sequence[str],
) -> LayeredComponentBreakdown:
    score_values: list[float] = []
    component_values: dict[str, list[float]] = {name: [] for name in component_names}
    unavailable_reasons: set[str] = set()
    for row in rows:
        score_key = f"{layer_name}_score"
        component_key = "write_components" if layer_name == "write_governance" else "hygiene_components"
        reasons_key = (
            "write_unavailable_reasons"
            if layer_name == "write_governance"
            else "hygiene_unavailable_reasons"
        )
        layer_score = row[score_key]
        if isinstance(layer_score, (int, float)):
            score_values.append(float(layer_score))
        else:
            unavailable_reasons.update(
                str(reason) for reason in row.get(reasons_key, ())
            )
        component_dict = row[component_key]
        for name in component_names:
            value = component_dict.get(name)
            if isinstance(value, (int, float)):
                component_values[name].append(float(value))
    if not score_values:
        return LayeredComponentBreakdown(
            layer_name=layer_name,
            score="unavailable",
            components={name: "unavailable" for name in component_names},
            unavailable_reasons=tuple(sorted(unavailable_reasons or {"no_supporting_rows"})),
        )
    score = round(sum(score_values) / len(score_values), 4)
    components = {
        name: round(sum(values) / len(values), 4) if values else "unavailable"
        for name, values in component_values.items()
    }
    return LayeredComponentBreakdown(
        layer_name=layer_name,
        score=score,
        components=components,
        unavailable_reasons=(),
    )


def _summary_total_for_profile(
    answer_lookup: dict[tuple[str, str], QuantitativeProfileSummary],
    case_set: str,
    profile_name: str,
) -> float:
    row = answer_lookup[(case_set, profile_name)]
    return calculate_answer_layer_score(row)


def _build_report_metrics(
    cases: Sequence[EvalCase],
    summaries: Sequence[LayeredProfileSummary],
    case_records: Sequence[dict[str, object]],
) -> dict[str, object]:
    overall_baseline = _summary_lookup(summaries, "overall", "chain_memory_base")
    overall_final = _summary_lookup(summaries, "overall", "chain_all_on")
    common_final = _maybe_summary_lookup(summaries, "common", "chain_all_on")
    hard_final = _maybe_summary_lookup(summaries, "hard", "chain_all_on")
    total_uplift_points = round(
        overall_final.layered_total_score - overall_baseline.layered_total_score,
        4,
    )
    total_uplift_pct = (
        round(total_uplift_points / overall_baseline.layered_total_score * 100.0, 4)
        if overall_baseline.layered_total_score
        else None
    )
    overall_steps = [
        row
        for row in summaries
        if row.case_set == "overall" and row.profile_name != "chain_memory_base"
    ]
    strongest = max(overall_steps, key=lambda row: row.adjacent_total_delta_points, default=None)
    weakest = min(overall_steps, key=lambda row: row.adjacent_total_delta_points, default=None)
    return {
        "measurement_mode": "offline_trace_layered_scoring",
        "case_count": len(cases),
        "common_case_count": sum(1 for case in cases if case.id.startswith("common_")),
        "hard_case_count": sum(1 for case in cases if case.id.startswith("hard_")),
        "profile_count": len(CHAIN_PROFILES),
        "layer_count": 3,
        "case_record_count": len(case_records),
        "profile_summary_count": len(summaries),
        "baseline_total_layered_score": overall_baseline.layered_total_score,
        "final_total_layered_score": overall_final.layered_total_score,
        "total_layered_uplift_points": total_uplift_points,
        "total_layered_uplift_pct": total_uplift_pct,
        "common_total_layered_score": common_final.layered_total_score
        if common_final
        else "unavailable",
        "hard_total_layered_score": hard_final.layered_total_score
        if hard_final
        else "unavailable",
        "final_profile_name": overall_final.profile_name,
        "strongest_step": strongest.profile_name if strongest else "unavailable",
        "strongest_step_delta": strongest.adjacent_total_delta_points
        if strongest
        else "unavailable",
        "weakest_step": weakest.profile_name if weakest else "unavailable",
        "weakest_step_delta": weakest.adjacent_total_delta_points if weakest else "unavailable",
        "score_formulas": {
            "answer_layer": ANSWER_LAYER_FORMULA,
            "write_governance": "write_governance_score = 0.35 * useful_write_precision_score + 0.25 * pollution_block_score + 0.15 * duplicate_control_score + 0.15 * review_safety_score + 0.10 * write_reduction_score",
            "memory_hygiene": "memory_hygiene_score = 0.25 * source_ref_health_score + 0.20 * stale_cleanup_signal_score + 0.20 * duplicate_merge_signal_score + 0.15 * conflict_resolution_signal_score + 0.10 * low_value_cleanup_signal_score + 0.10 * token_saving_score",
            "layered_total": LAYERED_TOTAL_FORMULA,
        },
    }


def _summary_lookup(
    summaries: Sequence[LayeredProfileSummary],
    case_set: str,
    profile_name: str,
) -> LayeredProfileSummary:
    for row in summaries:
        if row.case_set == case_set and row.profile_name == profile_name:
            return row
    raise KeyError((case_set, profile_name))


def _maybe_summary_lookup(
    summaries: Sequence[LayeredProfileSummary],
    case_set: str,
    profile_name: str,
) -> LayeredProfileSummary | None:
    try:
        return _summary_lookup(summaries, case_set, profile_name)
    except KeyError:
        return None


def _trace_for_layer(profile: Any, feature_name: str) -> Any | None:
    return profile.traces.get(feature_name)


def _trace_metrics(profile: Any, feature_name: str) -> dict[str, object]:
    trace = _trace_for_layer(profile, feature_name)
    return dict(trace.metrics) if trace is not None else {}


def _preferred_profile(case_result: EvalCaseResult) -> Any:
    if "all" in case_result.profiles:
        return case_result.profiles["all"]
    if "off" in case_result.profiles:
        return case_result.profiles["off"]
    return next(iter(case_result.profiles.values()))


def _summary_from_record(
    record: dict[str, object],
    case_set: str,
    profile_name: str,
) -> QuantitativeProfileSummary:
    return QuantitativeProfileSummary(
        profile_name=profile_name,
        feature_name=str(record.get("feature_name") or CHAIN_PROFILE_LABELS[profile_name]),
        case_set=case_set,
        case_count=1,
        target_count=int(record.get("target_count") or 0),
        success_count=int(record.get("success_count") or 0),
        miss_count=int(record.get("miss_count") or 0),
        recall_rate=float(record.get("recall_rate") or 0.0),
        grounding_count=int(record.get("grounding_count") or 0),
        forbidden_count=int(record.get("forbidden_count") or 0),
        repeat_count=1,
        answer_rule_pass_rate=float(record.get("answer_rule_pass_rate") or 0.0),
        memory_grounding_pass_rate=float(record.get("memory_grounding_pass_rate") or 0.0),
        forbidden_violation_rate=float(record.get("forbidden_violation_rate") or 0.0),
        main_score=float(record.get("main_score") or 0.0),
        baseline_score=float(record.get("baseline_score") or 0.0),
        uplift_points=float(record.get("uplift_points") or 0.0),
        uplift_pct=record.get("uplift_pct"),  # type: ignore[assignment]
        token_signal_kind=str(record.get("token_signal_kind") or "unavailable"),
        token_signal_value=record.get("token_signal_value", "unavailable"),
        token_signal_delta=record.get("token_signal_delta", "unavailable"),
        latency_ms=record.get("latency_ms", "unavailable"),
        latency_delta_ms=record.get("latency_delta_ms", "unavailable"),
        unavailable=tuple(record.get("unavailable", ())),
    )


def _case_set(case: EvalCase) -> str:
    if case.id.startswith("common_"):
        return "common"
    if case.id.startswith("hard_"):
        return "hard"
    return "overall"


def _clamp_0_100(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def _required_metric(
    metrics: dict[str, object],
    key: str,
) -> float | None:
    value = metrics.get(key, None)
    if value is None or not isinstance(value, (int, float)):
        return None
    return float(value)


def _missing_reasons(metrics: dict[str, object], keys: Sequence[str]) -> tuple[str, ...]:
    reasons: list[str] = []
    for key in keys:
        value = metrics.get(key, None)
        if value is None:
            reasons.append(f"{key}:missing")
        elif not isinstance(value, (int, float)):
            reasons.append(f"{key}:non_numeric")
    return tuple(reasons)


def _weighted_available(
    items: Sequence[tuple[str, float, float | str]],
) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    available = [
        (name, weight, float(value))
        for name, weight, value in items
        if isinstance(value, (int, float))
    ]
    unavailable = tuple(name for name, _, value in items if not isinstance(value, (int, float)))
    if not available:
        return 0.0, tuple(name for name, _, _ in available), unavailable
    weight_sum = sum(weight for _, weight, _ in available)
    score = (
        round(sum(weight * value for _, weight, value in available) / weight_sum, 4)
        if weight_sum
        else 0.0
    )
    return score, tuple(name for name, _, _ in available), unavailable


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return str(value)
    return str(value)


def _deterministic_run_id(cases: Sequence[EvalCase], profile_names: Sequence[str]) -> str:
    payload = "|".join(
        [str(len(cases))]
        + [case.id for case in cases]
        + list(profile_names)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _breakdown_by_layer(
    row: LayeredProfileSummary,
    layer_name: str,
) -> LayeredComponentBreakdown:
    for item in row.layer_breakdowns:
        if item.layer_name == layer_name:
            return item
    raise KeyError(layer_name)


if __name__ == "__main__":
    raise SystemExit(main())
