#!/usr/bin/env python3
"""Deep fully automated live eval runner for Akashic Agent.

The runner connects to an already-running Akashic IPC socket, executes selected
live cases, reads local trace databases, applies rule checks, optionally calls a
judge model, and writes Markdown + JSON reports.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少 PyYAML，请先安装 yaml 支持。") from exc


ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ROOT / "deep-live-eval-cases.yaml"
DEFAULT_REPORT_DIR = ROOT / "reports"
DEFAULT_WORKSPACE = Path.home() / ".akashic" / "workspace"
DEFAULT_SOCKET = "127.0.0.1:8765" if os.name == "nt" else "/tmp/akashic.sock"
DEFAULT_JUDGE_MODEL = "deepseek-chat"
DEFAULT_JUDGE_BASE_URL = "https://api.deepseek.com/v1"


@dataclass
class TurnEvidence:
    id: int | None = None
    session_key: str = ""
    user_msg: str = ""
    output: str = ""
    tool_names: list[str] = field(default_factory=list)
    tool_count: int = 0
    error: str = ""
    iteration_count: int | None = None
    prompt_tokens: int | None = None
    cache_hit_tokens: int | None = None
    cache_prompt_tokens: int | None = None


@dataclass
class StepResult:
    channel: str
    text: str
    response: str
    turn: TurnEvidence


@dataclass
class JudgeResult:
    verdict: str = "skipped"
    score: float = 0.0
    reason: str = ""
    failure_type: str = "judge_skipped"


@dataclass
class CaseResult:
    case_id: str
    title: str
    category: str
    priority: str
    risk_level: str
    status: str
    score: float
    failure_type: str
    step_results: list[StepResult]
    issues: list[str]
    judge: JudgeResult


class IpcClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        if self.endpoint.count(":") == 1 and not self.endpoint.startswith("/"):
            host, port_text = self.endpoint.rsplit(":", 1)
            self.reader, self.writer = await asyncio.open_connection(host, int(port_text))
            return
        self.reader, self.writer = await asyncio.open_unix_connection(self.endpoint)

    async def ask(self, text: str, timeout: float) -> str:
        if self.reader is None or self.writer is None:
            await self.connect()
        assert self.reader is not None
        assert self.writer is not None
        self.writer.write((json.dumps({"content": text}, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.writer.drain()
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError(f"等待回复超时: {text[:80]}")
            line = await asyncio.wait_for(self.reader.readline(), timeout=left)
            if not line:
                raise ConnectionError("IPC 连接已断开")
            data = json.loads(line.decode("utf-8"))
            if data.get("type") == "assistant":
                return str(data.get("content") or "")

    async def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()


class TraceStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.observe_db = workspace / "observe" / "observe.db"
        self.sessions_db = workspace / "sessions.db"
        self.memory_db = workspace / "memory" / "memory2.db"

    def max_turn_id(self) -> int:
        if not self.observe_db.exists():
            return 0
        con = sqlite3.connect(self.observe_db)
        try:
            row = con.execute("SELECT COALESCE(MAX(id), 0) FROM turns").fetchone()
            return int(row[0] or 0)
        finally:
            con.close()

    def find_turn_after(self, baseline_id: int, user_msg: str, timeout: float = 10.0) -> TurnEvidence:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            turn = self._find_turn_after_once(baseline_id, user_msg)
            if turn.id is not None:
                return turn
            time.sleep(0.25)
        return TurnEvidence(user_msg=user_msg, error="observe turn not found")

    def _find_turn_after_once(self, baseline_id: int, user_msg: str) -> TurnEvidence:
        if not self.observe_db.exists():
            return TurnEvidence(user_msg=user_msg, error="observe.db not found")
        con = sqlite3.connect(self.observe_db)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                """
                SELECT id, session_key, user_msg, llm_output, tool_calls, error,
                       react_iteration_count, prompt_tokens,
                       react_cache_hit_tokens, react_cache_prompt_tokens
                FROM turns
                WHERE id > ? AND user_msg = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (baseline_id, user_msg),
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return TurnEvidence(user_msg=user_msg)
        names = tool_names(row["tool_calls"])
        return TurnEvidence(
            id=int(row["id"]),
            session_key=str(row["session_key"] or ""),
            user_msg=str(row["user_msg"] or ""),
            output=str(row["llm_output"] or ""),
            tool_names=names,
            tool_count=len(names),
            error=str(row["error"] or ""),
            iteration_count=row["react_iteration_count"],
            prompt_tokens=row["prompt_tokens"],
            cache_hit_tokens=row["react_cache_hit_tokens"],
            cache_prompt_tokens=row["react_cache_prompt_tokens"],
        )

    def memory_rows_like(self, text: str) -> list[dict[str, Any]]:
        if not self.memory_db.exists():
            return []
        con = sqlite3.connect(self.memory_db)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                """
                SELECT id, memory_type, summary, source_ref, status, created_at, updated_at
                FROM memory_items
                WHERE summary LIKE ?
                ORDER BY updated_at DESC
                LIMIT 20
                """,
                (f"%{text}%",),
            ).fetchall()
        finally:
            con.close()
        return [dict(row) for row in rows]


