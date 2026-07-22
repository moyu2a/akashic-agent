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
from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)


FIXED_NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SleepHygieneEvidenceReport:
    records: tuple[dict[str, object], ...]
    metrics: dict[str, object]
    shadow_metrics: dict[str, object]


def build_sleep_hygiene_evidence_records(
    cases: Sequence[SleepHygieneCase],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, object], ...]:
    items = flatten_sleep_hygiene_memory_items(cases)
    item_by_id = {str(item["id"]): item for item in items}
    shadow = build_sleep_consolidation_shadow_result(
        memory_items=items,
        now=now or FIXED_NOW,
        max_duplicate_groups=10_000,
        max_merge_candidates=10_000,
        max_stale_candidates=10_000,
        max_low_value_candidates=10_000,
        max_conflict_candidates=10_000,
    )
    candidate_state_by_id = _candidate_state_by_id(shadow.experimental_result)

    records: list[dict[str, object]] = []
    for case in cases:
        for item_id in case.expected_item_ids:
            item = item_by_id[str(item_id)]
            after_state = _after_state_for_label(
                label=case.label,
                item_id=str(item_id),
                candidate_state_by_id=candidate_state_by_id,
            )
            records.append(_record(item, label=case.label, after_state=after_state))
    return tuple(records)


def run_sleep_hygiene_evidence_eval(
    *,
    duplicate_groups: int = 120,
    stale_count: int = 120,
    low_value_count: int = 120,
    retained_count: int = 120,
    missing_source_count: int = 40,
    cases: Sequence[SleepHygieneCase] | None = None,
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
    records = build_sleep_hygiene_evidence_records(selected_cases, now=FIXED_NOW)
    candidate_state_by_id = _candidate_state_by_id(shadow.experimental_result)
    return SleepHygieneEvidenceReport(
        records=records,
        metrics=_metrics(
            records,
            case_count=len(selected_cases),
            scanned_active_item_count=int(shadow.metrics.get("scanned_count", 0) or 0),
            candidate_state_by_id=candidate_state_by_id,
        ),
        shadow_metrics=dict(shadow.metrics),
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
        f"| proxy 回源成功率 | {metrics['source_fetch_success_rate']}% |",
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _candidate_state_by_id(experimental_result: dict[str, object]) -> dict[str, str]:
    states: dict[str, str] = {}
    for item_id in _non_representative_duplicate_ids(
        experimental_result.get("duplicate_groups")
    ):
        states[item_id] = "merged"
    for item_id in _non_representative_duplicate_ids(
        experimental_result.get("merge_candidates")
    ):
        states.setdefault(item_id, "merged")
    for item_id in _str_set(experimental_result.get("stale_candidate_ids")):
        states.setdefault(item_id, "stale")
    for item_id in _str_set(experimental_result.get("low_value_candidate_ids")):
        states[item_id] = "low_value_removed"
    return states


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


def _record(
    item: dict[str, object],
    *,
    label: str,
    after_state: str,
) -> dict[str, object]:
    baseline_tokens = _token_estimate(item.get("summary"))
    after_tokens = (
        0 if after_state in {"merged", "stale", "low_value_removed"} else baseline_tokens
    )
    source_ref_available = bool(str(item.get("source_ref") or "").strip())
    return {
        "item_id": str(item["id"]),
        "baseline_state": "active",
        "after_state": after_state,
        "label": label,
        "source_ref_available": source_ref_available,
        "source_fetch_success": source_ref_available,
        "baseline_token_estimate": baseline_tokens,
        "after_token_estimate": after_tokens,
        "infra_error": False,
    }


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


def _str_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item_id) for item_id in value if str(item_id)}


def _metrics(
    records: Sequence[dict[str, object]],
    *,
    case_count: int,
    scanned_active_item_count: int,
    candidate_state_by_id: dict[str, str],
) -> dict[str, object]:
    baseline_tokens = sum(float(record["baseline_token_estimate"]) for record in records)
    after_tokens = sum(float(record["after_token_estimate"]) for record in records)
    source_rows = [record for record in records if record["source_ref_available"]]
    retained_candidate_leak_count = sum(
        1
        for record in records
        if record["label"] == "retained" and record["item_id"] in candidate_state_by_id
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
