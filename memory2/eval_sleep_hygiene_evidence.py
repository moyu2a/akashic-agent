from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from memory2.eval_sleep_hygiene_cases import (
    SleepHygieneCase,
    build_sleep_hygiene_cases,
    flatten_sleep_hygiene_memory_items,
)
from memory2.eval_sleep_hygiene_provenance import (
    ProxySourceRefResolver,
    SourceRefEvidence,
    SourceRefResolver,
)
from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)


FIXED_NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SleepHygieneEvidenceReport:
    records: tuple[dict[str, object], ...]
    metrics: dict[str, object]
    shadow_metrics: dict[str, object]


@dataclass(frozen=True)
class CandidateDecision:
    after_state: str = "active"
    shadow_after_state: str = "active"
    candidate_action: str = "none"
    candidate_source: str = "none"
    requires_review: bool = False
    safe_cleanup_candidate: bool = False


def build_sleep_hygiene_evidence_records(
    cases: Sequence[SleepHygieneCase],
    *,
    now: datetime | None = None,
    source_ref_resolver: SourceRefResolver | None = None,
) -> tuple[dict[str, object], ...]:
    items = flatten_sleep_hygiene_memory_items(cases)
    item_by_id = {str(item["id"]): item for item in items}
    resolver = source_ref_resolver or ProxySourceRefResolver()
    shadow = build_sleep_consolidation_shadow_result(
        memory_items=items,
        now=now or FIXED_NOW,
        max_duplicate_groups=10_000,
        max_merge_candidates=10_000,
        max_stale_candidates=10_000,
        max_low_value_candidates=10_000,
        max_conflict_candidates=10_000,
    )
    candidate_decision_by_id = _candidate_decision_by_id(shadow.experimental_result)

    records: list[dict[str, object]] = []
    for case in cases:
        for item_id in case.evaluated_item_ids():
            item = item_by_id[str(item_id)]
            expected_after_state = case.expected_state_for(str(item_id))
            decision = candidate_decision_by_id.get(str(item_id), CandidateDecision())
            source_evidence = resolver.resolve(
                item.get("source_ref"),
                expected_terms=_expected_terms_for_item(item),
            )
            records.append(
                _record(
                    item,
                    label=_label_for_expected_state(expected_after_state),
                    after_state=decision.after_state,
                    case_id=case.case_id,
                    case_set=case.case_set,
                    scenario=case.scenario,
                    expected_after_state=expected_after_state,
                    decision=decision,
                    source_evidence=source_evidence,
                )
            )
    return tuple(records)


def run_sleep_hygiene_evidence_eval(
    *,
    duplicate_groups: int = 120,
    stale_count: int = 120,
    low_value_count: int = 120,
    retained_count: int = 120,
    missing_source_count: int = 40,
    cases: Sequence[SleepHygieneCase] | None = None,
    source_ref_resolver: SourceRefResolver | None = None,
) -> SleepHygieneEvidenceReport:
    selected_cases = (
        tuple(cases)
        if cases is not None
        else build_sleep_hygiene_cases(
            duplicate_groups=duplicate_groups,
            stale_count=stale_count,
            low_value_count=low_value_count,
            retained_count=retained_count,
            missing_source_count=missing_source_count,
        )
    )
    items = flatten_sleep_hygiene_memory_items(selected_cases)
    shadow = build_sleep_consolidation_shadow_result(
        memory_items=items,
        now=FIXED_NOW,
        max_duplicate_groups=10_000,
        max_merge_candidates=10_000,
        max_stale_candidates=10_000,
        max_low_value_candidates=10_000,
        max_conflict_candidates=10_000,
    )
    records = build_sleep_hygiene_evidence_records(
        selected_cases,
        now=FIXED_NOW,
        source_ref_resolver=source_ref_resolver,
    )
    shadow_metrics = _stable_shadow_metrics(shadow.metrics)
    return SleepHygieneEvidenceReport(
        records=records,
        metrics=_metrics(
            records,
            case_count=len(selected_cases),
            scanned_active_item_count=int(shadow_metrics.get("scanned_count", 0) or 0),
        ),
        shadow_metrics=shadow_metrics,
    )


