from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from memory2.eval_cases import EvalCase
from memory2.eval_quantitative_cases import QUANTITATIVE_FEATURES
from memory2.eval_quantitative_uplift import (
    QuantitativeProfileSummary,
    _build_profile_summaries,
    _case_set,
    _score_case_feature_set,
)
from memory2.eval_runner import run_eval_cases


ANSWER_SINGLE_PROFILES: tuple[str, ...] = (
    "memory_base",
    "tri_retrieval_only",
    "graph_only",
    "rerank_only",
    "version_provenance_only",
    "all_on",
)

ANSWER_CHAIN_PROFILES: tuple[str, ...] = (
    "chain_memory_base",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_all_on",
)

ANSWER_PROFILE_FEATURES: dict[str, tuple[str, ...]] = {
    "memory_base": (),
    "tri_retrieval_only": ("tri_retrieval",),
    "graph_only": ("graph_retrieval",),
    "rerank_only": ("rerank_shadow", "injection_governance_shadow"),
    "version_provenance_only": ("version_chain_shadow", "provenance_shadow"),
    "all_on": (
        "tri_retrieval",
        "graph_retrieval",
        "rerank_shadow",
        "injection_governance_shadow",
        "version_chain_shadow",
        "provenance_shadow",
    ),
}

ANSWER_CHAIN_PROFILE_FEATURES: dict[str, tuple[str, ...]] = {
    "chain_memory_base": (),
    "chain_tri_retrieval": ("tri_retrieval",),
    "chain_graph_retrieval": ("tri_retrieval", "graph_retrieval"),
    "chain_rerank_injection": (
        "tri_retrieval",
        "graph_retrieval",
        "rerank_shadow",
        "injection_governance_shadow",
    ),
    "chain_version_provenance": ANSWER_PROFILE_FEATURES["all_on"],
    "chain_all_on": ANSWER_PROFILE_FEATURES["all_on"],
}

ANSWER_PROFILE_LABELS: dict[str, str] = {
    "memory_base": "原始记忆基线",
    "tri_retrieval_only": "三路召回",
    "graph_only": "图谱召回",
    "rerank_only": "重排与注入治理",
    "version_provenance_only": "版本链与溯源",
    "all_on": "回答链路全开",
}

ANSWER_CHAIN_PROFILE_LABELS: dict[str, str] = {
    "chain_memory_base": "原始记忆基线",
    "chain_tri_retrieval": "加入三路召回",
    "chain_graph_retrieval": "加入图谱召回",
    "chain_rerank_injection": "加入重排与注入治理",
    "chain_version_provenance": "加入版本链与溯源",
    "chain_all_on": "回答链路全开校验",
}

_FORBIDDEN_ANSWER_FEATURES = {
    "write_value_score",
    "sleep_consolidation_shadow",
}

_FIXED_REPORT_TIME = datetime(2026, 7, 21, tzinfo=timezone.utc)


@dataclass(frozen=True)
class AnswerRetrievalCountReport:
    generated_at: str
    single_module_rows: tuple[dict[str, Any], ...]
    chain_rows: tuple[dict[str, Any], ...]
    metrics: dict[str, Any]


def build_answer_retrieval_count_report(
    cases: Sequence[EvalCase],
) -> AnswerRetrievalCountReport:
    eval_report = run_eval_cases(cases)
    if not eval_report.passed:
        failures = "\n".join(
            f"- {case.case_id}: {', '.join(case.failures) or 'unknown failure'}"
            for case in eval_report.cases
            if not case.passed
        )
        raise RuntimeError(
            "eval runner failed before answer retrieval report generation:\n"
            f"{failures or '- unknown failure'}"
        )
    case_results = {case.case_id: case for case in eval_report.cases}
    single_rows_raw: list[dict[str, object]] = []
    chain_rows_raw: list[dict[str, object]] = []
    for case in cases:
        case_set = _case_set(case)
        all_profile = case_results[case.id].profiles["all"]
        for profile in ANSWER_SINGLE_PROFILES:
            single_rows_raw.append(
                _score_case_feature_set(
                    case=case,
                    runtime_profile=all_profile,
                    case_set=case_set,
                    profile_name=profile,
                    feature_name=ANSWER_PROFILE_LABELS[profile],
                    feature_names=ANSWER_PROFILE_FEATURES[profile],
                )
            )
        for profile in ANSWER_CHAIN_PROFILES:
            chain_rows_raw.append(
                _score_case_feature_set(
                    case=case,
                    runtime_profile=all_profile,
                    case_set=case_set,
                    profile_name=profile,
                    feature_name=ANSWER_CHAIN_PROFILE_LABELS[profile],
                    feature_names=ANSWER_CHAIN_PROFILE_FEATURES[profile],
                )
            )
    single_all = {
        row.profile_name: row
        for row in _build_profile_summaries(
            single_rows_raw,
            profile_order=ANSWER_SINGLE_PROFILES,
            label_map=ANSWER_PROFILE_LABELS,
            baseline_profile="memory_base",
        )
        if row.case_set == "overall"
    }
    chain_all = {
        row.profile_name: row
        for row in _build_profile_summaries(
            chain_rows_raw,
            profile_order=ANSWER_CHAIN_PROFILES,
            label_map=ANSWER_CHAIN_PROFILE_LABELS,
            baseline_profile="chain_memory_base",
        )
        if row.case_set == "overall"
    }
    single_baseline = single_all["memory_base"]
    chain_baseline = chain_all["chain_memory_base"]

    single_rows = tuple(
        _row_vs_baseline(
            single_all[profile],
            single_baseline,
            feature_names=ANSWER_PROFILE_FEATURES[profile],
        )
        for profile in ANSWER_SINGLE_PROFILES
    )
    chain_rows = tuple(
        _chain_row(
            row=chain_all[profile],
            baseline=chain_baseline,
            previous=chain_all[ANSWER_CHAIN_PROFILES[index - 1]] if index else None,
            feature_names=ANSWER_CHAIN_PROFILE_FEATURES[profile],
        )
        for index, profile in enumerate(ANSWER_CHAIN_PROFILES)
    )
    answer_feature_names = tuple(
        feature
        for feature in QUANTITATIVE_FEATURES
        if feature not in _FORBIDDEN_ANSWER_FEATURES
    )
    metrics = {
        "measurement_mode": "offline_answer_retrieval_count_eval",
        "case_count": len(cases),
        "target_count": single_baseline.target_count,
        "baseline_profile": "memory_base",
        "chain_baseline_profile": "chain_memory_base",
        "single_profile_count": len(single_rows),
        "chain_profile_count": len(chain_rows),
        "disabled_controls_excluded": True,
        "write_governance_excluded": True,
        "sleep_consolidation_excluded": True,
        "answer_feature_names": answer_feature_names,
        "forbidden_answer_features": tuple(sorted(_FORBIDDEN_ANSWER_FEATURES)),
        "timestamp_mode": "fixed_for_deterministic_eval",
    }
    return AnswerRetrievalCountReport(
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        single_module_rows=single_rows,
        chain_rows=chain_rows,
        metrics=metrics,
    )


