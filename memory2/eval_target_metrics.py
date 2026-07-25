from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from memory2.eval_cases import EvalCase
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_runner import EvalCaseResult, EvalTrace, run_eval_cases


_FIXED_REPORT_TIME = datetime(2026, 7, 20, tzinfo=timezone.utc)
_WRITE_EVIDENCE_REQUIRED = frozenset(
    {"candidate_id", "baseline_decision", "after_decision", "label", "infra_error"}
)
_WRITE_EVIDENCE_LABELS = frozenset({"useful", "pollution", "duplicate", "conflict"})
_WRITE_EVIDENCE_DECISIONS = frozenset({"allow", "reject", "review"})
_HYGIENE_EVIDENCE_REQUIRED = frozenset(
    {
        "item_id",
        "baseline_state",
        "after_state",
        "label",
        "source_ref_available",
        "source_fetch_success",
        "baseline_token_estimate",
        "after_token_estimate",
        "infra_error",
    }
)
_HYGIENE_EVIDENCE_LABELS = frozenset({"duplicate", "stale", "low_value", "retained"})
_HYGIENE_EVIDENCE_STATES = frozenset({"active", "merged", "stale", "low_value_removed"})


@dataclass(frozen=True)
class MetricDelta:
    name: str
    before: float | str
    after: float | str
    delta_points: float | str
    relative_uplift_pct: float | str


@dataclass(frozen=True)
class TargetMetricRow:
    group_name: str
    module_name: str
    profile_name: str
    case_set: str
    case_count: int
    metrics: dict[str, MetricDelta]
    unit_count: int | str = "unavailable"
    measurement_layer: str = "offline_trace"
    measurement_source: str = "eval_runner_trace"
    checkpoint_source: str = "none"
    gated_reason: str = ""


@dataclass(frozen=True)
class TargetMetricReport:
    run_id: str
    generated_at: str
    answer_retrieval_rows: tuple[TargetMetricRow, ...]
    write_governance_rows: tuple[TargetMetricRow, ...]
    memory_hygiene_rows: tuple[TargetMetricRow, ...]
    case_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]


def build_target_metric_report(
    cases: Sequence[EvalCase],
    *,
    online_case_records: Sequence[dict[str, object]] | None = None,
    online_checkpoint_source: str = "unknown",
    online_write_records: Sequence[dict[str, object]] | None = None,
    online_hygiene_records: Sequence[dict[str, object]] | None = None,
) -> TargetMetricReport:
    run_report = run_eval_cases(cases)
    if not run_report.passed:
        failures = "\n".join(
            f"- {case.case_id}: {', '.join(case.failures) or 'unknown failure'}"
            for case in run_report.cases
            if not case.passed
        )
        raise RuntimeError(
            "eval runner failed before target metric report generation:\n"
            f"{failures or '- unknown failure'}"
        )
    case_lookup = {case.id: case for case in cases}
    case_records: list[dict[str, object]] = []
    for case_result in run_report.cases:
        case = case_lookup[case_result.case_id]
        case_records.extend(_case_target_records(case, case_result))

    answer_rows = _build_group_rows(
        case_records,
        group_name="召回与回答",
        modules=(
            ("tri_retrieval", "三路召回", "chain_tri_retrieval"),
            ("graph_retrieval", "图谱召回", "chain_graph_retrieval"),
            ("rerank_injection", "重排与注入治理", "chain_rerank_injection"),
            ("version_provenance", "版本链与溯源", "chain_version_provenance"),
        ),
        metric_names=(
            "target_recall_rate",
            "answer_hit_rate",
            "evidence_hit_rate",
            "wrong_recall_rate",
            "wrong_injection_rate",
            "stale_version_misuse_rate",
            "current_version_recall_rate",
            "conflict_chain_detection_rate",
        ),
    )
    answer_rows = answer_rows + _build_online_answer_rows(
        online_case_records or (),
        checkpoint_source=online_checkpoint_source,
    )
    write_rows = _build_group_rows(
        case_records,
        group_name="写入治理",
        modules=(("write_value", "写入价值治理", "chain_write_value"),),
        metric_names=(
            "useful_write_precision",
            "pollution_block_rate",
            "duplicate_control_rate",
            "conflict_review_rate",
            "write_reduction_rate",
            "false_reject_rate",
            "false_accept_rate",
        ),
    )
    write_rows = write_rows + _build_online_write_rows(
        online_write_records,
        checkpoint_source=online_checkpoint_source,
    )
    hygiene_rows = _build_group_rows(
        case_records,
        group_name="记忆库卫生",
        modules=(("sleep_consolidation", "睡眠巩固", "chain_sleep_consolidation"),),
        metric_names=(
            "duplicate_merge_rate",
            "stale_cleanup_rate",
            "low_value_cleanup_rate",
            "source_ref_coverage_rate",
            "source_fetch_success_rate",
            "token_saving_rate",
            "post_consolidation_recall_retention_rate",
        ),
    )
    hygiene_rows = hygiene_rows + _build_online_hygiene_rows(
        online_hygiene_records,
        checkpoint_source=online_checkpoint_source,
    )
    return TargetMetricReport(
        run_id=_deterministic_run_id(cases),
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        answer_retrieval_rows=answer_rows,
        write_governance_rows=write_rows,
        memory_hygiene_rows=hygiene_rows,
        case_records=tuple(case_records),
        metrics=_build_report_metrics(
            cases,
            case_records,
            answer_rows,
            write_rows,
            hygiene_rows,
            online_case_records or (),
            online_write_records,
            online_hygiene_records,
        ),
    )


