from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_SKIPPED_STATUSES = frozenset(
    {
        "batch_skipped_by_react_boundary",
        "tool_boundary_soft_stop",
        "blocked_by_tool_access_gateway",
        "blocked_by_tool_boundary",
        "soft_stopped_by_tool_boundary",
    }
)

_SKIPPED_BOUNDARY_REASONS = frozenset(
    {
        "tool_blocked_by_doc_rag_policy",
        "document_rag_batch_evidence_complete",
    }
)

_SKIPPED_ERROR_CODES = frozenset(
    {
        "react_boundary_batch_skip",
        "tool_boundary_soft_stop",
        "blocked_by_tool_access_gateway",
        "tool_blocked_by_doc_rag_policy",
    }
)


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

    def get_recent_turns(
        self, session_key: str, limit: int = 10
    ) -> list[TurnTraceSummary]:
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

    def _resolve_recent_nth(
        self, session_key: str, n: int
    ) -> TurnTraceQueryResult:
        normalized_n = max(1, int(n))
        rows = self._fetch_all(
            """
            SELECT id, ts, session_key, user_msg, llm_output, error,
                   react_iteration_count, tool_chain_json, tool_calls
            FROM turns
            WHERE session_key = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_key, normalized_n),
        )
        if len(rows) < normalized_n:
            return TurnTraceQueryResult(
                ok=False,
                error_code="turn_not_found",
                candidates=tuple(self.get_recent_turns(session_key, 5)),
                message="Not enough recent turns exist in this session.",
            )
        return TurnTraceQueryResult(
            ok=True, turn=self._row_to_trace(rows[normalized_n - 1])
        )

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
        matches = [
            self._row_to_trace(row)
            for row in rows
            if term in str(row["user_msg"] or "").lower()
        ]
        if len(matches) == 1:
            return TurnTraceQueryResult(ok=True, turn=matches[0])
        fallback = matches or [self._row_to_trace(row) for row in rows[:5]]
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
                for trace in fallback
            ),
            message="Selector did not identify exactly one turn.",
        )

    def _resolve_nth_user_question_in_window(
        self, session_key: str, n: int
    ) -> TurnTraceQueryResult:
        normalized_n = max(1, int(n))
        rows = list(
            reversed(
                self._fetch_all(
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
            )
        )
        if len(rows) < normalized_n:
            return TurnTraceQueryResult(
                ok=False,
                error_code="ambiguous_selector",
                candidates=tuple(self.get_recent_turns(session_key, 5)),
                message="The requested ordinal question is ambiguous or outside the recent window.",
            )
        return TurnTraceQueryResult(
            ok=True, turn=self._row_to_trace(rows[normalized_n - 1])
        )

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

    def _fetch_one(
        self, sql: str, params: tuple[object, ...]
    ) -> sqlite3.Row | None:
        if not self._observe_db_path.exists():
            return None
        with self._connect() as conn:
            return conn.execute(sql, params).fetchone()

    def _fetch_all(self, sql: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
        if not self._observe_db_path.exists():
            return []
        with self._connect() as conn:
            return list(conn.execute(sql, params).fetchall())


def _parse_tool_chain(
    tool_chain_json: str | None, tool_calls_json: str | None
) -> list[TurnToolCall]:
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
    return [
        _to_tool_call(raw, 0)
        for raw in _loads_json_list(tool_calls_json)
        if isinstance(raw, dict)
    ]


def _to_tool_call(raw: dict[str, Any], iteration: int) -> TurnToolCall:
    name = str(raw.get("name") or raw.get("tool") or "")
    status = str(raw.get("status") or "")
    result_text = str(raw.get("result") or "")
    error_code = str(raw.get("error_code") or "") or _extract_error_code(result_text)
    boundary_reason = str(raw.get("boundary_reason") or "")
    skipped = (
        status in _SKIPPED_STATUSES
        or boundary_reason in _SKIPPED_BOUNDARY_REASONS
        or error_code in _SKIPPED_ERROR_CODES
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
