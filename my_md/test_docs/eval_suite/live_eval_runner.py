#!/usr/bin/env python3
"""Live eval runner for Akashic Agent YAML cases.

This runner connects to the already-running Akashic IPC socket, sends selected
safe live cases, waits for assistant responses, reads observe.db, and writes a
Markdown report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("缺少 PyYAML，请先安装 yaml 支持。") from exc


ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ROOT / "large-eval-cases.yaml"
DEFAULT_WORKSPACE = Path.home() / ".akashic" / "workspace"
DEFAULT_SOCKET = "127.0.0.1:8765" if os.name == "nt" else "/tmp/akashic.sock"


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


@dataclass
class StepResult:
    channel: str
    text: str
    response: str
    turn: TurnEvidence


@dataclass
class CaseResult:
    case_id: str
    title: str
    category: str
    priority: str
    status: str
    score: float
    step_results: list[StepResult]
    issues: list[str]


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
        payload = json.dumps({"content": text}, ensure_ascii=False) + "\n"
        self.writer.write(payload.encode("utf-8"))
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
        if self.writer is None:
            return
        self.writer.close()
        await self.writer.wait_closed()


class ObserveStore:
    def __init__(self, workspace: Path) -> None:
        self.db_path = workspace / "observe" / "observe.db"

    def max_turn_id(self) -> int:
        if not self.db_path.exists():
            return 0
        con = sqlite3.connect(self.db_path)
        try:
            row = con.execute("SELECT COALESCE(MAX(id), 0) FROM turns").fetchone()
            return int(row[0] or 0)
        finally:
            con.close()

    def find_turn_after(self, baseline_id: int, user_msg: str, timeout: float = 8.0) -> TurnEvidence:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            turn = self._find_turn_after_once(baseline_id, user_msg)
            if turn.id is not None:
                return turn
            time.sleep(0.25)
        return TurnEvidence(user_msg=user_msg, error="observe turn not found")

    def _find_turn_after_once(self, baseline_id: int, user_msg: str) -> TurnEvidence:
        if not self.db_path.exists():
            return TurnEvidence(user_msg=user_msg, error="observe.db not found")
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                """
                SELECT id, session_key, user_msg, llm_output, tool_calls, error,
                       react_iteration_count, prompt_tokens
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
        tool_names = _tool_names(row["tool_calls"])
        return TurnEvidence(
            id=int(row["id"]),
            session_key=str(row["session_key"] or ""),
            user_msg=str(row["user_msg"] or ""),
            output=str(row["llm_output"] or ""),
            tool_names=tool_names,
            tool_count=len(tool_names),
            error=str(row["error"] or ""),
            iteration_count=row["react_iteration_count"],
            prompt_tokens=row["prompt_tokens"],
        )


