# Turn Trace Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a current-session structured trace query path so the agent can answer "which tools did you use?" from observe/session facts instead of natural-language inference.

**Architecture:** Keep source-of-truth logic in a core read-only service under `agent/tracing/`. Expose it through a deferred read-only tool `inspect_turn_trace`, and let `ToolAccessGateway` make that tool visible only for session/meta/tool-history turns. Do not make the tool always-on, do not write it to LRU through intent preload, and do not change `AgentLoop`.

**Tech Stack:** Python dataclasses, sqlite3, existing `Tool` / `ToolRegistry`, existing `ToolAccessGateway`, pytest, existing observe/session SQLite schemas.

## Global Constraints

- Core query logic must live outside plugin code so CLI, dashboard, tests, and tools can share the same source of truth.
- The first implementation is current-session only; cross-session trace queries are out of scope.
- `inspect_turn_trace` must be read-only and must not mutate observe/session/ToolDiscoveryState/LRU.
- `inspect_turn_trace` must not be always-on; expose it only through current-turn `ToolAccessPlan.visible_add`.
- `inspect_turn_trace` must be excluded from ToolDiscoveryState LRU even when it appears in `tools_used`.
- `inspect_turn_trace` must not expose `session_key` in its public JSON schema and must not trust model-supplied session identifiers.
- Protected tool context keys must override model arguments for `inspect_turn_trace`'s current-session binding.
- Session/meta questions must continue to suppress stale Document RAG LRU tools.
- Tool-history/session-meta intent must win over document intent for mixed prompts such as "刚才项目文档那个问题用了哪些工具？".
- `react_boundary_batch_skip` and other skipped calls must be distinguishable from real executed tools.
- Observe slim records must preserve enough structured fields to distinguish skipped/blocked calls from real executions without parsing truncated result text.
- If selector resolution is ambiguous, return candidates instead of guessing.
- `nth_user_question_in_window` means the Nth completed user turn in chronological order within the recent completed-turn window, not the all-time Nth turn in the session.
- For ordinal language such as "第二个问题" without a clear recent-window context, the tool should return candidates or the model should ask for clarification instead of guessing.

---

## File Map

- Create: `agent/tracing/turn_trace_query.py`
  - Core dataclasses and `TurnTraceQueryService`.
  - Reads `observe.db` turns and parses `tool_chain_json` / `tool_calls`.
  - Resolves current-session turn selectors.
- Create: `agent/tools/turn_trace.py`
  - `InspectTurnTraceTool`, a thin adapter around `TurnTraceQueryService`.
- Modify: `bootstrap/tools.py`
  - Construct `TurnTraceQueryService(workspace / "observe" / "observe.db")`.
  - Register `InspectTurnTraceTool` with `always_on=False`.
- Modify: `agent/lifecycle/phases/before_reasoning.py`
  - Include protected `_session_key` in `ToolRegistry.set_context(...)` so trace tools bind to current session.
- Modify: `agent/looping/handlers.py`
  - Include protected current-session context in direct `tools.set_context(...)` path if present.
- Modify: `agent/tools/registry.py`
  - Preserve protected context keys after model arguments are merged.
- Modify: `agent/core/runtime_support.py`
  - Exclude `inspect_turn_trace` from ToolDiscoveryState LRU updates.
- Modify: `plugins/observe/plugin.py`
  - Preserve `status`, `boundary_reason`, `boundary_action`, and structured `error_code` in slim tool traces.
- Modify: `agent/policies/tool_access.py`
  - Add `TRACE_TOOL_NAMES = frozenset({"inspect_turn_trace"})`.
  - Extend `SessionMetaAccessPolicy` to add `inspect_turn_trace` for tool-history/session-meta turns.
- Test: `tests/test_observe_writer.py`
  - Regression for slim trace preserving skipped/blocked metadata.
- Test: `tests/test_turn_trace_query.py`
  - Unit tests for selector resolution and tool-chain normalization.
- Test: `tests/test_turn_trace_tool.py`
  - Tool adapter tests for default current-session lookup and JSON output.
- Test: `tests/test_tool_access_gateway.py`
  - Gateway exposes trace tool for session/meta questions and still suppresses Document RAG LRU.
- Test: `tests/test_tool_access_gateway_reasoner.py`
  - Reasoner-visible schema includes `inspect_turn_trace` only for tool-history turns.

---

### Task 1: Core Turn Trace Query Service

**Files:**
- Create: `agent/tracing/turn_trace_query.py`
- Test: `tests/test_turn_trace_query.py`

**Interfaces:**
- Produces:
  - `TurnToolCall(name: str, status: str, real_executed: bool, skipped: bool, error_code: str, iteration: int)`
  - `TurnTrace(id: int, ts: str, session_key: str, user_msg: str, llm_output: str, error: str, react_iteration_count: int | None, tools: tuple[TurnToolCall, ...])`
  - `TurnTraceQueryService(observe_db_path: Path)`
  - `TurnTraceQueryService.get_recent_turns(session_key: str, limit: int = 10) -> list[TurnTraceSummary]`
  - `TurnTraceQueryService.get_turn(session_key: str, turn_id: int) -> TurnTraceQueryResult`
  - `TurnTraceQueryService.resolve(session_key: str, selector: str, n: int | None = None, turn_id: int | None = None, query: str | None = None) -> TurnTraceQueryResult`
  - Supported selectors: `previous_completed`, `recent_nth_completed`, `nth_user_question_in_window`, `turn_id`, `query`.
  - `nth_user_question_in_window` uses the recent completed-turn window in chronological order and is valid only when the user is referring to the current short run of recent questions.
- Consumes:
  - SQLite `observe.turns` table.
  - JSON fields `tool_chain_json` and `tool_calls`.

- [ ] **Step 1: Write failing tests for recent turns and exact turn lookup**

Create `tests/test_turn_trace_query.py` with helper DB setup and these tests:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agent.tracing.turn_trace_query import TurnTraceQueryService
from plugins.observe.db import open_db


def _make_observe_db(path: Path) -> None:
    conn = open_db(path)
    conn.close()


