from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memory2.eval_cases import EvalCase


@dataclass(frozen=True)
class RealSampleIssue:
    issue_type: str
    count: int
    detail: str = ""


@dataclass(frozen=True)
class RealMemorySample:
    sample_id: str
    category: str
    session_key: str
    channel: str
    chat_id: str
    query: str
    should_recall_ids: tuple[str, ...]
    should_not_recall_ids: tuple[str, ...]
    memory_items: tuple[dict[str, object], ...]
    memory_replacements: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class RealSampleSet:
    samples: tuple[RealMemorySample, ...]
    metrics: dict[str, Any]
    issues: tuple[RealSampleIssue, ...] = ()


def open_readonly_connection(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def load_memory_items_readonly(memory_db: Path, *, limit: int = 5000) -> list[dict[str, object]]:
    rows, _metrics = _load_memory_items_with_metrics(memory_db, limit=limit)
    return rows


def load_replacements_readonly(memory_db: Path, *, limit: int = 5000) -> list[dict[str, object]]:
    try:
        con = open_readonly_connection(memory_db)
    except sqlite3.OperationalError:
        return []
    try:
        if not _table_exists(con, "memory_replacements"):
            return []
        rows = con.execute(
            """
            SELECT old_item_id, old_memory_type, old_summary, old_source_ref,
                   old_extra_json, new_item_id, new_memory_type, new_summary,
                   new_source_ref, new_extra_json, relation_type, source_ref
            FROM memory_replacements
            ORDER BY created_at DESC, id ASC
            LIMIT ?
            """,
            (max(0, int(limit)),),
        ).fetchall()
    finally:
        con.close()
    result: list[dict[str, object]] = []
    for row in rows:
        result.append(
            {
                "old_item_id": str(row["old_item_id"] or ""),
                "old_memory_type": str(row["old_memory_type"] or ""),
                "old_summary": str(row["old_summary"] or ""),
                "old_source_ref": str(row["old_source_ref"] or ""),
                "old_extra_json": _parse_json_object(row["old_extra_json"])[0],
                "new_item_id": str(row["new_item_id"] or ""),
                "new_memory_type": str(row["new_memory_type"] or ""),
                "new_summary": str(row["new_summary"] or ""),
                "new_source_ref": str(row["new_source_ref"] or ""),
                "new_extra_json": _parse_json_object(row["new_extra_json"])[0],
                "relation_type": str(row["relation_type"] or ""),
                "source_ref": str(row["source_ref"] or ""),
            }
        )
    return result


def collect_real_memory_samples(
    workspace: Path,
    *,
    limit_per_category: int = 20,
) -> RealSampleSet:
    memory_db = workspace / "memory" / "memory2.db"
    item_limit = max(0, int(limit_per_category)) * 50 or 5000
    memory_items, item_metrics = _load_memory_items_with_metrics(memory_db, limit=item_limit)
    replacements = load_replacements_readonly(memory_db, limit=item_limit)
    usable_items = [
        item
        for item in memory_items
        if str(item.get("scope_channel") or "").strip()
        and str(item.get("scope_chat_id") or "").strip()
    ]
    missing_scope_count = len(memory_items) - len(usable_items)
    limit = max(0, int(limit_per_category))
    cross_scope_available = bool(_cross_scope_samples(usable_items, 1))
    version_chain_available = bool(_version_chain_samples(usable_items, replacements, 1))
    samples: list[RealMemorySample] = []
    samples.extend(_samples_by_type(usable_items, "preference", limit))
    samples.extend(_samples_by_type(usable_items, "procedure", limit))
    cross_scope_samples = _cross_scope_samples(usable_items, limit)
    samples.extend(cross_scope_samples)
    version_samples = _version_chain_samples(usable_items, replacements, limit)
    samples.extend(version_samples)

    missing_table_count = int(item_metrics.get("missing_table_count", 0))
    if memory_db.exists():
        try:
            con = open_readonly_connection(memory_db)
            try:
                if not _table_exists(con, "memory_replacements"):
                    missing_table_count += 1
            finally:
                con.close()
        except sqlite3.OperationalError:
            missing_table_count += 1

    metrics = {
        "memory_item_count": len(memory_items),
        "usable_memory_item_count": len(usable_items),
        "replacement_count": len(replacements),
        "invalid_extra_json_count": int(item_metrics.get("invalid_extra_json_count", 0)),
        "missing_scope_count": missing_scope_count,
        "missing_table_count": missing_table_count,
        "cross_scope_sample_unavailable": 0 if cross_scope_available else 1,
        "version_chain_sample_unavailable": 0 if version_chain_available else 1,
        "sample_count": len(samples),
    }
    issues = tuple(
        RealSampleIssue(key, int(value))
        for key, value in metrics.items()
        if key.endswith("_count") and isinstance(value, int) and value > 0
    )
    return RealSampleSet(samples=tuple(samples), metrics=metrics, issues=issues)


def real_sample_to_eval_case(sample: RealMemorySample) -> EvalCase:
    phase_targets, config_profiles, expected_traces, metric_keys, profile_expectations = (
        _case_shape_for_category(sample.category)
    )
    return EvalCase(
        id=sample.sample_id,
        title=f"Real sample {sample.category}: {sample.sample_id}",
        category=sample.category,
        phase_targets=phase_targets,
        config_profiles=config_profiles,
        setup={
            "scope": {
                "session_key": sample.session_key,
                "channel": sample.channel,
                "chat_id": sample.chat_id,
            },
            "memory_items": [dict(item) for item in sample.memory_items],
            "memory_replacements": [
                dict(replacement) for replacement in sample.memory_replacements
            ],
            "query": sample.query,
        },
        expectations={
            "should_recall_ids": list(sample.should_recall_ids),
            "should_not_recall_ids": list(sample.should_not_recall_ids),
            "expected_trace_features": expected_traces,
            "expected_metric_keys": metric_keys,
            "profile_expectations": profile_expectations,
        },
        source_path="real_sample",
    )


def real_samples_to_eval_cases(
    samples: list[RealMemorySample] | tuple[RealMemorySample, ...],
) -> list[EvalCase]:
    return [real_sample_to_eval_case(sample) for sample in samples]


def _load_memory_items_with_metrics(
    memory_db: Path,
    *,
    limit: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    metrics = {"invalid_extra_json_count": 0, "missing_table_count": 0}
    try:
        con = open_readonly_connection(memory_db)
    except sqlite3.OperationalError:
        metrics["missing_table_count"] = 1
        return [], metrics
    try:
        if not _table_exists(con, "memory_items"):
            metrics["missing_table_count"] = 1
            return [], metrics
        rows = con.execute(
            """
            SELECT id, memory_type, summary, reinforcement, emotional_weight,
                   extra_json, source_ref, happened_at, status, created_at, updated_at
            FROM memory_items
            ORDER BY updated_at DESC, id ASC
            LIMIT ?
            """,
            (max(0, int(limit)),),
        ).fetchall()
    finally:
        con.close()
    result: list[dict[str, object]] = []
    for row in rows:
        extra, ok = _parse_json_object(row["extra_json"])
        if not ok:
            metrics["invalid_extra_json_count"] += 1
            continue
        item = {
            "id": str(row["id"] or ""),
            "memory_type": str(row["memory_type"] or ""),
            "summary": str(row["summary"] or ""),
            "reinforcement": int(row["reinforcement"] or 0),
            "emotional_weight": int(row["emotional_weight"] or 0),
            "extra_json": extra,
            "source_ref": str(row["source_ref"] or ""),
            "happened_at": row["happened_at"],
            "status": str(row["status"] or "active"),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
            "scope_channel": str(extra.get("scope_channel") or ""),
            "scope_chat_id": str(extra.get("scope_chat_id") or ""),
        }
        result.append(item)
    return result, metrics


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _parse_json_object(raw: object) -> tuple[dict[str, object], bool]:
    if not raw:
        return {}, True
    try:
        loaded = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}, False
    if not isinstance(loaded, dict):
        return {}, False
    return dict(loaded), True


def _samples_by_type(
    memory_items: list[dict[str, object]],
    memory_type: str,
    limit: int,
) -> list[RealMemorySample]:
    samples: list[RealMemorySample] = []
    for item in memory_items:
        if len(samples) >= limit:
            break
        if str(item.get("status") or "") != "active":
            continue
        if str(item.get("memory_type") or "") != memory_type:
            continue
        samples.append(
            _sample(
                sample_id=f"real_{memory_type}_{item['id']}",
                category=memory_type,
                query=_query_for_item(item),
                should_recall_ids=(str(item["id"]),),
                should_not_recall_ids=(),
                memory_items=_same_scope_items(memory_items, item),
                memory_replacements=(),
                scope_item=item,
            )
        )
    return samples


def _cross_scope_samples(
    memory_items: list[dict[str, object]],
    limit: int,
) -> list[RealMemorySample]:
    samples: list[RealMemorySample] = []
    active = [
        item for item in memory_items if str(item.get("status") or "active") == "active"
    ]
    for item in active:
        if len(samples) >= limit:
            break
        negative = _find_cross_scope_item(item, active)
        if negative is None:
            continue
        samples.append(
            _sample(
                sample_id=f"real_cross_scope_{item['id']}_{negative['id']}",
                category="cross_scope",
                query=_query_for_item(item),
                should_recall_ids=(str(item["id"]),),
                should_not_recall_ids=(str(negative["id"]),),
                memory_items=(dict(item), dict(negative)),
                memory_replacements=(),
                scope_item=item,
            )
        )
    return samples


def _version_chain_samples(
    memory_items: list[dict[str, object]],
    replacements: list[dict[str, object]],
    limit: int,
) -> list[RealMemorySample]:
    by_id = {str(item.get("id") or ""): item for item in memory_items}
    samples: list[RealMemorySample] = []
    for replacement in replacements:
        if len(samples) >= limit:
            break
        new_id = str(replacement.get("new_item_id") or "")
        item = by_id.get(new_id)
        if item is None:
            continue
        samples.append(
            _sample(
                sample_id=f"real_version_chain_{replacement['old_item_id']}_{new_id}",
                category="version_chain",
                query=_query_for_item(item),
                should_recall_ids=(new_id,),
                should_not_recall_ids=(str(replacement.get("old_item_id") or ""),),
                memory_items=_same_scope_items(memory_items, item),
                memory_replacements=(dict(replacement),),
                scope_item=item,
            )
        )
    return samples


def _sample(
    *,
    sample_id: str,
    category: str,
    query: str,
    should_recall_ids: tuple[str, ...],
    should_not_recall_ids: tuple[str, ...],
    memory_items: tuple[dict[str, object], ...],
    memory_replacements: tuple[dict[str, object], ...],
    scope_item: dict[str, object],
) -> RealMemorySample:
    channel = str(scope_item.get("scope_channel") or "")
    chat_id = str(scope_item.get("scope_chat_id") or "")
    return RealMemorySample(
        sample_id=sample_id,
        category=category,
        session_key=f"{channel}:{chat_id}",
        channel=channel,
        chat_id=chat_id,
        query=query,
        should_recall_ids=should_recall_ids,
        should_not_recall_ids=should_not_recall_ids,
        memory_items=memory_items,
        memory_replacements=memory_replacements,
    )


def _same_scope_items(
    memory_items: list[dict[str, object]],
    item: dict[str, object],
) -> tuple[dict[str, object], ...]:
    channel = str(item.get("scope_channel") or "")
    chat_id = str(item.get("scope_chat_id") or "")
    return tuple(
        dict(candidate)
        for candidate in memory_items
        if str(candidate.get("scope_channel") or "") == channel
        and str(candidate.get("scope_chat_id") or "") == chat_id
    )


def _find_cross_scope_item(
    item: dict[str, object],
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    channel = str(item.get("scope_channel") or "")
    chat_id = str(item.get("scope_chat_id") or "")
    for candidate in candidates:
        if str(candidate.get("id") or "") == str(item.get("id") or ""):
            continue
        if (
            str(candidate.get("scope_chat_id") or "") == chat_id
            and str(candidate.get("scope_channel") or "") != channel
        ):
            return candidate
    for candidate in candidates:
        if str(candidate.get("id") or "") == str(item.get("id") or ""):
            continue
        if (
            str(candidate.get("scope_channel") or "") == channel
            and str(candidate.get("scope_chat_id") or "") != chat_id
        ):
            return candidate
    return None


def _query_for_item(item: dict[str, object]) -> str:
    memory_type = str(item.get("memory_type") or "")
    summary = str(item.get("summary") or "")
    if memory_type == "preference":
        return f"我的偏好是什么？{summary}"
    if memory_type == "procedure":
        return f"处理这个问题时应该遵守什么流程？{summary}"
    return summary


def _case_shape_for_category(
    category: str,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    list[str],
    dict[str, list[str]],
    dict[str, dict[str, object]],
]:
    if category in {"preference", "procedure"}:
        expected_traces = [
            "tri_retrieval",
            "rerank_shadow",
            "injection_governance_shadow",
        ]
        return (
            ("phase2a", "phase3a", "phase3b"),
            ("off", "phase2", "phase3", "all"),
            expected_traces,
            {
                "tri_retrieval": ["semantic_hit_count", "fused_hit_count"],
                "rerank_shadow": ["rerank_changed_count"],
                "injection_governance_shadow": ["prompt_token_delta"],
            },
            {
                "off": {"forbidden_trace_features": expected_traces},
                "phase2": {
                    "required_trace_features": ["tri_retrieval"],
                    "metric_keys": {
                        "tri_retrieval": ["semantic_hit_count", "fused_hit_count"]
                    },
                },
                "phase3": {
                    "required_trace_features": [
                        "rerank_shadow",
                        "injection_governance_shadow",
                    ],
                    "metric_keys": {
                        "rerank_shadow": ["rerank_changed_count"],
                        "injection_governance_shadow": ["prompt_token_delta"],
                    },
                },
                "all": {"required_trace_features": expected_traces},
            },
        )
    if category == "cross_scope":
        return (
            ("phase4b",),
            ("off", "phase4", "all"),
            ["provenance_shadow"],
            {"provenance_shadow": ["cross_scope_memory_count", "cross_scope_risk_count"]},
            {
                "off": {"forbidden_trace_features": ["provenance_shadow"]},
                "phase4": {
                    "required_trace_features": ["provenance_shadow"],
                    "metric_keys": {
                        "provenance_shadow": [
                            "cross_scope_memory_count",
                            "cross_scope_risk_count",
                        ]
                    },
                },
                "all": {"required_trace_features": ["provenance_shadow"]},
            },
        )
    return (
        ("phase4a",),
        ("off", "phase4", "all"),
        ["version_chain_shadow"],
        {"version_chain_shadow": ["replacement_count", "chain_count"]},
        {
            "off": {"forbidden_trace_features": ["version_chain_shadow"]},
            "phase4": {
                "required_trace_features": ["version_chain_shadow"],
                "metric_keys": {
                    "version_chain_shadow": ["replacement_count", "chain_count"]
                },
            },
            "all": {"required_trace_features": ["version_chain_shadow"]},
        },
    )