def _tool_names(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        if isinstance(item, dict):
            name = item.get("name")
            if name:
                names.append(str(name))
    return names


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not isinstance(cases, list):
        raise SystemExit("YAML 中未找到 cases 列表")
    return [case for case in cases if isinstance(case, dict)]


def select_cases(cases: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    include_ids = set(args.case or [])
    for case in cases:
        if include_ids and str(case.get("id")) not in include_ids:
            continue
        if not include_ids:
            if case.get("execution_mode") != "live":
                continue
            if not args.include_guarded and case.get("risk_level", "safe") != "safe":
                continue
            if args.priority and case.get("priority") not in set(args.priority):
                continue
            if args.category and case.get("category") not in set(args.category):
                continue
        selected.append(case)
    if args.limit:
        selected = selected[: args.limit]
    return selected


def steps_for_case(case: dict[str, Any]) -> list[dict[str, str]]:
    raw_input = case.get("input") or {}
    if not isinstance(raw_input, dict):
        return []
    raw_steps = raw_input.get("steps")
    if isinstance(raw_steps, list):
        steps: list[dict[str, str]] = []
        for step in raw_steps:
            if not isinstance(step, dict):
                continue
            text = str(step.get("text") or "").strip()
            if text:
                steps.append({"channel": str(step.get("channel") or "cli"), "text": text})
        return steps
    text = str(raw_input.get("text") or "").strip()
    if not text:
        return []
    return [{"channel": str(raw_input.get("channel") or "cli"), "text": text}]


async def run_case(
    case: dict[str, Any],
    *,
    endpoint: str,
    observe: ObserveStore,
    timeout: float,
    dry_run: bool,
) -> CaseResult:
    case_id = str(case.get("id"))
    title = str(case.get("title") or "")
    category = str(case.get("category") or "")
    priority = str(case.get("priority") or "")
    planned_steps = steps_for_case(case)
    if dry_run:
        return CaseResult(case_id, title, category, priority, "dry_run", 0.0, [], [])
    clients: dict[str, IpcClient] = {}
    step_results: list[StepResult] = []
    issues: list[str] = []
    baseline = observe.max_turn_id()
    try:
        for step in planned_steps:
            channel = step["channel"]
            text = step["text"]
            client = clients.get(channel)
            if client is None:
                client = IpcClient(endpoint)
                clients[channel] = client
            try:
                response = await client.ask(text, timeout=timeout)
            except Exception as exc:
                issues.append(f"step failed: {channel} {type(exc).__name__}: {exc}")
                response = ""
                turn = TurnEvidence(user_msg=text, error=str(exc))
            else:
                turn = observe.find_turn_after(baseline, text)
                if turn.id is not None:
                    baseline = max(baseline, turn.id)
            step_results.append(StepResult(channel, text, response, turn))
    finally:
        for client in clients.values():
            await client.close()
    issues.extend(score_issues(case, step_results))
    status, score = status_from_issues(issues)
    return CaseResult(case_id, title, category, priority, status, score, step_results, issues)


def score_issues(case: dict[str, Any], steps: list[StepResult]) -> list[str]:
    expected = case.get("expected") or {}
    if not isinstance(expected, dict):
        return ["expected is not an object"]
    issues: list[str] = []
    if not steps:
        return ["no executable steps"]
    final = steps[-1]
    output = final.response or final.turn.output
    all_tools = [name for step in steps for name in step.turn.tool_names]
    if any(step.turn.error for step in steps):
        issues.append("turn error exists")

    contains = expected.get("final_answer_contains")
    if isinstance(contains, list):
        missing = [str(x) for x in contains if str(x) not in output]
        if missing:
            issues.append(f"missing answer text: {missing}")
    elif isinstance(contains, str) and contains not in output:
        issues.append(f"missing answer text: {contains}")

    contains_any = expected.get("final_answer_contains_any")
    if isinstance(contains_any, list) and contains_any:
        if not any(str(x) in output for x in contains_any):
            issues.append(f"answer contains none of: {contains_any}")

    not_contains = expected.get("final_answer_not_contains")
    if isinstance(not_contains, list):
        found = [str(x) for x in not_contains if str(x) in output]
        if found:
            issues.append(f"forbidden answer text found: {found}")

    tool_rule = expected.get("tool_calls")
    if isinstance(tool_rule, dict):
        expected_tools = tool_rule.get("expected")
        if expected_tools == [] and all_tools:
            issues.append(f"expected no tools, got {all_tools}")
        max_count = tool_rule.get("max_count")
        if isinstance(max_count, int) and len(all_tools) > max_count:
            issues.append(f"too many tools: {len(all_tools)} > {max_count}")
        must_include = tool_rule.get("must_include")
        if isinstance(must_include, list):
            missing = [str(x) for x in must_include if str(x) not in all_tools]
            if missing:
                issues.append(f"missing tools: {missing}; got {all_tools}")
        must_not_include = tool_rule.get("must_not_include")
        if isinstance(must_not_include, list):
            found = [str(x) for x in must_not_include if str(x) in all_tools]
            if found:
                issues.append(f"forbidden tools called: {found}")
        must_include_any = tool_rule.get("must_include_any")
        if isinstance(must_include_any, list) and must_include_any:
            if not any(str(x) in all_tools for x in must_include_any):
                issues.append(f"missing any tool from {must_include_any}; got {all_tools}")
    return issues


def status_from_issues(issues: list[str]) -> tuple[str, float]:
    if not issues:
        return "pass", 1.0
    hard = [issue for issue in issues if not issue.startswith("missing answer text")]
    if len(issues) <= 2 and not hard:
        return "partial", 0.5
    return "fail", 0.0


def write_report(path: Path, results: list[CaseResult], selected_count: int, dry_run: bool) -> None:
    passed = sum(1 for r in results if r.status == "pass")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "fail")
    lines = [
        "# Live Eval Report",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"执行模式：{'dry-run' if dry_run else 'live'}",
        f"选择用例数：{selected_count}",
        f"完成用例数：{len(results)}",
        "",
        "## 总览",
        "",
        "| 状态 | 数量 |",
        "| --- | ---: |",
        f"| pass | {passed} |",
        f"| partial | {partial} |",
        f"| fail | {failed} |",
        "",
        "## 明细",
        "",
        "| Case | 分类 | 优先级 | 状态 | 分数 | Turn | 工具 | 问题 |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for result in results:
        turn_ids = ",".join(str(s.turn.id) for s in result.step_results if s.turn.id is not None)
        tools = ",".join(name for s in result.step_results for name in s.turn.tool_names) or "-"
        issues = "<br>".join(result.issues) if result.issues else "-"
        lines.append(
            f"| {result.case_id} {result.title} | {result.category} | {result.priority} | "
            f"{result.status} | {result.score:.1f} | {turn_ids or '-'} | {tools} | {issues} |"
        )
    lines.append("")
    lines.append("## 输入与回答")
    for result in results:
        lines.append("")
        lines.append(f"### {result.case_id} {result.title}")
        for step in result.step_results:
            lines.append("")
            lines.append(f"- channel: `{step.channel}`")
            lines.append(f"- turn_id: `{step.turn.id}`")
            lines.append("")
            lines.append("输入：")
            lines.append("")
            lines.append("```text")
            lines.append(step.text)
            lines.append("```")
            lines.append("")
            lines.append("回答：")
            lines.append("")
            lines.append("```text")
            lines.append((step.response or step.turn.output).strip())
            lines.append("```")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Run selected Akashic live eval cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    parser.add_argument("--priority", action="append", default=["P0"])
    parser.add_argument("--category", action="append")
    parser.add_argument("--case", action="append", help="Run one case id; can be repeated.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--include-guarded", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / f"live-eval-report-{datetime.now().date().isoformat()}.md",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases)
    selected = select_cases(cases, args)
    if not selected:
        raise SystemExit("没有选中任何 case，请检查过滤条件。")
    observe = ObserveStore(args.workspace)

    results: list[CaseResult] = []
    print(f"selected={len(selected)} dry_run={args.dry_run} report={args.report}")
    for index, case in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {case.get('id')} {case.get('title')}")
        result = await run_case(
            case,
            endpoint=args.socket,
            observe=observe,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        results.append(result)
        print(f"  -> {result.status} issues={len(result.issues)}")
    write_report(args.report, results, len(selected), args.dry_run)
    print(f"report written: {args.report}")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
