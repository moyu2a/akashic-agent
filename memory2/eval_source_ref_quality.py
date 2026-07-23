from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from memory2.eval_sleep_hygiene_provenance import (
    SessionStoreSourceRefResolver,
    SourceRefEvidence,
    SourceRefResolver,
    parse_source_ref_for_fetch,
)
from memory2.source_ref_quality import (
    SourceRefQualityInput,
    normalize_source_ref_shadow,
)
from session.store import SessionStore


@dataclass(frozen=True)
class SourceRefQualityReport:
    records: tuple[dict[str, object], ...]
    metrics: dict[str, object]
    metadata: dict[str, object]
    group_metrics: dict[str, dict[str, dict[str, object]]]


@dataclass(frozen=True)
class SourceRefFixtureHandle:
    resolver: SourceRefResolver
    store: SessionStore

    def close(self) -> None:
        self.store.close()


def build_source_ref_quality_fixture(
    db_path: Path,
) -> tuple[SourceRefQualityInput, ...]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _reset_fixture_db_if_safe(db_path)
    store = SessionStore(db_path)
    try:
        store.create_session(key="cli:local")
        _insert(store, 0, "用户偏好：回答记忆问题时先说结论")
        _insert(store, 1, "用户强调 source_ref 要能回到真实消息")
        _insert(store, 2, "用户希望长期记忆来源使用消息级 id")
        _insert(store, 3, "用户说临时测试内容不要长期保存")
        _insert(store, 4, "这条消息不支持候选摘要")
    finally:
        store.close()
    _mark_fixture_db(db_path)
    return (
        SourceRefQualityInput(
            candidate_id="already-message-supported",
            session_key="cli:local",
            baseline_source_ref="cli:local:0",
            candidate_message_ids=("cli:local:0",),
            expected_terms=("偏好",),
        ),
        SourceRefQualityInput(
            candidate_id="session-level-upgradable",
            session_key="cli:local",
            baseline_source_ref="cli:local@post_response",
            candidate_message_ids=("cli:local:1",),
            expected_terms=("source_ref",),
        ),
        SourceRefQualityInput(
            candidate_id="missing-upgradable",
            session_key="cli:local",
            baseline_source_ref="",
            candidate_message_ids=("cli:local:2",),
            expected_terms=("消息级",),
        ),
        SourceRefQualityInput(
            candidate_id="malformed-upgradable",
            session_key="cli:local",
            baseline_source_ref='["broken"',
            candidate_message_ids=("cli:local:3",),
            expected_terms=("临时测试",),
        ),
        SourceRefQualityInput(
            candidate_id="unsupported-message-kept",
            session_key="cli:local",
            baseline_source_ref="cli:local:4",
            candidate_message_ids=("cli:local:4",),
            expected_terms=("不存在的支持词",),
        ),
        SourceRefQualityInput(
            candidate_id="session-level-no-ids",
            session_key="cli:local",
            baseline_source_ref="cli:local@post_response",
            candidate_message_ids=(),
            expected_terms=("无法猜测",),
        ),
    )


def open_marked_source_ref_quality_fixture_resolver(
    db_path: Path,
) -> SourceRefFixtureHandle:
    if not _is_marked_fixture_db(db_path):
        raise ValueError(
            f"refusing to open unmarked source_ref quality fixture db: {db_path}"
        )
    store = SessionStore(db_path)
    return SourceRefFixtureHandle(
        resolver=SessionStoreSourceRefResolver(store),
        store=store,
    )


def reset_source_ref_quality_fixture_db_if_safe(db_path: Path) -> None:
    _reset_fixture_db_if_safe(db_path)


def mark_source_ref_quality_fixture_db(db_path: Path) -> None:
    _mark_fixture_db(db_path)


def run_source_ref_quality_eval(
    *,
    candidates: Sequence[SourceRefQualityInput],
    source_ref_resolver: SourceRefResolver,
) -> SourceRefQualityReport:
    records = tuple(
        _record(candidate, source_ref_resolver)
        for candidate in candidates
    )
    return SourceRefQualityReport(
        records=records,
        metrics=_metrics(records),
        metadata={
            "evaluation_mode": "synthetic_fixture_shadow",
            "production_uplift": False,
            "writes_production_memory": False,
            "description": (
                "Synthetic controlled fixture result only; this does not prove "
                "production online uplift and does not modify memory_items.source_ref."
            ),
        },
        group_metrics={
            "case_sets": _group_metrics(records, _case_set_from_candidate_id),
            "scenarios": _group_metrics(records, _scenario_from_candidate_id),
        },
    )


