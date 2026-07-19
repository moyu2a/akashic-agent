from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from memory2.eval_cases import EvalCase
from memory2.eval_runner import EvalCaseResult, EvalProfileResult, EvalRunReport, EvalTrace


@dataclass(frozen=True)
class UpliftFeatureRecord:
    case_id: str
    category: str
    profile: str
    phase: str
    feature_name: str
    expected_ids: tuple[str, ...]
    forbidden_ids: tuple[str, ...]
    baseline_score: float
    experimental_score: float
    uplift: float
    metric_kind: str
    metric_name: str
    baseline_ids: tuple[str, ...]
    experimental_ids: tuple[str, ...]
    positive_signal_count: int
    negative_signal_count: int
    token_delta: int
    estimated_token_saving: int
    notes: tuple[str, ...]


@dataclass(frozen=True)
class UpliftPhaseSummary:
    phase: str
    evaluated_case_count: int
    feature_record_count: int
    avg_baseline_score: float
    avg_experimental_score: float
    avg_uplift: float
    positive_signal_count: int
    negative_signal_count: int
    total_token_delta: int
    estimated_token_saving: int


@dataclass(frozen=True)
class UpliftReport:
    feature_records: tuple[UpliftFeatureRecord, ...]
    phase_summaries: dict[str, UpliftPhaseSummary]
    metrics: dict[str, Any]


def build_uplift_report(
    cases: Sequence[EvalCase],
    eval_report: EvalRunReport,
) -> UpliftReport:
    case_by_id = {case.id: case for case in cases}
    records = tuple(
        record
        for result_case in eval_report.cases
        for profile in result_case.profiles.values()
        for record in _profile_feature_records(
            case_by_id[result_case.case_id],
            result_case,
            profile,
        )
    )
    summaries = _phase_summaries(records)
    metrics = _report_metrics(eval_report, records, summaries)
    return UpliftReport(
        feature_records=records,
        phase_summaries=summaries,
        metrics=metrics,
    )