def write_answer_retrieval_count_json(
    report: AnswerRetrievalCountReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_answer_retrieval_count_markdown(
    report: AnswerRetrievalCountReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 召回与回答增益计数评测",
        "",
        "本报告只评价当前回答链路，不包含写入治理和睡眠巩固。",
        "",
        "## 单模块启动测试",
        "",
        "| profile | success | miss | 召回率 | 命中增量 | 漏召回减少 | 召回率提升百分点 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.single_module_rows:
        lines.append(_markdown_row(row))
    lines.extend(
        [
            "",
            "## 组合链路测试",
            "",
            "| profile | success | miss | 召回率 | 相邻命中增量 | 相邻漏召回减少 | 相邻召回率提升百分点 | 累计命中增量 | 累计召回率提升百分点 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report.chain_rows:
        lines.append(_markdown_chain_row(row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _row_vs_baseline(
    row: QuantitativeProfileSummary,
    baseline: QuantitativeProfileSummary,
    *,
    feature_names: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "profile_name": row.profile_name,
        "feature_names": list(feature_names),
        "target_count": row.target_count,
        "success_count": row.success_count,
        "miss_count": row.miss_count,
        "recall_rate": round(row.recall_rate, 4),
        "success_delta_vs_baseline": row.success_count - baseline.success_count,
        "miss_reduction_vs_baseline": baseline.miss_count - row.miss_count,
        "recall_delta_points_vs_baseline": round(
            row.recall_rate - baseline.recall_rate,
            4,
        ),
    }


def _chain_row(
    *,
    row: QuantitativeProfileSummary,
    baseline: QuantitativeProfileSummary,
    previous: QuantitativeProfileSummary | None,
    feature_names: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "profile_name": row.profile_name,
        "feature_names": list(feature_names),
        "target_count": row.target_count,
        "success_count": row.success_count,
        "miss_count": row.miss_count,
        "recall_rate": round(row.recall_rate, 4),
        "adjacent_success_delta": 0
        if previous is None
        else row.success_count - previous.success_count,
        "adjacent_miss_reduction": 0
        if previous is None
        else previous.miss_count - row.miss_count,
        "adjacent_recall_delta_points": 0.0
        if previous is None
        else round(row.recall_rate - previous.recall_rate, 4),
        "cumulative_success_delta": row.success_count - baseline.success_count,
        "cumulative_recall_delta_points": round(
            row.recall_rate - baseline.recall_rate,
            4,
        ),
    }


def _markdown_row(row: dict[str, Any]) -> str:
    return (
        f"| {row['profile_name']} | "
        f"{row['success_count']}/{row['target_count']} | "
        f"{row['miss_count']}/{row['target_count']} | "
        f"{row['recall_rate']}% | "
        f"{row['success_delta_vs_baseline']} | "
        f"{row['miss_reduction_vs_baseline']} | "
        f"{row['recall_delta_points_vs_baseline']} |"
    )


def _markdown_chain_row(row: dict[str, Any]) -> str:
    return (
        f"| {row['profile_name']} | "
        f"{row['success_count']}/{row['target_count']} | "
        f"{row['miss_count']}/{row['target_count']} | "
        f"{row['recall_rate']}% | "
        f"{row['adjacent_success_delta']} | "
        f"{row['adjacent_miss_reduction']} | "
        f"{row['adjacent_recall_delta_points']} | "
        f"{row['cumulative_success_delta']} | "
        f"{row['cumulative_recall_delta_points']} |"
    )
