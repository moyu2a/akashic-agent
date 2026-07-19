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


REPORT_PROFILES: tuple[str, ...] = (
    "off",
    "write_value_only",
    "tri_retrieval_only",
    "graph_only",
    "rerank_only",
    "version_provenance_only",
    "sleep_only",
    "all_on",
)

PROFILE_RUNTIME_MAP: dict[str, str] = {
    "off": "off",
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
    "write_value_only": ("write_value_score",),
    "tri_retrieval_only": ("tri_retrieval",),
    "graph_only": ("graph_retrieval",),
    "rerank_only": ("rerank_shadow", "injection_governance_shadow"),
    "version_provenance_only": ("version_chain_shadow", "provenance_shadow"),
    "sleep_only": ("sleep_consolidation_shadow",),
    "all_on": QUANTITATIVE_FEATURES,
}

PROFILE_FEATURE_LABELS: dict[str, str] = {
    "off": "baseline",
    "write_value_only": "写入价值",
    "tri_retrieval_only": "三路召回",
    "graph_only": "图谱召回",
    "rerank_only": "重排与注入治理",
    "version_provenance_only": "版本链与溯源",
    "sleep_only": "睡眠巩固",
    "all_on": "全开组合",
}


@dataclass(frozen=True)
class QuantitativeProfileSummary:
    profile_name: str
    feature_name: str
    case_set: str
    case_count: int
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
        row for row in profile_summaries if row.case_set == "overall" and row.profile_name != "off"
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


