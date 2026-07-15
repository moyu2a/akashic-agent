from __future__ import annotations

import json
import sqlite3
from typing import Any, cast
from uuid import uuid4

from agent.task_plan.execution_models import (
    AttemptStatus,
    ExecutionEventType,
    ExecutionMode,
    TaskExecutionAttempt,
    TaskExecutionEvent,
    validate_attempt_status,
)


EXECUTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS task_execution_attempts (
    attempt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    session_key TEXT NOT NULL,
    request_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    attempt_no INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'pending', 'running', 'waiting_authorization',
            'succeeded', 'failed', 'blocked', 'cancelled'
        )
    ),
    execution_mode TEXT NOT NULL CHECK (
        execution_mode IN ('read_only_auto', 'authorization_required')
    ),
    owner_instance_id TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    source_turn_id INTEGER,
    requested_tool_name TEXT NOT NULL DEFAULT '',
    requested_arguments_json TEXT NOT NULL DEFAULT '{}',
    requested_capabilities_json TEXT NOT NULL DEFAULT '[]',
    result_summary TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL DEFAULT '',
    terminal_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(task_id) REFERENCES task_plans(task_id) ON DELETE CASCADE,
    FOREIGN KEY(step_id) REFERENCES task_steps(step_id) ON DELETE CASCADE,
    UNIQUE(step_id, attempt_no),
    UNIQUE(session_key, request_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_execution_one_active_per_step
ON task_execution_attempts(step_id)
WHERE status IN ('pending', 'running', 'waiting_authorization');

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_execution_one_active_per_task
ON task_execution_attempts(task_id)
WHERE status IN ('pending', 'running', 'waiting_authorization');

CREATE TABLE IF NOT EXISTS task_execution_events (
    event_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '',
    tool_call_id TEXT NOT NULL DEFAULT '',
    source_turn_id INTEGER,
    tool_risk TEXT NOT NULL DEFAULT '',
    tool_capabilities_json TEXT NOT NULL DEFAULT '[]',
    counts_as_work INTEGER NOT NULL DEFAULT 0,
    invoker_reached INTEGER NOT NULL DEFAULT 0,
    invoker_succeeded INTEGER NOT NULL DEFAULT 0,
    execution_status TEXT NOT NULL DEFAULT '',
    result_ok INTEGER,
    error_code TEXT NOT NULL DEFAULT '',
    arguments_hash TEXT NOT NULL DEFAULT '',
    result_preview TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(attempt_id) REFERENCES task_execution_attempts(attempt_id)
        ON DELETE CASCADE,
    UNIQUE(attempt_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS ix_task_execution_events_attempt_sequence
ON task_execution_events(attempt_id, sequence_no);
"""


def new_execution_event_id() -> str:
    return f"event_{uuid4().hex}"


def row_to_execution_attempt(row: sqlite3.Row) -> TaskExecutionAttempt:
    return TaskExecutionAttempt(
        attempt_id=str(row["attempt_id"]),
        task_id=str(row["task_id"]),
        step_id=str(row["step_id"]),
        session_key=str(row["session_key"]),
        request_id=str(row["request_id"]),
        idempotency_key=str(row["idempotency_key"]),
        attempt_no=int(row["attempt_no"]),
        status=validate_attempt_status(str(row["status"])),
        execution_mode=cast(ExecutionMode, str(row["execution_mode"])),
        owner_instance_id=str(row["owner_instance_id"]),
        lease_expires_at=str(row["lease_expires_at"]),
        source_turn_id=row["source_turn_id"],
        requested_tool_name=str(row["requested_tool_name"] or ""),
        requested_arguments=_json_loads_dict(row["requested_arguments_json"]),
        requested_capabilities=tuple(_json_loads_list(row["requested_capabilities_json"])),
        result_summary=str(row["result_summary"] or ""),
        error_code=str(row["error_code"] or ""),
        terminal_reason=str(row["terminal_reason"] or ""),
        created_at=str(row["created_at"]),
        started_at=row["started_at"],
        updated_at=str(row["updated_at"]),
        finished_at=row["finished_at"],
        metadata=_json_loads_dict(row["metadata_json"]),
    )


def row_to_execution_event(row: sqlite3.Row) -> TaskExecutionEvent:
    result_ok = row["result_ok"]
    return TaskExecutionEvent(
        event_id=str(row["event_id"]),
        attempt_id=str(row["attempt_id"]),
        sequence_no=int(row["sequence_no"]),
        event_type=cast(ExecutionEventType, str(row["event_type"])),
        tool_name=str(row["tool_name"] or ""),
        tool_call_id=str(row["tool_call_id"] or ""),
        source_turn_id=row["source_turn_id"],
        tool_risk=str(row["tool_risk"] or ""),
        tool_capabilities=tuple(_json_loads_list(row["tool_capabilities_json"])),
        counts_as_work=bool(row["counts_as_work"]),
        invoker_reached=bool(row["invoker_reached"]),
        invoker_succeeded=bool(row["invoker_succeeded"]),
        execution_status=str(row["execution_status"] or ""),
        result_ok=None if result_ok is None else bool(result_ok),
        error_code=str(row["error_code"] or ""),
        arguments_hash=str(row["arguments_hash"] or ""),
        result_preview=str(row["result_preview"] or ""),
        created_at=str(row["created_at"]),
        metadata=_json_loads_dict(row["metadata_json"]),
    )


def json_dump(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _json_loads_dict(raw: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw or "{}"))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_loads_list(raw: object) -> list[str]:
    try:
        parsed = json.loads(str(raw or "[]"))
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]