def write_uplift_json(report: UpliftReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metrics": report.metrics,
        "phase_summaries": {
            phase: _phase_summary_to_dict(summary)
            for phase, summary in report.phase_summaries.items()
        },
        "feature_records": [
            _feature_record_to_dict(record) for record in report.feature_records
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_uplift_markdown(report: UpliftReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Memory Offline Uplift Proxy Report",
        "",
        "本报告基于离线 fixture traces，反映 proxy uplift，不代表线上答案质量或生产效果。",
        "",
        "## Summary",
        "",
    ]
    for key in sorted(report.metrics):
        lines.append(f"- `{key}`: `{report.metrics[key]}`")
    lines.extend(["", "## Phase Summaries", ""])
    for phase in _ordered_phases(report.feature_records):
        summary = report.phase_summaries[phase]
        lines.append(
            f"- `{phase}`: `{json.dumps(_phase_summary_to_dict(summary), ensure_ascii=False, sort_keys=True)}`"
        )
    lines.extend(["", "## Feature Records", ""])
    for record in report.feature_records:
        lines.append(
            f"- `{record.case_id}/{record.profile}/{record.feature_name}`: "
            f"`{json.dumps(_feature_record_to_dict(record), ensure_ascii=False, sort_keys=True)}`"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _profile_phase(profile: str) -> str:
    if profile in {"phase2", "phase3", "phase4", "phase5", "all"}:
        return profile
    return profile


def _profile_feature_records(
    source_case: EvalCase,
    result_case: EvalCaseResult,
    profile: EvalProfileResult,
) -> tuple[UpliftFeatureRecord, ...]:
    if profile.profile in {"off", "phase1"}:
        return ()
    return tuple(
        _trace_record(source_case, result_case, profile, trace)
        for trace in profile.traces.values()
        if trace.feature_name
    )


def _trace_record(
    source_case: EvalCase,
    case: EvalCaseResult,
    profile: EvalProfileResult,
    trace: EvalTrace,
) -> UpliftFeatureRecord:
    if trace.feature_name in {"tri_retrieval", "graph_retrieval"}:
        return _retrieval_record(source_case, case, profile, trace)
    if trace.feature_name in {"rerank_shadow", "injection_governance_shadow"}:
        return _injection_or_rerank_record(source_case, case, profile, trace)
    if trace.feature_name in {"version_chain_shadow", "provenance_shadow"}:
        return _consistency_or_provenance_record(source_case, case, profile, trace)
    if trace.feature_name == "sleep_consolidation_shadow":
        return _consolidation_record(source_case, case, profile, trace)
    return _generic_record(source_case, case, profile, trace)


def _retrieval_record(
    source_case: EvalCase,
    result_case: EvalCaseResult,
    profile: EvalProfileResult,
    trace: EvalTrace,
) -> UpliftFeatureRecord:
    expected_ids = _case_expectation_ids(source_case, "should_recall_ids")
    forbidden_ids = _case_expectation_ids(source_case, "should_not_recall_ids")
    baseline_ids = _ids(
        trace.baseline_result.get("baseline_ids")
        or trace.baseline_result.get("baseline_fused_ids")
    )
    experimental_ids = _ids(
        trace.experimental_result.get("fused_ids")
        or trace.experimental_result.get("graph_fused_ids")
    )
    baseline_score = _round_score(
        _label_hit_rate(baseline_ids, expected_ids)
        - _label_violation_rate(baseline_ids, forbidden_ids)
    )
    experimental_score = _round_score(
        _label_hit_rate(experimental_ids, expected_ids)
        - _label_violation_rate(experimental_ids, forbidden_ids)
    )
    lane_contribution = trace.metrics.get("lane_contribution")
    graph_hit_count = int(trace.metrics.get("graph_hit_count", 0) or 0)
    provenance_hit_count = int(trace.metrics.get("provenance_hit_count", 0) or 0)
    positive_signal_count = _contribution_total(lane_contribution) + graph_hit_count + provenance_hit_count
    negative_signal_count = (
        len(set(experimental_ids) - set(expected_ids))
        + len(set(experimental_ids) & set(forbidden_ids))
    )
    return _record(
        source_case,
        result_case,
        profile,
        trace,
        metric_kind="retrieval_proxy",
        metric_name="label_hit_rate",
        baseline_score=baseline_score,
        experimental_score=experimental_score,
        expected_ids=expected_ids,
        forbidden_ids=forbidden_ids,
        baseline_ids=baseline_ids,
        experimental_ids=experimental_ids,
        positive_signal_count=positive_signal_count,
        negative_signal_count=negative_signal_count,
        token_delta=0,
        estimated_token_saving=0,
        notes=(
            "retrieval proxy scored against should_recall_ids and should_not_recall_ids",
            f"lane_contribution={lane_contribution!r}",
        ),
    )


def _injection_or_rerank_record(
    source_case: EvalCase,
    result_case: EvalCaseResult,
    profile: EvalProfileResult,
    trace: EvalTrace,
) -> UpliftFeatureRecord:
    expected_ids = _case_expectation_ids(source_case, "should_recall_ids")
    forbidden_ids = _case_expectation_ids(source_case, "should_not_recall_ids")
    if trace.feature_name == "injection_governance_shadow":
        baseline_ids = _ids(trace.baseline_result.get("baseline_injected_ids"))
        experimental_ids = _ids(trace.experimental_result.get("experimental_injected_ids"))
        low_confidence_injected_count = int(
            trace.metrics.get("low_confidence_injected_count", 0) or 0
        )
        baseline_score = _round_score(max(0.0, 1.0 - low_confidence_injected_count))
        experimental_score = 1.0 if low_confidence_injected_count == 0 else 0.0
        positive_signal_count = int(trace.metrics.get("dropped_count", 0) or 0) + int(
            trace.metrics.get("newly_injected_count", 0) or 0
        )
        negative_signal_count = low_confidence_injected_count
        token_delta = int(trace.metrics.get("prompt_token_delta", 0) or 0)
        return _record(
            source_case,
            result_case,
            profile,
            trace,
            metric_kind="injection_proxy",
            metric_name="injection_quality",
            baseline_score=baseline_score,
            experimental_score=experimental_score,
            expected_ids=expected_ids,
            forbidden_ids=forbidden_ids,
            baseline_ids=baseline_ids,
            experimental_ids=experimental_ids,
            positive_signal_count=positive_signal_count,
            negative_signal_count=negative_signal_count,
            token_delta=token_delta,
            estimated_token_saving=0,
            notes=(
                "injection proxy uses low_confidence_injected_count",
                f"prompt_token_delta={token_delta}",
            ),
        )

    baseline_ids = _ids(trace.baseline_result.get("baseline_ids"))
    experimental_ids = _ids(trace.experimental_result.get("reranked_ids"))
    baseline_score = _round_score(
        _label_hit_rate(baseline_ids, expected_ids)
        - _label_violation_rate(baseline_ids, forbidden_ids)
    )
    experimental_score = _round_score(
        _label_hit_rate(experimental_ids, expected_ids)
        - _label_violation_rate(experimental_ids, forbidden_ids)
    )
    positive_signal_count = int(trace.metrics.get("rerank_changed_count", 0) or 0) + int(
        trace.metrics.get("scope_match_count", 0) or 0
    )
    negative_signal_count = len(set(experimental_ids) & set(forbidden_ids))
    return _record(
        source_case,
        result_case,
        profile,
        trace,
        metric_kind="injection_proxy",
        metric_name="label_hit_rate",
        baseline_score=baseline_score,
        experimental_score=experimental_score,
        expected_ids=expected_ids,
        forbidden_ids=forbidden_ids,
        baseline_ids=baseline_ids,
        experimental_ids=experimental_ids,
        positive_signal_count=positive_signal_count,
        negative_signal_count=negative_signal_count,
        token_delta=0,
        estimated_token_saving=0,
        notes=(
            "rerank proxy tracks changed and scope-matched candidates",
            f"rerank_changed_count={trace.metrics.get('rerank_changed_count', 0)}",
        ),
    )


def _consistency_or_provenance_record(
    source_case: EvalCase,
    result_case: EvalCaseResult,
    profile: EvalProfileResult,
    trace: EvalTrace,
) -> UpliftFeatureRecord:
    expected_ids = _case_expectation_ids(source_case, "should_recall_ids")
    forbidden_ids = _case_expectation_ids(source_case, "should_not_recall_ids")
    baseline_ids = _ids(trace.baseline_result.get("baseline_recalled_ids"))
    if trace.feature_name == "version_chain_shadow":
        experimental_ids = _ids(trace.experimental_result.get("active_leaf_ids"))
        positive_signal_count = (
            int(trace.metrics.get("stale_recalled_count", 0) or 0)
            + int(trace.metrics.get("conflict_chain_count", 0) or 0)
            + int(trace.metrics.get("rollback_candidate_count", 0) or 0)
        )
        metric_kind = "consistency_proxy"
        metric_name = "diagnostic_signal_presence"
    else:
        experimental_ids = _ids(trace.experimental_result.get("cross_scope_memory_ids"))
        positive_signal_count = (
            int(round(float(trace.metrics.get("source_ref_coverage", 0.0) or 0.0)))
            + int(trace.metrics.get("orphan_memory_count", 0) or 0)
            + int(trace.metrics.get("cross_scope_memory_count", 0) or 0)
            + int(trace.metrics.get("message_level_source_count", 0) or 0)
            + int(trace.metrics.get("session_level_source_count", 0) or 0)
            + int(trace.metrics.get("span_level_source_count", 0) or 0)
        )
        metric_kind = "provenance_proxy"
        metric_name = "diagnostic_signal_presence"
    negative_signal_count = int(trace.metrics.get("superseded_recalled_count", 0) or 0) + int(
        trace.metrics.get("cross_scope_risk_count", 0) or 0
    )
    experimental_score = 1.0 if positive_signal_count > 0 else 0.0
    return _record(
        source_case,
        result_case,
        profile,
        trace,
        metric_kind=metric_kind,
        metric_name=metric_name,
        baseline_score=0.0,
        experimental_score=experimental_score,
        expected_ids=expected_ids,
        forbidden_ids=forbidden_ids,
        baseline_ids=baseline_ids,
        experimental_ids=experimental_ids,
        positive_signal_count=positive_signal_count,
        negative_signal_count=negative_signal_count,
        token_delta=0,
        estimated_token_saving=0,
        notes=(
            f"{trace.feature_name} proxy uses diagnostic signal presence",
            f"positive_signal_count={positive_signal_count}",
        ),
    )


def _consolidation_record(
    source_case: EvalCase,
    result_case: EvalCaseResult,
    profile: EvalProfileResult,
    trace: EvalTrace,
) -> UpliftFeatureRecord:
    expected_ids = _case_expectation_ids(source_case, "should_recall_ids")
    forbidden_ids = _case_expectation_ids(source_case, "should_not_recall_ids")
    baseline_ids = _ids(trace.baseline_result.get("baseline_item_ids"))
    experimental_ids = (
        _flatten_group_ids(trace.experimental_result.get("duplicate_groups"))
        + _flatten_group_ids(trace.experimental_result.get("merge_candidates"))
        + _ids(trace.experimental_result.get("stale_candidate_ids"))
        + _ids(trace.experimental_result.get("low_value_candidate_ids"))
        + _flatten_group_ids(trace.experimental_result.get("conflict_candidates"))
    )
    positive_signal_count = (
        int(trace.metrics.get("duplicate_group_count", 0) or 0)
        + int(trace.metrics.get("merge_candidate_count", 0) or 0)
        + int(trace.metrics.get("stale_candidate_count", 0) or 0)
        + int(trace.metrics.get("low_value_candidate_count", 0) or 0)
        + int(trace.metrics.get("conflict_candidate_count", 0) or 0)
    )
    estimated_token_saving = int(trace.metrics.get("estimated_token_saving", 0) or 0)
    return _record(
        source_case,
        result_case,
        profile,
        trace,
        metric_kind="consolidation_proxy",
        metric_name="diagnostic_signal_presence",
        baseline_score=0.0,
        experimental_score=1.0 if positive_signal_count > 0 else 0.0,
        expected_ids=expected_ids,
        forbidden_ids=forbidden_ids,
        baseline_ids=baseline_ids,
        experimental_ids=experimental_ids,
        positive_signal_count=positive_signal_count,
        negative_signal_count=0,
        token_delta=0,
        estimated_token_saving=estimated_token_saving,
        notes=(
            "consolidation proxy uses duplicate/merge/stale/low_value/conflict signals",
            f"estimated_token_saving={estimated_token_saving}",
        ),
    )


def _generic_record(
    source_case: EvalCase,
    result_case: EvalCaseResult,
    profile: EvalProfileResult,
    trace: EvalTrace,
) -> UpliftFeatureRecord:
    expected_ids = _case_expectation_ids(source_case, "should_recall_ids")
    forbidden_ids = _case_expectation_ids(source_case, "should_not_recall_ids")
    baseline_ids = _ids(
        trace.baseline_result.get("written_item_ids")
        or trace.baseline_result.get("baseline_ids")
        or trace.baseline_result.get("baseline_item_ids")
    )
    experimental_ids = _ids(
        trace.experimental_result.get("experimental_injected_ids")
        or trace.experimental_result.get("reranked_ids")
    )
    baseline_written_count = int(trace.metrics.get("baseline_written_count", 0) or 0)
    policy_reject_count = int(trace.metrics.get("policy_reject_count", 0) or 0)
    candidate_count = int(trace.metrics.get("candidate_count", 0) or 0)
    baseline_score = float(baseline_written_count)
    experimental_score = float(policy_reject_count)
    return _record(
        source_case,
        result_case,
        profile,
        trace,
        metric_kind="write_proxy",
        metric_name="write_reduction_count",
        baseline_score=baseline_score,
        experimental_score=experimental_score,
        expected_ids=expected_ids,
        forbidden_ids=forbidden_ids,
        baseline_ids=baseline_ids,
        experimental_ids=experimental_ids,
        positive_signal_count=policy_reject_count,
        negative_signal_count=max(candidate_count - policy_reject_count, 0),
        token_delta=0,
        estimated_token_saving=0,
        notes=(
            "generic write proxy fallback",
            f"candidate_count={candidate_count}",
        ),
    )


def _record(
    source_case: EvalCase,
    result_case: EvalCaseResult,
    profile: EvalProfileResult,
    trace: EvalTrace,
    *,
    metric_kind: str,
    metric_name: str,
    baseline_score: float,
    experimental_score: float,
    expected_ids: tuple[str, ...],
    forbidden_ids: tuple[str, ...],
    baseline_ids: tuple[str, ...],
    experimental_ids: tuple[str, ...],
    positive_signal_count: int,
    negative_signal_count: int,
    token_delta: int,
    estimated_token_saving: int,
    notes: tuple[str, ...],
) -> UpliftFeatureRecord:
    return UpliftFeatureRecord(
        case_id=result_case.case_id,
        category=result_case.category,
        profile=profile.profile,
        phase=_profile_phase(profile.profile),
        feature_name=trace.feature_name,
        expected_ids=expected_ids,
        forbidden_ids=forbidden_ids,
        baseline_score=_round_score(baseline_score),
        experimental_score=_round_score(experimental_score),
        uplift=_round_score(experimental_score - baseline_score),
        metric_kind=metric_kind,
        metric_name=metric_name,
        baseline_ids=baseline_ids,
        experimental_ids=experimental_ids,
        positive_signal_count=positive_signal_count,
        negative_signal_count=negative_signal_count,
        token_delta=token_delta,
        estimated_token_saving=estimated_token_saving,
        notes=notes,
    )


def _phase_summaries(
    records: tuple[UpliftFeatureRecord, ...],
) -> dict[str, UpliftPhaseSummary]:
    result: dict[str, UpliftPhaseSummary] = {}
    for phase in _ordered_phases(records):
        phase_records = tuple(record for record in records if record.phase == phase)
        result[phase] = UpliftPhaseSummary(
            phase=phase,
            evaluated_case_count=len({record.case_id for record in phase_records}),
            feature_record_count=len(phase_records),
            avg_baseline_score=_avg(record.baseline_score for record in phase_records),
            avg_experimental_score=_avg(
                record.experimental_score for record in phase_records
            ),
            avg_uplift=_avg(record.uplift for record in phase_records),
            positive_signal_count=sum(
                record.positive_signal_count for record in phase_records
            ),
            negative_signal_count=sum(
                record.negative_signal_count for record in phase_records
            ),
            total_token_delta=sum(record.token_delta for record in phase_records),
            estimated_token_saving=sum(
                record.estimated_token_saving for record in phase_records
            ),
        )
    return result


def _report_metrics(
    eval_report: EvalRunReport,
    records: tuple[UpliftFeatureRecord, ...],
    summaries: dict[str, UpliftPhaseSummary],
) -> dict[str, Any]:
    return {
        "phase6c_level": "offline_uplift_proxy",
        "offline_fixture_only": True,
        "llm_calls_enabled": False,
        "embedding_calls_enabled": False,
        "real_memory_db_enabled": False,
        "answer_quality_available": False,
        "production_uplift_claimed": False,
        "case_count": eval_report.metrics.get("case_count", len(eval_report.cases)),
        "profile_count": eval_report.metrics.get("profile_count", 0),
        "feature_record_count": len(records),
        "phase_summary_count": len(summaries),
        "overall_avg_uplift": _avg(record.uplift for record in records),
        "positive_signal_count": sum(
            record.positive_signal_count for record in records
        ),
        "negative_signal_count": sum(
            record.negative_signal_count for record in records
        ),
        "total_token_delta": sum(record.token_delta for record in records),
        "estimated_token_saving": sum(
            record.estimated_token_saving for record in records
        ),
    }


def _ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value if str(item))


def _label_hit_rate(candidate_ids: tuple[str, ...], target_ids: tuple[str, ...]) -> float:
    if not target_ids:
        return 0.0
    return round(len(set(candidate_ids) & set(target_ids)) / len(set(target_ids)), 4)


def _label_violation_rate(
    candidate_ids: tuple[str, ...],
    forbidden_ids: tuple[str, ...],
) -> float:
    if not forbidden_ids:
        return 0.0
    return round(
        len(set(candidate_ids) & set(forbidden_ids)) / len(set(forbidden_ids)),
        4,
    )


def _ordered_phases(records: Sequence[UpliftFeatureRecord]) -> tuple[str, ...]:
    order = ("phase2", "phase3", "phase4", "phase5", "all")
    seen = {record.phase for record in records}
    return tuple(phase for phase in order if phase in seen) + tuple(
        sorted(phase for phase in seen if phase not in order)
    )


def _avg(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _phase_summary_to_dict(summary: UpliftPhaseSummary) -> dict[str, Any]:
    return asdict(summary)


def _feature_record_to_dict(record: UpliftFeatureRecord) -> dict[str, Any]:
    return asdict(record)


def _case_expectation_ids(case: EvalCase, key: str) -> tuple[str, ...]:
    return _ids(case.expectations.get(key))


def _contribution_total(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    return sum(int(item or 0) for item in value.values())


def _flatten_group_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    result: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        result.extend(_ids(item.get("item_ids")))
    return tuple(result)


def _round_score(value: float) -> float:
    return round(float(value), 4)
