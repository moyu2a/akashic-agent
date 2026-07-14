from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

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
