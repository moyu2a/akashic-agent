from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import load_config
from agent.config_models import OptimizationConfig
from agent.optimization.real_ab_run import (
    RealABRecord,
    expected_fast_path_for_profile,
    phase_profiles,
    sanitize_preview,
    select_suite_cases,
    summarize_real_ab_records,
    write_real_ab_json,
    write_real_ab_markdown,
)
from bootstrap.tools import build_core_runtime
from core.net.http import SharedHttpResources

_COST_LATENCY_DISABLED_TOOLS: frozenset[str] = frozenset(
    {
        "shell",
        "task_output",
        "task_stop",
        "write_file",
        "edit_file",
        "message_push",
        "memorize",
        "forget_memory",
    }
)


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("realab-%Y%m%dT%H%M%S%fZ")


def _sanitize_runtime_config(cfg) -> None:
    cfg.optimization = OptimizationConfig(enabled=True, default_profile="baseline")
    cfg.peer_agents = []
    cfg.proactive.enabled = False
    cfg.memory_optimizer_enabled = False
    cfg.spawn_enabled = False
    cfg.tool_search_enabled = False
    cfg.wiring.toolsets = [
        name for name in cfg.wiring.toolsets if name in {"meta_common", "schedule"}
    ]


def _strip_cost_latency_side_effect_tools(runtime) -> None:
    for name in _COST_LATENCY_DISABLED_TOOLS:
        runtime.tools.unregister(name)


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", default="my_md/optimization_profiles/real_ab")
    parser.add_argument("--enable-real-llm", action="store_true")
    parser.add_argument(
        "--suite",
        default="cost_latency",
        choices=("cost_latency", "disabled_tool_policy"),
    )
    args = parser.parse_args()

    if not bool(args.enable_real_llm):
        parser.error("--enable-real-llm is required for real A/B runs")
    try:
        profiles = phase_profiles(args.phase)
        cases = select_suite_cases(args.phase, args.suite)
    except ValueError as exc:
        parser.error(str(exc))
    if not cases:
        parser.error(f"no cases selected for phase={args.phase} suite={args.suite}")

    run_id = _run_id()
    workspace = Path(args.workspace)
    out_dir = Path(args.out_dir)
    records = await _run_phase(
        phase=str(args.phase).strip().upper(),
        profiles=profiles,
        cases=cases,
        config_path=Path(args.config),
        workspace=workspace,
        run_id=run_id,
    )
    report = summarize_real_ab_records(records)
    phase_name = str(args.phase).strip().lower()
    json_path = out_dir / f"optimization_real_ab_phase_{phase_name}.json"
    md_path = out_dir / f"optimization_real_ab_phase_{phase_name}.md"
    write_real_ab_json(report, json_path)
    write_real_ab_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0 if report.metrics["gate_pass"] else 1


async def _run_phase(
    *,
    phase: str,
    profiles: tuple[str, ...],
    cases: tuple[Any, ...],
    config_path: Path,
    workspace: Path,
    run_id: str,
) -> list[RealABRecord]:
    cfg = load_config(config_path)
    _sanitize_runtime_config(cfg)
    records: list[RealABRecord] = []
    for profile in profiles:
        for case in cases:
            records.append(
                await _run_single_case(
                    cfg=cfg,
                    phase=phase,
                    profile=profile,
                    case=case,
                    workspace=workspace / run_id / phase.lower() / profile / case.case_id,
                    run_id=run_id,
                )
            )
    return records


