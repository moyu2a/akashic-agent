from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class OfflineRouteGovernanceRow:
    scene: str
    case_count: int
    baseline_success: int
    gated_success: int
    graph_success: int
    candidate_drop_rate: float
    expected_route_hit_rate: float
    candidate_accept_rate: float
    graph_used_rate: float
    note: str


@dataclass(frozen=True)
class LiveRouteGovernanceRow:
    scene: str
    case_count: int
    candidate_accept_rate: float
    candidate_drop_rate: float
    graph_used_rate: float
    note: str


@dataclass(frozen=True)
class RouteGovernanceReport:
    offline_rows: tuple[OfflineRouteGovernanceRow, ...]
    live_rows: tuple[LiveRouteGovernanceRow, ...]
    metrics: dict[str, object]


def build_offline_route_governance_rows(
    quantitative_report: object,
) -> tuple[OfflineRouteGovernanceRow, ...]:
    records = [dict(row) for row in getattr(quantitative_report, "case_records", ())]
    by_case_profile = {
        (str(row.get("case_id") or ""), str(row.get("profile_name") or "")): row
        for row in records
    }
    tri_rows = [
        row
        for row in records
        if row.get("profile_name") == "tri_retrieval_only"
        and str(row.get("retrieval_scene") or "").strip()
    ]
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in tri_rows:
        grouped.setdefault(str(row.get("retrieval_scene") or "unknown"), []).append(row)

    result: list[OfflineRouteGovernanceRow] = []
    for scene, rows in sorted(grouped.items()):
        baseline_success = 0
        gated_success = 0
        graph_success = 0
        drop_rates: list[float] = []
        expected_hit_rates: list[float] = []
        accept_rates: list[float] = []
        graph_used_values: list[float] = []
        note = ""
        for row in rows:
            case_id = str(row.get("case_id") or "")
            baseline = by_case_profile.get((case_id, "memory_base"), {})
            graph = by_case_profile.get((case_id, "graph_only"), {})
            baseline_success += _int(baseline.get("success_count"))
            gated_success += _int(row.get("success_count"))
            graph_success += _int(graph.get("success_count"))
            drop_rates.append(_rate_pct(row.get("candidate_drop_rate")))
            expected_hit_rates.append(
                _rate_pct(row.get("expected_route_hit_rate", row.get("route_hit_rate")))
            )
            accept_rates.append(_rate_pct(row.get("candidate_accept_rate")))
            graph_used_values.append(100.0 if bool(graph.get("graph_lane_used")) else 0.0)
            if not note:
                decision = row.get("route_decision")
                if isinstance(decision, Mapping):
                    note = str(decision.get("reason") or "")
        result.append(
            OfflineRouteGovernanceRow(
                scene=scene,
                case_count=len(rows),
                baseline_success=baseline_success,
                gated_success=gated_success,
                graph_success=graph_success,
                candidate_drop_rate=_avg(drop_rates),
                expected_route_hit_rate=_avg(expected_hit_rates),
                candidate_accept_rate=_avg(accept_rates),
                graph_used_rate=_avg(graph_used_values),
                note=note or "offline trace",
            )
        )
    return tuple(result)


def build_live_route_governance_rows(
    route_results: Sequence[Mapping[str, object]],
) -> tuple[LiveRouteGovernanceRow, ...]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for result in route_results:
        scene = str(result.get("scene") or "unknown")
        grouped.setdefault(scene, []).append(result)
    rows: list[LiveRouteGovernanceRow] = []
    for scene, results in sorted(grouped.items()):
        rows.append(
            LiveRouteGovernanceRow(
                scene=scene,
                case_count=len(results),
                candidate_accept_rate=_avg(
                    [
                        _rate_pct(
                            result.get("candidate_accept_rate", result.get("route_hit_rate"))
                        )
                        for result in results
                    ]
                ),
                candidate_drop_rate=_avg(
                    [_rate_pct(result.get("candidate_drop_rate")) for result in results]
                ),
                graph_used_rate=_avg(
                    [100.0 if bool(result.get("graph_used")) else 0.0 for result in results]
                ),
                note=_join_notes(result.get("note") for result in results),
            )
        )
    return tuple(rows)


