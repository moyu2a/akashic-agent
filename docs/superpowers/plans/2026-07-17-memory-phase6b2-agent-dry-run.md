# Memory Phase6b-2 Agent Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fake-LLM real `AgentLoop` dry-run evaluator for memory eval cases, producing quantitative integration metrics without touching the user's real workspace or calling external services.

**Architecture:** Add a focused `memory2.eval_agent_dry_run` harness that wires real `AgentLoop`, `SessionManager`, `ToolRegistry`, `EventBus`, and `DefaultMemoryRetrievalPipeline` around controlled fake provider and memory engine objects. Add a CLI that loads existing `EvalCase` fixtures, runs them in a temporary workspace, and writes JSON/Markdown reports under `my_md/memory_optimization/eval_reports/`. Keep this phase separate from Phase6b-3 real LLM answer evaluation.

**Tech Stack:** Python dataclasses, asyncio, existing `AgentLoop`, existing `SessionManager`, existing `EvalCase` loader, pytest, JSON/Markdown reports.

## Global Constraints

- Phase6b-2 must not start `main.py`, IPC, Telegram, QQ, Dashboard, or any long-running server.
- Phase6b-2 must not call real LLM, embedding APIs, external network, or paid services.
- Phase6b-2 must not write the user's real `workspace/memory/memory2.db`, `workspace/sessions.db`, or `workspace/observe/observe.db`.
- All runtime writes must go under a caller-provided temporary workspace or pytest `tmp_path`.
- Reports must not include raw query text, raw memory summaries, assembled prompts, full session messages, or LLM response text.
- Reports may include ids, categories, session keys, channel/chat ids, counts, booleans, trace/event names, and failure reasons.
- Failure reasons must be fixed diagnostic strings or sanitized count/scope messages. Do not include raw exception messages in reports.
- Do not add dependencies.
- Do not stage or commit `uv.lock`.
- Preserve Phase6a and Phase6b-1 behavior and tests.

---

## File Structure

- Create: `memory2/eval_agent_dry_run.py`
  - AgentLoop dry-run harness, fake provider, controlled memory engine, report writers.
- Create: `scripts/run_memory_agent_dry_run_eval.py`
  - CLI for fixture-based dry-run reports.
- Create: `tests/test_memory_eval_agent_dry_run.py`
  - Harness, privacy, event, and report tests.
- Create: `tests/test_memory_agent_dry_run_cli.py`
  - CLI success and empty-case behavior tests.
- Modify: `my_md/memory_optimization/README.md`
  - Record Phase6b-2 result.
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
  - Add Agent dry-run metrics and boundaries.
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - Mark Phase6b-2 implemented after verification.

---

### Task 1: Agent Dry-Run Harness

**Files:**
- Create: `memory2/eval_agent_dry_run.py`
- Create: `tests/test_memory_eval_agent_dry_run.py`

**Interfaces:**
- Consumes:
  - `memory2.eval_cases.EvalCase`
  - `agent.looping.core.AgentLoop`
  - `session.manager.SessionManager`
- Produces:
  - `AgentDryRunCaseResult`
  - `AgentDryRunReport`
  - `run_agent_dry_run_case(case: EvalCase, workspace: Path) -> AgentDryRunCaseResult`
  - `run_agent_dry_run_cases(cases: Sequence[EvalCase], workspace: Path) -> AgentDryRunReport`
  - `write_agent_dry_run_json(report: AgentDryRunReport, path: Path) -> None`
  - `write_agent_dry_run_markdown(report: AgentDryRunReport, path: Path) -> None`

- [ ] **Step 1: Write failing harness tests**

Create `tests/test_memory_eval_agent_dry_run.py` with these tests:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory2.eval_agent_dry_run import (
    run_agent_dry_run_case,
    run_agent_dry_run_cases,
    write_agent_dry_run_json,
    write_agent_dry_run_markdown,
)
from memory2.eval_cases import load_eval_case


FIXTURE_ROOT = Path("tests/fixtures/memory_eval_cases")


