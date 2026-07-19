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
    token_cost: float | str
    token_cost_delta: float | str
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
    case_records: list[dict[str, object]] = []
    per_case_rows: list[dict[str, object]] = []

    for case in cases:
        case_set = _case_set(case)
        for profile_name in REPORT_PROFILES:
            row = _score_case_profile(case, case_set, profile_name)
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
        generated_at=datetime.now(timezone.utc).isoformat(),
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
        "| profile | case_set | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_cost | token_cost_delta | latency_ms | latency_delta_ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
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
            "| case_set | profile | main_score | uplift_points | answer | grounding | forbidden | token_cost_delta | latency_delta_ms |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
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
                    _fmt(row.token_cost_delta),
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
            "- `token_cost` / `latency_ms` 若无直接可用值，会标记为 `unavailable`。",
            "- `all_on` 行展示组合态的原始聚合，不额外加成。",
            "- `feature_contributions` 只展示 overall 视角，便于看单项开关的净增益。",
            "- `off` 作为 baseline，只用于对比，不应单独解读为生产结论。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


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
    case_set: str,
    profile_name: str,
) -> dict[str, object]:
    family_scores = tuple(
        _score_family(
            case=case,
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
                "token_cost": "unavailable",
                "latency_ms": "unavailable",
                "unavailable": ("token_cost", "latency_ms"),
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
    token_cost = _first_available(row["token_cost"] for row in family_scores)
    latency_ms = _first_available(row["latency_ms"] for row in family_scores)
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
        "token_cost": token_cost,
        "latency_ms": latency_ms,
        "unavailable": unavailable,
    }


def _score_family(
    *,
    case: EvalCase,
    profile_name: str,
    family_name: str,
) -> dict[str, object]:
    if profile_name == "off":
        return {
            "family_name": family_name,
            "answer_rule_pass_rate": 0.0,
            "memory_grounding_pass_rate": 0.0,
            "forbidden_violation_rate": 0.0,
            "token_cost": "unavailable",
            "latency_ms": "unavailable",
            "unavailable": ("token_cost", "latency_ms"),
        }

    trace = _family_trace_for_case(case, family_name)
    if trace is None:
        return {
            "family_name": family_name,
            "answer_rule_pass_rate": 0.0,
            "memory_grounding_pass_rate": 0.0,
            "forbidden_violation_rate": 0.0,
            "token_cost": "unavailable",
            "latency_ms": "unavailable",
            "unavailable": (family_name, "token_cost", "latency_ms"),
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
        return _score_provenance_family(
            trace,
            forbidden_ids=forbidden_ids,
        )
    if family_name == "sleep_consolidation_shadow":
        return _score_sleep_family(trace)
    return {
        "family_name": family_name,
        "answer_rule_pass_rate": 0.0,
        "memory_grounding_pass_rate": 0.0,
        "forbidden_violation_rate": 0.0,
        "token_cost": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": (family_name, "token_cost", "latency_ms"),
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
        "token_cost": candidate_count,
        "latency_ms": "unavailable",
        "unavailable": ("latency_ms",),
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
        "token_cost": "unavailable",
        "latency_ms": latency,
        "unavailable": ("token_cost",) if latency != "unavailable" else ("token_cost",),
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
        "token_cost": prompt_token_delta,
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
        "token_cost": prompt_token_delta,
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
        "token_cost": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": ("token_cost", "latency_ms"),
    }


def _score_provenance_family(trace: Any, *, forbidden_ids: tuple[str, ...]) -> dict[str, object]:
    source_ref_coverage = float(trace.metrics.get("source_ref_coverage", 0.0) or 0.0) * 100.0
    parse_success_rate = float(trace.metrics.get("parse_success_rate", 0.0) or 0.0) * 100.0
    cross_scope_risk_count = max(0, int(trace.metrics.get("cross_scope_risk_count", 0) or 0))
    cross_scope_memory_count = max(
        0, int(trace.metrics.get("cross_scope_memory_count", 0) or 0)
    )
    grounding = _avg([source_ref_coverage, parse_success_rate])
    forbidden = _ratio(cross_scope_risk_count, max(1, cross_scope_memory_count))
    if forbidden_ids:
        forbidden = max(forbidden, _ratio(cross_scope_memory_count, max(1, cross_scope_memory_count)))
    return {
        "family_name": "provenance_shadow",
        "answer_rule_pass_rate": source_ref_coverage,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden * 100.0,
        "token_cost": "unavailable",
        "latency_ms": "unavailable",
        "unavailable": ("token_cost", "latency_ms"),
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
    token_cost = estimated_token_saving
    return {
        "family_name": "sleep_consolidation_shadow",
        "answer_rule_pass_rate": answer,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden,
        "token_cost": token_cost,
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
            token_cost_delta = _delta_value(
                aggregate["token_cost"], baseline.get("token_cost") if baseline else "unavailable",
            )
            latency_delta_ms = _delta_value(
                aggregate["latency_ms"], baseline.get("latency_ms") if baseline else "unavailable",
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
                    token_cost=aggregate["token_cost"],
                    token_cost_delta=token_cost_delta,
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
    token_cost_values = [row["token_cost"] for row in rows if isinstance(row["token_cost"], (int, float))]
    latency_values = [row["latency_ms"] for row in rows if isinstance(row["latency_ms"], (int, float))]
    return {
        "case_count": len(rows),
        "answer_rule_pass_rate": answer,
        "memory_grounding_pass_rate": grounding,
        "forbidden_violation_rate": forbidden,
        "main_score": main_score,
        "token_cost": _maybe_sum(token_cost_values),
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
        "common_main_score": common.main_score if common else 0.0,
        "hard_main_score": hard.main_score if hard else 0.0,
        "common_baseline_main_score": common_baseline.main_score if common_baseline else 0.0,
        "hard_baseline_main_score": hard_baseline.main_score if hard_baseline else 0.0,
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
        f"{_fmt(row.forbidden_violation_rate)} | {_fmt(row.token_cost)} | "
        f"{_fmt(row.token_cost_delta)} | {_fmt(row.latency_ms)} | "
        f"{_fmt(row.latency_delta_ms)} |"
    )


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


def _first_available(values: Iterable[object]) -> float | str:
    for value in values:
        if isinstance(value, (int, float)):
            return round(float(value), 4)
    return "unavailable"


def _delta_value(
    profile_value: float | str,
    baseline_value: float | str,
) -> float | str:
    if isinstance(profile_value, (int, float)):
        if isinstance(baseline_value, (int, float)):
            return round(float(profile_value) - float(baseline_value), 4)
        return round(float(profile_value), 4)
    if isinstance(baseline_value, (int, float)):
        return round(-float(baseline_value), 4)
    return "unavailable"


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