def tool_names(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item.get("name")) for item in data if isinstance(item, dict) and item.get("name")]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if key in {"id", "suffix"}:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("YAML 顶层必须是对象")
    cases = [case for case in data.get("cases", []) if isinstance(case, dict)]
    for group in data.get("matrix_cases", []) or []:
        if not isinstance(group, dict):
            continue
        prefix = str(group.get("id_prefix") or "")
        template = {k: v for k, v in group.items() if k not in {"id_prefix", "variants"}}
        for variant in group.get("variants", []) or []:
            if not isinstance(variant, dict):
                continue
            case = deep_merge(template, variant)
            suffix = str(variant.get("id") or variant.get("suffix") or "")
            case["id"] = f"{prefix}{suffix}"
            cases.append(case)
    return cases


def select_cases(cases: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    ids = set(args.case or [])
    selected: list[dict[str, Any]] = []
    for case in cases:
        if ids and str(case.get("id")) not in ids:
            continue
        if not ids:
            if case.get("execution_mode", "live") not in {"live", "offline_after_live"}:
                continue
            if not args.include_guarded and case.get("risk_level", "safe") != "safe":
                continue
            if args.priority and case.get("priority") not in set(args.priority):
                continue
            if args.category and case.get("category") not in set(args.category):
                continue
            if args.suite == "smoke" and case.get("priority") != "P0":
                continue
        selected.append(case)
    if args.suite == "smoke" and not args.limit:
        selected = selected[:10]
    if args.limit:
        selected = selected[: args.limit]
    return selected


def steps_for_case(case: dict[str, Any]) -> list[dict[str, str]]:
    raw = case.get("input") or {}
    if not isinstance(raw, dict):
        return []
    if isinstance(raw.get("steps"), list):
        steps: list[dict[str, str]] = []
        for step in raw["steps"]:
            if isinstance(step, dict) and str(step.get("text") or "").strip():
                steps.append(
                    {
                        "channel": str(step.get("channel") or "cli"),
                        "text": str(step.get("text")).strip(),
                    }
                )
        return steps
    text = str(raw.get("text") or "").strip()
    return [{"channel": str(raw.get("channel") or "cli"), "text": text}] if text else []


async def run_case(
    case: dict[str, Any],
    *,
    endpoint: str,
    trace: TraceStore,
    timeout: float,
    dry_run: bool,
    judge_enabled: bool,
) -> CaseResult:
    case_id = str(case.get("id"))
    title = str(case.get("title") or "")
    category = str(case.get("category") or "")
    priority = str(case.get("priority") or "")
    risk_level = str(case.get("risk_level") or "safe")
    if dry_run:
        return CaseResult(case_id, title, category, priority, risk_level, "dry_run", 0.0, "dry_run", [], [], JudgeResult())

    clients: dict[str, IpcClient] = {}
    step_results: list[StepResult] = []
    issues: list[str] = []
    baseline = trace.max_turn_id()
    try:
        for step in steps_for_case(case):
            channel = step["channel"]
            client = clients.get(channel)
            if client is None:
                client = IpcClient(endpoint)
                clients[channel] = client
            try:
                response = await client.ask(step["text"], timeout=timeout)
                turn = trace.find_turn_after(baseline, step["text"])
                if turn.id is not None:
                    baseline = max(baseline, turn.id)
            except Exception as exc:
                response = ""
                turn = TurnEvidence(user_msg=step["text"], error=f"{type(exc).__name__}: {exc}")
                issues.append(f"step failed: {channel} {type(exc).__name__}: {exc}")
            step_results.append(StepResult(channel, step["text"], response, turn))
    finally:
        for client in clients.values():
            await client.close()

    issues.extend(score_rule_issues(case, step_results, trace))
    judge = await judge_case(case, step_results, enabled=judge_enabled)
    if judge.verdict == "fail":
        issues.append(f"judge fail: {judge.reason}")
    elif judge.verdict == "partial":
        issues.append(f"judge partial: {judge.reason}")

    status, score = status_from_issues(issues, judge)
    failure_type = infer_failure_type(issues, judge)
    return CaseResult(case_id, title, category, priority, risk_level, status, score, failure_type, step_results, issues, judge)


def score_rule_issues(case: dict[str, Any], steps: list[StepResult], trace: TraceStore) -> list[str]:
    expected = case.get("expected") or {}
    issues: list[str] = []
    if not steps:
        return ["no executable steps"]
    if any(step.turn.error for step in steps):
        issues.append("turn error exists")
    final_output = steps[-1].response or steps[-1].turn.output
    all_output = "\n".join(step.response or step.turn.output for step in steps)
    all_tools = [name for step in steps for name in step.turn.tool_names]

    check_contains(expected.get("final_answer_contains"), final_output, "final answer", issues)
    check_contains_any(expected.get("final_answer_contains_any"), final_output, "final answer", issues)
    check_not_contains(expected.get("final_answer_not_contains"), final_output, "final answer", issues)
    check_not_contains(expected.get("final_answer_not_contains_as_fact"), final_output, "final answer fact", issues)
    check_not_contains(expected.get("final_answer_not_contains_as_current"), final_output, "final current fact", issues)
    check_contains(expected.get("all_answers_contain"), all_output, "all answers", issues)

    tool_rule = expected.get("tool_calls")
    if isinstance(tool_rule, dict):
        if tool_rule.get("expected") == [] and all_tools:
            issues.append(f"expected no tools, got {all_tools}")
        max_count = tool_rule.get("max_count")
        if isinstance(max_count, int) and len(all_tools) > max_count:
            issues.append(f"too many tools: {len(all_tools)} > {max_count}")
        must_include = tool_rule.get("must_include")
        if isinstance(must_include, list):
            missing = [str(x) for x in must_include if str(x) not in all_tools]
            if missing:
                issues.append(f"missing tools: {missing}; got {all_tools}")
        must_include_any = tool_rule.get("must_include_any")
        if isinstance(must_include_any, list) and not any(str(x) in all_tools for x in must_include_any):
            issues.append(f"missing any tool from {must_include_any}; got {all_tools}")
        must_not_include = tool_rule.get("must_not_include")
        if isinstance(must_not_include, list):
            found = [str(x) for x in must_not_include if str(x) in all_tools]
            if found:
                issues.append(f"forbidden tools called: {found}")

    session_rule = expected.get("session")
    if isinstance(session_rule, dict):
        channel_to_key = {step.channel: step.turn.session_key for step in steps if step.turn.session_key}
        for pair in session_rule.get("different", []) or []:
            if len(pair) == 2 and channel_to_key.get(pair[0]) == channel_to_key.get(pair[1]):
                issues.append(f"sessions should differ: {pair}")
        for pair in session_rule.get("same", []) or []:
            if len(pair) == 2 and channel_to_key.get(pair[0]) != channel_to_key.get(pair[1]):
                issues.append(f"sessions should match: {pair}")

    memory_rule = expected.get("memory")
    if isinstance(memory_rule, dict):
        contains = memory_rule.get("contains")
        if contains:
            rows = trace.memory_rows_like(str(contains))
            if not rows:
                issues.append(f"memory missing: {contains}")
            if memory_rule.get("active") and not any(str(row.get("status")) == "active" for row in rows):
                issues.append(f"memory not active: {contains}")
            if memory_rule.get("source_ref_non_empty") and not any(str(row.get("source_ref") or "").strip() for row in rows):
                issues.append(f"memory source_ref missing: {contains}")

    cost = expected.get("cost")
    if isinstance(cost, dict):
        total_tools = sum(step.turn.tool_count for step in steps)
        max_tools = cost.get("tool_call_count_max")
        if isinstance(max_tools, int) and total_tools > max_tools:
            issues.append(f"tool count too high: {total_tools} > {max_tools}")
        max_iter = cost.get("react_iteration_count_max")
        if isinstance(max_iter, int):
            for step in steps:
                if step.turn.iteration_count is not None and step.turn.iteration_count > max_iter:
                    issues.append(f"iteration too high: turn {step.turn.id} {step.turn.iteration_count} > {max_iter}")
        max_tokens = cost.get("prompt_tokens_soft_max")
        if isinstance(max_tokens, int):
            for step in steps:
                if step.turn.prompt_tokens is not None and step.turn.prompt_tokens > max_tokens:
                    issues.append(f"prompt tokens high: turn {step.turn.id} {step.turn.prompt_tokens} > {max_tokens}")
    return issues


def check_contains(expected: Any, text: str, label: str, issues: list[str]) -> None:
    if isinstance(expected, list):
        missing = [str(x) for x in expected if str(x) not in text]
        if missing:
            issues.append(f"{label} missing text: {missing}")
    elif isinstance(expected, str) and expected not in text:
        issues.append(f"{label} missing text: {expected}")


def check_contains_any(expected: Any, text: str, label: str, issues: list[str]) -> None:
    if isinstance(expected, list) and expected and not any(str(x) in text for x in expected):
        issues.append(f"{label} contains none of: {expected}")


def check_not_contains(expected: Any, text: str, label: str, issues: list[str]) -> None:
    if isinstance(expected, list):
        found = [str(x) for x in expected if str(x) in text]
        if found:
            issues.append(f"{label} forbidden text found: {found}")


async def judge_case(case: dict[str, Any], steps: list[StepResult], *, enabled: bool) -> JudgeResult:
    judge_cfg = ((case.get("scoring") or {}).get("judge") or {}) if isinstance(case.get("scoring"), dict) else {}
    if not enabled or not judge_cfg.get("enabled"):
        return JudgeResult()
    api_key = (
        os.getenv("EVAL_JUDGE_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    model = os.getenv("EVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    base_url = os.getenv("EVAL_JUDGE_BASE_URL", DEFAULT_JUDGE_BASE_URL)
    if not api_key:
        return JudgeResult(reason="judge api key not configured; set DEEPSEEK_API_KEY or EVAL_JUDGE_API_KEY")
    rubric = str(judge_cfg.get("rubric") or "判断该 case 是否满足 expected。")
    payload = {
        "case": {
            "id": case.get("id"),
            "title": case.get("title"),
            "expected": case.get("expected"),
            "rubric": rubric,
        },
        "steps": [
            {
                "channel": step.channel,
                "input": step.text,
                "answer": step.response or step.turn.output,
                "tools": step.turn.tool_names,
            }
            for step in steps
        ],
    }
    prompt = (
        "你是 agent eval judge。只输出 JSON，不要输出 Markdown。\n"
        "字段必须是 verdict, score, reason, failure_type。\n"
        "verdict 只能是 pass/partial/fail；failure_type 只能是 "
        "agent_bug/test_assertion_too_strict/judge_uncertain/infra_issue。\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        content = await call_openai_compatible_chat(
            api_key=api_key,
            base_url=base_url,
            model=model,
            prompt=prompt,
        )
        data = json.loads(content)
    except Exception as exc:
        return JudgeResult(verdict="skipped", reason=f"judge failed: {exc}", failure_type="infra_issue")
    verdict = str(data.get("verdict") or "skipped")
    if verdict not in {"pass", "partial", "fail"}:
        verdict = "skipped"
    return JudgeResult(
        verdict=verdict,
        score=float(data.get("score") or 0.0),
        reason=str(data.get("reason") or ""),
        failure_type=str(data.get("failure_type") or "judge_uncertain"),
    )


async def call_openai_compatible_chat(*, api_key: str, base_url: str, model: str, prompt: str) -> str:
    """Call an OpenAI-compatible chat endpoint without requiring the openai package."""

    def _post() -> str:
        endpoint = base_url.rstrip("/") + "/chat/completions"
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"judge http {exc.code}: {detail[:500]}") from exc
        data = json.loads(raw)
        return str(data["choices"][0]["message"].get("content") or "{}")

    return await asyncio.to_thread(_post)


def status_from_issues(issues: list[str], judge: JudgeResult) -> tuple[str, float]:
    if judge.verdict in {"pass", "partial", "fail"} and not issues:
        return judge.verdict, judge.score
    if not issues:
        return "pass", 1.0
    hard = [issue for issue in issues if not issue.startswith("final answer missing text")]
    if len(issues) <= 2 and not hard:
        return "partial", 0.5
    return "fail", 0.0


def infer_failure_type(issues: list[str], judge: JudgeResult) -> str:
    if not issues:
        return "none"
    if judge.failure_type not in {"", "judge_skipped"}:
        return judge.failure_type
    if any("step failed" in issue or "turn error" in issue for issue in issues):
        return "infra_issue"
    if any("missing text" in issue or "contains none" in issue for issue in issues):
        return "test_assertion_too_strict"
    return "agent_bug"


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = {}
    for result in results:
        by_status[result.status] = by_status.get(result.status, 0) + 1
        cat = by_category.setdefault(result.category, {})
        cat[result.status] = cat.get(result.status, 0) + 1
    avg_tools = 0.0
    avg_iters = 0.0
    turn_count = 0
    iter_count = 0
    for result in results:
        for step in result.step_results:
            avg_tools += step.turn.tool_count
            turn_count += 1
            if step.turn.iteration_count is not None:
                avg_iters += step.turn.iteration_count
                iter_count += 1
    return {
        "total": len(results),
        "by_status": by_status,
        "by_category": by_category,
        "avg_tool_calls_per_turn": round(avg_tools / turn_count, 2) if turn_count else 0.0,
        "avg_iterations_per_turn": round(avg_iters / iter_count, 2) if iter_count else 0.0,
    }


def write_reports(report_dir: Path, results: list[CaseResult], *, dry_run: bool) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    md_path = report_dir / f"deep-live-report-{stamp}.md"
    json_path = report_dir / f"deep-live-report-{stamp}.json"
    summary = summarize(results)
    payload = {"summary": summary, "dry_run": dry_run, "results": [asdict(result) for result in results]}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Deep Live Eval Report",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"执行模式：{'dry-run' if dry_run else 'live'}",
        "",
        "## 总览",
        "",
        f"- total: {summary['total']}",
        f"- pass: {summary['by_status'].get('pass', 0)}",
        f"- partial: {summary['by_status'].get('partial', 0)}",
        f"- fail: {summary['by_status'].get('fail', 0)}",
        f"- avg_tool_calls_per_turn: {summary['avg_tool_calls_per_turn']}",
        f"- avg_iterations_per_turn: {summary['avg_iterations_per_turn']}",
        "",
        "## 分模块",
        "",
        "| Category | Pass | Partial | Fail |",
        "| --- | ---: | ---: | ---: |",
    ]
    for category, counts in sorted(summary["by_category"].items()):
        lines.append(
            f"| {category} | {counts.get('pass', 0)} | {counts.get('partial', 0)} | {counts.get('fail', 0)} |"
        )
    lines.extend(
        [
            "",
            "## 明细",
            "",
            "| Case | 分类 | 优先级 | 风险 | 状态 | 分数 | Failure Type | Turn | Tools | Issues | Judge |",
            "| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for result in results:
        turn_ids = ",".join(str(step.turn.id) for step in result.step_results if step.turn.id is not None) or "-"
        tools = ",".join(name for step in result.step_results for name in step.turn.tool_names) or "-"
        issues = "<br>".join(result.issues) if result.issues else "-"
        judge = result.judge.verdict if result.judge.verdict != "skipped" else "-"
        lines.append(
            f"| {result.case_id} {result.title} | {result.category} | {result.priority} | {result.risk_level} | "
            f"{result.status} | {result.score:.1f} | {result.failure_type} | {turn_ids} | {tools} | {issues} | {judge} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Run deep automated Akashic live eval cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--suite", choices=["all", "smoke"], default="all")
    parser.add_argument("--priority", action="append")
    parser.add_argument("--category", action="append")
    parser.add_argument("--case", action="append")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--include-guarded", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    selected = select_cases(cases, args)
    if not selected:
        raise SystemExit("没有选中任何 case，请检查过滤条件。")
    trace = TraceStore(args.workspace)
    results: list[CaseResult] = []
    print(f"selected={len(selected)} dry_run={args.dry_run} judge={args.judge}")
    for index, case in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {case.get('id')} {case.get('title')}", flush=True)
        result = await run_case(
            case,
            endpoint=args.socket,
            trace=trace,
            timeout=args.timeout,
            dry_run=args.dry_run,
            judge_enabled=args.judge,
        )
        results.append(result)
        print(f"  -> {result.status} issues={len(result.issues)} failure_type={result.failure_type}", flush=True)
    md_path, json_path = write_reports(args.report_dir, results, dry_run=args.dry_run)
    print(f"markdown report: {md_path}")
    print(f"json report: {json_path}")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