@pytest.mark.asyncio
async def test_agent_dry_run_processes_case_through_real_agent_loop(tmp_path: Path) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")

    result = await run_agent_dry_run_case(case, tmp_path / "workspace")

    assert result.passed is True
    assert result.case_id == "preference_recall"
    assert result.session_key == "cli:local"
    assert result.reply_length > 0
    assert result.retrieval_request_count == 1
    assert result.fake_llm_call_count == 1
    assert result.turn_committed_count == 1
    assert result.session_message_count >= 2
    assert result.retrieval_query_matched is True
    assert result.retrieval_history_seen is True
    assert result.failures == ()
    assert (tmp_path / "workspace" / "sessions.db").exists()


@pytest.mark.asyncio
async def test_agent_dry_run_report_aggregates_counts(tmp_path: Path) -> None:
    cases = [
        load_eval_case(FIXTURE_ROOT / "preference_recall.json"),
        load_eval_case(FIXTURE_ROOT / "cross_scope_isolation.json"),
    ]

    report = await run_agent_dry_run_cases(cases, tmp_path / "workspace")

    assert report.passed is True
    assert report.metrics["phase6b_level"] == "agent_dry_run"
    assert report.metrics["agent_loop_enabled"] is True
    assert report.metrics["fake_llm_enabled"] is True
    assert report.metrics["llm_calls_enabled"] is False
    assert report.metrics["embedding_calls_enabled"] is False
    assert report.metrics["answer_quality_available"] is False
    assert report.metrics["raw_query_included"] is False
    assert report.metrics["raw_memory_summary_included"] is False
    assert report.metrics["prompt_included"] is False
    assert report.metrics["session_text_included"] is False
    assert report.metrics["case_count"] == 2
    assert report.metrics["passed_case_count"] == 2
    assert report.metrics["failed_case_count"] == 0
    assert report.metrics["retrieval_request_count"] == 2
    assert len(report.case_records) == 2


@pytest.mark.asyncio
async def test_agent_dry_run_report_does_not_include_raw_memory_text(tmp_path: Path) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    report = await run_agent_dry_run_cases([case], tmp_path / "workspace")
    json_path = tmp_path / "agent_dry_run.json"
    md_path = tmp_path / "agent_dry_run.md"

    write_agent_dry_run_json(report, json_path)
    write_agent_dry_run_markdown(report, md_path)

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    assert "用户偏好中文回答" not in json_text
    assert "用户偏好中文回答" not in md_text
    assert "你应该用什么语言回答我" not in json_text
    assert "你应该用什么语言回答我" not in md_text
    assert "dry-run response" not in json_text
    assert "dry-run response" not in md_text
    payload = json.loads(json_text)
    assert payload["case_records"][0]["case_id"] == "preference_recall"
    assert "query" not in payload["case_records"][0]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_eval_agent_dry_run.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'memory2.eval_agent_dry_run'`.

- [ ] **Step 3: Implement harness dataclasses and fake services**

Create `memory2/eval_agent_dry_run.py` with:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock

from agent.looping.core import AgentLoop
from agent.looping.ports import AgentLoopConfig, AgentLoopDeps, LLMConfig, MemoryServices
from agent.provider import LLMResponse
from agent.tools.registry import ToolRegistry
from bus.event_bus import EventBus
from bus.events_lifecycle import TurnCommitted
from core.memory.engine import (
    ExplicitRetrievalRequest,
    ExplicitRetrievalResult,
    ForgetRequest,
    ForgetResult,
    InterestRetrievalRequest,
    InterestRetrievalResult,
    MemoryEngineRetrieveRequest,
    MemoryEngineRetrieveResult,
    MemoryHit,
    MemoryIngestRequest,
    MemoryIngestResult,
    RememberRequest,
    RememberResult,
)
from memory2.eval_cases import EvalCase
from session.manager import SessionManager


@dataclass(frozen=True)
class AgentDryRunCaseResult:
    case_id: str
    category: str
    session_key: str
    channel: str
    chat_id: str
    passed: bool
    reply_length: int
    retrieval_request_count: int
    fake_llm_call_count: int
    turn_committed_count: int
    session_message_count: int
    retrieval_query_matched: bool
    retrieval_history_seen: bool
    failures: tuple[str, ...]


@dataclass(frozen=True)
class AgentDryRunReport:
    cases: tuple[AgentDryRunCaseResult, ...]
    metrics: dict[str, object]
    case_records: tuple[dict[str, object], ...]
    failure_records: tuple[dict[str, object], ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)
```

Add `ScriptedDryRunProvider`:

```python
class ScriptedDryRunProvider:
    def __init__(self, content: str = "dry-run response") -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        return LLMResponse(content=self.content, tool_calls=[])
```

Add `CaseMemoryEngine`:

```python
class CaseMemoryEngine:
    def __init__(self, case: EvalCase) -> None:
        self.case = case
        self.retrieve_requests: list[MemoryEngineRetrieveRequest] = []

    async def retrieve(self, request: MemoryEngineRetrieveRequest) -> MemoryEngineRetrieveResult:
        self.retrieve_requests.append(request)
        ids = [str(item_id) for item_id in _expectations(self.case).get("should_recall_ids", [])]
        hits = [
            MemoryHit(
                id=item_id,
                summary="",
                content="",
                score=1.0,
                source_ref="",
                engine_kind="agent_dry_run",
                injected=True,
            )
            for item_id in ids
        ]
        block = "\n".join(f"- memory_id={item_id}" for item_id in ids)
        return MemoryEngineRetrieveResult(text_block=block, hits=hits, raw={"ids": ids})

    async def retrieve_explicit(self, request: ExplicitRetrievalRequest) -> ExplicitRetrievalResult:
        return ExplicitRetrievalResult()

    async def retrieve_interest_block(self, request: InterestRetrievalRequest) -> InterestRetrievalResult:
        return InterestRetrievalResult()

    async def remember(self, request: RememberRequest) -> RememberResult:
        return RememberResult(item_id="dry-run-memory", actual_type=request.memory_type)

    async def forget(self, request: ForgetRequest) -> ForgetResult:
        return ForgetResult(missing_ids=list(request.ids))

    async def ingest(self, request: MemoryIngestRequest) -> MemoryIngestResult:
        return MemoryIngestResult(accepted=True)

    async def refresh_recent_turns(self, request: object) -> None:
        return None

    async def consolidate(self, request: object) -> object:
        return None

    def read_self(self) -> str:
        return ""

    def read_recent_context(self) -> str:
        return ""

    def get_memory_context(self) -> str:
        return ""

    def has_long_term_memory(self) -> bool:
        return False
```

- [ ] **Step 4: Implement run functions and writers**

Add helpers:

```python
async def run_agent_dry_run_case(case: EvalCase, workspace: Path) -> AgentDryRunCaseResult:
    workspace.mkdir(parents=True, exist_ok=True)
    provider = ScriptedDryRunProvider()
    memory = CaseMemoryEngine(case)
    event_bus = EventBus()
    turn_events: list[TurnCommitted] = []
    event_bus.on(TurnCommitted, lambda event: turn_events.append(event))
    session_manager = SessionManager(workspace)
    tools = ToolRegistry()
    loop = AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=provider,  # type: ignore[arg-type]
            light_provider=provider,  # type: ignore[arg-type]
            tools=tools,
            session_manager=session_manager,
            workspace=workspace,
            event_bus=event_bus,
            memory_services=MemoryServices(engine=memory),  # type: ignore[arg-type]
        ),
        AgentLoopConfig(llm=LLMConfig(max_iterations=2)),
    )
    scope = _scope(case)
    query = _query(case)
    reply = ""
    failures: list[str] = []
    try:
        reply = await loop.process_direct(
            query,
            session_key=scope["session_key"],
            channel=scope["channel"],
            chat_id=scope["chat_id"],
            skip_post_memory=True,
        )
        await event_bus.drain()
    finally:
        await event_bus.aclose()
    if not reply:
        failures.append("empty reply")
    if len(memory.retrieve_requests) != 1:
        failures.append(f"expected 1 retrieval request, got {len(memory.retrieve_requests)}")
    if not provider.calls:
        failures.append("fake llm was not called")
    if not turn_events:
        failures.append("TurnCommitted was not observed")
    if memory.retrieve_requests:
        req = memory.retrieve_requests[0]
        if req.scope.session_key != scope["session_key"]:
            failures.append("retrieval session_key mismatch")
        if req.scope.channel != scope["channel"]:
            failures.append("retrieval channel mismatch")
        if req.scope.chat_id != scope["chat_id"]:
            failures.append("retrieval chat_id mismatch")
        if req.query != query:
            failures.append("retrieval query mismatch")
        history = req.context.get("history", [])
        if not isinstance(history, list):
            failures.append("retrieval history missing")
    session = session_manager.get_or_create(scope["session_key"])
    return AgentDryRunCaseResult(
        case_id=case.id,
        category=case.category,
        session_key=scope["session_key"],
        channel=scope["channel"],
        chat_id=scope["chat_id"],
        passed=not failures,
        reply_length=len(reply),
        retrieval_request_count=len(memory.retrieve_requests),
        fake_llm_call_count=len(provider.calls),
        turn_committed_count=len(turn_events),
        session_message_count=len(session.messages),
        retrieval_query_matched=(
            bool(memory.retrieve_requests) and memory.retrieve_requests[0].query == query
        ),
        retrieval_history_seen=(
            bool(memory.retrieve_requests)
            and isinstance(memory.retrieve_requests[0].context.get("history", []), list)
        ),
        failures=tuple(failures),
    )
```