def build_route_governance_report(
    *,
    quantitative_report: object,
    live_route_results: Sequence[Mapping[str, object]] = (),
) -> RouteGovernanceReport:
    offline_rows = build_offline_route_governance_rows(quantitative_report)
    live_rows = build_live_route_governance_rows(live_route_results)
    return RouteGovernanceReport(
        offline_rows=offline_rows,
        live_rows=live_rows,
        metrics={
            "offline_scene_count": len(offline_rows),
            "offline_case_count": sum(row.case_count for row in offline_rows),
            "live_scene_count": len(live_rows),
            "live_case_count": sum(row.case_count for row in live_rows),
        },
    )


def route_governance_markdown_lines(
    offline_rows: Sequence[OfflineRouteGovernanceRow],
    *,
    heading: str = "## 三路召回路由表",
) -> list[str]:
    lines = [
        "",
        heading,
        "",
        "| scene | cases | baseline_success | gated_success | graph_success | candidate_drop_rate | expected_route_hit_rate | candidate_accept_rate | graph_used_rate | note |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    if not offline_rows:
        lines.append("| unavailable | 0 | 0 | 0 | 0 | unavailable | unavailable | unavailable | unavailable | no route trace |")
        return lines
    for row in offline_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scene,
                    str(row.case_count),
                    str(row.baseline_success),
                    str(row.gated_success),
                    str(row.graph_success),
                    _fmt_pct(row.candidate_drop_rate),
                    _fmt_pct(row.expected_route_hit_rate),
                    _fmt_pct(row.candidate_accept_rate),
                    _fmt_pct(row.graph_used_rate),
                    row.note,
                ]
            )
            + " |"
        )
    return lines


def live_route_governance_markdown_lines(
    live_rows: Sequence[LiveRouteGovernanceRow],
    *,
    heading: str = "## 真实引擎 route smoke",
) -> list[str]:
    lines = [
        "",
        heading,
        "",
        "| scene | case_count | candidate_accept_rate | candidate_drop_rate | graph_used_rate | note |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    if not live_rows:
        lines.append("| unavailable | 0 | unavailable | unavailable | unavailable | no live route trace |")
        return lines
    for row in live_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scene,
                    str(row.case_count),
                    _fmt_pct(row.candidate_accept_rate),
                    _fmt_pct(row.candidate_drop_rate),
                    _fmt_pct(row.graph_used_rate),
                    row.note,
                ]
            )
            + " |"
        )
    return lines


def write_route_governance_json(
    report: RouteGovernanceReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "metrics": report.metrics,
                "offline_rows": [asdict(row) for row in report.offline_rows],
                "live_rows": [asdict(row) for row in report.live_rows],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def write_route_governance_markdown(
    report: RouteGovernanceReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 记忆三路召回路由治理报告",
        "",
        "本报告只展示路由和候选治理证据。离线表来自确定性 trace，真实引擎表来自 `DefaultMemoryEngine.retrieve()` 的 route smoke。",
    ]
    lines.extend(route_governance_markdown_lines(report.offline_rows))
    lines.extend(live_route_governance_markdown_lines(report.live_rows))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rate_pct(value: object) -> float:
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return round(numeric * 100.0, 4) if 0.0 <= numeric <= 1.0 else round(numeric, 4)


def _avg(values: Sequence[float]) -> float:
    clean = [float(value) for value in values]
    if not clean:
        return 0.0
    return round(sum(clean) / len(clean), 4)


def _fmt_pct(value: object) -> str:
    if isinstance(value, int | float):
        return f"{round(float(value), 4)}%"
    return str(value)


def _join_notes(values: Sequence[object]) -> str:
    notes = sorted({str(value).strip() for value in values if str(value).strip()})
    return "; ".join(notes[:3]) if notes else "ok"
