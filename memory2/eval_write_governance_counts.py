from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from memory2.eval_write_governance_cases import WriteGovernanceCandidate
from memory2.write_governance_review import (
    apply_final_write_safety_gate,
    resolve_write_review_candidate,
)
from plugins.default_memory.experiments import score_write_candidate_shadow


@dataclass(frozen=True)
class WriteGovernanceCountReport:
    generated_at: str
    main_rows: tuple[dict[str, Any], ...]
    case_set_rows: tuple[dict[str, Any], ...]
    subtype_rows: tuple[dict[str, Any], ...]
    review_resolution_rows: tuple[dict[str, Any], ...]
    final_safety_rows: tuple[dict[str, Any], ...]
    false_reject_rows: tuple[dict[str, Any], ...]
    false_accept_rows: tuple[dict[str, Any], ...]
    review_miss_rows: tuple[dict[str, Any], ...]
    decision_rows: tuple[dict[str, Any], ...]
    metrics: dict[str, Any]


def build_write_governance_count_report(
    candidates: Sequence[WriteGovernanceCandidate],
) -> WriteGovernanceCountReport:
    records = tuple(_score_candidate(candidate) for candidate in candidates)
    categories = tuple(dict.fromkeys(record["category"] for record in records))
    main_rows = tuple(_aggregate_row({"category": category}, records) for category in categories)
    case_set_rows = tuple(
        _aggregate_row({"case_set": case_set, "category": category}, records)
        for case_set in ("common", "hard")
        for category in categories
        if any(record["case_set"] == case_set and record["category"] == category for record in records)
    )
    subtype_rows = tuple(
        _aggregate_row({"case_set": case_set, "category": category, "subtype": subtype}, records)
        for case_set, category, subtype in dict.fromkeys(
            (record["case_set"], record["category"], record["subtype"]) for record in records
        )
    )
    return WriteGovernanceCountReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        main_rows=main_rows,
        case_set_rows=case_set_rows,
        subtype_rows=subtype_rows,
        review_resolution_rows=tuple(_review_resolution_rows(records)),
        final_safety_rows=tuple(_final_safety_rows(records)),
        false_reject_rows=_diagnostic_rows(main_rows, "false_reject_count"),
        false_accept_rows=_diagnostic_rows(main_rows, "false_accept_count"),
        review_miss_rows=_diagnostic_rows(main_rows, "review_miss_count"),
        decision_rows=tuple(_decision_rows(records)),
        metrics=_metrics(records, main_rows),
    )