Implement aggregate and writers:

```python
async def run_agent_dry_run_cases(cases: Sequence[EvalCase], workspace: Path) -> AgentDryRunReport:
    results = []
    for index, case in enumerate(cases):
        result = await run_agent_dry_run_case(case, workspace / f"case-{index:03d}-{case.id}")
        results.append(result)
    return _build_report(tuple(results))


def write_agent_dry_run_json(report: AgentDryRunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_agent_dry_run_markdown(report: AgentDryRunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Memory Agent Dry-Run Evaluation Report",
        "",
        "本报告使用真实 AgentLoop 和 fake LLM，不调用真实 LLM，不代表最终回答质量。",
        "报告默认不包含真实 query、memory summary、prompt 或 session 原文。",
        "",
        "## Summary",
        "",
    ]
    for key in sorted(report.metrics):
        lines.append(f"- `{key}`: `{report.metrics[key]}`")
    lines.extend(["", "## Case Records", ""])
    for record in report.case_records:
        lines.append(f"- `{record['case_id']}`: `{json.dumps(record, ensure_ascii=False, sort_keys=True)}`")
    lines.extend(["", "## Failure Records", ""])
    for record in report.failure_records:
        lines.append(f"- `{json.dumps(record, ensure_ascii=False, sort_keys=True)}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
```

Use private helpers `_scope()`, `_query()`, `_expectations()`, `_build_report()`, `_case_record()`, `_failure_records()`, and `_report_to_dict()` with only id/count fields. `_build_report()` must set `raw_query_included`, `raw_memory_summary_included`, `prompt_included`, and `session_text_included` to `False`. `AgentDryRunReport.passed` should require all cases to pass, while CLI exit code should use `passed_case_count > 0`.

- [ ] **Step 5: Run harness tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_eval_agent_dry_run.py -q
```

Expected: `3 passed`.

---

### Task 2: Agent Dry-Run CLI

**Files:**
- Create: `scripts/run_memory_agent_dry_run_eval.py`
- Create: `tests/test_memory_agent_dry_run_cli.py`

**Interfaces:**
- Consumes:
  - `memory2.eval_cases.load_eval_cases`
  - `memory2.eval_agent_dry_run.run_agent_dry_run_cases`