def _insert_turn(
    path: Path,
    *,
    session_key: str,
    user_msg: str,
    tool_chain: list[dict],
    tool_calls: list[dict] | None = None,
    react_iteration_count: int = 1,
) -> int:
    conn = sqlite3.connect(path)
    cur = conn.execute(
        """
        INSERT INTO turns (
            ts, source, session_key, user_msg, llm_output,
            tool_calls, tool_chain_json, react_iteration_count, error
        )
        VALUES (?, 'agent', ?, ?, 'ok', ?, ?, ?, NULL)
        """,
        (
            "2026-07-13T11:11:03+00:00",
            session_key,
            user_msg,
            json.dumps(tool_calls or [], ensure_ascii=False),
            json.dumps(tool_chain, ensure_ascii=False),
            react_iteration_count,
        ),
    )
    conn.commit()
    turn_id = int(cur.lastrowid)
    conn.close()
    return turn_id


def test_get_turn_returns_real_tool_summary(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    turn_id = _insert_turn(
        db,
        session_key="cli:s1",
        user_msg="根据项目文档和源码回答",
        tool_chain=[
            {"text": "", "calls": [{"name": "read_file", "status": "success", "result": "a"}]},
            {"text": "", "calls": [{"name": "read_file", "status": "success", "result": "b"}]},
            {"text": "", "calls": [{"name": "read_file", "status": "success", "result": "c"}]},
        ],
        react_iteration_count=4,
    )

    result = TurnTraceQueryService(db).get_turn("cli:s1", turn_id)

    assert result.ok is True
    assert result.turn is not None
    assert result.turn.id == turn_id
    assert result.turn.real_tool_counts == {"read_file": 3}
    assert [tool.name for tool in result.turn.tools] == ["read_file", "read_file", "read_file"]
    assert all(tool.real_executed for tool in result.turn.tools)


def test_get_turn_is_current_session_only(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    turn_id = _insert_turn(
        db,
        session_key="cli:other",
        user_msg="private",
        tool_chain=[],
    )

    result = TurnTraceQueryService(db).get_turn("cli:current", turn_id)

    assert result.ok is False
    assert result.error_code == "turn_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_query.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.tracing'`.

- [ ] **Step 3: Implement dataclasses and exact turn lookup**

Create `agent/tracing/turn_trace_query.py`:

```python
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_SKIPPED_STATUSES = frozenset({
    "batch_skipped_by_react_boundary",
    "tool_boundary_soft_stop",
    "blocked_by_tool_access_gateway",
    "blocked_by_tool_boundary",
    "soft_stopped_by_tool_boundary",
})

_SKIPPED_BOUNDARY_REASONS = frozenset({
    "tool_blocked_by_doc_rag_policy",
    "document_rag_batch_evidence_complete",
})


@dataclass(frozen=True)
class TurnToolCall:
    name: str
    status: str = "success"
    real_executed: bool = True
    skipped: bool = False
    error_code: str = ""
    iteration: int = 0


@dataclass(frozen=True)
class TurnTrace:
    id: int
    ts: str
    session_key: str
    user_msg: str
    llm_output: str
    error: str
    react_iteration_count: int | None
    tools: tuple[TurnToolCall, ...] = ()

    @property
    def real_tool_counts(self) -> dict[str, int]:
        return dict(Counter(tool.name for tool in self.tools if tool.real_executed))

    @property
    def skipped_tool_counts(self) -> dict[str, int]:
        return dict(Counter(tool.name for tool in self.tools if tool.skipped))


@dataclass(frozen=True)
class TurnTraceSummary:
    id: int
    ts: str
    user_msg: str
    real_tool_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TurnTraceQueryResult:
    ok: bool
    source: str = "observe.turns.tool_chain_json"
    turn: TurnTrace | None = None
    candidates: tuple[TurnTraceSummary, ...] = ()
    error_code: str = ""
    message: str = ""


class TurnTraceQueryService:
    def __init__(self, observe_db_path: Path) -> None:
        self._observe_db_path = observe_db_path

    def get_turn(self, session_key: str, turn_id: int) -> TurnTraceQueryResult:
        row = self._fetch_one(
            """
            SELECT id, ts, session_key, user_msg, llm_output, error,
                   react_iteration_count, tool_chain_json, tool_calls
            FROM turns
            WHERE session_key = ? AND id = ?
            """,
            (session_key, int(turn_id)),
        )
        if row is None:
            return TurnTraceQueryResult(
                ok=False,
                error_code="turn_not_found",
                message="No turn exists for this session and turn_id.",
            )
        return TurnTraceQueryResult(ok=True, turn=self._row_to_trace(row))

    def get_recent_turns(self, session_key: str, limit: int = 10) -> list[TurnTraceSummary]:
        rows = self._fetch_all(
            """
            SELECT id, ts, session_key, user_msg, llm_output, error,
                   react_iteration_count, tool_chain_json, tool_calls
            FROM turns
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_key, max(1, min(int(limit), 20))),
        )
        traces = [self._row_to_trace(row) for row in rows]
        return [
            TurnTraceSummary(
                id=trace.id,
                ts=trace.ts,
                user_msg=trace.user_msg,
                real_tool_counts=trace.real_tool_counts,
            )
            for trace in traces
        ]

    def resolve(
        self,
        session_key: str,
        selector: str,
        n: int | None = None,
        turn_id: int | None = None,
        query: str | None = None,
    ) -> TurnTraceQueryResult:
        if selector == "turn_id":
            if turn_id is None:
                return TurnTraceQueryResult(
                    ok=False,
                    error_code="missing_turn_id",
                    message="selector='turn_id' requires turn_id.",
                )
            return self.get_turn(session_key, turn_id)

        if selector in {"previous_completed", "last_user_question"}:
            return self._resolve_recent_nth(session_key, 1)

        if selector == "recent_nth_completed":
            return self._resolve_recent_nth(session_key, n or 1)

        if selector == "nth_user_question_in_window":
            return self._resolve_nth_user_question_in_window(session_key, n or 1)

        if selector == "query":
            return self._resolve_query(session_key, query or "")

        return TurnTraceQueryResult(
            ok=False,
            error_code="unsupported_selector",
            message=f"Unsupported selector: {selector}",
        )

    def _resolve_recent_nth(self, session_key: str, n: int) -> TurnTraceQueryResult:
        rows = self._fetch_all(
            """
            SELECT id, ts, session_key, user_msg, llm_output, error,
                   react_iteration_count, tool_chain_json, tool_calls
            FROM turns
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_key, max(1, int(n))),
        )
        if len(rows) < max(1, int(n)):
            return TurnTraceQueryResult(
                ok=False,
                error_code="turn_not_found",
                candidates=tuple(self.get_recent_turns(session_key, 5)),
                message="Not enough recent turns exist in this session.",
            )
        return TurnTraceQueryResult(ok=True, turn=self._row_to_trace(rows[max(1, int(n)) - 1]))

    def _resolve_query(self, session_key: str, query: str) -> TurnTraceQueryResult:
        term = query.strip().lower()
        if not term:
            return TurnTraceQueryResult(
                ok=False,
                error_code="missing_query",
                candidates=tuple(self.get_recent_turns(session_key, 5)),
                message="selector='query' requires a non-empty query.",
            )
        rows = self._fetch_all(
            """
            SELECT id, ts, session_key, user_msg, llm_output, error,
                   react_iteration_count, tool_chain_json, tool_calls
            FROM turns
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (session_key,),
        )
        matches = [self._row_to_trace(row) for row in rows if term in str(row["user_msg"] or "").lower()]
        if len(matches) == 1:
            return TurnTraceQueryResult(ok=True, turn=matches[0])
        return TurnTraceQueryResult(
            ok=False,
            error_code="ambiguous_selector" if matches else "turn_not_found",
            candidates=tuple(
                TurnTraceSummary(
                    id=trace.id,
                    ts=trace.ts,
                    user_msg=trace.user_msg,
                    real_tool_counts=trace.real_tool_counts,
                )
                for trace in (matches or [self._row_to_trace(row) for row in rows[:5]])
            ),
            message="Selector did not identify exactly one turn.",
        )

    def _resolve_nth_user_question_in_window(self, session_key: str, n: int) -> TurnTraceQueryResult:
        rows = list(reversed(self._fetch_all(
            """
            SELECT id, ts, session_key, user_msg, llm_output, error,
                   react_iteration_count, tool_chain_json, tool_calls
            FROM turns
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (session_key,),
        )))
        if len(rows) < max(1, int(n)):
            return TurnTraceQueryResult(
                ok=False,
                error_code="ambiguous_selector",
                candidates=tuple(self.get_recent_turns(session_key, 5)),
                message="The requested ordinal question is ambiguous or outside the recent window.",
            )
        return TurnTraceQueryResult(ok=True, turn=self._row_to_trace(rows[max(1, int(n)) - 1]))

    def _row_to_trace(self, row: sqlite3.Row) -> TurnTrace:
        tools = _parse_tool_chain(row["tool_chain_json"], row["tool_calls"])
        return TurnTrace(
            id=int(row["id"]),
            ts=str(row["ts"] or ""),
            session_key=str(row["session_key"] or ""),
            user_msg=str(row["user_msg"] or ""),
            llm_output=str(row["llm_output"] or ""),
            error=str(row["error"] or ""),
            react_iteration_count=(
                int(row["react_iteration_count"])
                if row["react_iteration_count"] is not None
                else None
            ),
            tools=tuple(tools),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._observe_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_one(self, sql: str, params: tuple[object, ...]) -> sqlite3.Row | None:
        if not self._observe_db_path.exists():
            return None
        with self._connect() as conn:
            return conn.execute(sql, params).fetchone()

    def _fetch_all(self, sql: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
        if not self._observe_db_path.exists():
            return []
        with self._connect() as conn:
            return list(conn.execute(sql, params).fetchall())


def _parse_tool_chain(tool_chain_json: str | None, tool_calls_json: str | None) -> list[TurnToolCall]:
    groups = _loads_json_list(tool_chain_json)
    calls: list[TurnToolCall] = []
    for iteration, group in enumerate(groups):
        raw_calls = group.get("calls") if isinstance(group, dict) else None
        if not isinstance(raw_calls, list):
            continue
        for raw in raw_calls:
            if not isinstance(raw, dict):
                continue
            calls.append(_to_tool_call(raw, iteration))
    if calls:
        return calls
    return [_to_tool_call(raw, 0) for raw in _loads_json_list(tool_calls_json) if isinstance(raw, dict)]


def _to_tool_call(raw: dict[str, Any], iteration: int) -> TurnToolCall:
    name = str(raw.get("name") or raw.get("tool") or "")
    status = str(raw.get("status") or "")
    result_text = str(raw.get("result") or "")
    error_code = str(raw.get("error_code") or "") or _extract_error_code(result_text)
    boundary_reason = str(raw.get("boundary_reason") or "")
    skipped = (
        status in _SKIPPED_STATUSES
        or boundary_reason in _SKIPPED_BOUNDARY_REASONS
        or error_code in {
            "react_boundary_batch_skip",
            "tool_boundary_soft_stop",
            "blocked_by_tool_access_gateway",
            "tool_blocked_by_doc_rag_policy",
        }
    )
    return TurnToolCall(
        name=name,
        status=status or ("skipped" if skipped else "success"),
        real_executed=bool(name) and not skipped,
        skipped=skipped,
        error_code=error_code,
        iteration=iteration,
    )


def _extract_error_code(result_text: str) -> str:
    try:
        payload = json.loads(result_text)
    except (TypeError, ValueError):
        return ""
    if isinstance(payload, dict):
        return str(payload.get("error_code") or "")
    return ""


def _loads_json_list(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []
```

- [ ] **Step 4: Run tests to verify exact lookup passes**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_query.py -q
```

Expected: PASS for the two tests.

- [ ] **Step 5: Add selector and skipped-call tests**

Append to `tests/test_turn_trace_query.py`:

```python
def test_recent_nth_completed_selector_uses_current_session_reverse_order(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    first = _insert_turn(db, session_key="cli:s1", user_msg="first", tool_chain=[])
    second = _insert_turn(db, session_key="cli:s1", user_msg="second", tool_chain=[])
    _insert_turn(db, session_key="cli:other", user_msg="other", tool_chain=[])

    result = TurnTraceQueryService(db).resolve("cli:s1", selector="recent_nth_completed", n=2)

    assert result.ok is True
    assert result.turn is not None
    assert result.turn.id == first
    assert result.turn.id != second


def test_nth_user_question_in_window_uses_chronological_recent_window(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    first = _insert_turn(db, session_key="cli:s1", user_msg="first", tool_chain=[])
    second = _insert_turn(db, session_key="cli:s1", user_msg="second", tool_chain=[])
    _insert_turn(db, session_key="cli:s1", user_msg="third", tool_chain=[])

    result = TurnTraceQueryService(db).resolve("cli:s1", selector="nth_user_question_in_window", n=2)

    assert result.ok is True
    assert result.turn is not None
    assert result.turn.id == second
    assert result.turn.id != first


def test_nth_user_question_in_window_returns_candidates_when_outside_recent_window(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    _insert_turn(db, session_key="cli:s1", user_msg="only one", tool_chain=[])

    result = TurnTraceQueryService(db).resolve("cli:s1", selector="nth_user_question_in_window", n=2)

    assert result.ok is False
    assert result.error_code == "ambiguous_selector"
    assert result.candidates


def test_batch_skipped_tool_is_not_real_executed(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    turn_id = _insert_turn(
        db,
        session_key="cli:s1",
        user_msg="doc evidence",
        tool_chain=[
            {
                "text": "",
                "calls": [
                    {"name": "search_docs", "status": "success", "result": "{}"},
                    {"name": "fetch_doc_chunk", "status": "success", "result": "{}"},
                    {
                        "name": "fetch_doc_chunk",
                        "status": "batch_skipped_by_react_boundary",
                        "result": '{"ok": false, "error_code": "react_boundary_batch_skip"}',
                    },
                ],
            }
        ],
    )

    result = TurnTraceQueryService(db).get_turn("cli:s1", turn_id)

    assert result.ok is True
    assert result.turn is not None
    assert result.turn.real_tool_counts == {"search_docs": 1, "fetch_doc_chunk": 1}
    assert result.turn.skipped_tool_counts == {"fetch_doc_chunk": 1}


def test_access_blocked_tool_is_not_real_executed_even_without_status(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    turn_id = _insert_turn(
        db,
        session_key="cli:s1",
        user_msg="doc question tried local file",
        tool_chain=[
            {
                "text": "",
                "calls": [
                    {
                        "name": "read_file",
                        "result": '{"ok": false, "error_code": "blocked_by_tool_access_gateway"}',
                    },
                ],
            }
        ],
    )

    result = TurnTraceQueryService(db).get_turn("cli:s1", turn_id)

    assert result.ok is True
    assert result.turn is not None
    assert result.turn.real_tool_counts == {}
    assert result.turn.skipped_tool_counts == {"read_file": 1}


def test_runtime_boundary_blocked_tool_is_not_real_executed(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    turn_id = _insert_turn(
        db,
        session_key="cli:s1",
        user_msg="doc question tried local file after gateway",
        tool_chain=[
            {
                "text": "",
                "calls": [
                    {
                        "name": "read_file",
                        "status": "blocked_by_tool_boundary",
                        "boundary_action": "block",
                        "boundary_reason": "tool_blocked_by_doc_rag_policy",
                        "result": (
                            '{"ok": false, '
                            '"error_code": "tool_blocked_by_doc_rag_policy"}'
                        ),
                    },
                ],
            }
        ],
    )

    result = TurnTraceQueryService(db).get_turn("cli:s1", turn_id)

    assert result.ok is True
    assert result.turn is not None
    assert result.turn.real_tool_counts == {}
    assert result.turn.skipped_tool_counts == {"read_file": 1}
    tool = result.turn.tools[0]
    assert tool.status == "blocked_by_tool_boundary"
    assert tool.error_code == "tool_blocked_by_doc_rag_policy"
```

- [ ] **Step 6: Run expanded tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_query.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add agent/tracing/turn_trace_query.py tests/test_turn_trace_query.py
git commit -m "feat: add structured turn trace query service"
```

---

### Task 2: Trace Fact Preservation and Non-LRU Contract

**Files:**
- Modify: `plugins/observe/plugin.py`
- Modify: `agent/core/runtime_support.py`
- Test: `tests/test_observe_writer.py`
- Test: `tests/test_turn_trace_query.py`

**Interfaces:**
- Consumes: existing `tool_chain` records from `DefaultReasoner`.
- Produces:
  - Slim observe calls preserve `status`, `boundary_reason`, `boundary_action`, and `error_code`.
  - `ToolDiscoveryState.update(...)` ignores `inspect_turn_trace`.

- [ ] **Step 1: Add observe slim metadata regression**

Add to `tests/test_observe_writer.py`:

```python
from plugins.observe.plugin import _slim_tool_chain, _slim_tool_calls


def test_observe_slim_trace_preserves_boundary_metadata() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "fetch_doc_chunk",
                    "arguments": {"chunk_id": "abc"},
                    "status": "batch_skipped_by_react_boundary",
                    "boundary_reason": "document_rag_batch_evidence_complete",
                    "boundary_action": "answer_from_existing_evidence",
                    "result": '{"ok": false, "error_code": "react_boundary_batch_skip"}',
                }
            ],
        }
    ]

    slim_chain = _slim_tool_chain(tool_chain)
    slim_calls = _slim_tool_calls(tool_chain)

    call = slim_chain[0]["calls"][0]
    flat_call = slim_calls[0]
    assert call["status"] == "batch_skipped_by_react_boundary"
    assert call["boundary_reason"] == "document_rag_batch_evidence_complete"
    assert call["boundary_action"] == "answer_from_existing_evidence"
    assert call["error_code"] == "react_boundary_batch_skip"
    assert flat_call["error_code"] == "react_boundary_batch_skip"
```

- [ ] **Step 2: Run observe metadata regression to verify it fails**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_observe_writer.py::test_observe_slim_trace_preserves_boundary_metadata -q
```

Expected: FAIL because slim trace does not preserve these fields yet.

- [ ] **Step 3: Preserve structured metadata in observe slim traces**

Modify `plugins/observe/plugin.py`:

```python
def _tool_error_code(call: dict[str, object]) -> str:
    direct = call.get("error_code")
    if isinstance(direct, str) and direct:
        return direct
    try:
        payload = json.loads(str(call.get("result", "") or ""))
    except (TypeError, ValueError):
        return ""
    if isinstance(payload, dict):
        value = payload.get("error_code")
        return value if isinstance(value, str) else ""
    return ""


def _slim_call(call: dict[str, object], *, args_limit: int, result_limit: int) -> dict[str, str]:
    out = {
        "name": str(call.get("name", "")),
        "args": str(call.get("arguments", ""))[:args_limit],
        "result": str(call.get("result", ""))[:result_limit],
    }
    for key in ("status", "boundary_reason", "boundary_action"):
        value = call.get(key)
        if isinstance(value, str) and value:
            out[key] = value
    error_code = _tool_error_code(call)
    if error_code:
        out["error_code"] = error_code
    return out
```

Then update `_slim_tool_calls(...)` and `_slim_tool_chain(...)` to call `_slim_call(...)` instead of constructing the dict inline.

- [ ] **Step 4: Add non-LRU regression**

Append to `tests/test_turn_trace_query.py`:

```python
from agent.core.runtime_support import ToolDiscoveryState


def test_inspect_turn_trace_is_not_added_to_lru() -> None:
    state = ToolDiscoveryState()

    state.update(
        "cli:s1",
        ["inspect_turn_trace", "read_file"],
        always_on=set(),
    )

    assert state.get_preloaded("cli:s1") == {"read_file"}
```

- [ ] **Step 5: Run non-LRU regression to verify it fails**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_query.py::test_inspect_turn_trace_is_not_added_to_lru -q
```

Expected: FAIL because `inspect_turn_trace` is added to LRU.

- [ ] **Step 6: Exclude trace tool from ToolDiscoveryState LRU**

Modify `agent/core/runtime_support.py`:

```python
NON_LRU_TOOL_NAMES = frozenset({"tool_search", "inspect_turn_trace"})
```

Then update `ToolDiscoveryState.update(...)`:

```python
skip = always_on | NON_LRU_TOOL_NAMES
```

- [ ] **Step 7: Run infrastructure tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_observe_writer.py::test_observe_slim_trace_preserves_boundary_metadata \
  tests/test_turn_trace_query.py::test_inspect_turn_trace_is_not_added_to_lru \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add plugins/observe/plugin.py agent/core/runtime_support.py tests/test_observe_writer.py tests/test_turn_trace_query.py
git commit -m "fix: preserve trace metadata and exclude trace tool from lru"
```

---

### Task 3: Inspect Turn Trace Tool Adapter

**Files:**
- Create: `agent/tools/turn_trace.py`
- Modify: `bootstrap/tools.py`
- Test: `tests/test_turn_trace_tool.py`

**Interfaces:**
- Consumes: `TurnTraceQueryService.resolve(...)`.
- Produces: `InspectTurnTraceTool`, name `inspect_turn_trace`.

- [ ] **Step 1: Write failing tool tests**

Create `tests/test_turn_trace_tool.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tools.turn_trace import InspectTurnTraceTool
from tests.test_turn_trace_query import _insert_turn, _make_observe_db
from agent.tracing.turn_trace_query import TurnTraceQueryService


@pytest.mark.asyncio
async def test_inspect_turn_trace_returns_structured_tool_counts(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    turn_id = _insert_turn(
        db,
        session_key="cli:s1",
        user_msg="source question",
        tool_chain=[
            {"text": "", "calls": [{"name": "read_file", "status": "success", "result": "a"}]},
            {"text": "", "calls": [{"name": "read_file", "status": "success", "result": "b"}]},
        ],
    )
    tool = InspectTurnTraceTool(TurnTraceQueryService(db))

    raw = await tool.execute(_session_key="cli:s1", selector="turn_id", turn_id=turn_id)
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["turn"]["id"] == turn_id
    assert payload["summary"]["real_tools"] == {"read_file": 2}


@pytest.mark.asyncio
async def test_inspect_turn_trace_requires_session_key(tmp_path: Path) -> None:
    tool = InspectTurnTraceTool(TurnTraceQueryService(tmp_path / "observe.db"))

    raw = await tool.execute(selector="previous_completed")
    payload = json.loads(raw)

    assert payload["ok"] is False
    assert payload["error_code"] == "missing_session_context"


def test_inspect_turn_trace_schema_does_not_expose_session_keys(tmp_path: Path) -> None:
    tool = InspectTurnTraceTool(TurnTraceQueryService(tmp_path / "observe.db"))

    schema = tool.to_schema()
    properties = schema["function"]["parameters"]["properties"]

    assert "session_key" not in properties
    assert "_session_key" not in properties
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_tool.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.tools.turn_trace'`.

- [ ] **Step 3: Implement `InspectTurnTraceTool`**

Create `agent/tools/turn_trace.py`:

```python
from __future__ import annotations

import json
from typing import Any

from agent.tools.base import Tool
from agent.tracing.turn_trace_query import TurnTraceQueryResult, TurnTraceQueryService


class InspectTurnTraceTool(Tool):
    name = "inspect_turn_trace"
    description = (
        "读取当前 session 的结构化 turn/tool trace，用于回答“刚才用了哪些工具”、"
        "“上一轮工具链是什么”、“第 N 个问题调用了哪些工具”。"
        "这是工具历史事实的 source of truth；不要用 search_messages 的自然语言预览猜测工具链。"
        "只查询当前 session，不跨 session。若返回 ambiguous_selector，先向用户确认候选 turn。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "enum": [
                    "previous_completed",
                    "recent_nth_completed",
                    "nth_user_question_in_window",
                    "turn_id",
                    "query",
                ],
                "description": "选择要查询的 turn。",
                "default": "previous_completed",
            },
            "n": {
                "type": "integer",
                "description": "selector=recent_nth_completed 或 nth_user_question_in_window 时使用。",
                "minimum": 1,
                "maximum": 20,
            },
            "turn_id": {
                "type": "integer",
                "description": "selector=turn_id 时使用。",
                "minimum": 1,
            },
            "query": {
                "type": "string",
                "description": "selector=query 时用于匹配用户问题文本。",
            },
        },
        "required": ["selector"],
    }

    def __init__(self, service: TurnTraceQueryService) -> None:
        self._service = service

    async def execute(
        self,
        selector: str = "previous_completed",
        n: int | None = None,
        turn_id: int | None = None,
        query: str | None = None,
        _session_key: str | None = None,
        **_: Any,
    ) -> str:
        clean_session_key = str(_session_key or "").strip()
        if not clean_session_key:
            return json.dumps(
                {
                    "ok": False,
                    "error_code": "missing_session_context",
                    "message": "inspect_turn_trace requires protected current-session context.",
                },
                ensure_ascii=False,
            )
        result = self._service.resolve(
            clean_session_key,
            selector=selector,
            n=n,
            turn_id=turn_id,
            query=query,
        )
        return json.dumps(_result_to_payload(result), ensure_ascii=False)


def _result_to_payload(result: TurnTraceQueryResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": result.ok,
        "source": result.source,
    }
    if result.error_code:
        payload["error_code"] = result.error_code
    if result.message:
        payload["message"] = result.message
    if result.candidates:
        payload["candidates"] = [
            {
                "id": item.id,
                "ts": item.ts,
                "user_msg": item.user_msg,
                "real_tools": item.real_tool_counts,
            }
            for item in result.candidates
        ]
    if result.turn is not None:
        turn = result.turn
        payload["turn"] = {
            "id": turn.id,
            "ts": turn.ts,
            "current_session": True,
            "user_msg": turn.user_msg,
            "error": turn.error,
            "react_iteration_count": turn.react_iteration_count,
        }
        payload["tools"] = [
            {
                "name": tool.name,
                "status": tool.status,
                "real_executed": tool.real_executed,
                "skipped": tool.skipped,
                "error_code": tool.error_code,
                "iteration": tool.iteration,
            }
            for tool in turn.tools
        ]
        payload["summary"] = {
            "real_tools": turn.real_tool_counts,
            "skipped_tools": turn.skipped_tool_counts,
            "tool_count": len(turn.tools),
        }
    return payload
```

- [ ] **Step 4: Run tool tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_tool.py tests/test_turn_trace_query.py -q
```

Expected: PASS.

- [ ] **Step 5: Register tool in bootstrap**

Modify `bootstrap/tools.py`:

```python
from agent.tools.turn_trace import InspectTurnTraceTool
from agent.tracing.turn_trace_query import TurnTraceQueryService
```

Inside `build_registered_tools(...)`, after `store = session_store or SessionStore(...)`, add:

```python
    turn_trace_service = TurnTraceQueryService(workspace / "observe" / "observe.db")
    tools.register(
        InspectTurnTraceTool(turn_trace_service),
        always_on=False,
        risk="read-only",
        search_hint="工具历史 tool chain 上一轮 刚才 用了哪些工具",
    )
```

- [ ] **Step 6: Add bootstrap registration test**

Append this assertion to `tests/test_bootstrap_toolsets_p1.py::test_build_registered_tools_uses_toolset_providers` after the existing assertions:

```python
    assert tools.has_tool("inspect_turn_trace")
    assert "inspect_turn_trace" not in tools.get_always_on_names()
```

- [ ] **Step 7: Run registration tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_tool.py tests/test_turn_trace_query.py tests/test_bootstrap_toolsets_p1.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add agent/tools/turn_trace.py bootstrap/tools.py tests/test_turn_trace_tool.py tests/test_bootstrap_toolsets_p1.py
git commit -m "feat: expose turn trace query as deferred tool"
```

---

### Task 4: Tool Context and Gateway Visibility

**Files:**
- Modify: `agent/lifecycle/phases/before_reasoning.py`
- Modify: `agent/looping/handlers.py`
- Modify: `agent/tools/registry.py`
- Modify: `agent/policies/tool_access.py`
- Test: `tests/test_tool_access_gateway.py`
- Test: `tests/test_tool_access_gateway_reasoner.py`

**Interfaces:**
- Consumes: registered deferred tool `inspect_turn_trace`.
- Produces:
  - `TRACE_TOOL_NAMES = frozenset({"inspect_turn_trace"})`
  - session/meta turns include `inspect_turn_trace` in `visible_add`.
  - `ToolRegistry` context includes protected `_session_key`.
  - Protected context keys beginning with `_` override model-supplied arguments.

- [ ] **Step 1: Write failing gateway unit tests**

Append to `tests/test_tool_access_gateway.py`:

```python
from agent.policies.tool_access import ToolAccessContext, ToolAccessGateway


def test_session_meta_tool_history_exposes_trace_tool_and_suppresses_doc_rag() -> None:
    context = ToolAccessContext(
        session_key="cli:s1",
        user_text="刚才第二个问题你用了哪些工具？",
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset({"search_docs", "fetch_doc_chunk"}),
        disabled_tools=frozenset(),
    )

    plan = ToolAccessGateway().build_plan(context)
    visible = ToolAccessGateway().compute_visible_names(context, plan)

    assert "inspect_turn_trace" in plan.visible_add
    assert "inspect_turn_trace" in visible
    assert "search_docs" not in visible
    assert "fetch_doc_chunk" not in visible
    assert "SessionMetaAccessPolicy" in plan.policies


def test_tool_history_intent_wins_over_mixed_doc_intent() -> None:
    context = ToolAccessContext(
        session_key="cli:s1",
        user_text="刚才项目文档那个问题用了哪些工具？",
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset({"search_docs", "fetch_doc_chunk"}),
        disabled_tools=frozenset(),
    )

    plan = ToolAccessGateway().build_plan(context)
    visible = ToolAccessGateway().compute_visible_names(context, plan)

    assert "inspect_turn_trace" in plan.visible_add
    assert "inspect_turn_trace" in visible
    assert "search_docs" not in visible
    assert "fetch_doc_chunk" not in visible
    assert plan.execution_block.issuperset({"search_docs", "fetch_doc_chunk"})
    assert "SessionMetaAccessPolicy" in plan.policies
```

- [ ] **Step 2: Run gateway tests to verify they fail**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_tool_access_gateway.py::test_session_meta_tool_history_exposes_trace_tool_and_suppresses_doc_rag \
  tests/test_tool_access_gateway.py::test_tool_history_intent_wins_over_mixed_doc_intent \
  -q
```

Expected: FAIL because `inspect_turn_trace` is not in `visible_add`, and mixed doc/tool-history prompts still allow stale Document RAG tools.

- [ ] **Step 3: Extend `SessionMetaAccessPolicy`**

Modify `agent/policies/tool_access.py`:

```python
TRACE_TOOL_NAMES = frozenset({"inspect_turn_trace"})
```

In `SessionMetaAccessPolicy.build_plan(...)`, change the returned plan to:

```python
        matched = _matched_terms(context.user_text, _SESSION_META_TERMS)
        if not matched:
            return ToolAccessPlan()
        return ToolAccessPlan(
            visible_add=TRACE_TOOL_NAMES,
            visible_suppress=DOC_RAG_TOOL_NAMES,
            tool_search_block=DOC_RAG_TOOL_NAMES,
            execution_block=DOC_RAG_TOOL_NAMES,
            reason="session_meta_suppress_doc_rag_lru",
            matched_terms=matched,
            policies=(self.name,),
        )
```

Remove the existing early return that skips `SessionMetaAccessPolicy` when `decide_doc_rag_preload(...)` is true. Tool-history/session-meta intent must win over document intent because the user is asking about a prior turn's trace, not asking to re-answer from the document corpus.

- [ ] **Step 4: Run gateway tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_access_gateway.py -q
```

Expected: PASS.

- [ ] **Step 5: Add reasoner schema visibility tests**

Add to `tests/test_tool_access_gateway_reasoner.py` tests that register `inspect_turn_trace` and verify session-meta prompts expose it while suppressing RAG tools. Use the existing fake provider/test harness style in that file. Extract a local helper named `_run_reasoner_visibility_case(prompt: str)` from the existing setup code in this test file; it must return `(result, provider)` after running one turn with `inspect_turn_trace`, `search_docs`, and `fetch_doc_chunk` registered as deferred tools. Cover both a pure tool-history prompt and a mixed doc/tool-history prompt:

```python
@pytest.mark.parametrize(
    "prompt",
    [
        "刚才第二个问题你用了哪些工具？",
        "刚才项目文档那个问题用了哪些工具？",
    ],
)
@pytest.mark.asyncio
async def test_reasoner_exposes_trace_tool_for_tool_history_prompts(prompt: str) -> None:
    result, provider = await _run_reasoner_visibility_case(prompt)

    schemas = provider.calls[0]["tools"]
    names = {schema["function"]["name"] for schema in schemas}
    assert "inspect_turn_trace" in names
    assert "search_docs" not in names
    assert "fetch_doc_chunk" not in names
    assert "inspect_turn_trace" in result.tools_used
```

- [ ] **Step 6: Run reasoner visibility test**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_access_gateway_reasoner.py -q
```

Expected: PASS.

- [ ] **Step 7: Add reasoner-level non-LRU regression**

Add a test in `tests/test_tool_access_gateway_reasoner.py` that:

1. Registers `inspect_turn_trace` as deferred.
2. Runs a turn where the fake provider calls `inspect_turn_trace`.
3. Lets the turn finish successfully.
4. Asserts `discovery.get_preloaded(session_key)` does not include `inspect_turn_trace`.

Core assertion:

```python
assert "inspect_turn_trace" not in discovery.get_preloaded(session_key)
```

- [ ] **Step 8: Add protected context merge semantics**

Add a test in `tests/test_tool_executor.py` or `tests/test_tool_search.py` using a dummy tool that echoes `_session_key`:

```python
class _EchoPrivateSessionTool(Tool):
    name = "echo_private_session"
    description = "echo private session"
    parameters = {
        "type": "object",
        "properties": {
            "_session_key": {"type": "string"},
        },
    }

    async def execute(self, _session_key: str = "", **_: object) -> str:
        return _session_key


def test_registry_protected_context_overrides_model_arguments() -> None:
    registry = ToolRegistry()
    registry.register(_EchoPrivateSessionTool())
    registry.set_context(_session_key="cli:current")

    result = asyncio.run(
        registry.execute("echo_private_session", {"_session_key": "cli:other"})
    )

    assert result == "cli:current"
```

Modify `agent/tools/registry.py::ToolRegistry.execute(...)`:

```python
public_context = {k: v for k, v in self._context.items() if not k.startswith("_")}
protected_context = {k: v for k, v in self._context.items() if k.startswith("_")}
merged: dict[str, Any] = {**public_context, **arguments, **protected_context}
```

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_executor.py -q
```

Expected: PASS.

- [ ] **Step 9: Inject protected `_session_key` into tool context**

Modify `agent/lifecycle/phases/before_reasoning.py` in `_SyncToolContextModule.run(...)` so the existing `self._tools.set_context(...)` call includes:

```python
            session_key=before_turn.session_key,
            _session_key=before_turn.session_key,
```

Modify `agent/looping/handlers.py` direct context sync from:

```python
tools.set_context(channel=item.channel, chat_id=item.chat_id)
```

to:

```python
tools.set_context(
    channel=item.channel,
    chat_id=item.chat_id,
    session_key=key,
    _session_key=key,
)
```

- [ ] **Step 10: Add context propagation test**

Extend `tests/test_lifecycle_phases.py::test_before_reasoning_setup_calls_tools_set_context` or nearby test to assert `session_key` is present:

```python
kwargs = tools.set_context.call_args.kwargs
assert kwargs["session_key"] == "cli:s1"
assert kwargs["_session_key"] == "cli:s1"
```

- [ ] **Step 11: Run context and gateway tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_lifecycle_phases.py tests/test_tool_access_gateway.py tests/test_tool_access_gateway_reasoner.py -q
```

Expected: PASS.

- [ ] **Step 12: Commit Task 4**

```bash
git add agent/lifecycle/phases/before_reasoning.py agent/looping/handlers.py agent/tools/registry.py agent/policies/tool_access.py tests/test_lifecycle_phases.py tests/test_tool_access_gateway.py tests/test_tool_access_gateway_reasoner.py tests/test_tool_executor.py
git commit -m "feat: expose turn trace tool for session meta turns"
```

---

### Task 5: End-to-End Regression for Tool-History Accuracy

**Files:**
- Test: `tests/test_turn_trace_reasoner.py`
- Modify only if required: `agent/core/passive_turn.py`

**Interfaces:**
- Consumes:
  - `inspect_turn_trace` visible only for session-meta/tool-history turns.
  - `InspectTurnTraceTool` JSON output.
- Produces:
  - Regression that prevents turn `370`-style hallucinated tool history.

- [ ] **Step 1: Write failing end-to-end reasoner test**

Create `tests/test_turn_trace_reasoner.py` using the existing fake provider style from `tests/test_tool_access_gateway_reasoner.py`. The scenario:

1. The prompt is `刚才第二个问题你用了哪些工具？`.
2. First LLM call sees `inspect_turn_trace`.
3. The test seeds a real temporary `observe.db` via `plugins.observe.db.open_db()`.
4. The test inserts recent turns in chronological order:
   - first seeded turn: a Document RAG question with `search_docs + fetch_doc_chunk`;
   - second seeded turn: the source question with `read_file x3`;
   - third seeded turn: another non-target turn, so selecting by exact `turn_id` is not the only way to pass.
5. The registry registers the real `InspectTurnTraceTool(TurnTraceQueryService(observe_db))`.
6. Fake provider calls `inspect_turn_trace(selector="nth_user_question_in_window", n=2)`.
7. The test inspects the second provider call input and asserts the tool result contains `"real_tools": {"read_file": 3}` and does not contain `"real_tools": {"search_docs": ...}` for the selected turn.
8. Final LLM response says `read_file x3`.

The assertions:

```python
assert "inspect_turn_trace" in result.tools_used
assert "search_docs" not in result.tools_used
assert "fetch_doc_chunk" not in result.tools_used
assert "read_file x3" in result.text
```

Also assert the trace tool call arguments:

```python
assert tool_call.name == "inspect_turn_trace"
assert tool_call.arguments == {"selector": "nth_user_question_in_window", "n": 2}
```

And assert the second LLM call receives the structured tool result:

```python
second_call_messages = provider.calls[1]["messages"]
tool_payload_text = next(
    msg["content"]
    for msg in second_call_messages
    if msg.get("role") == "tool"
)
assert '"real_tools": {"read_file": 3}' in tool_payload_text
assert '"real_tools": {"search_docs"' not in tool_payload_text
```

- [ ] **Step 2: Run reasoner regression**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_trace_reasoner.py -q
```

Expected: FAIL until the tool is correctly registered/exposed in the harness.

- [ ] **Step 3: Fix test harness registration or integration gaps**

The test must not stub the trace result. It must register the real tool against the seeded DB:

```python
tools.register(InspectTurnTraceTool(TurnTraceQueryService(observe_db)), always_on=False)
```

If the failure is schema visibility, fix Task 4 integration before proceeding.

- [ ] **Step 4: Run regression and adjacent suites**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_trace_query.py \
  tests/test_turn_trace_tool.py \
  tests/test_turn_trace_reasoner.py \
  tests/test_observe_writer.py \
  tests/test_tool_executor.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_message_lookup_tool.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add tests/test_turn_trace_reasoner.py agent/core/passive_turn.py
git commit -m "test: cover structured trace tool history answers"
```

Only include `agent/core/passive_turn.py` if it was actually modified.

---

### Task 6: Documentation and Runtime Smoke

**Files:**
- Modify: `my_md/governance/02-current-issues.md`
- Modify: `my_md/governance/04-fix-roadmap.md`
- Modify: `my_md/governance/06-star-log.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: completed implementation and tests.
- Produces: documented current status and manual smoke checklist.

- [ ] **Step 1: Run full relevant automated verification**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_trace_query.py \
  tests/test_turn_trace_tool.py \
  tests/test_turn_trace_reasoner.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_message_lookup_tool.py \
  tests/test_lifecycle_phases.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run compile check**

Run:

```bash
python3 -m compileall agent/tracing agent/tools/turn_trace.py agent/tools/registry.py agent/core/runtime_support.py agent/policies/tool_access.py plugins/observe/plugin.py tests/test_turn_trace_query.py tests/test_turn_trace_tool.py tests/test_turn_trace_reasoner.py
```

Expected: exit code 0.

- [ ] **Step 3: Run full pytest if time allows**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest -q
```

Expected: PASS or document exact failures if unrelated.

- [ ] **Step 4: Manual CLI smoke**

Use the same session pattern that produced turns `367-370`:

```text
请从文档知识库中检索agent runtime负责什么？回答必须带文档引用
根据项目文档回答agent runtime负责什么，并展开原文证据
根据项目文档和源码回答 agent runtime 负责什么，请读取 agent/core/passive_turn.py
刚才第二个问题你用了哪些工具？
```

Expected:

- The fourth turn calls `inspect_turn_trace`.
- The fourth turn does not call `search_docs` or `fetch_doc_chunk`.
- The fourth turn answer matches observe facts for the selected turn.
- If the selector "第二个问题" is ambiguous, the agent returns candidates or clarifies instead of guessing.

- [ ] **Step 5: Update docs**

Update:

- `my_md/governance/02-current-issues.md`
  - Mark trace/source-of-truth boundary implementation status.
  - Record automated and manual smoke results.
- `my_md/governance/04-fix-roadmap.md`
  - Add trace query as the next session/meta fix after P10a.4b.
- `my_md/governance/06-star-log.md`
  - Extend CASE-003 with the new source-of-truth boundary.
- `progress.md`
  - Record test commands and turn ids from manual smoke.

- [ ] **Step 6: Run doc whitespace check**

Run:

```bash
git diff --check -- \
  my_md/governance/02-current-issues.md \
  my_md/governance/04-fix-roadmap.md \
  my_md/governance/06-star-log.md \
  progress.md
```

Expected: exit code 0.

- [ ] **Step 7: Commit Task 6**

```bash
git add \
  my_md/governance/02-current-issues.md \
  my_md/governance/04-fix-roadmap.md \
  my_md/governance/06-star-log.md \
  progress.md
git commit -m "docs: record structured turn trace query rollout"
```

---

## Final Verification

Run before declaring the feature complete:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_trace_query.py \
  tests/test_turn_trace_tool.py \
  tests/test_turn_trace_reasoner.py \
  tests/test_observe_writer.py \
  tests/test_tool_executor.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_message_lookup_tool.py \
  tests/test_lifecycle_phases.py \
  -q
```

Expected: PASS.

Run:

```bash
python3 -m compileall agent/tracing agent/tools/turn_trace.py agent/tools/registry.py agent/core/runtime_support.py agent/policies/tool_access.py plugins/observe/plugin.py
```

Expected: exit code 0.

Run:

```bash
git diff --check
```

Expected: exit code 0.

## Self-Review Notes

- Scope is one subsystem: current-session structured tool-history trace lookup.
- Cross-session trace lookup, dashboard UI, and long-term audit export are explicitly out of scope.
- The plan keeps correctness in a core service and uses the tool/plugin layer only as an adapter.
- The revised plan closes review blockers: trace tool is non-LRU, session binding uses protected context, and observe slim traces preserve skipped/blocked metadata.
- The plan does not make `inspect_turn_trace` always-on and does not write intent state to LRU.
- The plan includes tests for the original failure mode: context said RAG evidence existed, but the selected turn actually used only `read_file x3`.