def write_write_governance_count_json(
    report: WriteGovernanceCountReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_write_governance_count_markdown(
    report: WriteGovernanceCountReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 写入治理离线计数评测",
        "",
        "本报告只评价写入阶段：原本写入方式作为基线，写入价值治理作为叠加模块。",
        "",
        "## 总体指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 原本写入 | {report.metrics['baseline_written_count']}/{report.metrics['candidate_count']} |",
        f"| 治理后直接写入 | {report.metrics['enhanced_written_count']}/{report.metrics['candidate_count']} |",
        f"| 写入减少率 | {report.metrics['write_reduction_rate']}% |",
        f"| 有用候选保留率 | {report.metrics['useful_retention_rate']}% |",
        f"| 污染候选控制率 | {report.metrics['pollution_control_rate']}% |",
        f"| 直接拒绝误伤率 | {report.metrics['direct_reject_false_reject_rate']}% |",
        f"| 复核分流率 | {report.metrics['review_deferral_rate']}% |",
        f"| 未直接写入有用候选率 | {report.metrics['not_directly_written_useful_rate']}% |",
        f"| 漏拦率 | {report.metrics['false_accept_rate']}% |",
        f"| 复核缺口率 | {report.metrics['review_miss_rate']}% |",
        "",
        "## 复核处理总体指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 复核候选数 | {report.metrics['review_candidate_count']} |",
        f"| 复核后晋升写入数 | {report.metrics['review_promoted_write_count']} |",
        f"| 复核后保持复核数 | {report.metrics['review_kept_count']} |",
        f"| 复核后拒绝数 | {report.metrics['review_rejected_count']} |",
        f"| 有用候选最终保留率 | {report.metrics['useful_final_retention_rate']}% |",
        f"| hard 有用候选最终保留率 | {report.metrics['hard_useful_final_retention_rate']}% |",
        f"| 最终污染控制率 | {report.metrics['final_pollution_control_rate']}% |",
        f"| 冲突复核保持率 | {report.metrics['conflict_review_preservation_rate']}% |",
        f"| hard 重复泄漏率 | {report.metrics['duplicate_hard_leakage_rate']}% |",
        "",
        "## 写入治理主表",
        "",
        "| 类别 | 期望 | 原本写入 | 治理后写入 | 治理后拒绝 | 治理后复核 | 污染减少 | 有用保留率 | 治理率 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.main_rows:
        lines.append(_main_row_md(row))
    lines.extend(
        [
            "",
            "## Common/Hard 分组表",
            "",
            "| 难度 | 类别 | 期望 | 原本写入 | 治理后写入 | 治理后拒绝 | 治理后复核 | 治理率 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report.case_set_rows:
        lines.append(_case_set_row_md(row))
    lines.extend(
        [
            "",
            "## 复核处理表",
            "",
            "| 难度 | 类别 | 复核候选 | 晋升写入 | 保持复核 | 复核拒绝 |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report.review_resolution_rows:
        lines.append(_review_resolution_row_md(row))
    lines.extend(
        [
            "",
            "## 最终写入安全门表",
            "",
            "| 难度 | 类别 | 安全门拦截 | 转回复核 | 最终拒绝 |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    if report.final_safety_rows:
        for row in report.final_safety_rows:
            lines.append(_final_safety_row_md(row))
    else:
        lines.append("| 无 | 无 | 0 | 0/0 (0.0%) | 0/0 (0.0%) |")
    _append_diagnostic_table(lines, "误伤表", "false_reject_count", report.false_reject_rows, "该写入的内容被拦截或复核")
    _append_diagnostic_table(lines, "漏拦表", "false_accept_count", report.false_accept_rows, "不应直接写入的内容仍被写入")
    _append_diagnostic_table(lines, "复核缺口表", "review_miss_count", report.review_miss_rows, "期望复核但没有进入复核")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _score_candidate(candidate: WriteGovernanceCandidate) -> dict[str, Any]:
    scored = score_write_candidate_shadow(
        candidate.summary,
        source_ref=f"{candidate.case_set}:write_governance_eval",
        existing_memories=list(candidate.existing_memories),
    )
    enhanced_decision = str(scored.get("decision") or "reject")
    if enhanced_decision == "allow":
        final_decision = "write"
        final_reason = str(scored.get("reason") or "")
        review_resolution_decision = "not_applicable"
        review_resolution_reason = "not_applicable"
    elif enhanced_decision == "review":
        resolution = resolve_write_review_candidate(
            summary=candidate.summary,
            score_result=scored,
            existing_memories=list(candidate.existing_memories),
            source_ref=f"{candidate.case_set}:write_governance_eval",
            category=candidate.category,
            case_set=candidate.case_set,
            subtype=candidate.subtype,
        )
        review_resolution_decision = resolution.decision
        review_resolution_reason = resolution.reason
        if resolution.decision == "approve_write":
            final_decision = "write"
        elif resolution.decision == "keep_review":
            final_decision = "review"
        else:
            final_decision = "reject"
        final_reason = resolution.reason
    else:
        final_decision = "reject"
        final_reason = str(scored.get("reason") or "")
        review_resolution_decision = "not_applicable"
        review_resolution_reason = "not_applicable"
    final_safety_decision = "not_applicable"
    final_safety_reason = "not_applicable"
    if final_decision == "write":
        safety = apply_final_write_safety_gate(
            summary=candidate.summary,
            score_result=scored,
            existing_memories=list(candidate.existing_memories),
            source_ref=f"{candidate.case_set}:write_governance_eval",
        )
        if safety is not None:
            final_safety_decision = safety.decision
            final_safety_reason = safety.reason
            if safety.decision == "keep_review":
                final_decision = "review"
            else:
                final_decision = "reject"
            final_reason = safety.reason
    return {
        "candidate_id": candidate.id,
        "case_set": candidate.case_set,
        "category": candidate.category,
        "subtype": candidate.subtype,
        "expected_action": candidate.expected_action,
        "baseline_decision": "allow",
        "enhanced_decision": enhanced_decision,
        "enhanced_reason": str(scored.get("reason") or ""),
        "enhanced_score": float(scored.get("final_score") or 0.0),
        "review_resolution_decision": review_resolution_decision,
        "review_resolution_reason": review_resolution_reason,
        "final_safety_decision": final_safety_decision,
        "final_safety_reason": final_safety_reason,
        "final_decision": final_decision,
        "final_reason": final_reason,
    }


def _aggregate_row(filters: dict[str, str], records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    selected = [
        record
        for record in records
        if all(str(record.get(key)) == value for key, value in filters.items())
    ]
    if not selected:
        raise ValueError(f"no records for filters: {filters}")
    expected_action = str(selected[0]["expected_action"])
    total = len(selected)
    enhanced_written = sum(1 for item in selected if item["enhanced_decision"] == "allow")
    enhanced_review = sum(1 for item in selected if item["enhanced_decision"] == "review")
    enhanced_rejected = sum(1 for item in selected if item["enhanced_decision"] == "reject")
    enhanced_controlled = enhanced_review + enhanced_rejected
    final_written = sum(1 for item in selected if item["final_decision"] == "write")
    final_review = sum(1 for item in selected if item["final_decision"] == "review")
    final_rejected = sum(1 for item in selected if item["final_decision"] == "reject")
    final_controlled = final_review + final_rejected
    false_reject_count = enhanced_controlled if expected_action == "write" else 0
    false_accept_count = enhanced_written if expected_action in {"block", "review"} else 0
    review_miss_count = total - enhanced_review if expected_action == "review" else 0
    pollution_reduction_count = total - enhanced_written if expected_action != "write" else 0
    final_pollution_reduction_count = total - final_written if expected_action != "write" else 0
    row: dict[str, Any] = {
        **filters,
        "expected_action": expected_action,
        "candidate_count": total,
        "baseline_written_count": total,
        "enhanced_written_count": enhanced_written,
        "enhanced_rejected_count": enhanced_rejected,
        "enhanced_review_count": enhanced_review,
        "enhanced_controlled_count": enhanced_controlled,
        "final_written_count": final_written,
        "final_rejected_count": final_rejected,
        "final_review_count": final_review,
        "final_controlled_count": final_controlled,
        "pollution_reduction_count": pollution_reduction_count,
        "final_pollution_reduction_count": final_pollution_reduction_count,
        "false_reject_count": false_reject_count,
        "false_accept_count": false_accept_count,
        "review_miss_count": review_miss_count,
        "baseline_written_rate": _pct(1.0),
        "enhanced_written_rate": _pct(enhanced_written / total),
        "enhanced_rejected_rate": _pct(enhanced_rejected / total),
        "enhanced_review_rate": _pct(enhanced_review / total),
        "write_retention_rate": _pct(enhanced_written / total),
        "control_rate": _pct(enhanced_controlled / total),
        "final_write_retention_rate": _pct(final_written / total),
        "final_control_rate": _pct(final_controlled / total),
        "pollution_reduction_rate": _pct(pollution_reduction_count / total),
        "final_pollution_reduction_rate": _pct(final_pollution_reduction_count / total),
        "false_reject_rate": _pct(false_reject_count / total),
        "false_accept_rate": _pct(false_accept_count / total),
        "review_miss_rate": _pct(review_miss_count / total),
    }
    return row


def _review_resolution_rows(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    review_records = [record for record in records if record["enhanced_decision"] == "review"]
    result: list[dict[str, Any]] = []
    groups = dict.fromkeys((record["case_set"], record["category"]) for record in review_records)
    for case_set, category in groups:
        selected = [
            record
            for record in review_records
            if record["case_set"] == case_set and record["category"] == category
        ]
        total = len(selected)
        promoted = sum(
            1
            for item in selected
            if item["review_resolution_decision"] == "approve_write"
        )
        kept = sum(
            1
            for item in selected
            if item["review_resolution_decision"] == "keep_review"
        )
        rejected = sum(
            1
            for item in selected
            if item["review_resolution_decision"] == "reject"
        )
        result.append(
            {
                "case_set": case_set,
                "category": category,
                "review_candidate_count": total,
                "review_promoted_write_count": promoted,
                "review_kept_count": kept,
                "review_rejected_count": rejected,
                "review_promoted_write_rate": _pct(promoted / max(1, total)),
                "review_kept_rate": _pct(kept / max(1, total)),
                "review_rejected_rate": _pct(rejected / max(1, total)),
            }
        )
    return result


def _final_safety_rows(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    safety_records = [
        record
        for record in records
        if record["final_safety_decision"] != "not_applicable"
    ]
    result: list[dict[str, Any]] = []
    groups = dict.fromkeys((record["case_set"], record["category"]) for record in safety_records)
    for case_set, category in groups:
        selected = [
            record
            for record in safety_records
            if record["case_set"] == case_set and record["category"] == category
        ]
        total = len(selected)
        rejected = sum(1 for item in selected if item["final_safety_decision"] == "reject")
        kept = sum(1 for item in selected if item["final_safety_decision"] == "keep_review")
        result.append(
            {
                "case_set": case_set,
                "category": category,
                "final_safety_count": total,
                "final_safety_rejected_count": rejected,
                "final_safety_kept_review_count": kept,
                "final_safety_rejected_rate": _pct(rejected / max(1, total)),
                "final_safety_kept_review_rate": _pct(kept / max(1, total)),
            }
        )
    return result


def _diagnostic_rows(rows: Sequence[dict[str, Any]], count_key: str) -> tuple[dict[str, Any], ...]:
    return tuple(row for row in rows if int(row[count_key]) > 0)


def _decision_rows(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    groups = dict.fromkeys((record["case_set"], record["category"]) for record in records)
    for case_set, category in groups:
        selected = [
            record
            for record in records
            if record["case_set"] == case_set and record["category"] == category
        ]
        for decision in ("allow", "review", "reject"):
            count = sum(1 for item in selected if item["enhanced_decision"] == decision)
            result.append(
                {
                    "case_set": case_set,
                    "category": category,
                    "decision": decision,
                    "count": count,
                    "rate": _pct(count / max(1, len(selected))),
                }
            )
    return result


def _metrics(records: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    baseline_written = len(records)
    enhanced_written = sum(1 for record in records if record["enhanced_decision"] == "allow")
    final_written = sum(1 for record in records if record["final_decision"] == "write")
    useful_candidates = sum(int(row["candidate_count"]) for row in rows if row["expected_action"] == "write")
    useful_written = sum(int(row["enhanced_written_count"]) for row in rows if row["expected_action"] == "write")
    useful_final_written = sum(int(row["final_written_count"]) for row in rows if row["expected_action"] == "write")
    hard_useful_records = [
        record
        for record in records
        if record["case_set"] == "hard" and record["expected_action"] == "write"
    ]
    hard_useful_final_written = sum(1 for record in hard_useful_records if record["final_decision"] == "write")
    pollution_candidates = sum(int(row["candidate_count"]) for row in rows if row["expected_action"] != "write")
    pollution_controlled = sum(int(row["enhanced_controlled_count"]) for row in rows if row["expected_action"] != "write")
    final_pollution_controlled = sum(int(row["final_controlled_count"]) for row in rows if row["expected_action"] != "write")
    false_reject_count = sum(int(row["false_reject_count"]) for row in rows)
    direct_reject_false_reject_count = sum(
        int(row["enhanced_rejected_count"])
        for row in rows
        if row["expected_action"] == "write"
    )
    review_deferral_count = sum(
        int(row["enhanced_review_count"])
        for row in rows
        if row["expected_action"] == "write"
    )
    false_accept_count = sum(int(row["false_accept_count"]) for row in rows)
    first_stage_review_candidates = sum(1 for record in records if record["enhanced_decision"] == "review")
    review_promoted_write_count = sum(
        1
        for record in records
        if record["review_resolution_decision"] == "approve_write"
    )
    review_kept_count = sum(
        1
        for record in records
        if record["review_resolution_decision"] == "keep_review"
    )
    review_rejected_count = sum(
        1
        for record in records
        if record["review_resolution_decision"] == "reject"
    )
    expected_review_candidates = sum(int(row["candidate_count"]) for row in rows if row["expected_action"] == "review")
    review_miss_count = sum(int(row["review_miss_count"]) for row in rows)
    conflict_records = [record for record in records if record["category"] == "conflict"]
    conflict_final_review = sum(1 for record in conflict_records if record["final_decision"] == "review")
    duplicate_hard_records = [
        record
        for record in records
        if record["case_set"] == "hard" and record["category"] == "duplicate"
    ]
    duplicate_hard_final_written = sum(1 for record in duplicate_hard_records if record["final_decision"] == "write")
    return {
        "measurement_mode": "offline_write_governance_count_eval",
        "candidate_count": len(records),
        "baseline_profile": "original_write_behavior",
        "enhanced_profile": "write_value_governance",
        "baseline_written_count": baseline_written,
        "enhanced_written_count": enhanced_written,
        "final_written_count": final_written,
        "write_reduction_count": baseline_written - enhanced_written,
        "write_reduction_rate": _pct((baseline_written - enhanced_written) / max(1, baseline_written)),
        "useful_candidate_count": useful_candidates,
        "useful_written_count": useful_written,
        "useful_retention_rate": _pct(useful_written / max(1, useful_candidates)),
        "useful_final_written_count": useful_final_written,
        "useful_final_retention_rate": _pct(useful_final_written / max(1, useful_candidates)),
        "hard_useful_candidate_count": len(hard_useful_records),
        "hard_useful_final_written_count": hard_useful_final_written,
        "hard_useful_final_retention_rate": _pct(
            hard_useful_final_written / max(1, len(hard_useful_records))
        ),
        "pollution_candidate_count": pollution_candidates,
        "pollution_controlled_count": pollution_controlled,
        "pollution_control_rate": _pct(pollution_controlled / max(1, pollution_candidates)),
        "final_pollution_controlled_count": final_pollution_controlled,
        "final_pollution_control_rate": _pct(final_pollution_controlled / max(1, pollution_candidates)),
        "false_reject_count": false_reject_count,
        "false_reject_rate": _pct(false_reject_count / max(1, useful_candidates)),
        "direct_reject_false_reject_count": direct_reject_false_reject_count,
        "direct_reject_false_reject_rate": _pct(
            direct_reject_false_reject_count / max(1, useful_candidates)
        ),
        "review_deferral_count": review_deferral_count,
        "review_deferral_rate": _pct(review_deferral_count / max(1, useful_candidates)),
        "not_directly_written_useful_count": false_reject_count,
        "not_directly_written_useful_rate": _pct(
            false_reject_count / max(1, useful_candidates)
        ),
        "false_accept_count": false_accept_count,
        "false_accept_rate": _pct(false_accept_count / max(1, pollution_candidates)),
        "review_candidate_count": first_stage_review_candidates,
        "review_promoted_write_count": review_promoted_write_count,
        "review_kept_count": review_kept_count,
        "review_rejected_count": review_rejected_count,
        "expected_review_candidate_count": expected_review_candidates,
        "review_miss_count": review_miss_count,
        "review_miss_rate": _pct(review_miss_count / max(1, expected_review_candidates)),
        "conflict_review_preservation_count": conflict_final_review,
        "conflict_review_preservation_rate": _pct(
            conflict_final_review / max(1, len(conflict_records))
        ),
        "duplicate_hard_leakage_count": duplicate_hard_final_written,
        "duplicate_hard_leakage_rate": _pct(
            duplicate_hard_final_written / max(1, len(duplicate_hard_records))
        ),
        "offline_only": True,
        "llm_calls_enabled": False,
        "db_access_enabled": False,
        "production_state_access_enabled": False,
        "online_status": "gated_until_offline_report_reviewed",
    }


def _main_row_md(row: dict[str, Any]) -> str:
    return (
        f"| {row['category']} | {row['expected_action']} | "
        f"{_count_pct(row, 'baseline_written')} | "
        f"{_count_pct(row, 'enhanced_written')} | "
        f"{_count_pct(row, 'enhanced_rejected')} | "
        f"{_count_pct(row, 'enhanced_review')} | "
        f"{_count_pct(row, 'pollution_reduction')} | "
        f"{row['write_retention_rate']}% | {row['control_rate']}% |"
    )


def _case_set_row_md(row: dict[str, Any]) -> str:
    return (
        f"| {row['case_set']} | {row['category']} | {row['expected_action']} | "
        f"{_count_pct(row, 'baseline_written')} | "
        f"{_count_pct(row, 'enhanced_written')} | "
        f"{_count_pct(row, 'enhanced_rejected')} | "
        f"{_count_pct(row, 'enhanced_review')} | "
        f"{row['control_rate']}% |"
    )


def _review_resolution_row_md(row: dict[str, Any]) -> str:
    total = int(row["review_candidate_count"])
    promoted = int(row["review_promoted_write_count"])
    kept = int(row["review_kept_count"])
    rejected = int(row["review_rejected_count"])
    return (
        f"| {row['case_set']} | {row['category']} | {total} | "
        f"{promoted}/{total} ({_pct(promoted / max(1, total))}%) | "
        f"{kept}/{total} ({_pct(kept / max(1, total))}%) | "
        f"{rejected}/{total} ({_pct(rejected / max(1, total))}%) |"
    )


def _final_safety_row_md(row: dict[str, Any]) -> str:
    total = int(row["final_safety_count"])
    kept = int(row["final_safety_kept_review_count"])
    rejected = int(row["final_safety_rejected_count"])
    return (
        f"| {row['case_set']} | {row['category']} | {total} | "
        f"{kept}/{total} ({_pct(kept / max(1, total))}%) | "
        f"{rejected}/{total} ({_pct(rejected / max(1, total))}%) |"
    )


def _append_diagnostic_table(
    lines: list[str],
    title: str,
    count_key: str,
    rows: Sequence[dict[str, Any]],
    note: str,
) -> None:
    lines.extend(["", f"## {title}", "", "| 类别 | 数量 | 占比 | 说明 |", "| --- | ---: | ---: | --- |"])
    if not rows:
        lines.append("| 无 | 0/0 | 0.0% | 本次没有对应问题 |")
        return
    for row in rows:
        count = int(row[count_key])
        total = int(row["candidate_count"])
        lines.append(f"| {row['category']} | {count}/{total} | {_pct(count / max(1, total))}% | {note} |")


def _count_pct(row: dict[str, Any], prefix: str) -> str:
    count = int(row[f"{prefix}_count"])
    total = int(row["candidate_count"])
    return f"{count}/{total} ({_pct(count / max(1, total))}%)"


def _pct(value: float) -> float:
    return round(float(value) * 100.0, 4)