def write_target_metric_json(report: TargetMetricReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_target_metric_markdown(report: TargetMetricReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 记忆系统目标指标百分比评测报告",
        "",
        "本报告是离线确定性代理结果，用于把 memory 模块效果拆成可解释百分比；它不是生产准确率。",
        "",
        "## 总览",
        "",
        f"- `case_count`: `{report.metrics.get('case_count')}`",
        f"- `common_case_count`: `{report.metrics.get('common_case_count')}`",
        f"- `hard_case_count`: `{report.metrics.get('hard_case_count')}`",
        f"- `measurement_mode`: `{report.metrics.get('measurement_mode')}`",
        f"- `online_status`: `{report.metrics.get('online_status')}`",
        f"- `online_row_count`: `{report.metrics.get('online_row_count')}`",
        "",
        "## 离线真实 before/after",
        "",
        "离线层的 `before` 来自同一轮 trace 的 baseline 字段，不再固定写成 0。它是可复现代理指标，不是生产准确率。",
        "",
        "## 线上真实 LLM / checkpoint before/after",
        "",
        "线上层来自真实 AgentLoop/checkpoint 或显式 evidence JSON；如果没有输入，报告会标记为 gated/unavailable，不会复用离线数值。",
        "",
        "## 召回与回答增益表",
        "",
        "| measurement_layer | measurement_source | checkpoint_source | 模块 | case 数 | 目标召回率 before | 目标召回率 after | 提升百分点 | 相对提升 | 回答命中率 after | 证据命中率 after | 错误召回率 after | 错误注入率 after |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in _main_rows(report.answer_retrieval_rows):
        lines.append(
            _answer_row(row)
        )
    lines.extend(
        [
            "",
            "## 写入治理增益表",
            "",
            "| measurement_layer | measurement_source | checkpoint_source | 模块 | candidate 数 | 有效写入精度 before | 有效写入精度 after | 污染拦截率 before | 污染拦截率 after | 重复控制率 after | 写入减少率 after | 误拒率 after |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in _main_rows(report.write_governance_rows):
        lines.append(_write_row(row))
    lines.extend(
        [
            "",
            "## 记忆库卫生增益表",
            "",
            "| measurement_layer | measurement_source | checkpoint_source | 模块 | scanned 数 | 重复合并率 after | 过期清理率 after | 低价值清理率 after | source_ref 覆盖率 after | 回源成功率 after | token 节省率 after | 巩固后召回保持率 after |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in _main_rows(report.memory_hygiene_rows):
        lines.append(_hygiene_row(row))
    online_evidence_rows = [
        row
        for row in (report.write_governance_rows + report.memory_hygiene_rows)
        if row.measurement_layer == "online_evidence"
    ]
    if online_evidence_rows:
        lines.extend(
            [
                "",
                "## 在线证据行",
                "",
                "| group | measurement_source | checkpoint_source | measurement_layer | 主要结果 |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in online_evidence_rows:
            if row.group_name == "写入治理":
                result = (
                    f"污染拦截率 after {_fmt(row.metrics['pollution_block_rate'].after)}; "
                    f"写入减少率 after {_fmt(row.metrics['write_reduction_rate'].after)}"
                )
            else:
                result = (
                    f"source_ref 覆盖率 after {_fmt(row.metrics['source_ref_coverage_rate'].after)}; "
                    f"token 节省率 after {_fmt(row.metrics['token_saving_rate'].after)}"
                )
            lines.append(
                "| "
                + " | ".join(
                    [
                        row.group_name,
                        row.measurement_source,
                        row.checkpoint_source,
                        row.measurement_layer,
                        result,
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## 版本链专项指标",
            "",
            "| measurement_layer | measurement_source | checkpoint_source | case_set | case 数 | current_version_recall_rate before | current_version_recall_rate after | stale_version_misuse_rate before | stale_version_misuse_rate after | conflict_chain_detection_rate after |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in _main_rows(report.answer_retrieval_rows):
        if row.module_name != "版本链与溯源" or row.measurement_layer != "offline_trace":
            continue
        current = row.metrics["current_version_recall_rate"]
        stale = row.metrics["stale_version_misuse_rate"]
        conflict = row.metrics["conflict_chain_detection_rate"]
        lines.append(
            "| "
            + " | ".join(
                [
                    row.measurement_layer,
                    row.measurement_source,
                    row.checkpoint_source,
                    row.case_set,
                    str(row.case_count),
                    _fmt(current.before),
                    _fmt(current.after),
                    _fmt(stale.before),
                    _fmt(stale.after),
                    _fmt(conflict.after),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## common / hard 明细",
            "",
            "| group | case_set | 模块 | 主指标 before | 主指标 after | 提升百分点 | 相对提升 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in (
        report.answer_retrieval_rows
        + report.write_governance_rows
        + report.memory_hygiene_rows
    ):
        if row.case_set in {"overall", "online"}:
            continue
        metric = _primary_metric(row)
        lines.append(
            "| "
            + " | ".join(
                [
                    row.group_name,
                    row.case_set,
                    row.module_name,
                    _fmt(metric.before),
                    _fmt(metric.after),
                    _fmt(metric.delta_points),
                    _fmt(metric.relative_uplift_pct),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- `提升百分点` 是 after - before。",
            "- `相对提升` 只有 before 是有效且非零数值时才计算。",
            "- 写入治理和记忆库卫生的指标来自 shadow trace，是离线代理指标。",
            "- 真实 LLM 报告应复用 Phase 6e checkpoint，避免仅为换展示口径重复调用 provider。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--case-set", choices=("all", "common", "hard"), default="all")
    parser.add_argument(
        "--case-pack",
        choices=("standard", "comprehensive"),
        default="standard",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--online-checkpoint-jsonl", default="")
    parser.add_argument("--exclude-online-infra-failures", action="store_true")
    parser.add_argument(
        "--online-checkpoint-source",
        choices=("real_llm", "fake_provider", "unknown"),
        default="unknown",
    )
    parser.add_argument("--online-write-evidence-json", default="")
    parser.add_argument("--online-hygiene-evidence-json", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cases = build_quantitative_eval_cases(
        case_set=args.case_set,
        limit=args.limit,
        case_pack=args.case_pack,
    )
    if not cases:
        print("No quantitative cases available.")
        return 1

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_target_metrics_eval.json"
    md_path = out_dir / "memory_target_metrics_eval.md"
    tmp_json = out_dir / "memory_target_metrics_eval.json.tmp"
    tmp_md = out_dir / "memory_target_metrics_eval.md.tmp"
    try:
        online_records: tuple[dict[str, object], ...] = ()
        checkpoint_source = str(args.online_checkpoint_source)
        if args.online_checkpoint_jsonl:
            from memory2.eval_comprehensive_online import (
                build_comprehensive_online_report_from_checkpoint,
            )

            online_report = build_comprehensive_online_report_from_checkpoint(
                Path(args.online_checkpoint_jsonl),
                real_llm_enabled=checkpoint_source == "real_llm",
                exclude_infra_failures=bool(args.exclude_online_infra_failures),
            )
            online_records = tuple(online_report.case_records)
            if checkpoint_source == "unknown":
                checkpoint_source = (
                    "real_llm"
                    if bool(online_report.metrics.get("real_llm_enabled"))
                    else "unknown"
                )
        report = build_target_metric_report(
            cases,
            online_case_records=online_records,
            online_checkpoint_source=checkpoint_source,
            online_write_records=_load_write_evidence_records(args.online_write_evidence_json),
            online_hygiene_records=_load_hygiene_evidence_records(args.online_hygiene_evidence_json),
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        write_target_metric_json(report, tmp_json)
        write_target_metric_markdown(report, tmp_md)
        tmp_json.replace(json_path)
        tmp_md.replace(md_path)
        print(json_path)
        print(md_path)
        return 0
    except Exception as exc:  # pragma: no cover - exercised via CLI tests
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for tmp_path in (tmp_json, tmp_md):
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except FileNotFoundError:
                pass


def _case_target_records(case: EvalCase, case_result: EvalCaseResult) -> list[dict[str, object]]:
    all_profile = case_result.profiles["all"]
    traces = all_profile.traces
    records: list[dict[str, object]] = []
    for module_key, metric_values in (
        ("tri_retrieval", _tri_metrics(case, traces.get("tri_retrieval"))),
        ("graph_retrieval", _graph_metrics(case, traces.get("graph_retrieval"))),
        (
            "rerank_injection",
            _rerank_injection_metrics(
                case,
                traces.get("rerank_shadow"),
                traces.get("injection_governance_shadow"),
            ),
        ),
        (
            "version_provenance",
            _version_provenance_metrics(
                case,
                traces.get("version_chain_shadow"),
                traces.get("provenance_shadow"),
            ),
        ),
        ("write_value", _write_metrics(traces.get("write_value_score"))),
        (
            "sleep_consolidation",
            _hygiene_metrics(
                case,
                traces.get("sleep_consolidation_shadow"),
                traces.get("provenance_shadow"),
            ),
        ),
    ):
        records.append(
            {
                "case_id": case.id,
                "case_set": _case_set(case),
                "module_key": module_key,
                **metric_values,
            }
        )
    return records


def _tri_metrics(case: EvalCase, trace: EvalTrace | None) -> dict[str, object]:
    if trace is None:
        return _unavailable_answer_metrics()
    expected = _expected_ids(case)
    forbidden = _forbidden_ids(case)
    before_ids = _str_tuple(trace.baseline_result.get("baseline_ids"))
    after_ids = _str_tuple(trace.experimental_result.get("fused_ids"))
    source_ref_coverage = _pct(float(trace.metrics.get("source_ref_coverage", 0.0) or 0.0))
    return {
        "target_recall_rate_before": _hit_pct(before_ids, expected),
        "target_recall_rate_after": _hit_pct(after_ids, expected),
        "answer_hit_rate_before": _hit_pct(before_ids, expected),
        "answer_hit_rate_after": _hit_pct(after_ids, expected),
        "evidence_hit_rate_before": "unavailable",
        "evidence_hit_rate_after": source_ref_coverage,
        "wrong_recall_rate_before": _hit_pct(before_ids, forbidden),
        "wrong_recall_rate_after": _hit_pct(after_ids, forbidden),
        "wrong_injection_rate_before": "unavailable",
        "wrong_injection_rate_after": "unavailable",
        "stale_version_misuse_rate_before": "unavailable",
        "stale_version_misuse_rate_after": "unavailable",
    }


def _graph_metrics(case: EvalCase, trace: EvalTrace | None) -> dict[str, object]:
    if trace is None:
        return _unavailable_answer_metrics()
    expected = _expected_graph_ids(case) or _expected_ids(case)
    forbidden = _forbidden_ids(case)
    before_ids = _str_tuple(
        trace.baseline_result.get("baseline_fused_ids")
        or trace.baseline_result.get("baseline_ids")
    )
    after_ids = _str_tuple(trace.experimental_result.get("graph_fused_ids"))
    return {
        "target_recall_rate_before": _hit_pct(before_ids, expected),
        "target_recall_rate_after": _hit_pct(after_ids, expected),
        "answer_hit_rate_before": _hit_pct(before_ids, expected),
        "answer_hit_rate_after": _hit_pct(after_ids, expected),
        "evidence_hit_rate_before": "unavailable",
        "evidence_hit_rate_after": "unavailable",
        "wrong_recall_rate_before": _hit_pct(before_ids, forbidden),
        "wrong_recall_rate_after": _hit_pct(after_ids, forbidden),
        "wrong_injection_rate_before": "unavailable",
        "wrong_injection_rate_after": "unavailable",
        "stale_version_misuse_rate_before": "unavailable",
        "stale_version_misuse_rate_after": "unavailable",
    }


def _rerank_injection_metrics(
    case: EvalCase,
    rerank_trace: EvalTrace | None,
    injection_trace: EvalTrace | None,
) -> dict[str, object]:
    expected = _expected_ids(case)
    forbidden = _forbidden_ids(case)
    before_ids = _str_tuple(
        (injection_trace.baseline_result.get("baseline_injected_ids") if injection_trace else ())
    )
    after_ids = _str_tuple(
        (
            injection_trace.experimental_result.get("experimental_injected_ids")
            if injection_trace
            else ()
        )
    )
    candidate_count = int((rerank_trace.metrics.get("candidate_count", 0) if rerank_trace else 0) or 0)
    source_ref_count = int((rerank_trace.metrics.get("source_ref_count", 0) if rerank_trace else 0) or 0)
    evidence_after: float | str = (
        _pct(source_ref_count / candidate_count) if candidate_count else "unavailable"
    )
    return {
        "target_recall_rate_before": _hit_pct(before_ids, expected),
        "target_recall_rate_after": _hit_pct(after_ids, expected),
        "answer_hit_rate_before": _hit_pct(before_ids, expected),
        "answer_hit_rate_after": _hit_pct(after_ids, expected),
        "evidence_hit_rate_before": "unavailable",
        "evidence_hit_rate_after": evidence_after,
        "wrong_recall_rate_before": _hit_pct(before_ids, forbidden),
        "wrong_recall_rate_after": _hit_pct(after_ids, forbidden),
        "wrong_injection_rate_before": _hit_pct(before_ids, forbidden),
        "wrong_injection_rate_after": _hit_pct(after_ids, forbidden),
        "stale_version_misuse_rate_before": "unavailable",
        "stale_version_misuse_rate_after": "unavailable",
    }


def _version_provenance_metrics(
    case: EvalCase,
    version_trace: EvalTrace | None,
    provenance_trace: EvalTrace | None,
) -> dict[str, object]:
    if version_trace is None:
        return _unavailable_answer_metrics()
    expected = _expected_active_version_ids(case) or _expected_ids(case)
    stale_expected = _expected_stale_version_ids(case)
    expected_conflict_chain_count = _expected_conflict_chain_count(case)
    forbidden = _forbidden_ids(case)
    before_ids = _str_tuple(version_trace.baseline_result.get("baseline_recalled_ids"))
    after_ids = _str_tuple(version_trace.experimental_result.get("active_leaf_ids"))
    stale_after_ids = _str_tuple(version_trace.experimental_result.get("stale_recalled_ids"))
    conflict_count = int(version_trace.metrics.get("conflict_chain_count", 0) or 0)
    source_ref = (
        _pct(float(provenance_trace.metrics.get("source_ref_coverage", 0.0) or 0.0))
        if provenance_trace
        else "unavailable"
    )
    parse_success = (
        _pct(float(provenance_trace.metrics.get("parse_success_rate", 0.0) or 0.0))
        if provenance_trace
        else "unavailable"
    )
    evidence = _avg_available((source_ref, parse_success))
    target_before = _hit_pct(before_ids, expected)
    target_after = _hit_pct(after_ids, expected)
    conflict_after: float | str = (
        "unavailable"
        if expected_conflict_chain_count <= 0
        else _pct(conflict_count / expected_conflict_chain_count)
    )
    return {
        "target_recall_rate_before": target_before,
        "target_recall_rate_after": target_after,
        "answer_hit_rate_before": target_before,
        "answer_hit_rate_after": target_after,
        "evidence_hit_rate_before": "unavailable",
        "evidence_hit_rate_after": evidence,
        "wrong_recall_rate_before": _hit_pct(before_ids, forbidden),
        "wrong_recall_rate_after": _hit_pct(after_ids, forbidden),
        "wrong_injection_rate_before": "unavailable",
        "wrong_injection_rate_after": "unavailable",
        "stale_version_misuse_rate_before": _hit_pct(before_ids, stale_expected),
        "stale_version_misuse_rate_after": _hit_pct(stale_after_ids, stale_expected),
        "current_version_recall_rate_before": target_before,
        "current_version_recall_rate_after": target_after,
        "conflict_chain_detection_rate_before": "unavailable",
        "conflict_chain_detection_rate_after": conflict_after,
    }


def _write_metrics(trace: EvalTrace | None) -> dict[str, object]:
    if trace is None:
        return {name: "unavailable" for name in _write_metric_fields()}
    metrics = trace.metrics
    candidate_count = int(metrics.get("candidate_count", 0) or 0)
    baseline_written = int(metrics.get("baseline_written_count", 0) or 0)
    allow_count = int(metrics.get("policy_allow_count", 0) or 0)
    reject_count = int(metrics.get("policy_reject_count", 0) or 0)
    review_count = int(metrics.get("policy_review_count", 0) or 0)
    duplicate_count = int(metrics.get("duplicate_risk_count", 0) or 0)
    temporary_count = int(metrics.get("temporary_risk_count", 0) or 0)
    assistant_count = int(metrics.get("assistant_inference_risk_count", 0) or 0)
    pollution_count = min(candidate_count, temporary_count + assistant_count + duplicate_count)
    blocked_count = reject_count + review_count
    safe_candidate_count = max(0, candidate_count - pollution_count)
    after_precision: float | str = (
        _pct(min(allow_count, safe_candidate_count) / allow_count)
        if allow_count
        else "unavailable"
    )
    return {
        "candidate_count": candidate_count,
        "useful_write_precision_before": _pct(safe_candidate_count / max(1, baseline_written)),
        "useful_write_precision_after": after_precision,
        "pollution_block_rate_before": "unavailable",
        "pollution_block_rate_after": _pct(min(blocked_count, pollution_count) / max(1, pollution_count)),
        "duplicate_control_rate_before": "unavailable",
        "duplicate_control_rate_after": _pct(duplicate_count / max(1, candidate_count)),
        "conflict_review_rate_before": "unavailable",
        "conflict_review_rate_after": _pct(review_count / max(1, candidate_count)),
        "write_reduction_rate_before": 0.0,
        "write_reduction_rate_after": _pct(float(metrics.get("write_reduction_rate", 0.0) or 0.0)),
        "false_reject_rate_before": "unavailable",
        "false_reject_rate_after": _pct(max(0, blocked_count - pollution_count) / max(1, safe_candidate_count)),
        "false_accept_rate_before": _pct(pollution_count / max(1, baseline_written)),
        "false_accept_rate_after": _pct(max(0, allow_count - safe_candidate_count) / max(1, pollution_count)),
    }


def _hygiene_metrics(
    case: EvalCase,
    sleep_trace: EvalTrace | None,
    provenance_trace: EvalTrace | None,
) -> dict[str, object]:
    if sleep_trace is None:
        return {name: "unavailable" for name in _hygiene_metric_fields()}
    metrics = sleep_trace.metrics
    scanned = int(metrics.get("scanned_count", 0) or 0)
    duplicate_groups = int(metrics.get("duplicate_group_count", 0) or 0)
    merge_candidates = int(metrics.get("merge_candidate_count", 0) or 0)
    stale_count = int(metrics.get("stale_candidate_count", 0) or 0)
    low_value_count = int(metrics.get("low_value_candidate_count", 0) or 0)
    missing_source_ref = int(metrics.get("missing_source_ref_count", 0) or 0)
    estimated_redundancy_drop = float(metrics.get("estimated_redundancy_drop", 0.0) or 0.0)
    expected = _expected_ids(case)
    baseline_ids = _str_tuple(sleep_trace.baseline_result.get("baseline_item_ids"))
    stale_ids = _str_tuple(sleep_trace.experimental_result.get("stale_candidate_ids"))
    low_value_ids = _str_tuple(sleep_trace.experimental_result.get("low_value_candidate_ids"))
    retained_ids = tuple(
        item_id
        for item_id in baseline_ids
        if item_id not in set(stale_ids) and item_id not in set(low_value_ids)
    )
    fetch_success = (
        _pct(float(provenance_trace.metrics.get("parse_success_rate", 0.0) or 0.0))
        if provenance_trace
        else "unavailable"
    )
    return {
        "scanned_count": scanned,
        "duplicate_merge_rate_before": "unavailable",
        "duplicate_merge_rate_after": _pct(min(duplicate_groups, merge_candidates) / max(1, duplicate_groups)),
        "stale_cleanup_rate_before": "unavailable",
        "stale_cleanup_rate_after": _pct(stale_count / max(1, scanned)),
        "low_value_cleanup_rate_before": "unavailable",
        "low_value_cleanup_rate_after": _pct(low_value_count / max(1, scanned)),
        "source_ref_coverage_rate_before": "unavailable",
        "source_ref_coverage_rate_after": _pct((scanned - missing_source_ref) / max(1, scanned)),
        "source_fetch_success_rate_before": "unavailable",
        "source_fetch_success_rate_after": fetch_success,
        "token_saving_rate_before": 0.0,
        "token_saving_rate_after": _pct(estimated_redundancy_drop),
        "post_consolidation_recall_retention_rate_before": _hit_pct(baseline_ids, expected),
        "post_consolidation_recall_retention_rate_after": _hit_pct(retained_ids, expected),
    }


def _build_group_rows(
    case_records: Sequence[dict[str, object]],
    *,
    group_name: str,
    modules: Sequence[tuple[str, str, str]],
    metric_names: Sequence[str],
) -> tuple[TargetMetricRow, ...]:
    rows: list[TargetMetricRow] = []
    for case_set in ("common", "hard", "overall"):
        for module_key, module_name, profile_name in modules:
            records = [
                record
                for record in case_records
                if str(record["module_key"]) == module_key
                and (case_set == "overall" or str(record["case_set"]) == case_set)
            ]
            if not records:
                continue
            metrics: dict[str, MetricDelta] = {}
            for metric_name in metric_names:
                before = _avg_record_metric(records, f"{metric_name}_before")
                after = _avg_record_metric(records, f"{metric_name}_after")
                delta_points, relative = _delta(before, after)
                metrics[metric_name] = MetricDelta(
                    name=metric_name,
                    before=before,
                    after=after,
                    delta_points=delta_points,
                    relative_uplift_pct=relative,
                )
            unit_count = _unit_count(group_name, records)
            rows.append(
                TargetMetricRow(
                    group_name=group_name,
                    module_name=module_name,
                    profile_name=profile_name,
                    case_set=case_set,
                    case_count=len(records),
                    metrics=metrics,
                    unit_count=unit_count,
                )
            )
    return tuple(rows)


def _build_online_answer_rows(
    records: Sequence[dict[str, object]],
    *,
    checkpoint_source: str,
) -> tuple[TargetMetricRow, ...]:
    pairs = (
        ("chain_off", "chain_tri_retrieval", "三路召回", "chain_tri_retrieval"),
        ("chain_tri_retrieval", "chain_graph_retrieval", "图谱召回", "chain_graph_retrieval"),
        (
            "chain_graph_retrieval",
            "chain_rerank_injection",
            "重排与注入治理",
            "chain_rerank_injection",
        ),
        (
            "chain_rerank_injection",
            "chain_version_provenance",
            "版本链与溯源",
            "chain_version_provenance",
        ),
    )
    if not records:
        return ()
    usable = [
        record
        for record in records
        if not bool(record.get("provider_error")) and not bool(record.get("timeout"))
    ]
    by_profile_key: dict[tuple[str, str, str, int], dict[str, object]] = {}
    for record in usable:
        key = (
            str(record.get("profile_name") or ""),
            str(record.get("case_id") or ""),
            str(record.get("prompt_variant") or ""),
            int(record.get("repeat_index") or 0),
        )
        by_profile_key[key] = record

    rows: list[TargetMetricRow] = []
    for before_profile, after_profile, module_name, profile_name in pairs:
        before_keys = {
            (case_id, prompt_variant, repeat_index)
            for profile, case_id, prompt_variant, repeat_index in by_profile_key
            if profile == before_profile
        }
        after_keys = {
            (case_id, prompt_variant, repeat_index)
            for profile, case_id, prompt_variant, repeat_index in by_profile_key
            if profile == after_profile
        }
        paired = sorted(before_keys & after_keys)
        before_only = before_keys - after_keys
        after_only = after_keys - before_keys
        if not paired:
            metrics = _answer_metric_deltas(
                {
                    "target_recall_rate": "unavailable",
                    "answer_hit_rate": "unavailable",
                    "evidence_hit_rate": "unavailable",
                    "wrong_recall_rate": "unavailable",
                    "wrong_injection_rate": "unavailable",
                    "stale_version_misuse_rate": "unavailable",
                },
                {
                    "target_recall_rate": "unavailable",
                    "answer_hit_rate": "unavailable",
                    "evidence_hit_rate": "unavailable",
                    "wrong_recall_rate": "unavailable",
                    "wrong_injection_rate": "unavailable",
                    "stale_version_misuse_rate": "unavailable",
                },
            )
            rows.append(
                TargetMetricRow(
                    group_name="召回与回答",
                    module_name=module_name,
                    profile_name=profile_name,
                    case_set="online",
                    case_count=0,
                    metrics=metrics,
                    unit_count=0,
                    measurement_layer="online_checkpoint",
                    measurement_source="comprehensive_online_checkpoint",
                    checkpoint_source=checkpoint_source,
                    gated_reason="no_paired_online_cases",
                )
            )
            continue

        before_rows = [
            by_profile_key[(before_profile, case_id, prompt_variant, repeat_index)]
            for case_id, prompt_variant, repeat_index in paired
        ]
        after_rows = [
            by_profile_key[(after_profile, case_id, prompt_variant, repeat_index)]
            for case_id, prompt_variant, repeat_index in paired
        ]
        before_values = {
            "target_recall_rate": "unavailable",
            "answer_hit_rate": _bool_rate(before_rows, "answer_rule_passed"),
            "evidence_hit_rate": _bool_rate(before_rows, "memory_grounding_passed"),
            "wrong_recall_rate": "unavailable",
            "wrong_injection_rate": _violation_rate(before_rows),
            "stale_version_misuse_rate": "unavailable",
        }
        after_values = {
            "target_recall_rate": "unavailable",
            "answer_hit_rate": _bool_rate(after_rows, "answer_rule_passed"),
            "evidence_hit_rate": _bool_rate(after_rows, "memory_grounding_passed"),
            "wrong_recall_rate": "unavailable",
            "wrong_injection_rate": _violation_rate(after_rows),
            "stale_version_misuse_rate": "unavailable",
        }
        rows.append(
            TargetMetricRow(
                group_name="召回与回答",
                module_name=module_name,
                profile_name=profile_name,
                case_set="online",
                case_count=len(paired),
                metrics=_answer_metric_deltas(before_values, after_values),
                unit_count=len(paired),
                measurement_layer="online_checkpoint",
                measurement_source="comprehensive_online_checkpoint",
                checkpoint_source=checkpoint_source,
                gated_reason=(
                    f"dropped_before_only={len(before_only)};dropped_after_only={len(after_only)}"
                ),
            )
        )
    return tuple(rows)


def _build_online_write_rows(
    records: Sequence[dict[str, object]] | None,
    *,
    checkpoint_source: str,
) -> tuple[TargetMetricRow, ...]:
    if not records:
        return ()
    usable = [record for record in records if not bool(record.get("infra_error"))]
    baseline_allow = sum(1 for row in usable if row.get("baseline_decision") == "allow")
    after_allow = [row for row in usable if row.get("after_decision") == "allow"]
    useful = [row for row in usable if row.get("label") == "useful"]
    pollution = [row for row in usable if row.get("label") == "pollution"]
    duplicate = [row for row in usable if row.get("label") == "duplicate"]
    before_values = {
        "useful_write_precision": _pct(
            sum(1 for row in usable if row.get("baseline_decision") == "allow" and row.get("label") == "useful")
            / max(1, baseline_allow)
        ),
        "pollution_block_rate": _decision_rate(pollution, "baseline_decision", {"reject", "review"}),
        "duplicate_control_rate": _decision_rate(duplicate, "baseline_decision", {"reject", "review"}),
        "conflict_review_rate": _decision_rate(
            [row for row in usable if row.get("label") == "conflict"],
            "baseline_decision",
            {"review"},
        ),
        "write_reduction_rate": 0.0,
        "false_reject_rate": _decision_rate(useful, "baseline_decision", {"reject"}),
        "false_accept_rate": _decision_rate(pollution, "baseline_decision", {"allow"}),
    }
    after_values = {
        "useful_write_precision": (
            _pct(sum(1 for row in after_allow if row.get("label") == "useful") / len(after_allow))
            if after_allow
            else "unavailable"
        ),
        "pollution_block_rate": _decision_rate(pollution, "after_decision", {"reject", "review"}),
        "duplicate_control_rate": _decision_rate(duplicate, "after_decision", {"reject", "review"}),
        "conflict_review_rate": _decision_rate(
            [row for row in usable if row.get("label") == "conflict"],
            "after_decision",
            {"review"},
        ),
        "write_reduction_rate": (
            _pct(1 - (len(after_allow) / baseline_allow))
            if baseline_allow
            else "unavailable"
        ),
        "false_reject_rate": _decision_rate(useful, "after_decision", {"reject"}),
        "false_accept_rate": _decision_rate(pollution, "after_decision", {"allow"}),
    }
    return (
        TargetMetricRow(
            group_name="写入治理",
            module_name="写入价值治理",
            profile_name="chain_write_value",
            case_set="online",
            case_count=len(usable),
            metrics=_metric_deltas(before_values, after_values),
            unit_count=len(usable),
            measurement_layer="online_evidence",
            measurement_source="write_governance_evidence_json",
            checkpoint_source=checkpoint_source,
        ),
    )


def _build_online_hygiene_rows(
    records: Sequence[dict[str, object]] | None,
    *,
    checkpoint_source: str,
) -> tuple[TargetMetricRow, ...]:
    if not records:
        return ()
    usable = [record for record in records if not bool(record.get("infra_error"))]
    duplicates = [row for row in usable if row.get("label") == "duplicate"]
    stale = [row for row in usable if row.get("label") == "stale"]
    low_value = [row for row in usable if row.get("label") == "low_value"]
    retained = [row for row in usable if row.get("label") == "retained"]
    source_rows = [row for row in usable if bool(row.get("source_ref_available"))]
    baseline_tokens = sum(float(row.get("baseline_token_estimate") or 0.0) for row in usable)
    after_tokens = sum(float(row.get("after_token_estimate") or 0.0) for row in usable)
    before_values = {
        "duplicate_merge_rate": _state_rate(duplicates, "baseline_state", {"merged"}),
        "stale_cleanup_rate": _state_rate(stale, "baseline_state", {"stale"}),
        "low_value_cleanup_rate": _state_rate(low_value, "baseline_state", {"low_value_removed"}),
        "source_ref_coverage_rate": _bool_rate(usable, "source_ref_available"),
        "source_fetch_success_rate": _bool_rate(source_rows, "source_fetch_success"),
        "token_saving_rate": 0.0,
        "post_consolidation_recall_retention_rate": _state_rate(
            retained,
            "baseline_state",
            {"active"},
        ),
    }
    after_values = {
        "duplicate_merge_rate": _state_rate(duplicates, "after_state", {"merged"}),
        "stale_cleanup_rate": _state_rate(stale, "after_state", {"stale"}),
        "low_value_cleanup_rate": _state_rate(low_value, "after_state", {"low_value_removed"}),
        "source_ref_coverage_rate": _bool_rate(usable, "source_ref_available"),
        "source_fetch_success_rate": _bool_rate(source_rows, "source_fetch_success"),
        "token_saving_rate": (
            _pct(1 - (after_tokens / baseline_tokens))
            if baseline_tokens
            else "unavailable"
        ),
        "post_consolidation_recall_retention_rate": _state_rate(
            retained,
            "after_state",
            {"active"},
        ),
    }
    return (
        TargetMetricRow(
            group_name="记忆库卫生",
            module_name="睡眠巩固",
            profile_name="chain_sleep_consolidation",
            case_set="online",
            case_count=len(usable),
            metrics=_metric_deltas(before_values, after_values),
            unit_count=len(usable),
            measurement_layer="online_evidence",
            measurement_source="memory_hygiene_evidence_json",
            checkpoint_source=checkpoint_source,
        ),
    )


def _build_report_metrics(
    cases: Sequence[EvalCase],
    case_records: Sequence[dict[str, object]],
    answer_rows: Sequence[TargetMetricRow],
    write_rows: Sequence[TargetMetricRow],
    hygiene_rows: Sequence[TargetMetricRow],
    online_case_records: Sequence[dict[str, object]],
    online_write_records: Sequence[dict[str, object]] | None,
    online_hygiene_records: Sequence[dict[str, object]] | None,
) -> dict[str, object]:
    online_row_count = sum(
        1
        for row in tuple(answer_rows) + tuple(write_rows) + tuple(hygiene_rows)
        if row.measurement_layer.startswith("online")
    )
    return {
        "measurement_mode": (
            "offline_trace_real_baseline_plus_online_checkpoint_target_metrics"
            if online_row_count
            else "offline_trace_real_baseline_target_metrics"
        ),
        "case_count": len(cases),
        "common_case_count": sum(1 for case in cases if _case_set(case) == "common"),
        "hard_case_count": sum(1 for case in cases if _case_set(case) == "hard"),
        "case_record_count": len(case_records),
        "answer_retrieval_row_count": len(answer_rows),
        "write_governance_row_count": len(write_rows),
        "memory_hygiene_row_count": len(hygiene_rows),
        "online_row_count": online_row_count,
        "online_answer_record_count": len(online_case_records),
        "online_write_record_count": len(online_write_records or ()),
        "online_hygiene_record_count": len(online_hygiene_records or ()),
        "online_status": "available" if online_row_count else "gated_no_checkpoint",
        "report_tables": (
            "answer_retrieval",
            "write_governance",
            "memory_hygiene",
        ),
        "real_llm_used": False,
        "real_llm_checkpoint_reuse_supported": True,
    }


def _primary_metric(row: TargetMetricRow) -> MetricDelta:
    if row.group_name == "召回与回答":
        return row.metrics["target_recall_rate"]
    if row.group_name == "写入治理":
        return row.metrics["pollution_block_rate"]
    return row.metrics["token_saving_rate"]


def _metric_deltas(
    before_values: dict[str, float | str],
    after_values: dict[str, float | str],
) -> dict[str, MetricDelta]:
    result: dict[str, MetricDelta] = {}
    for name, before in before_values.items():
        after = after_values.get(name, "unavailable")
        delta_points, relative = _delta(before, after)
        result[name] = MetricDelta(
            name=name,
            before=before,
            after=after,
            delta_points=delta_points,
            relative_uplift_pct=relative,
        )
    return result


def _answer_metric_deltas(
    before_values: dict[str, float | str],
    after_values: dict[str, float | str],
) -> dict[str, MetricDelta]:
    return _metric_deltas(before_values, after_values)


def _bool_rate(records: Sequence[dict[str, object]], field: str) -> float | str:
    if not records:
        return "unavailable"
    return _pct(sum(1 for record in records if bool(record.get(field))) / len(records))


def _violation_rate(records: Sequence[dict[str, object]]) -> float | str:
    if not records:
        return "unavailable"
    return _pct(
        sum(
            1
            for record in records
            if int(record.get("forbidden_contains_violation_count") or 0) > 0
        )
        / len(records)
    )


def _decision_rate(
    records: Sequence[dict[str, object]],
    field: str,
    accepted: set[str],
) -> float | str:
    if not records:
        return "unavailable"
    return _pct(
        sum(1 for record in records if str(record.get(field) or "") in accepted)
        / len(records)
    )


def _state_rate(
    records: Sequence[dict[str, object]],
    field: str,
    accepted: set[str],
) -> float | str:
    return _decision_rate(records, field, accepted)


def _answer_row(row: TargetMetricRow) -> str:
    recall = row.metrics["target_recall_rate"]
    return (
        "| "
        + " | ".join(
            [
                row.measurement_layer,
                row.measurement_source,
                row.checkpoint_source,
                row.module_name,
                str(row.case_count),
                _fmt(recall.before),
                _fmt(recall.after),
                _fmt(recall.delta_points),
                _fmt(recall.relative_uplift_pct),
                _fmt(row.metrics["answer_hit_rate"].after),
                _fmt(row.metrics["evidence_hit_rate"].after),
                _fmt(row.metrics["wrong_recall_rate"].after),
                _fmt(row.metrics["wrong_injection_rate"].after),
            ]
        )
        + " |"
    )


def _write_row(row: TargetMetricRow) -> str:
    precision = row.metrics["useful_write_precision"]
    pollution = row.metrics["pollution_block_rate"]
    candidate_count = row.unit_count
    return (
        "| "
        + " | ".join(
            [
                row.measurement_layer,
                row.measurement_source,
                row.checkpoint_source,
                row.module_name,
                _fmt(candidate_count),
                _fmt(precision.before),
                _fmt(precision.after),
                _fmt(pollution.before),
                _fmt(pollution.after),
                _fmt(row.metrics["duplicate_control_rate"].after),
                _fmt(row.metrics["write_reduction_rate"].after),
                _fmt(row.metrics["false_reject_rate"].after),
            ]
        )
        + " |"
    )


def _hygiene_row(row: TargetMetricRow) -> str:
    scanned_count = row.unit_count
    return (
        "| "
        + " | ".join(
            [
                row.measurement_layer,
                row.measurement_source,
                row.checkpoint_source,
                row.module_name,
                _fmt(scanned_count),
                _fmt(row.metrics["duplicate_merge_rate"].after),
                _fmt(row.metrics["stale_cleanup_rate"].after),
                _fmt(row.metrics["low_value_cleanup_rate"].after),
                _fmt(row.metrics["source_ref_coverage_rate"].after),
                _fmt(row.metrics["source_fetch_success_rate"].after),
                _fmt(row.metrics["token_saving_rate"].after),
                _fmt(row.metrics["post_consolidation_recall_retention_rate"].after),
            ]
        )
        + " |"
    )


def _unit_count(group_name: str, records: Sequence[dict[str, object]]) -> int | str:
    if group_name == "写入治理":
        return int(sum(int(record.get("candidate_count") or 0) for record in records))
    if group_name == "记忆库卫生":
        return int(sum(int(record.get("scanned_count") or 0) for record in records))
    return len(records)


def _main_rows(rows: Sequence[TargetMetricRow]) -> tuple[TargetMetricRow, ...]:
    return tuple(row for row in rows if row.case_set in {"overall", "online"})


def _delta(before: float | str, after: float | str) -> tuple[float | str, float | str]:
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return "unavailable", "unavailable"
    delta_points = round(float(after) - float(before), 4)
    if float(before) == 0.0:
        return delta_points, "unavailable"
    return delta_points, round(delta_points / float(before) * 100.0, 4)


def _avg_record_metric(records: Sequence[dict[str, object]], name: str) -> float | str:
    values = [record.get(name) for record in records]
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return "unavailable"
    return round(sum(numeric) / len(numeric), 4)


def _case_set(case: EvalCase) -> str:
    if case.id.startswith("hard_") or str(case.category).startswith("hard_"):
        return "hard"
    return "common"


def _load_json_records(path_value: str) -> tuple[dict[str, object], ...]:
    if not path_value:
        return ()
    path = Path(path_value)
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix == ".jsonl":
        rows: list[dict[str, object]] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"expected object on JSONL line {line_no} in {path}")
            rows.append(payload)
        return tuple(rows)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"expected list records in {path}")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected object records in {path}")
    return tuple(row for row in rows if isinstance(row, dict))


def _load_write_evidence_records(path_value: str) -> tuple[dict[str, object], ...]:
    rows = _load_json_records(path_value)
    _validate_write_evidence_records(rows)
    return rows


def _load_hygiene_evidence_records(path_value: str) -> tuple[dict[str, object], ...]:
    rows = _load_json_records(path_value)
    _validate_hygiene_evidence_records(rows)
    return rows


def _validate_write_evidence_records(records: Sequence[dict[str, object]]) -> None:
    for index, record in enumerate(records):
        missing = sorted(_WRITE_EVIDENCE_REQUIRED - set(record))
        if missing:
            raise ValueError(
                f"write evidence row {index} missing required fields: {', '.join(missing)}"
            )
        _require_bool(record, "infra_error", prefix=f"write evidence row {index}")
        if str(record.get("label")) not in _WRITE_EVIDENCE_LABELS:
            raise ValueError(
                f"write evidence row {index} has invalid label: {record.get('label')}"
            )
        for field in ("baseline_decision", "after_decision"):
            if str(record.get(field)) not in _WRITE_EVIDENCE_DECISIONS:
                raise ValueError(
                    f"write evidence row {index} field {field} has invalid decision: {record.get(field)}"
                )


def _validate_hygiene_evidence_records(records: Sequence[dict[str, object]]) -> None:
    for index, record in enumerate(records):
        missing = sorted(_HYGIENE_EVIDENCE_REQUIRED - set(record))
        if missing:
            raise ValueError(
                f"hygiene evidence row {index} missing required fields: {', '.join(missing)}"
            )
        _require_bool(record, "infra_error", prefix=f"hygiene evidence row {index}")
        _require_bool(record, "source_ref_available", prefix=f"hygiene evidence row {index}")
        _require_bool(record, "source_fetch_success", prefix=f"hygiene evidence row {index}")
        if str(record.get("label")) not in _HYGIENE_EVIDENCE_LABELS:
            raise ValueError(
                f"hygiene evidence row {index} has invalid label: {record.get('label')}"
            )
        for field in ("baseline_state", "after_state"):
            if str(record.get(field)) not in _HYGIENE_EVIDENCE_STATES:
                raise ValueError(
                    f"hygiene evidence row {index} field {field} has invalid state: {record.get(field)}"
                )
        for field in ("baseline_token_estimate", "after_token_estimate"):
            if not _is_nonnegative_number(record.get(field)):
                raise ValueError(
                    f"hygiene evidence row {index} field {field} must be a nonnegative number"
                )


def _require_bool(record: dict[str, object], field: str, *, prefix: str) -> None:
    if not isinstance(record.get(field), bool):
        raise ValueError(f"{prefix} field {field} must be boolean")


def _is_nonnegative_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) >= 0.0


def _expected_ids(case: EvalCase) -> tuple[str, ...]:
    return _str_tuple(case.expectations.get("should_recall_ids"))


def _expected_graph_ids(case: EvalCase) -> tuple[str, ...]:
    return _str_tuple(case.expectations.get("expected_graph_recall_ids"))


def _expected_active_version_ids(case: EvalCase) -> tuple[str, ...]:
    return _str_tuple(case.expectations.get("expected_active_version_ids"))


def _expected_stale_version_ids(case: EvalCase) -> tuple[str, ...]:
    return _str_tuple(case.expectations.get("expected_stale_version_ids"))


def _expected_conflict_chain_count(case: EvalCase) -> int:
    try:
        return max(0, int(case.expectations.get("expected_conflict_chain_count") or 0))
    except (TypeError, ValueError):
        return 0


def _forbidden_ids(case: EvalCase) -> tuple[str, ...]:
    return _str_tuple(case.expectations.get("should_not_recall_ids"))


def _hit_pct(candidate_ids: Sequence[str], target_ids: Sequence[str]) -> float | str:
    if not target_ids:
        return "unavailable"
    candidate_set = {str(item) for item in candidate_ids}
    hits = sum(1 for item in target_ids if str(item) in candidate_set)
    return _pct(hits / len(target_ids))


def _pct(value: float) -> float:
    return round(max(0.0, min(100.0, float(value) * 100.0)), 4)


def _avg_available(values: Sequence[float | str]) -> float | str:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return "unavailable"
    return round(sum(numeric) / len(numeric), 4)


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item))


def _unavailable_answer_metrics() -> dict[str, object]:
    return {
        "target_recall_rate_before": "unavailable",
        "target_recall_rate_after": "unavailable",
        "answer_hit_rate_before": "unavailable",
        "answer_hit_rate_after": "unavailable",
        "evidence_hit_rate_before": "unavailable",
        "evidence_hit_rate_after": "unavailable",
        "wrong_recall_rate_before": "unavailable",
        "wrong_recall_rate_after": "unavailable",
        "wrong_injection_rate_before": "unavailable",
        "wrong_injection_rate_after": "unavailable",
        "stale_version_misuse_rate_before": "unavailable",
        "stale_version_misuse_rate_after": "unavailable",
        "current_version_recall_rate_before": "unavailable",
        "current_version_recall_rate_after": "unavailable",
        "conflict_chain_detection_rate_before": "unavailable",
        "conflict_chain_detection_rate_after": "unavailable",
    }


def _write_metric_fields() -> tuple[str, ...]:
    return (
        "candidate_count",
        "useful_write_precision_before",
        "useful_write_precision_after",
        "pollution_block_rate_before",
        "pollution_block_rate_after",
        "duplicate_control_rate_before",
        "duplicate_control_rate_after",
        "conflict_review_rate_before",
        "conflict_review_rate_after",
        "write_reduction_rate_before",
        "write_reduction_rate_after",
        "false_reject_rate_before",
        "false_reject_rate_after",
        "false_accept_rate_before",
        "false_accept_rate_after",
    )


def _hygiene_metric_fields() -> tuple[str, ...]:
    return (
        "scanned_count",
        "duplicate_merge_rate_before",
        "duplicate_merge_rate_after",
        "stale_cleanup_rate_before",
        "stale_cleanup_rate_after",
        "low_value_cleanup_rate_before",
        "low_value_cleanup_rate_after",
        "source_ref_coverage_rate_before",
        "source_ref_coverage_rate_after",
        "source_fetch_success_rate_before",
        "source_fetch_success_rate_after",
        "token_saving_rate_before",
        "token_saving_rate_after",
        "post_consolidation_recall_retention_rate_before",
        "post_consolidation_recall_retention_rate_after",
    )


def _fmt(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(value)


def _deterministic_run_id(cases: Sequence[EvalCase]) -> str:
    raw = "|".join(case.id for case in cases)
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    raise SystemExit(main())