def with_source_ref_quality_metadata(
    report: SourceRefQualityReport,
    extra_metadata: dict[str, object],
) -> SourceRefQualityReport:
    return SourceRefQualityReport(
        records=report.records,
        metrics=report.metrics,
        metadata={**report.metadata, **extra_metadata},
        group_metrics=report.group_metrics,
    )


def write_source_ref_quality_json(
    report: SourceRefQualityReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_source_ref_quality_markdown(
    report: SourceRefQualityReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = report.metrics
    lines = [
        "# Source Ref Quality Shadow Report",
        "",
        "本报告只评估 shadow normalized_source_ref，不修改真实 memory_items.source_ref。",
        "",
        "数据语境：synthetic controlled fixture；这不是线上真实提升结论。",
        "",
        "| metric | before | after | delta points |",
        "| --- | ---: | ---: | ---: |",
        _metric_row(metrics, "message_level_rate"),
        _metric_row(metrics, "parse_success_rate"),
        _metric_row(metrics, "fetch_success_rate"),
        _metric_row(metrics, "support_rate"),
        _metric_row(metrics, "source_backed_eligible_rate"),
        "",
        "| count | value |",
        "| --- | ---: |",
        f"| candidate_count | {metrics['candidate_count']} |",
        f"| source_backed_eligible_count_before | {metrics['source_backed_eligible_count_before']} |",
        f"| source_backed_eligible_count_after | {metrics['source_backed_eligible_count_after']} |",
        f"| malformed_source_ref_count_before | {metrics['malformed_source_ref_count_before']} |",
        f"| malformed_source_ref_count_after | {metrics['malformed_source_ref_count_after']} |",
    ]
    case_set_groups = report.group_metrics.get("case_sets", {})
    scenario_groups = report.group_metrics.get("scenarios", {})
    if case_set_groups:
        lines.extend(
            [
                "",
                "## Case Set Metrics",
                "",
                "| case_set | candidates | before eligible | after eligible | delta points |",
                "| --- | ---: | ---: | ---: | ---: |",
                *_group_rows(case_set_groups),
            ]
        )
    if scenario_groups:
        lines.extend(
            [
                "",
                "## Scenario Metrics",
                "",
                "| scenario | candidates | before eligible | after eligible | fetch after | support after |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
                *_scenario_rows(scenario_groups),
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _record(
    candidate: SourceRefQualityInput,
    resolver: SourceRefResolver,
) -> dict[str, object]:
    normalized = normalize_source_ref_shadow(candidate)
    baseline_evidence = _resolve_scoped(
        resolver,
        normalized.baseline_source_ref,
        session_key=normalized.session_key,
        expected_terms=normalized.expected_terms,
    )
    normalized_evidence = _resolve_scoped(
        resolver,
        normalized.normalized_source_ref,
        session_key=normalized.session_key,
        expected_terms=normalized.expected_terms,
    )
    return {
        **asdict(normalized),
        "baseline_fetch_success": baseline_evidence.source_fetch_success,
        "normalized_fetch_success": normalized_evidence.source_fetch_success,
        "baseline_support_status": baseline_evidence.source_support_status,
        "normalized_support_status": normalized_evidence.source_support_status,
        "baseline_source_backed_eligible": _eligible(baseline_evidence),
        "normalized_source_backed_eligible": _eligible(normalized_evidence),
    }


def _resolve_scoped(
    resolver: SourceRefResolver,
    source_ref: object,
    *,
    session_key: str,
    expected_terms: Sequence[str],
) -> SourceRefEvidence:
    parsed = parse_source_ref_for_fetch(source_ref)
    if parsed.fetchable_by_id:
        if any(
            not _is_message_id_for_session(message_id, session_key=session_key)
            for message_id in parsed.message_ids
        ):
            support_status = "foreign_session_source"
            if any(
                str(message_id or "").strip().startswith(
                    f"{str(session_key).strip()}:"
                )
                for message_id in parsed.message_ids
            ):
                support_status = "invalid_message_id"
            return SourceRefEvidence(
                source_ref_available=bool(str(source_ref or "").strip()),
                source_ref_parse_success=parsed.parse_ok,
                source_fetch_success=False,
                source_fetch_mode="scoped",
                source_support_status=support_status,
            )
    return resolver.resolve(source_ref, expected_terms=expected_terms)


def _metrics(records: Sequence[dict[str, object]]) -> dict[str, object]:
    return {
        "candidate_count": len(records),
        "baseline_message_level_rate": _rate(records, "baseline_level", "message"),
        "normalized_message_level_rate": _rate(records, "normalized_level", "message"),
        "message_level_uplift_points": _delta_rate(
            records,
            "baseline_level",
            "normalized_level",
            "message",
        ),
        "baseline_parse_success_rate": _bool_rate(records, "baseline_parse_ok"),
        "normalized_parse_success_rate": _bool_rate(records, "normalized_parse_ok"),
        "parse_success_uplift_points": _delta_bool_rate(
            records,
            "baseline_parse_ok",
            "normalized_parse_ok",
        ),
        "baseline_fetch_success_rate": _bool_rate(records, "baseline_fetch_success"),
        "normalized_fetch_success_rate": _bool_rate(
            records,
            "normalized_fetch_success",
        ),
        "fetch_success_uplift_points": _delta_bool_rate(
            records,
            "baseline_fetch_success",
            "normalized_fetch_success",
        ),
        "baseline_support_rate": _status_rate(
            records,
            "baseline_support_status",
            "supported",
        ),
        "normalized_support_rate": _status_rate(
            records,
            "normalized_support_status",
            "supported",
        ),
        "support_uplift_points": _delta_status_rate(
            records,
            "baseline_support_status",
            "normalized_support_status",
            "supported",
        ),
        "source_backed_eligible_count_before": _bool_count(
            records,
            "baseline_source_backed_eligible",
        ),
        "source_backed_eligible_count_after": _bool_count(
            records,
            "normalized_source_backed_eligible",
        ),
        "baseline_source_backed_eligible_rate": _bool_rate(
            records,
            "baseline_source_backed_eligible",
        ),
        "normalized_source_backed_eligible_rate": _bool_rate(
            records,
            "normalized_source_backed_eligible",
        ),
        "source_backed_eligible_uplift_points": _delta_bool_rate(
            records,
            "baseline_source_backed_eligible",
            "normalized_source_backed_eligible",
        ),
        "malformed_source_ref_count_before": _level_count(
            records,
            "baseline_level",
            "malformed",
        ),
        "malformed_source_ref_count_after": _level_count(
            records,
            "normalized_level",
            "malformed",
        ),
    }


def _group_metrics(
    records: Sequence[dict[str, object]],
    key_fn: Callable[[str], str],
) -> dict[str, dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for record in records:
        key = key_fn(str(record.get("candidate_id") or ""))
        if not key:
            continue
        groups.setdefault(key, []).append(record)
    return {
        key: _metrics(tuple(group_records))
        for key, group_records in sorted(groups.items())
    }


def _case_set_from_candidate_id(candidate_id: str) -> str:
    parts = candidate_id.split("::", 2)
    if len(parts) != 3:
        return ""
    case_set, _scenario, index = parts
    if case_set not in {"common", "hard"} or not index.isdigit():
        return ""
    return case_set


def _scenario_from_candidate_id(candidate_id: str) -> str:
    parts = candidate_id.split("::", 2)
    if len(parts) != 3:
        return ""
    case_set, scenario, index = parts
    if case_set not in {"common", "hard"} or not index.isdigit():
        return ""
    return scenario


def _insert(store: SessionStore, seq: int, content: str) -> None:
    store.insert_message(
        "cli:local",
        role="user",
        content=content,
        ts="2026-07-22T00:00:00+08:00",
        seq=seq,
        extra={"source_ref_quality_fixture": True},
    )


def _reset_fixture_db_if_safe(db_path: Path) -> None:
    if db_path.exists() and not _is_marked_fixture_db(db_path):
        raise ValueError(
            f"refusing to overwrite existing non-fixture session db: {db_path}"
        )
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()


def _is_marked_fixture_db(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                """
                SELECT value
                FROM source_ref_quality_fixture_meta
                WHERE key = 'fixture_name'
                """
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
    return row is not None and row[0] == "source_ref_quality_shadow"


def _is_message_id_for_session(message_id: object, *, session_key: str) -> bool:
    prefix = f"{str(session_key).strip()}:"
    clean_id = str(message_id or "").strip()
    if not clean_id.startswith(prefix):
        return False
    return clean_id[len(prefix):].isdigit()


def _mark_fixture_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_ref_quality_fixture_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO source_ref_quality_fixture_meta (key, value)
            VALUES ('fixture_name', 'source_ref_quality_shadow')
            """
        )
        conn.commit()
    finally:
        conn.close()


def _eligible(evidence: SourceRefEvidence) -> bool:
    return (
        evidence.source_fetch_success is True
        and evidence.source_support_status == "supported"
    )


def _rate(
    records: Sequence[dict[str, object]],
    field: str,
    expected: str,
) -> float | str:
    if not records:
        return "unavailable"
    count = sum(1 for record in records if str(record.get(field) or "") == expected)
    return round(count / len(records) * 100, 4)


def _bool_rate(records: Sequence[dict[str, object]], field: str) -> float | str:
    if not records:
        return "unavailable"
    return round(_bool_count(records, field) / len(records) * 100, 4)


def _status_rate(
    records: Sequence[dict[str, object]],
    field: str,
    expected: str,
) -> float | str:
    return _rate(records, field, expected)


def _delta_rate(
    records: Sequence[dict[str, object]],
    before_field: str,
    after_field: str,
    expected: str,
) -> float | str:
    before = _rate(records, before_field, expected)
    after = _rate(records, after_field, expected)
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return "unavailable"
    return round(after - before, 4)


def _delta_bool_rate(
    records: Sequence[dict[str, object]],
    before_field: str,
    after_field: str,
) -> float | str:
    before = _bool_rate(records, before_field)
    after = _bool_rate(records, after_field)
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return "unavailable"
    return round(after - before, 4)


def _delta_status_rate(
    records: Sequence[dict[str, object]],
    before_field: str,
    after_field: str,
    expected: str,
) -> float | str:
    return _delta_rate(records, before_field, after_field, expected)


def _bool_count(records: Sequence[dict[str, object]], field: str) -> int:
    return sum(1 for record in records if record.get(field) is True)


def _level_count(
    records: Sequence[dict[str, object]],
    field: str,
    expected: str,
) -> int:
    return sum(1 for record in records if str(record.get(field) or "") == expected)


def _metric_row(metrics: dict[str, object], stem: str) -> str:
    before = metrics[f"baseline_{stem}"]
    after = metrics[f"normalized_{stem}"]
    delta = metrics[f"{stem.removesuffix('_rate')}_uplift_points"]
    return f"| {stem} | {_fmt(before)} | {_fmt(after)} | {_fmt(delta)} |"


def _group_rows(groups: dict[str, dict[str, object]]) -> list[str]:
    rows = []
    for name, metrics in groups.items():
        rows.append(
            f"| {name} | {metrics['candidate_count']} | "
            f"{_fmt(metrics['baseline_source_backed_eligible_rate'])} | "
            f"{_fmt(metrics['normalized_source_backed_eligible_rate'])} | "
            f"{_fmt(metrics['source_backed_eligible_uplift_points'])} |"
        )
    return rows


def _scenario_rows(groups: dict[str, dict[str, object]]) -> list[str]:
    rows = []
    for name, metrics in groups.items():
        rows.append(
            f"| {name} | {metrics['candidate_count']} | "
            f"{_fmt(metrics['baseline_source_backed_eligible_rate'])} | "
            f"{_fmt(metrics['normalized_source_backed_eligible_rate'])} | "
            f"{_fmt(metrics['normalized_fetch_success_rate'])} | "
            f"{_fmt(metrics['normalized_support_rate'])} |"
        )
    return rows


def _fmt(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value}%"
    return str(value)