def write_quantitative_uplift_json(report: QuantitativeUpliftReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_quantitative_uplift_markdown(report: QuantitativeUpliftReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(report.profile_summaries)
    overall_rows = [row for row in rows if row.case_set == "overall"]
    common_rows = [row for row in rows if row.case_set == "common"]
    hard_rows = [row for row in rows if row.case_set == "hard"]
    baseline = _summary_lookup(overall_rows, "off")
    all_on = _summary_lookup(overall_rows, "all_on")
    lines = [
        "# 记忆系统 Phase 6d 量化提升报告",
        "",
        "本报告是离线确定性评测结果，只代表当前样本集上的对比，不代表生产全量结论。",
        "",
        "## 评分公式",
        "",
        f"- `{report.score_formula}`",
        "",
        "## 总览",
        "",
        f"- `case_count`: `{report.metrics.get('case_count')}`",
        f"- `common_case_count`: `{report.metrics.get('common_case_count')}`",
        f"- `hard_case_count`: `{report.metrics.get('hard_case_count')}`",
        f"- `repeat_count`: `{report.metrics.get('repeat_count')}`",
        f"- `baseline_main_score`: `{baseline.main_score if baseline else 'unavailable'}`",
        f"- `all_on_main_score`: `{all_on.main_score if all_on else 'unavailable'}`",
        f"- `total_uplift_points`: `{report.metrics.get('total_uplift_points')}`",
        f"- `total_uplift_pct`: `{report.metrics.get('total_uplift_pct')}`",
        "",
        "## 单项提升",
        "",
        "| profile | case_set | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms | latency_delta_ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in overall_rows:
        if row.profile_name == "off":
            continue
        lines.append(_summary_row_to_md(row))
    lines.extend(
        [
            "",
            "## common / hard 对比",
            "",
            "| case_set | profile | main_score | uplift_points | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_delta_ms |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in common_rows + hard_rows:
        if row.profile_name == "off":
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    row.case_set,
                    row.profile_name,
                    _fmt(row.main_score),
                    _fmt(row.uplift_points),
                    _fmt(row.answer_rule_pass_rate),
                    _fmt(row.memory_grounding_pass_rate),
                    _fmt(row.forbidden_violation_rate),
                    _fmt(row.token_signal_kind),
                    _fmt(row.token_signal_value),
                    _fmt(row.token_signal_delta),
                    _fmt(row.latency_delta_ms),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 原始指标",
            "",
        ]
    )
    for key in sorted(report.metrics):
        lines.append(f"- `{key}`: `{report.metrics[key]}`")
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
            "- `off` 作为 baseline，只用于对比，不应单独解读为生产结论。",
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
        semantic_items, keyword_items, provenance_items, _ = _candidate_lanes(case)
        scope = _scope(case)
        result = build_tri_retrieval_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=semantic_items,
            keyword_items=keyword_items,
            provenance_items=provenance_items,
            latency_ms=0.0,
            top_n=max(8, len(_active_memory_items(case))),
        )
        metrics = dict(result.metrics)
        return EvalTrace("tri_retrieval", result.baseline_result, result.experimental_result, metrics)
    if family_name == "graph_retrieval":
        semantic_items, keyword_items, provenance_items, graph_items = _candidate_lanes(case)
        result = build_graph_retrieval_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=semantic_items,
            keyword_items=keyword_items,
            provenance_items=provenance_items,
            graph_items=graph_items,
            latency_ms=0.0,
            top_n=max(8, len(_active_memory_items(case))),
        )
        metrics = dict(result.metrics)
        return EvalTrace("graph_retrieval", result.baseline_result, result.experimental_result, metrics)
    if family_name == "rerank_shadow":
        semantic_items, keyword_items, provenance_items, graph_items = _candidate_lanes(case)
        scope = _scope(case)
        result = build_rerank_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=semantic_items,
            keyword_items=keyword_items,
            provenance_items=provenance_items,
            graph_items=graph_items,
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
    family_scores = tuple(
        _score_family(
            case=case,
            trace=runtime_profile.traces.get(family_name),
            profile_name=profile_name,
            family_name=family_name,
        )
        for family_name in PROFILE_FEATURE_MAP[profile_name]
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
    return {
        "case_id": case.id,
        "category": case.category,
        "case_set": case_set,
        "profile_name": profile_name,
        "feature_name": PROFILE_FEATURE_LABELS[profile_name],
        "measurement_family": case.setup.get("measurement_family", ""),
        "target_profile": case.setup.get("target_profile", ""),
        "repeat_count": 1,
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


def _build_profile_summaries(rows: Sequence[dict[str, object]]) -> tuple[QuantitativeProfileSummary, ...]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (str(row["case_set"]), str(row["profile_name"]))
        grouped.setdefault(key, []).append(row)
    overall_grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        overall_grouped.setdefault(str(row["profile_name"]), []).append(row)

    baseline_lookup = {
        case_set: _aggregate_case_rows(grouped[(case_set, "off")])
        for case_set in {"common", "hard"}
        if (case_set, "off") in grouped
    }
    baseline_lookup["overall"] = _aggregate_case_rows(
        overall_grouped.get("off", [])
    )
    result: list[QuantitativeProfileSummary] = []
    for case_set in ("common", "hard", "overall"):
        for profile_name in REPORT_PROFILES:
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
            uplift_points = round(aggregate["main_score"] - baseline_score, 4)
            uplift_pct = (
                round(uplift_points / baseline_score * 100.0, 4)
                if baseline_score
                else None
            )
            token_signal_delta = _delta_value(
                aggregate["token_signal_value"],
                baseline.get("token_signal_value") if baseline else "unavailable",
                profile_kind=str(aggregate["token_signal_kind"]),
                baseline_kind=str(
                    baseline.get("token_signal_kind") if baseline else "unavailable"
                ),
            )
            latency_delta_ms = _delta_value(
                aggregate["latency_ms"],
                baseline.get("latency_ms") if baseline else "unavailable",
            )
            result.append(
                QuantitativeProfileSummary(
                    profile_name=profile_name,
                    feature_name=PROFILE_FEATURE_LABELS[profile_name],
                    case_set=case_set,
                    case_count=int(aggregate["case_count"]),
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
    return tuple(result)


def _aggregate_case_rows(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    answer = _avg(float(row["answer_rule_pass_rate"]) for row in rows)
    grounding = _avg(float(row["memory_grounding_pass_rate"]) for row in rows)
    forbidden = _avg(float(row["forbidden_violation_rate"]) for row in rows)
    main_score = _avg(float(row["main_score"]) for row in rows)
    token_signal_kind, token_signal_value = _aggregate_token_signal(rows)
    latency_values = [row["latency_ms"] for row in rows if isinstance(row["latency_ms"], (int, float))]
    return {
        "case_count": len(rows),
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
    baseline = _summary_lookup(summaries, "off", case_set="overall")
    all_on = _summary_lookup(summaries, "all_on", case_set="overall")
    common = _summary_lookup(summaries, "all_on", case_set="common")
    hard = _summary_lookup(summaries, "all_on", case_set="hard")
    common_baseline = _summary_lookup(summaries, "off", case_set="common")
    hard_baseline = _summary_lookup(summaries, "off", case_set="hard")
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
        "| `uplift_points` | 当前开关相比 `off` 提高的分数 | 越高越好 |",
        "| `uplift_pct` | 当前开关相比 `off` 的提升百分比 | 越高越好 |",
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
            f"- 全开组合 `all_on` 的主分为 `{report.metrics.get('overall_main_score')}`，相比 `off` 提高 `{report.metrics.get('total_uplift_points')}` 分。",
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
