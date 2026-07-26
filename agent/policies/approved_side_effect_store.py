from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4

SideEffectStatus = Literal[
    "payload_recorded",
    "preview_ready",
    "executed",
    "execution_failed",
    "rolled_back",
    "rollback_failed",
]

_CREATE_SIDE_EFFECTS_SQL = """
CREATE TABLE IF NOT EXISTS approved_side_effects (
    approval_request_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    session_key TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    approval_scope TEXT NOT NULL,
    args_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'payload_recorded', 'preview_ready', 'executed',
            'execution_failed', 'rolled_back', 'rollback_failed'
        )
    ),
    payload_ref TEXT NOT NULL DEFAULT '',
    preview_id TEXT NOT NULL DEFAULT '',
    target_path_hash TEXT NOT NULL DEFAULT '',
    before_hash TEXT NOT NULL DEFAULT '',
    after_hash TEXT NOT NULL DEFAULT '',
    diff_ref TEXT NOT NULL DEFAULT '',
    diff_truncated INTEGER NOT NULL DEFAULT 0,
    rollback_id TEXT NOT NULL DEFAULT '',
    execution_status TEXT NOT NULL DEFAULT '',
    rollback_status TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_AUDIT_SQL = """
CREATE TABLE IF NOT EXISTS approved_side_effect_audit_events (
    event_id TEXT PRIMARY KEY,
    approval_request_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class ApprovedSideEffectRecord:
    approval_request_id: str
    request_id: str
    session_key: str
    tool_name: str
    approval_scope: str
    args_hash: str
    status: SideEffectStatus
    payload_ref: str
    preview_id: str = ""
    target_path_hash: str = ""
    before_hash: str = ""
    after_hash: str = ""
    diff_ref: str = ""
    diff_truncated: bool = False
    rollback_id: str = ""
    execution_status: str = ""
    rollback_status: str = ""


@dataclass(frozen=True)
class ApprovedSideEffectAuditEvent:
    event_id: str
    approval_request_id: str
    event_type: str
    actor: str
    created_at: str


class ApprovedSideEffectStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @staticmethod
    def db_path_from_workspace(workspace: str | Path) -> Path:
        return Path(workspace).expanduser().resolve() / "tool_side_effects" / "side_effects.db"

    def record_payload(
        self,
        *,
        approval_request_id: str,
        request_id: str,
        session_key: str,
        tool_name: str,
        approval_scope: str,
        args_hash: str,
        payload_ref: str,
        actor: str,
        now: datetime,
    ) -> ApprovedSideEffectRecord:
        with self._immediate_transaction() as conn:
            existing = self._select(conn, approval_request_id)
            if existing is not None:
                return _record_from_row(existing)
            now_iso = _to_iso(now)
            conn.execute(
                """
                INSERT INTO approved_side_effects (
                    approval_request_id, request_id, session_key, tool_name,
                    approval_scope, args_hash, status, payload_ref, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'payload_recorded', ?, ?, ?)
                """,
                (
                    approval_request_id,
                    request_id,
                    session_key,
                    tool_name,
                    approval_scope or "tool_call",
                    args_hash,
                    payload_ref,
                    now_iso,
                    now_iso,
                ),
            )
            self._append_event(
                conn,
                approval_request_id=approval_request_id,
                event_type="payload_recorded",
                actor=actor,
                created_at=now_iso,
            )
            return _record_from_row(self._select_required(conn, approval_request_id))

    def record_preview(
        self,
        *,
        approval_request_id: str,
        preview_id: str,
        target_path_hash: str,
        before_hash: str,
        after_hash: str,
        diff_ref: str,
        diff_truncated: bool,
        actor: str,
        now: datetime,
    ) -> ApprovedSideEffectRecord:
        return self._update(
            approval_request_id=approval_request_id,
            status="preview_ready",
            actor=actor,
            now=now,
            assignments={
                "preview_id": preview_id,
                "target_path_hash": target_path_hash,
                "before_hash": before_hash,
                "after_hash": after_hash,
                "diff_ref": diff_ref,
                "diff_truncated": int(diff_truncated),
            },
        )

    def mark_executed(
        self,
        *,
        approval_request_id: str,
        rollback_id: str,
        execution_status: str,
        actor: str,
        now: datetime,
    ) -> ApprovedSideEffectRecord:
        return self._update(
            approval_request_id=approval_request_id,
            status="executed",
            actor=actor,
            now=now,
            assignments={
                "rollback_id": rollback_id,
                "execution_status": execution_status,
            },
        )

    def mark_execution_failed(
        self,
        *,
        approval_request_id: str,
        execution_status: str,
        actor: str,
        now: datetime,
    ) -> ApprovedSideEffectRecord:
        return self._update(
            approval_request_id=approval_request_id,
            status="execution_failed",
            actor=actor,
            now=now,
            assignments={"execution_status": execution_status},
        )

    def mark_rolled_back(
        self,
        *,
        approval_request_id: str,
        rollback_status: str,
        actor: str,
        now: datetime,
    ) -> ApprovedSideEffectRecord:
        return self._update(
            approval_request_id=approval_request_id,
            status="rolled_back",
            actor=actor,
            now=now,
            assignments={"rollback_status": rollback_status},
        )

    def mark_rollback_failed(
        self,
        *,
        approval_request_id: str,
        rollback_status: str,
        actor: str,
        now: datetime,
    ) -> ApprovedSideEffectRecord:
        return self._update(
            approval_request_id=approval_request_id,
            status="rollback_failed",
            actor=actor,
            now=now,
            assignments={"rollback_status": rollback_status},
        )

    def get_by_approval_id(
        self, approval_request_id: str
    ) -> ApprovedSideEffectRecord | None:
        with self._connect() as conn:
            row = self._select(conn, approval_request_id)
            return _record_from_row(row) if row is not None else None

    def list_audit_events(
        self, approval_request_id: str
    ) -> list[ApprovedSideEffectAuditEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM approved_side_effect_audit_events
                WHERE approval_request_id = ?
                ORDER BY created_at ASC, event_id ASC
                """,
                (approval_request_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_SIDE_EFFECTS_SQL)
            conn.execute(_CREATE_AUDIT_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _immediate_transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _update(
        self,
        *,
        approval_request_id: str,
        status: SideEffectStatus,
        actor: str,
        now: datetime,
        assignments: dict[str, object],
    ) -> ApprovedSideEffectRecord:
        with self._immediate_transaction() as conn:
            self._select_required(conn, approval_request_id)
            now_iso = _to_iso(now)
            values = dict(assignments)
            values["status"] = status
            values["updated_at"] = now_iso
            set_clause = ", ".join(f"{key} = ?" for key in values)
            conn.execute(
                f"""
                UPDATE approved_side_effects
                SET {set_clause}
                WHERE approval_request_id = ?
                """,
                (*values.values(), approval_request_id),
            )
            self._append_event(
                conn,
                approval_request_id=approval_request_id,
                event_type=status,
                actor=actor,
                created_at=now_iso,
            )
            return _record_from_row(self._select_required(conn, approval_request_id))

    def _select(
        self, conn: sqlite3.Connection, approval_request_id: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT * FROM approved_side_effects
            WHERE approval_request_id = ?
            """,
            (approval_request_id,),
        ).fetchone()

    def _select_required(
        self, conn: sqlite3.Connection, approval_request_id: str
    ) -> sqlite3.Row:
        row = self._select(conn, approval_request_id)
        if row is None:
            raise KeyError(approval_request_id)
        return row

    def _append_event(
        self,
        conn: sqlite3.Connection,
        *,
        approval_request_id: str,
        event_type: str,
        actor: str,
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO approved_side_effect_audit_events (
                event_id, approval_request_id, event_type, actor, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (uuid4().hex, approval_request_id, event_type, actor, created_at),
        )


def _record_from_row(row: sqlite3.Row) -> ApprovedSideEffectRecord:
    return ApprovedSideEffectRecord(
        approval_request_id=str(row["approval_request_id"]),
        request_id=str(row["request_id"]),
        session_key=str(row["session_key"]),
        tool_name=str(row["tool_name"]),
        approval_scope=str(row["approval_scope"] or "tool_call"),
        args_hash=str(row["args_hash"]),
        status=row["status"],
        payload_ref=str(row["payload_ref"]),
        preview_id=str(row["preview_id"]),
        target_path_hash=str(row["target_path_hash"]),
        before_hash=str(row["before_hash"]),
        after_hash=str(row["after_hash"]),
        diff_ref=str(row["diff_ref"]),
        diff_truncated=bool(row["diff_truncated"]),
        rollback_id=str(row["rollback_id"]),
        execution_status=str(row["execution_status"]),
        rollback_status=str(row["rollback_status"]),
    )


def _event_from_row(row: sqlite3.Row) -> ApprovedSideEffectAuditEvent:
    return ApprovedSideEffectAuditEvent(
        event_id=str(row["event_id"]),
        approval_request_id=str(row["approval_request_id"]),
        event_type=str(row["event_type"]),
        actor=str(row["actor"]),
        created_at=str(row["created_at"]),
    )


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("side-effect timestamps must be timezone-aware")
    return value.isoformat()