def write_sleep_hygiene_evidence_jsonl(
    records: Sequence[dict[str, object]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def write_sleep_hygiene_report_json(
    report: SleepHygieneEvidenceReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_sleep_hygiene_report_markdown(
    report: SleepHygieneEvidenceReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = report.metrics
    shadow = report.shadow_metrics
    source_fetch_label = _source_fetch_success_label(metrics)
    lines = [
        "# 睡眠巩固记忆库卫生评测报告",
        "",
        "本报告来自确定性离线 evidence，不修改真实记忆库。",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| case 数 | {metrics['case_count']} |",
        f"| 扫描 active item 数 | {metrics['scanned_active_item_count']} |",
        f"| evidence row 数 | {metrics['evaluated_evidence_row_count']} |",
        f"| 重复候选识别率 | {metrics['duplicate_merge_rate']}% |",
        f"| 过期候选识别率 | {metrics['stale_cleanup_rate']}% |",
        f"| 低价值候选识别率 | {metrics['low_value_cleanup_rate']}% |",
        f"| 来源覆盖率 | {metrics['source_ref_coverage_rate']}% |",
        f"| {source_fetch_label} | {metrics['source_fetch_success_rate']}% |",
        f"| shadow 估算 token 节省率 | {metrics['shadow_estimated_token_saving_rate']}% |",
        f"| 关键记忆保持率 | {metrics['post_consolidation_recall_retention_rate']}% |",
        f"| 关键记忆误伤候选数 | {metrics['retained_candidate_leak_count']} |",
        f"| 非预期候选数 | {metrics['unexpected_candidate_count']} |",
        f"| 误伤候选率 | {metrics['false_positive_cleanup_rate']}% |",
        f"| 实际应用变更数 | {shadow['applied_change_count']} |",
        "",
        (
            "说明：当前阶段仍是 shadow / dry-run。重复、过期、低价值和 token "
            "节省均表示候选识别或估算，不表示真实 DB 已经被清理。"
        ),
    ]
    group_metrics = metrics.get("group_metrics")
    if isinstance(group_metrics, dict):
        lines.extend(
            [
                "",
                "## standard / hard / overall",
                "",
                "| case_set | case 数 | evaluated item 数 | candidate recall | candidate precision | retained protection | false positive cleanup | safe evidence token saving |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for name in ("standard", "hard", "overall"):
            group = group_metrics.get(name)
            if not isinstance(group, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        name,
                        str(group.get("case_count")),
                        str(group.get("evaluated_item_count")),
                        _fmt_pct(
                            group.get("candidate_recall"),
                        ),
                        _fmt_pct(group.get("candidate_precision")),
                        _fmt_pct(group.get("retained_protection_rate")),
                        _fmt_pct(group.get("false_positive_cleanup_rate")),
                        _fmt_pct(
                            group.get("safe_evidence_estimated_token_saving_rate")
                        ),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "## V3 cleanup / review action metrics",
                "",
                "| case_set | cleanup recall | cleanup precision | merge suggestions | review required | safe cleanup token saving |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for name in ("standard", "hard", "overall"):
            group = group_metrics.get(name)
            if not isinstance(group, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        name,
                        _fmt_pct(group.get("cleanup_candidate_recall")),
                        _fmt_pct(group.get("cleanup_candidate_precision")),
                        str(group.get("merge_suggestion_count")),
                        str(group.get("review_required_count")),
                        _fmt_pct(group.get("safe_cleanup_token_saving_rate")),
                    ]
                )
                + " |"
            )
    scenario_metrics = metrics.get("scenario_metrics")
    if isinstance(scenario_metrics, dict) and scenario_metrics:
        lines.extend(
            [
                "",
                "## hard scenario breakdown",
                "",
                "| scenario | case 数 | evaluated item 数 | cleanup recall | cleanup precision | merge suggestions | review required | retained protection |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for scenario, scenario_metric in sorted(scenario_metrics.items()):
            if not isinstance(scenario_metric, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        scenario,
                        str(scenario_metric.get("case_count")),
                        str(scenario_metric.get("evaluated_item_count")),
                        _fmt_pct(scenario_metric.get("cleanup_candidate_recall")),
                        _fmt_pct(scenario_metric.get("cleanup_candidate_precision")),
                        str(scenario_metric.get("merge_suggestion_count")),
                        str(scenario_metric.get("review_required_count")),
                        _fmt_pct(scenario_metric.get("retained_protection_rate")),
                    ]
                )
                + " |"
            )
    source_metrics = metrics.get("source_evidence_metrics")
    if isinstance(source_metrics, dict):
        lines.extend(
            [
                "",
                "## source evidence metrics",
                "",
                "| metric | value |",
                "| --- | ---: |",
                f"| source fetch mode | {source_metrics.get('source_fetch_mode')} |",
                f"| source_ref coverage | {_fmt_pct(source_metrics.get('source_ref_coverage_rate'))} |",
                f"| source_ref parse success | {_fmt_pct(source_metrics.get('source_ref_parse_success_rate'))} |",
                f"| source fetch success | {_fmt_pct(source_metrics.get('source_fetch_success_rate'))} |",
                f"| source support rate | {_fmt_pct(source_metrics.get('source_support_rate'))} |",
                f"| missing source count | {source_metrics.get('missing_source_count')} |",
                f"| unsupported source count | {source_metrics.get('unsupported_source_count')} |",
                f"| session ref not fetchable count | {source_metrics.get('session_ref_not_fetchable_count')} |",
                f"| malformed source_ref count | {source_metrics.get('malformed_source_ref_count')} |",
            ]
        )
    by_action = metrics.get("source_evidence_metrics_by_action")
    if isinstance(by_action, dict) and by_action:
        lines.extend(
            [
                "",
                "## source evidence by action",
                "",
                "| action | rows | source_ref coverage | parse success | fetch success | support rate |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for action, action_metrics in sorted(by_action.items()):
            if not isinstance(action_metrics, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        action,
                        str(action_metrics.get("row_count")),
                        _fmt_pct(action_metrics.get("source_ref_coverage_rate")),
                        _fmt_pct(action_metrics.get("source_ref_parse_success_rate")),
                        _fmt_pct(action_metrics.get("source_fetch_success_rate")),
                        _fmt_pct(action_metrics.get("source_support_rate")),
                    ]
                )
                + " |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _candidate_decision_by_id(
    experimental_result: dict[str, object],
) -> dict[str, CandidateDecision]:
    decisions: dict[str, CandidateDecision] = {}
    for item_id in _non_representative_duplicate_ids(
        experimental_result.get("duplicate_groups")
    ):
        decisions[item_id] = CandidateDecision(
            after_state="merged",
            shadow_after_state="merged",
            candidate_action="duplicate_merge",
            candidate_source="duplicate_group",
            safe_cleanup_candidate=True,
        )
    for item_id in _non_representative_duplicate_ids(
        experimental_result.get("merge_candidates")
    ):
        decisions.setdefault(
            item_id,
            CandidateDecision(
                after_state="active",
                shadow_after_state="merged",
                candidate_action="merge_suggestion",
                candidate_source="merge_candidate",
                requires_review=True,
                safe_cleanup_candidate=False,
            ),
        )
    for item_id in _str_set(experimental_result.get("stale_candidate_ids")):
        decisions.setdefault(
            item_id,
            CandidateDecision(
                after_state="stale",
                shadow_after_state="stale",
                candidate_action="stale_cleanup",
                candidate_source="stale_candidate",
                safe_cleanup_candidate=True,
            ),
        )
    for item_id in _str_set(experimental_result.get("low_value_candidate_ids")):
        decisions[item_id] = CandidateDecision(
            after_state="low_value_removed",
            shadow_after_state="low_value_removed",
            candidate_action="low_value_cleanup",
            candidate_source="low_value_candidate",
            safe_cleanup_candidate=True,
        )
    for item_id in _candidate_member_ids(experimental_result.get("conflict_candidates")):
        decisions.setdefault(
            item_id,
            CandidateDecision(
                after_state="active",
                shadow_after_state="active",
                candidate_action="conflict_review",
                candidate_source="conflict_candidate",
                requires_review=True,
                safe_cleanup_candidate=False,
            ),
        )
    return decisions


def _stable_shadow_metrics(metrics: dict[str, object]) -> dict[str, object]:
    stable = dict(metrics)
    stable["job_latency_ms"] = 0.0
    return stable


def _after_state_for_label(
    *,
    label: str,
    item_id: str,
    candidate_state_by_id: dict[str, str],
) -> str:
    candidate_state = candidate_state_by_id.get(item_id)
    if label == "duplicate":
        return "merged" if candidate_state == "merged" else "active"
    if label == "stale":
        return "stale" if candidate_state in {"stale", "low_value_removed"} else "active"
    if label == "low_value":
        return "low_value_removed" if candidate_state == "low_value_removed" else "active"
    if label == "retained":
        return candidate_state or "active"
    return "active"


def _after_state_for_expected(
    *,
    expected_after_state: str,
    item_id: str,
    candidate_state_by_id: dict[str, str],
) -> str:
    return candidate_state_by_id.get(item_id) or "active"


def _label_for_expected_state(expected_after_state: str) -> str:
    if expected_after_state == "merged":
        return "duplicate"
    if expected_after_state == "stale":
        return "stale"
    if expected_after_state == "low_value_removed":
        return "low_value"
    return "retained"


def _record(
    item: dict[str, object],
    *,
    label: str,
    after_state: str,
    case_id: str,
    case_set: str,
    scenario: str,
    expected_after_state: str,
    decision: CandidateDecision,
    source_evidence: SourceRefEvidence,
) -> dict[str, object]:
    baseline_tokens = _token_estimate(item.get("summary"))
    after_tokens = (
        0 if after_state in {"merged", "stale", "low_value_removed"} else baseline_tokens
    )
    return {
        "case_id": case_id,
        "case_set": case_set,
        "scenario": scenario,
        "item_id": str(item["id"]),
        "source_ref": str(item.get("source_ref") or ""),
        "baseline_state": "active",
        "after_state": after_state,
        "expected_after_state": expected_after_state,
        "label": label,
        "shadow_after_state": decision.shadow_after_state,
        "candidate_action": decision.candidate_action,
        "candidate_source": decision.candidate_source,
        "requires_review": decision.requires_review,
        "safe_cleanup_candidate": decision.safe_cleanup_candidate,
        "source_ref_available": source_evidence.source_ref_available,
        "source_fetch_success": source_evidence.source_fetch_success,
        "source_ref_parse_success": source_evidence.source_ref_parse_success,
        "source_fetch_mode": source_evidence.source_fetch_mode,
        "source_support_status": source_evidence.source_support_status,
        "source_support_reason": source_evidence.source_support_reason,
        "baseline_token_estimate": baseline_tokens,
        "after_token_estimate": after_tokens,
        "infra_error": False,
    }


_TARGET_HYGIENE_FIELDS = (
    "item_id",
    "baseline_state",
    "after_state",
    "label",
    "source_ref_available",
    "source_fetch_success",
    "baseline_token_estimate",
    "after_token_estimate",
    "infra_error",
)


def strip_sleep_hygiene_evidence_for_target_metrics(
    records: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {field: record[field] for field in _TARGET_HYGIENE_FIELDS}
        for record in records
    )


def _non_representative_duplicate_ids(groups: object) -> set[str]:
    duplicate_ids: set[str] = set()
    if not isinstance(groups, list):
        return duplicate_ids
    for group in groups:
        if not isinstance(group, dict):
            continue
        item_ids = [str(item_id) for item_id in group.get("item_ids", []) if str(item_id)]
        duplicate_ids.update(item_ids[1:])
    return duplicate_ids


def _candidate_member_ids(groups: object) -> set[str]:
    item_ids: set[str] = set()
    if not isinstance(groups, list):
        return item_ids
    for group in groups:
        if not isinstance(group, dict):
            continue
        item_ids.update(str(item_id) for item_id in group.get("item_ids", []) if str(item_id))
    return item_ids


def _expected_terms_for_item(item: dict[str, object]) -> tuple[str, ...]:
    fixture_terms = item.get("_source_expected_terms")
    if isinstance(fixture_terms, (list, tuple)):
        return tuple(str(term) for term in fixture_terms if str(term).strip())
    summary = str(item.get("summary") or "")
    terms = [term for term in ("用户", "memory", "偏好", "临时", "架构") if term in summary]
    return tuple(terms[:2])


def _str_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item_id) for item_id in value if str(item_id)}


def _metrics(
    records: Sequence[dict[str, object]],
    *,
    case_count: int,
    scanned_active_item_count: int,
) -> dict[str, object]:
    baseline_tokens = sum(float(record["baseline_token_estimate"]) for record in records)
    after_tokens = sum(float(record["after_token_estimate"]) for record in records)
    source_rows = [record for record in records if record["source_ref_available"]]
    retained_candidate_leak_count = sum(
        1
        for record in records
        if record["label"] == "retained"
        and record.get("safe_cleanup_candidate") is True
    )
    unexpected_candidate_count = sum(
        1 for record in records if not _record_matches_expected_candidate_state(record)
    )
    return {
        "case_count": case_count,
        "scanned_active_item_count": scanned_active_item_count,
        "evaluated_evidence_row_count": len(records),
        "duplicate_item_count": _count_label(records, "duplicate"),
        "stale_item_count": _count_label(records, "stale"),
        "low_value_item_count": _count_label(records, "low_value"),
        "retained_item_count": _count_label(records, "retained"),
        "duplicate_merge_rate": _rate(records, "duplicate", "merged"),
        "stale_cleanup_rate": _rate(records, "stale", "stale"),
        "low_value_cleanup_rate": _rate(records, "low_value", "low_value_removed"),
        "source_ref_coverage_rate": _bool_pct(records, "source_ref_available"),
        "source_fetch_success_rate": _bool_pct(source_rows, "source_fetch_success"),
        "shadow_estimated_token_saving_rate": round(
            (1 - after_tokens / baseline_tokens) * 100,
            4,
        )
        if baseline_tokens
        else "unavailable",
        "post_consolidation_recall_retention_rate": _rate(records, "retained", "active"),
        "retained_candidate_leak_count": retained_candidate_leak_count,
        "unexpected_candidate_count": unexpected_candidate_count,
        "false_positive_cleanup_rate": round(
            retained_candidate_leak_count / max(1, _count_label(records, "retained")) * 100,
            4,
        ),
        "source_evidence_metrics": _source_evidence_metrics(records),
        "source_evidence_metrics_by_action": _source_evidence_metrics_by_action(records),
        "group_metrics": _group_metrics(records),
        "scenario_metrics": _scenario_metrics(records),
    }


def _source_evidence_metrics(records: Sequence[dict[str, object]]) -> dict[str, object]:
    source_rows = [
        record for record in records if record.get("source_ref_available") is True
    ]
    parse_success_count = sum(
        1 for record in source_rows if record.get("source_ref_parse_success") is True
    )
    fetch_success_count = sum(
        1 for record in source_rows if record.get("source_fetch_success") is True
    )
    status_counts = _source_status_counts(records)
    mode_values = sorted(
        {
            str(record.get("source_fetch_mode") or "")
            for record in records
            if str(record.get("source_fetch_mode") or "").strip()
        }
    )
    return {
        "row_count": len(records),
        "source_fetch_mode": mode_values[0] if len(mode_values) == 1 else "mixed",
        "source_ref_available_count": len(source_rows),
        "source_ref_missing_count": len(records) - len(source_rows),
        "source_ref_coverage_rate": _ratio_pct(len(source_rows), len(records)),
        "source_ref_parse_success_count": parse_success_count,
        "source_ref_parse_success_rate": _ratio_pct(
            parse_success_count,
            len(source_rows),
        ),
        "source_fetch_success_count": fetch_success_count,
        "source_fetch_success_rate": _ratio_pct(fetch_success_count, len(source_rows)),
        "source_support_count": status_counts.get("supported", 0),
        "source_support_rate": _ratio_pct(
            status_counts.get("supported", 0),
            len(source_rows),
        ),
        "missing_source_count": status_counts.get("missing_source_ref", 0)
        + status_counts.get("missing", 0),
        "unsupported_source_count": status_counts.get("unsupported", 0),
        "session_ref_not_fetchable_count": status_counts.get(
            "session_ref_not_fetchable",
            0,
        ),
        "malformed_source_ref_count": status_counts.get("parse_failed", 0),
        "source_support_status_counts": status_counts,
    }


def _source_status_counts(records: Sequence[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        status = str(record.get("source_support_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _source_evidence_metrics_by_action(
    records: Sequence[dict[str, object]],
) -> dict[str, dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {
        "safe_cleanup_candidates": [
            record for record in records if record.get("safe_cleanup_candidate") is True
        ],
        "merge_suggestions": [
            record
            for record in records
            if record.get("candidate_action") == "merge_suggestion"
        ],
        "review_required": [
            record for record in records if record.get("requires_review") is True
        ],
        "retained_rows": [
            record for record in records if record.get("expected_after_state") == "active"
        ],
    }
    return {
        action: _source_evidence_metrics(action_records)
        for action, action_records in sorted(groups.items())
        if action_records
    }


def _record_matches_expected_candidate_state(record: dict[str, object]) -> bool:
    label = str(record["label"])
    after_state = str(record["after_state"])
    expected = {
        "duplicate": {"merged"},
        "stale": {"stale"},
        "low_value": {"low_value_removed"},
        "retained": {"active"},
    }[label]
    return after_state in expected


def _count_label(records: Sequence[dict[str, object]], label: str) -> int:
    return sum(1 for record in records if record["label"] == label)


def _rate(records: Sequence[dict[str, object]], label: str, after_state: str) -> float | str:
    labelled = [record for record in records if record["label"] == label]
    if not labelled:
        return "unavailable"
    return round(
        sum(1 for record in labelled if record["after_state"] == after_state)
        / len(labelled)
        * 100,
        4,
    )


def _bool_pct(records: Sequence[dict[str, object]], field: str) -> float | str:
    if not records:
        return "unavailable"
    return round(sum(1 for record in records if record[field]) / len(records) * 100, 4)


def _token_estimate(text: object) -> int:
    return max(1, len(str(text or "")) // 4)


def _fmt_pct(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value}%"
    return str(value)


def _source_fetch_success_label(metrics: dict[str, object]) -> str:
    source_metrics = metrics.get("source_evidence_metrics")
    if not isinstance(source_metrics, dict):
        return "proxy 回源成功率"
    mode = str(source_metrics.get("source_fetch_mode") or "").strip()
    if mode == "session-store":
        return "session-store 回源成功率"
    if mode:
        return f"{mode} 回源成功率"
    return "回源成功率"


def _group_metrics(records: Sequence[dict[str, object]]) -> dict[str, dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {
        "standard": [],
        "hard": [],
        "overall": list(records),
    }
    for record in records:
        groups.setdefault(str(record.get("case_set") or "standard"), []).append(record)
    return {
        name: _metrics_for_records(group_records)
        for name, group_records in groups.items()
        if group_records
    }


def _scenario_metrics(records: Sequence[dict[str, object]]) -> dict[str, dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for record in records:
        scenario = str(record.get("scenario") or "").strip()
        if not scenario:
            continue
        groups.setdefault(scenario, []).append(record)
    return {
        scenario: _metrics_for_records(group_records)
        for scenario, group_records in sorted(groups.items())
    }


def _metrics_for_records(records: Sequence[dict[str, object]]) -> dict[str, object]:
    expected_candidate_rows = [
        record for record in records if record["expected_after_state"] != "active"
    ]
    actual_candidate_rows = [
        record for record in records if record["after_state"] != "active"
    ]
    correct_candidate_rows = [
        record
        for record in actual_candidate_rows
        if record["after_state"] == record["expected_after_state"]
    ]
    retained_rows = [
        record for record in records if record["expected_after_state"] == "active"
    ]
    false_positive_rows = [
        record for record in retained_rows if record["after_state"] != "active"
    ]
    expected_cleanup_rows = [
        record for record in records if record["expected_after_state"] != "active"
    ]
    actual_safe_cleanup_rows = [
        record for record in records if record.get("safe_cleanup_candidate") is True
    ]
    correct_safe_cleanup_rows = [
        record
        for record in actual_safe_cleanup_rows
        if record["after_state"] == record["expected_after_state"]
    ]
    review_rows = [record for record in records if record.get("requires_review") is True]
    merge_suggestion_rows = [
        record for record in records if record.get("candidate_action") == "merge_suggestion"
    ]
    token_rate = _token_saving_rate(records)
    false_positive_rate = _ratio_pct(len(false_positive_rows), len(retained_rows))
    return {
        "case_count": len({str(record["case_id"]) for record in records}),
        "evaluated_item_count": len(records),
        "evidence_row_count": len(records),
        "candidate_recall": _ratio_pct(
            len(correct_candidate_rows),
            len(expected_candidate_rows),
        ),
        "candidate_precision": _ratio_pct(
            len(correct_candidate_rows),
            len(actual_candidate_rows),
        ),
        "retained_protection_rate": _ratio_pct(
            len(retained_rows) - len(false_positive_rows),
            len(retained_rows),
        ),
        "false_positive_cleanup_rate": false_positive_rate,
        "evidence_estimated_token_saving_rate": token_rate,
        "safe_evidence_estimated_token_saving_rate": (
            token_rate if false_positive_rate == 0.0 else "unsafe"
        ),
        "cleanup_candidate_recall": _ratio_pct(
            len(correct_safe_cleanup_rows),
            len(expected_cleanup_rows),
        ),
        "cleanup_candidate_precision": _ratio_pct(
            len(correct_safe_cleanup_rows),
            len(actual_safe_cleanup_rows),
        ),
        "merge_suggestion_count": len(merge_suggestion_rows),
        "review_required_count": len(review_rows),
        "safe_cleanup_token_saving_rate": _safe_cleanup_token_saving_rate(records),
    }


def _ratio_pct(numerator: int, denominator: int) -> float | str:
    if denominator <= 0:
        return "unavailable"
    return round(numerator / denominator * 100, 4)


def _token_saving_rate(records: Sequence[dict[str, object]]) -> float | str:
    baseline_tokens = sum(float(record["baseline_token_estimate"]) for record in records)
    after_tokens = sum(float(record["after_token_estimate"]) for record in records)
    if baseline_tokens <= 0:
        return "unavailable"
    return round((1 - after_tokens / baseline_tokens) * 100, 4)


def _safe_cleanup_token_saving_rate(records: Sequence[dict[str, object]]) -> float | str:
    baseline_tokens = sum(float(record["baseline_token_estimate"]) for record in records)
    if baseline_tokens <= 0:
        return "unavailable"
    saved_tokens = sum(
        float(record["baseline_token_estimate"]) - float(record["after_token_estimate"])
        for record in records
        if record.get("safe_cleanup_candidate") is True
    )
    return round(saved_tokens / baseline_tokens * 100, 4)
