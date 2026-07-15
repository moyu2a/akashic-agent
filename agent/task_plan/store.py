from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.task_plan.execution_models import (
    AttemptClaimResult,
    ExecutionEventType,
    TaskExecutionAttempt,
    TaskExecutionEvent,
)
from agent.task_plan.execution_store import (
    EXECUTION_SCHEMA_SQL,
    ReconciledExecutionAttempt,
    json_dump as _execution_json_dump,
    new_execution_event_id,
    normalize_execution_comparison_timestamp,
    normalize_execution_lease_timestamp,
    row_to_execution_attempt,
    row_to_execution_event,
)
from agent.task_plan.models import (
    StepStatus,
    TaskPlan,
    TaskStatus,
    TaskStep,
    new_step_id,
    new_task_id,
    utc_now_iso,
    validate_step_status,
    validate_task_status,
)


class ActiveTaskExistsError(RuntimeError):
    pass


class TaskPlanNotFoundError(RuntimeError):
    pass


class TaskStepNotFoundError(RuntimeError):
    pass


class ActiveExecutionAttemptExistsError(RuntimeError):
    pass


class ExecutionAttemptConflictError(RuntimeError):
    pass


class TaskExecutionAttemptNotFoundError(RuntimeError):
    pass


class TaskPlanStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._ensure_schema()

    def create_plan(
        self,
        *,
        session_key: str,
        title: str,
        step_titles: list[str],
        source_turn_id: int | None = None,
        replace_active: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> TaskPlan:
        task_id = new_task_id()
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if replace_active:
                    if self._has_active_execution_attempt_for_session(conn, session_key):
                        raise ActiveExecutionAttemptExistsError(
                            "abort the active execution attempt first"
                        )
                    conn.execute(
                        """
                        UPDATE task_plans
                        SET status = 'cancelled',
                            updated_at = ?,
                            completed_at = COALESCE(completed_at, ?),
                            terminal_reason = CASE
                                WHEN terminal_reason = '' THEN 'replaced'
                                ELSE terminal_reason
                            END
                        WHERE session_key = ? AND status = 'active'
                        """,
                        (now, now, session_key),
                    )
                conn.execute(
                    """
                    INSERT INTO task_plans (
                        task_id, session_key, title, status, source_turn_id,
                        created_at, updated_at, metadata_json
                    )
                    VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        session_key,
                        title,
                        source_turn_id,
                        now,
                        now,
                        _json_dump(metadata or {}),
                    ),
                )
                for index, step_title in enumerate(step_titles, start=1):
                    conn.execute(
                        """
                        INSERT INTO task_steps (
                            step_id, task_id, step_index, title, status
                        )
                        VALUES (?, ?, ?, ?, 'pending')
                        """,
                        (new_step_id(), task_id, index, step_title),
                    )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                if _is_active_unique_error(exc):
                    raise ActiveTaskExistsError(
                        "active task already exists"
                    ) from exc
                raise
            except Exception:
                conn.rollback()
                raise
        plan = self.get_plan(task_id)
        if plan is None:
            raise TaskPlanNotFoundError(task_id)
        return plan

    def get_plan(self, task_id: str) -> TaskPlan | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_plans WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            steps = self._fetch_steps(conn, task_id)
            return _row_to_plan(row, steps)

    def get_active_plan(self, session_key: str) -> TaskPlan | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM task_plans
                WHERE session_key = ? AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (session_key,),
            ).fetchone()
            if row is None:
                return None
            steps = self._fetch_steps(conn, str(row["task_id"]))
            return _row_to_plan(row, steps)

    def update_step(
        self,
        *,
        task_id: str,
        status: StepStatus | str,
        step_id: str | None = None,
        step_index: int | None = None,
        result_summary: str = "",
        tool_names: list[str] | None = None,
        source_turn_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskPlan:
        status = validate_step_status(str(status))
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                where, params = _step_selector_where(
                    task_id=task_id,
                    step_id=step_id,
                    step_index=step_index,
                )
                row = conn.execute(
                    f"SELECT * FROM task_steps WHERE {where}",
                    params,
                ).fetchone()
                if row is None:
                    raise TaskStepNotFoundError("task step not found")
                self._require_no_active_execution_attempt(conn, task_id)
                started_at = row["started_at"]
                completed_at = row["completed_at"]
                if status == "in_progress" and started_at is None:
                    started_at = now
                if status in {"completed", "failed", "skipped"}:
                    completed_at = now
                    if started_at is None:
                        started_at = now
                conn.execute(
                    f"""
                    UPDATE task_steps
                    SET status = ?,
                        result_summary = ?,
                        tool_names_json = ?,
                        source_turn_id = ?,
                        started_at = ?,
                        completed_at = ?,
                        metadata_json = ?
                    WHERE {where}
                    """,
                    (
                        status,
                        result_summary,
                        _json_dump(tool_names or []),
                        source_turn_id,
                        started_at,
                        completed_at,
                        _json_dump(metadata or {}),
                        *params,
                    ),
                )
                conn.execute(
                    "UPDATE task_plans SET updated_at = ? WHERE task_id = ?",
                    (now, task_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        plan = self.get_plan(task_id)
        if plan is None:
            raise TaskPlanNotFoundError(task_id)
        return plan

    def set_task_status(
        self,
        *,
        task_id: str,
        status: TaskStatus | str,
        terminal_reason: str = "",
    ) -> TaskPlan:
        status = validate_task_status(str(status))
        now = utc_now_iso()
        completed_at = now if status in {"completed", "cancelled", "failed"} else None
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._require_no_active_execution_attempt(conn, task_id)
                cur = conn.execute(
                    """
                    UPDATE task_plans
                    SET status = ?,
                        updated_at = ?,
                        completed_at = ?,
                        terminal_reason = ?
                    WHERE task_id = ?
                    """,
                    (status, now, completed_at, terminal_reason, task_id),
                )
                if cur.rowcount == 0:
                    raise TaskPlanNotFoundError(task_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        plan = self.get_plan(task_id)
        if plan is None:
            raise TaskPlanNotFoundError(task_id)
        return plan

    def _ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_plans (
                    task_id TEXT PRIMARY KEY,
                    session_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('active', 'completed', 'cancelled', 'failed')
                    ),
                    source_turn_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    terminal_reason TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE UNIQUE INDEX IF NOT EXISTS ux_task_plans_one_active_per_session
                ON task_plans(session_key)
                WHERE status = 'active';

                CREATE INDEX IF NOT EXISTS ix_task_plans_session_status_updated
                ON task_plans(session_key, status, updated_at);

                CREATE TABLE IF NOT EXISTS task_steps (
                    step_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN (
                            'pending', 'in_progress', 'completed', 'failed', 'skipped'
                        )
                    ),
                    tool_names_json TEXT NOT NULL DEFAULT '[]',
                    result_summary TEXT NOT NULL DEFAULT '',
                    source_turn_id INTEGER,
                    started_at TEXT,
                    completed_at TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(task_id) REFERENCES task_plans(task_id) ON DELETE CASCADE,
                    UNIQUE(task_id, step_index)
                );

                CREATE INDEX IF NOT EXISTS ix_task_steps_task_index
                ON task_steps(task_id, step_index);
                """
            )
            conn.executescript(EXECUTION_SCHEMA_SQL)
            self._normalize_persisted_execution_lease_timestamps(conn)
            conn.commit()

    def claim_execution_attempt(
        self,
        *,
        task_id: str,
        step_id: str,
        session_key: str,
        request_id: str,
        idempotency_key: str,
        owner_instance_id: str,
        lease_expires_at: str,
        source_turn_id: int | None = None,
        retry_from_attempt_id: str | None = None,
    ) -> AttemptClaimResult:
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                replay = conn.execute(
                    """
                    SELECT * FROM task_execution_attempts
                    WHERE session_key = ? AND request_id = ?
                    """,
                    (session_key, request_id),
                ).fetchone()
                if replay is not None:
                    conn.commit()
                    return AttemptClaimResult(
                        attempt=row_to_execution_attempt(replay),
                        disposition="request_replay",
                    )
                active = self._fetch_active_execution_attempt(conn, task_id)
                if active is not None:
                    conn.commit()
                    return AttemptClaimResult(
                        attempt=row_to_execution_attempt(active),
                        disposition="active_conflict",
                    )

                task = conn.execute(
                    "SELECT * FROM task_plans WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task is None or task["session_key"] != session_key:
                    raise TaskPlanNotFoundError(task_id)
                if task["status"] != "active":
                    raise ExecutionAttemptConflictError("task plan is not active")
                step = conn.execute(
                    "SELECT * FROM task_steps WHERE step_id = ? AND task_id = ?",
                    (step_id, task_id),
                ).fetchone()
                if step is None:
                    raise TaskStepNotFoundError("task step not found")
                latest = conn.execute(
                    """
                    SELECT * FROM task_execution_attempts
                    WHERE step_id = ?
                    ORDER BY attempt_no DESC LIMIT 1
                    """,
                    (step_id,),
                ).fetchone()
                if retry_from_attempt_id is None:
                    if step["status"] != "pending":
                        raise ExecutionAttemptConflictError("task step is not pending")
                    if latest is not None and latest["status"] in {
                        "failed",
                        "blocked",
                    }:
                        raise ExecutionAttemptConflictError(
                            "terminal step requires explicit retry"
                        )
                else:
                    if (
                        latest is None
                        or latest["attempt_id"] != retry_from_attempt_id
                        or latest["status"] not in {"failed", "blocked"}
                    ):
                        raise ExecutionAttemptConflictError(
                            "retry source attempt conflict"
                        )
                    if step["status"] not in {"failed", "pending"}:
                        raise ExecutionAttemptConflictError(
                            "retry step is not failed or pending"
                        )
                    if step["status"] == "failed":
                        self._reset_execution_step(conn, step_id, task_id)
                        self._after_execution_mutation("retry_after_step_reset")
                normalized_lease_expires_at = normalize_execution_lease_timestamp(
                    lease_expires_at
                )
                attempt_no = int(
                    conn.execute(
                        """
                        SELECT COALESCE(MAX(attempt_no), 0) + 1
                        FROM task_execution_attempts WHERE step_id = ?
                        """,
                        (step_id,),
                    ).fetchone()[0]
                )
                attempt = TaskExecutionAttempt.new(
                    task_id=task_id,
                    step_id=step_id,
                    session_key=session_key,
                    request_id=request_id,
                    idempotency_key=idempotency_key,
                    attempt_no=attempt_no,
                    owner_instance_id=owner_instance_id,
                    lease_expires_at=normalized_lease_expires_at,
                    source_turn_id=source_turn_id,
                )
                conn.execute(
                    """
                    INSERT INTO task_execution_attempts (
                        attempt_id, task_id, step_id, session_key, request_id,
                        idempotency_key, attempt_no, status, execution_mode,
                        owner_instance_id, lease_expires_at, source_turn_id,
                        requested_tool_name, requested_arguments_json,
                        requested_capabilities_json, result_summary, error_code,
                        terminal_reason, created_at, started_at, updated_at,
                        finished_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attempt.attempt_id,
                        attempt.task_id,
                        attempt.step_id,
                        attempt.session_key,
                        attempt.request_id,
                        attempt.idempotency_key,
                        attempt.attempt_no,
                        attempt.status,
                        attempt.execution_mode,
                        attempt.owner_instance_id,
                        attempt.lease_expires_at,
                        attempt.source_turn_id,
                        attempt.requested_tool_name,
                        _execution_json_dump(attempt.requested_arguments),
                        _execution_json_dump(list(attempt.requested_capabilities)),
                        attempt.result_summary,
                        attempt.error_code,
                        attempt.terminal_reason,
                        attempt.created_at,
                        attempt.started_at,
                        attempt.updated_at,
                        attempt.finished_at,
                        _execution_json_dump(attempt.metadata),
                    ),
                )
                self._after_execution_mutation("claim_after_attempt_insert")
                self._append_execution_event_in_transaction(
                    conn,
                    attempt_id=attempt.attempt_id,
                    event_type="attempt_claimed",
                    created_at=attempt.created_at,
                )
                self._after_execution_mutation("claim_after_event_insert")
                conn.commit()
                return AttemptClaimResult(attempt=attempt, disposition="created")
            except sqlite3.IntegrityError:
                conn.rollback()
                return self._claim_conflict_result(
                    conn,
                    task_id=task_id,
                    session_key=session_key,
                    request_id=request_id,
                )
            except Exception:
                conn.rollback()
                raise

    def get_execution_attempt(self, attempt_id: str) -> TaskExecutionAttempt | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_execution_attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        return None if row is None else row_to_execution_attempt(row)

    def get_execution_attempt_by_request(
        self, *, session_key: str, request_id: str
    ) -> TaskExecutionAttempt | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM task_execution_attempts
                WHERE session_key = ? AND request_id = ?
                """,
                (session_key, request_id),
            ).fetchone()
        return None if row is None else row_to_execution_attempt(row)

    def get_active_execution_attempt(self, task_id: str) -> TaskExecutionAttempt | None:
        with self._connect() as conn:
            row = self._fetch_active_execution_attempt(conn, task_id)
        return None if row is None else row_to_execution_attempt(row)

    def get_latest_execution_attempt_for_step(
        self, step_id: str
    ) -> TaskExecutionAttempt | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM task_execution_attempts WHERE step_id = ?
                ORDER BY attempt_no DESC LIMIT 1
                """,
                (step_id,),
            ).fetchone()
        return None if row is None else row_to_execution_attempt(row)

    def list_execution_attempts(self, task_id: str) -> list[TaskExecutionAttempt]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_execution_attempts WHERE task_id = ?
                ORDER BY step_id ASC, attempt_no ASC
                """,
                (task_id,),
            ).fetchall()
        return [row_to_execution_attempt(row) for row in rows]

    def list_recoverable_execution_attempts(
        self, session_key: str | None = None
    ) -> list[TaskExecutionAttempt]:
        with self._connect() as conn:
            if session_key is None:
                rows = conn.execute(
                    """
                    SELECT * FROM task_execution_attempts
                    WHERE status IN ('pending', 'running') ORDER BY created_at ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM task_execution_attempts
                    WHERE session_key = ? AND status IN ('pending', 'running')
                    ORDER BY created_at ASC
                    """,
                    (session_key,),
                ).fetchall()
        return [row_to_execution_attempt(row) for row in rows]

    def renew_execution_attempt_lease(
        self,
        *,
        attempt_id: str,
        owner_instance_id: str,
        now: datetime,
        lease_expires_at: str,
    ) -> TaskExecutionAttempt:
        timestamp = _datetime_to_iso(now)
        normalized_lease_expires_at = normalize_execution_lease_timestamp(
            lease_expires_at
        )
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE task_execution_attempts
                    SET lease_expires_at = ?, updated_at = ?
                    WHERE attempt_id = ? AND owner_instance_id = ?
                      AND status IN ('pending', 'running', 'waiting_authorization')
                      AND lease_expires_at > ?
                    """,
                    (
                        normalized_lease_expires_at,
                        timestamp,
                        attempt_id,
                        owner_instance_id,
                        timestamp,
                    ),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution attempt lease conflict")
                attempt = self._require_execution_attempt(conn, attempt_id)
                conn.commit()
                return attempt
            except Exception:
                conn.rollback()
                raise

    def list_execution_events(self, attempt_id: str) -> list[TaskExecutionEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_execution_events WHERE attempt_id = ?
                ORDER BY sequence_no ASC
                """,
                (attempt_id,),
            ).fetchall()
        return [row_to_execution_event(row) for row in rows]

    def start_execution_attempt(
        self, *, attempt_id: str, owner_instance_id: str, now: datetime
    ) -> TaskExecutionAttempt:
        timestamp = _datetime_to_iso(now)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE task_execution_attempts
                    SET status = 'running', started_at = ?, updated_at = ?
                    WHERE attempt_id = ? AND owner_instance_id = ? AND status = 'pending'
                      AND lease_expires_at > ?
                    """,
                    (timestamp, timestamp, attempt_id, owner_instance_id, timestamp),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution attempt start conflict")
                attempt = self._require_execution_attempt(conn, attempt_id)
                cur = conn.execute(
                    """
                    UPDATE task_steps
                    SET status = 'in_progress', started_at = COALESCE(started_at, ?)
                    WHERE step_id = ? AND task_id = ? AND status = 'pending'
                    """,
                    (timestamp, attempt.step_id, attempt.task_id),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution step start conflict")
                self._after_execution_mutation("start_after_step_update")
                self._append_execution_event_in_transaction(
                    conn,
                    attempt_id=attempt_id,
                    event_type="attempt_started",
                    created_at=timestamp,
                )
                conn.commit()
                return self._require_execution_attempt(conn, attempt_id)
            except Exception:
                conn.rollback()
                raise

    def append_execution_event(
        self,
        *,
        attempt_id: str,
        owner_instance_id: str,
        now: datetime,
        event_type: ExecutionEventType,
        tool_name: str = "",
        tool_call_id: str = "",
        source_turn_id: int | None = None,
        tool_risk: str = "",
        tool_capabilities: tuple[str, ...] = (),
        counts_as_work: bool = False,
        invoker_reached: bool = False,
        invoker_succeeded: bool = False,
        execution_status: str = "",
        result_ok: bool | None = None,
        error_code: str = "",
        arguments_hash: str = "",
        result_preview: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TaskExecutionEvent:
        timestamp = _datetime_to_iso(now)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE task_execution_attempts SET updated_at = ?
                    WHERE attempt_id = ? AND owner_instance_id = ? AND status = 'running'
                      AND lease_expires_at > ?
                    """,
                    (timestamp, attempt_id, owner_instance_id, timestamp),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution event conflict")
                event = self._append_execution_event_in_transaction(
                    conn,
                    attempt_id=attempt_id,
                    event_type=event_type,
                    created_at=timestamp,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    source_turn_id=source_turn_id,
                    tool_risk=tool_risk,
                    tool_capabilities=tool_capabilities,
                    counts_as_work=counts_as_work,
                    invoker_reached=invoker_reached,
                    invoker_succeeded=invoker_succeeded,
                    execution_status=execution_status,
                    result_ok=result_ok,
                    error_code=error_code,
                    arguments_hash=arguments_hash,
                    result_preview=result_preview,
                    metadata=metadata,
                )
                conn.commit()
                return event
            except Exception:
                conn.rollback()
                raise

    def finalize_execution_attempt(
        self,
        *,
        attempt_id: str,
        owner_instance_id: str,
        now: datetime,
        success: bool,
        result_summary: str = "",
        error_code: str = "",
        terminal_reason: str = "",
    ) -> TaskExecutionAttempt:
        timestamp = _datetime_to_iso(now)
        status = "succeeded" if success else "failed"
        step_status = "completed" if success else "failed"
        event_type: ExecutionEventType = (
            "attempt_succeeded" if success else "attempt_failed"
        )
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE task_execution_attempts
                    SET status = ?, result_summary = ?, error_code = ?,
                        terminal_reason = ?, updated_at = ?, finished_at = ?
                    WHERE attempt_id = ? AND owner_instance_id = ? AND status = 'running'
                      AND lease_expires_at > ?
                    """,
                    (
                        status,
                        result_summary,
                        error_code,
                        terminal_reason,
                        timestamp,
                        timestamp,
                        attempt_id,
                        owner_instance_id,
                        timestamp,
                    ),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution attempt finalize conflict")
                attempt = self._require_execution_attempt(conn, attempt_id)
                cur = conn.execute(
                    """
                    UPDATE task_steps
                    SET status = ?, result_summary = ?, completed_at = ?
                    WHERE step_id = ? AND task_id = ? AND status = 'in_progress'
                    """,
                    (
                        step_status,
                        result_summary,
                        timestamp,
                        attempt.step_id,
                        attempt.task_id,
                    ),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution step finalize conflict")
                if success and self._task_steps_are_complete(conn, attempt.task_id):
                    conn.execute(
                        """
                        UPDATE task_plans
                        SET status = 'completed', updated_at = ?, completed_at = ?
                        WHERE task_id = ? AND status = 'active'
                        """,
                        (timestamp, timestamp, attempt.task_id),
                    )
                    self._after_execution_mutation("finalize_after_plan_completion")
                self._append_execution_event_in_transaction(
                    conn,
                    attempt_id=attempt_id,
                    event_type=event_type,
                    created_at=timestamp,
                    error_code=error_code,
                    result_preview=result_summary,
                )
                conn.commit()
                return self._require_execution_attempt(conn, attempt_id)
            except Exception:
                conn.rollback()
                raise

    def block_execution_attempt(
        self,
        *,
        attempt_id: str,
        owner_instance_id: str,
        now: datetime,
        terminal_reason: str,
        error_code: str = "",
    ) -> TaskExecutionAttempt:
        timestamp = _datetime_to_iso(now)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE task_execution_attempts
                    SET status = 'blocked', terminal_reason = ?, error_code = ?,
                        updated_at = ?, finished_at = ?
                    WHERE attempt_id = ? AND owner_instance_id = ?
                      AND status IN ('pending', 'running') AND lease_expires_at > ?
                    """,
                    (
                        terminal_reason,
                        error_code,
                        timestamp,
                        timestamp,
                        attempt_id,
                        owner_instance_id,
                        timestamp,
                    ),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution attempt block conflict")
                self._after_execution_mutation("block_after_attempt_update")
                attempt = self._require_execution_attempt(conn, attempt_id)
                self._reset_execution_step(conn, attempt.step_id, attempt.task_id)
                self._after_execution_mutation("block_after_step_reset")
                self._append_execution_event_in_transaction(
                    conn,
                    attempt_id=attempt_id,
                    event_type="attempt_blocked",
                    created_at=timestamp,
                    error_code=error_code,
                    result_preview=terminal_reason,
                )
                conn.commit()
                return self._require_execution_attempt(conn, attempt_id)
            except Exception:
                conn.rollback()
                raise

    def defer_execution_attempt(
        self,
        *,
        attempt_id: str,
        owner_instance_id: str,
        now: datetime,
        terminal_reason: str = "",
    ) -> TaskExecutionAttempt:
        timestamp = _datetime_to_iso(now)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE task_execution_attempts
                    SET status = 'waiting_authorization', terminal_reason = ?,
                        execution_mode = 'authorization_required', updated_at = ?
                    WHERE attempt_id = ? AND owner_instance_id = ?
                      AND status IN ('pending', 'running') AND lease_expires_at > ?
                    """,
                    (terminal_reason, timestamp, attempt_id, owner_instance_id, timestamp),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution attempt defer conflict")
                attempt = self._require_execution_attempt(conn, attempt_id)
                self._reset_execution_step(conn, attempt.step_id, attempt.task_id)
                self._append_execution_event_in_transaction(
                    conn,
                    attempt_id=attempt_id,
                    event_type="authorization_deferred",
                    created_at=timestamp,
                    result_preview=terminal_reason,
                )
                conn.commit()
                return self._require_execution_attempt(conn, attempt_id)
            except Exception:
                conn.rollback()
                raise

    def abort_execution_attempt(
        self, *, attempt_id: str, terminal_reason: str = ""
    ) -> TaskExecutionAttempt:
        timestamp = utc_now_iso()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE task_execution_attempts
                    SET status = 'cancelled', terminal_reason = ?, updated_at = ?,
                        finished_at = ?
                    WHERE attempt_id = ?
                      AND status IN ('pending', 'running', 'waiting_authorization')
                    """,
                    (terminal_reason, timestamp, timestamp, attempt_id),
                )
                if cur.rowcount != 1:
                    raise ExecutionAttemptConflictError("execution attempt abort conflict")
                attempt = self._require_execution_attempt(conn, attempt_id)
                self._reset_execution_step(conn, attempt.step_id, attempt.task_id)
                self._append_execution_event_in_transaction(
                    conn,
                    attempt_id=attempt_id,
                    event_type="attempt_cancelled",
                    created_at=timestamp,
                    result_preview=terminal_reason,
                )
                conn.commit()
                return self._require_execution_attempt(conn, attempt_id)
            except Exception:
                conn.rollback()
                raise

    def reconcile_execution_attempts(
        self,
        *,
        now: datetime,
        runtime_instance_id: str,
        session_key: str | None = None,
    ) -> list[ReconciledExecutionAttempt]:
        timestamp = _datetime_to_iso(now)
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                query = """
                    SELECT * FROM task_execution_attempts
                    WHERE status IN ('pending', 'running')
                      AND (owner_instance_id != ? OR lease_expires_at <= ?)
                """
                params: tuple[object, ...] = (runtime_instance_id, timestamp)
                if session_key is not None:
                    query += " AND session_key = ?"
                    params = (runtime_instance_id, timestamp, session_key)
                rows = conn.execute(query + " ORDER BY created_at ASC", params).fetchall()
                reconciled: list[ReconciledExecutionAttempt] = []
                for row in rows:
                    attempt_id = str(row["attempt_id"])
                    previous_status = row_to_execution_attempt(row).status
                    if row["owner_instance_id"] != runtime_instance_id:
                        reason = (
                            "dispatch_interrupted"
                            if previous_status == "pending"
                            else "runtime_restarted_outcome_unknown"
                        )
                    else:
                        reason = "lease_expired_outcome_unknown"
                    cur = conn.execute(
                        """
                        UPDATE task_execution_attempts
                        SET status = 'blocked', terminal_reason = ?, updated_at = ?,
                            finished_at = ?
                        WHERE attempt_id = ? AND status IN ('pending', 'running')
                          AND (owner_instance_id != ? OR lease_expires_at <= ?)
                        """,
                        (
                            reason,
                            timestamp,
                            timestamp,
                            attempt_id,
                            runtime_instance_id,
                            timestamp,
                        ),
                    )
                    if cur.rowcount != 1:
                        continue
                    step_reset = False
                    if previous_status == "running":
                        step_reset = (
                            conn.execute(
                            """
                            UPDATE task_steps SET status = 'pending', started_at = NULL,
                                completed_at = NULL
                            WHERE step_id = ? AND task_id = ? AND status = 'in_progress'
                            """,
                            (row["step_id"], row["task_id"]),
                            ).rowcount
                            == 1
                        )
                    self._append_execution_event_in_transaction(
                        conn,
                        attempt_id=attempt_id,
                        event_type="recovery_reconciled",
                        created_at=timestamp,
                        result_preview=reason,
                    )
                    reconciled.append(
                        ReconciledExecutionAttempt(
                            attempt=self._require_execution_attempt(conn, attempt_id),
                            previous_status=previous_status,
                            reason=reason,
                            step_reset=step_reset,
                        )
                    )
                conn.commit()
                return reconciled
            except Exception:
                conn.rollback()
                raise

    def _after_execution_mutation(self, point: str) -> None:
        del point

    @staticmethod
    def _normalize_persisted_execution_lease_timestamps(
        conn: sqlite3.Connection,
    ) -> None:
        rows = conn.execute(
            "SELECT attempt_id, lease_expires_at FROM task_execution_attempts"
        ).fetchall()
        for row in rows:
            normalized = normalize_execution_lease_timestamp(
                str(row["lease_expires_at"])
            )
            if normalized != row["lease_expires_at"]:
                conn.execute(
                    """
                    UPDATE task_execution_attempts SET lease_expires_at = ?
                    WHERE attempt_id = ?
                    """,
                    (normalized, row["attempt_id"]),
                )

    def _append_execution_event_in_transaction(
        self,
        conn: sqlite3.Connection,
        *,
        attempt_id: str,
        event_type: ExecutionEventType,
        created_at: str,
        tool_name: str = "",
        tool_call_id: str = "",
        source_turn_id: int | None = None,
        tool_risk: str = "",
        tool_capabilities: tuple[str, ...] = (),
        counts_as_work: bool = False,
        invoker_reached: bool = False,
        invoker_succeeded: bool = False,
        execution_status: str = "",
        result_ok: bool | None = None,
        error_code: str = "",
        arguments_hash: str = "",
        result_preview: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TaskExecutionEvent:
        sequence_no = int(
            conn.execute(
                """
                SELECT COALESCE(MAX(sequence_no), 0) + 1
                FROM task_execution_events WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()[0]
        )
        event_id = new_execution_event_id()
        conn.execute(
            """
            INSERT INTO task_execution_events (
                event_id, attempt_id, sequence_no, event_type, tool_name,
                tool_call_id, source_turn_id, tool_risk, tool_capabilities_json,
                counts_as_work, invoker_reached, invoker_succeeded,
                execution_status, result_ok, error_code, arguments_hash,
                result_preview, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                attempt_id,
                sequence_no,
                event_type,
                tool_name,
                tool_call_id,
                source_turn_id,
                tool_risk,
                _execution_json_dump(list(tool_capabilities)),
                int(counts_as_work),
                int(invoker_reached),
                int(invoker_succeeded),
                execution_status,
                None if result_ok is None else int(result_ok),
                error_code,
                arguments_hash,
                result_preview,
                created_at,
                _execution_json_dump(metadata or {}),
            ),
        )
        row = conn.execute(
            "SELECT * FROM task_execution_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("execution event insert did not persist")
        return row_to_execution_event(row)

    def _claim_conflict_result(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        session_key: str,
        request_id: str,
    ) -> AttemptClaimResult:
        replay = conn.execute(
            """
            SELECT * FROM task_execution_attempts
            WHERE session_key = ? AND request_id = ?
            """,
            (session_key, request_id),
        ).fetchone()
        if replay is not None:
            return AttemptClaimResult(
                attempt=row_to_execution_attempt(replay), disposition="request_replay"
            )
        active = self._fetch_active_execution_attempt(conn, task_id)
        if active is not None:
            return AttemptClaimResult(
                attempt=row_to_execution_attempt(active), disposition="active_conflict"
            )
        raise ExecutionAttemptConflictError("execution attempt claim conflict")

    @staticmethod
    def _fetch_active_execution_attempt(
        conn: sqlite3.Connection, task_id: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT * FROM task_execution_attempts
            WHERE task_id = ? AND status IN ('pending', 'running', 'waiting_authorization')
            ORDER BY created_at DESC LIMIT 1
            """,
            (task_id,),
        ).fetchone()

    def _require_execution_attempt(
        self, conn: sqlite3.Connection, attempt_id: str
    ) -> TaskExecutionAttempt:
        row = conn.execute(
            "SELECT * FROM task_execution_attempts WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        if row is None:
            raise TaskExecutionAttemptNotFoundError(attempt_id)
        return row_to_execution_attempt(row)

    @staticmethod
    def _task_steps_are_complete(conn: sqlite3.Connection, task_id: str) -> bool:
        unfinished = conn.execute(
            """
            SELECT 1 FROM task_steps
            WHERE task_id = ? AND status NOT IN ('completed', 'skipped') LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        return unfinished is None

    @staticmethod
    def _reset_execution_step(
        conn: sqlite3.Connection, step_id: str, task_id: str
    ) -> None:
        conn.execute(
            """
            UPDATE task_steps
            SET status = 'pending', started_at = NULL, completed_at = NULL
            WHERE step_id = ? AND task_id = ?
            """,
            (step_id, task_id),
        )

    def _require_no_active_execution_attempt(
        self, conn: sqlite3.Connection, task_id: str
    ) -> None:
        if self._fetch_active_execution_attempt(conn, task_id) is not None:
            raise ActiveExecutionAttemptExistsError(
                "abort the active execution attempt first"
            )

    @staticmethod
    def _has_active_execution_attempt_for_session(
        conn: sqlite3.Connection, session_key: str
    ) -> bool:
        row = conn.execute(
            """
            SELECT 1 FROM task_execution_attempts AS attempts
            JOIN task_plans AS plans ON plans.task_id = attempts.task_id
            WHERE plans.session_key = ? AND plans.status = 'active'
              AND attempts.status IN ('pending', 'running', 'waiting_authorization')
            LIMIT 1
            """,
            (session_key,),
        ).fetchone()
        return row is not None

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _fetch_steps(
        self,
        conn: sqlite3.Connection,
        task_id: str,
    ) -> list[TaskStep]:
        rows = conn.execute(
            """
            SELECT * FROM task_steps
            WHERE task_id = ?
            ORDER BY step_index ASC
            """,
            (task_id,),
        ).fetchall()
        return [_row_to_step(row) for row in rows]


def _step_selector_where(
    *,
    task_id: str,
    step_id: str | None,
    step_index: int | None,
) -> tuple[str, tuple[object, ...]]:
    if step_id and step_index is not None:
        return (
            "task_id = ? AND step_id = ? AND step_index = ?",
            (task_id, step_id, step_index),
        )
    if step_id:
        return "task_id = ? AND step_id = ?", (task_id, step_id)
    if step_index is not None:
        return "task_id = ? AND step_index = ?", (task_id, step_index)
    raise TaskStepNotFoundError("step_id or step_index is required")


def _row_to_plan(row: sqlite3.Row, steps: list[TaskStep]) -> TaskPlan:
    return TaskPlan(
        task_id=str(row["task_id"]),
        session_key=str(row["session_key"]),
        title=str(row["title"]),
        status=validate_task_status(str(row["status"])),
        steps=steps,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        completed_at=row["completed_at"],
        source_turn_id=row["source_turn_id"],
        terminal_reason=str(row["terminal_reason"] or ""),
        metadata=_json_loads_dict(row["metadata_json"]),
    )


def _row_to_step(row: sqlite3.Row) -> TaskStep:
    return TaskStep(
        step_id=str(row["step_id"]),
        task_id=str(row["task_id"]),
        index=int(row["step_index"]),
        title=str(row["title"]),
        status=validate_step_status(str(row["status"])),
        tool_names=_json_loads_list(row["tool_names_json"]),
        result_summary=str(row["result_summary"] or ""),
        source_turn_id=row["source_turn_id"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        metadata=_json_loads_dict(row["metadata_json"]),
    )


def _json_dump(payload: object) -> str:
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


def _is_active_unique_error(exc: sqlite3.IntegrityError) -> bool:
    message = str(exc)
    return (
        "ux_task_plans_one_active_per_session" in message
        or "task_plans.session_key" in message
        or "UNIQUE constraint failed" in message
    )


def _datetime_to_iso(value: datetime) -> str:
    return normalize_execution_comparison_timestamp(value)