- Produces:
  - `memory_agent_dry_run_eval.json`
  - `memory_agent_dry_run_eval.md`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_memory_agent_dry_run_cli.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_memory_agent_dry_run_cli_writes_reports(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_agent_dry_run_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--limit",
            "2",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_agent_dry_run_eval.json" in completed.stdout
    payload = json.loads((out_dir / "memory_agent_dry_run_eval.json").read_text())
    assert payload["metrics"]["phase6b_level"] == "agent_dry_run"
    assert payload["metrics"]["case_count"] == 2
    assert payload["metrics"]["passed_case_count"] == 2
    assert (out_dir / "memory_agent_dry_run_eval.md").exists()


def test_memory_agent_dry_run_cli_returns_one_for_empty_cases(tmp_path: Path) -> None:
    case_root = tmp_path / "empty_cases"
    case_root.mkdir()
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_agent_dry_run_eval.py",
            "--case-root",
            str(case_root),
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    payload = json.loads((out_dir / "memory_agent_dry_run_eval.json").read_text())
    assert payload["metrics"]["case_count"] == 0
    assert (out_dir / "memory_agent_dry_run_eval.md").exists()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_agent_dry_run_cli.py -q
```

Expected: fail because CLI does not exist.

- [ ] **Step 3: Implement CLI**

Create `scripts/run_memory_agent_dry_run_eval.py`:

```python
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_agent_dry_run import (
    run_agent_dry_run_cases,
    write_agent_dry_run_json,
    write_agent_dry_run_markdown,
)
from memory2.eval_cases import load_eval_cases


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", default="tests/fixtures/memory_eval_cases")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = load_eval_cases(Path(args.case_root))
    if args.limit > 0:
        cases = cases[: args.limit]
    report = await run_agent_dry_run_cases(cases, Path(args.workspace))

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_agent_dry_run_eval.json"
    md_path = out_dir / "memory_agent_dry_run_eval.md"
    write_agent_dry_run_json(report, json_path)
    write_agent_dry_run_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0 if int(report.metrics["passed_case_count"]) > 0 else 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_agent_dry_run_cli.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run CLI locally**

Run:

```bash
.venv/bin/python scripts/run_memory_agent_dry_run_eval.py \
  --case-root tests/fixtures/memory_eval_cases \
  --workspace .tmp/memory_agent_dry_run \
  --out-dir my_md/memory_optimization/eval_reports \
  --limit 9
```

Expected:

- exit code `0`
- writes `memory_agent_dry_run_eval.json`
- writes `memory_agent_dry_run_eval.md`

---

### Task 3: Documentation and Verification

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`

**Interfaces:**
- Consumes:
  - Task 1 report fields
  - Task 2 local CLI output
- Produces:
  - Updated memory optimization docs

- [ ] **Step 1: Update docs**

Add Phase6b-2 notes:

```text
Phase 6b-2 已完成第一版：真实 AgentLoop dry-run。

本阶段使用真实 AgentLoop、SessionManager、DefaultMemoryRetrievalPipeline、EventBus 和 TurnCommitted 事件，但 LLM 是 fake provider，memory engine 是受控测试 engine。它能证明 eval case 可以穿过真实 turn pipeline，并输出 agent dry-run 集成指标。

它仍然不调用真实 LLM、embedding、网络或外部服务，不代表最终回答质量。
```

Record metrics:

```text
agent_loop_enabled
fake_llm_enabled
llm_calls_enabled
embedding_calls_enabled
answer_quality_available
case_count
passed_case_count
failed_case_count
agent_turn_count
turn_committed_count
retrieval_request_count
fake_llm_call_count
session_message_count
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_eval_cases.py \
  tests/test_memory_eval_runner.py \
  tests/test_memory_eval_real_samples.py \
  tests/test_memory_eval_real_candidates.py \
  tests/test_memory_eval_real_report.py \
  tests/test_memory_real_sample_eval_cli.py \
  tests/test_memory_eval_agent_dry_run.py \
  tests/test_memory_agent_dry_run_cli.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 3: Run compile and diff checks**

Run:

```bash
.venv/bin/python -m compileall memory2 tests scripts -q
git diff --check
```

Expected: both commands exit `0`.

- [ ] **Step 4: Commit**

Stage Phase6b-2 files only. Do not stage `uv.lock`.

```bash
git add \
  memory2/eval_agent_dry_run.py \
  scripts/run_memory_agent_dry_run_eval.py \
  tests/test_memory_eval_agent_dry_run.py \
  tests/test_memory_agent_dry_run_cli.py \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/memory_agent_dry_run_eval.json \
  my_md/memory_optimization/eval_reports/memory_agent_dry_run_eval.md \
  docs/superpowers/specs/2026-07-17-memory-phase6b2-agent-dry-run-design.md \
  docs/superpowers/plans/2026-07-17-memory-phase6b2-agent-dry-run.md
git commit -m "feat: add memory agent dry-run evaluation"
```

Expected: commit succeeds and `git status --short` only shows pre-existing `uv.lock`, unless new user changes appear.

---

## Self-Review

- Spec coverage: the plan covers fake-LLM AgentLoop dry-run, temporary workspace isolation, report output, CLI, docs, and verification.
- Placeholder scan: no `TBD`, `TODO`, or unspecified test commands remain.
- Type consistency: task interfaces consistently use `EvalCase`, `AgentDryRunCaseResult`, `AgentDryRunReport`, and explicit writer names.
- Scope check: real LLM metrics, answer quality, source support, Dashboard, and active gates are explicitly out of scope.