async def _run_single_case(
    *,
    cfg,
    phase: str,
    profile: str,
    case: Any,
    workspace: Path,
    run_id: str,
) -> RealABRecord:
    workspace.mkdir(parents=True, exist_ok=True)
    http_resources = SharedHttpResources()
    runtime = build_core_runtime(cfg, workspace, http_resources)
    _strip_cost_latency_side_effect_tools(runtime)
    session_key = f"real-ab:{phase}:{run_id}:{profile}:{case.case_id}"
    try:
        await runtime.start()
        reply = await runtime.loop.process_direct(
            case.prompt,
            session_key=session_key,
            channel="cli",
            chat_id=session_key,
            skip_post_memory=True,
            stream_events=False,
            turn_metadata={
                "optimization_profile": profile,
                "experiment_tag": f"real_ab_{phase.lower()}_{profile}",
                "run_id": run_id,
            },
        )
        row = _fetch_turn_row(workspace / "observe" / "observe.db", session_key)
        if row is None:
            raise RuntimeError(f"observe row not found for {session_key}")
        return RealABRecord(
            run_id=run_id,
            phase=phase,
            profile=profile,
            case_id=case.case_id,
            category=case.category,
            prompt_preview=sanitize_preview(case.prompt),
            reply_preview=sanitize_preview(reply),
            correctness=_determine_correctness(reply, case),
            simple_fast_path=bool(row["simple_fast_path"] or 0),
            expected_fast_path=expected_fast_path_for_profile(profile, case),
            tool_error_count=int(row["tool_error_count"] or 0),
            actual_prompt_tokens_sum=_opt_int(row["actual_prompt_tokens_sum"]),
            actual_total_tokens_sum=_opt_int(row["actual_total_tokens_sum"]),
            turn_duration_ms=_opt_int(row["turn_duration_ms"]),
            llm_duration_ms_sum=_opt_int(row["llm_duration_ms_sum"]),
            react_iteration_count=_opt_int(row["react_iteration_count"]),
            actual_tools=_actual_tools(row),
            expected_tools=tuple(case.expected_tools),
            denied_tool_attempt_count=_denied_tool_attempt_count(
                workspace / "tool_audit" / "tool_audit.db"
            ),
            unregistered_tool_count=_unregistered_tool_count(
                workspace / "tool_audit" / "tool_audit.db"
            ),
            forbidden_reply_pattern_count=_forbidden_reply_pattern_count(reply, case),
            expected_tool_missing_count=_expected_tool_missing_count(row, case),
            note="real llm gated ab; isolated workspace per profile/case",
        )
    finally:
        await runtime.stop()
        await http_resources.aclose()


def _fetch_turn_row(observe_db: Path, session_key: str) -> sqlite3.Row | None:
    if not observe_db.exists():
        return None
    conn = sqlite3.connect(observe_db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT *
            FROM turns
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_key,),
        ).fetchone()
    finally:
        conn.close()


def _actual_tools(row: sqlite3.Row) -> tuple[str, ...]:
    names: list[str] = []
    for raw in (row["tool_calls"], row["tool_chain_json"]):
        for name in _tool_names_from_json(raw):
            if name:
                names.append(name)
    return tuple(dict.fromkeys(names))


def _tool_names_from_json(raw: object) -> list[str]:
    try:
        payload = json.loads(str(raw or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    names: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if "calls" in item and isinstance(item["calls"], list):
            for call in item["calls"]:
                if isinstance(call, dict):
                    names.append(str(call.get("name") or call.get("tool") or ""))
        else:
            names.append(str(item.get("name") or item.get("tool") or ""))
    return names


def _denied_tool_attempt_count(audit_db: Path) -> int:
    return _audit_count(
        audit_db,
        """
        SELECT count(*)
        FROM tool_audit_events
        WHERE policy_action IN ('deny', 'defer', 'blocked')
           OR policy_reason LIKE '%unregistered_tool%'
        """,
    )


def _unregistered_tool_count(audit_db: Path) -> int:
    return _audit_count(
        audit_db,
        """
        SELECT count(*)
        FROM tool_audit_events
        WHERE policy_reason LIKE '%unregistered_tool%'
        """,
    )


def _audit_count(audit_db: Path, sql: str) -> int:
    if not audit_db.exists():
        return 0
    conn = sqlite3.connect(audit_db)
    try:
        row = conn.execute(sql).fetchone()
    finally:
        conn.close()
    return int(row[0] or 0) if row is not None else 0


def _forbidden_reply_pattern_count(reply: str, case: Any) -> int:
    text = str(reply or "")
    return sum(1 for pattern in case.forbidden_reply_patterns if pattern in text)


def _expected_tool_missing_count(row: sqlite3.Row, case: Any) -> int:
    actual = set(_actual_tools(row))
    return sum(1 for tool in case.expected_tools if tool not in actual)


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return None
    return ivalue


def _determine_correctness(reply: str, case: Any) -> str:
    text = str(reply or "").strip()
    if not text:
        return "FAIL"
    if any(pattern and pattern not in text for pattern in case.required_reply_patterns):
        return "FAIL"
    if case.expected_fast_path and len(text) > 4000:
        return "WARN"
    return "PASS"


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
