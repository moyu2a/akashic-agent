from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class SessionStore:
    """SQLite-backed store for session metadata and messages."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._has_fts = False
        self._conn.execute("PRAGMA busy_timeout = 3000")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    key               TEXT PRIMARY KEY,
                    created_at        TEXT NOT NULL,
                    updated_at        TEXT NOT NULL,
                    last_consolidated INTEGER NOT NULL DEFAULT 0,
                    metadata          TEXT
                )
                """
            )
            self._ensure_session_columns()
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id          TEXT PRIMARY KEY,
                    session_key TEXT NOT NULL,
                    seq         INTEGER NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT,
                    tool_chain  TEXT,
                    extra       TEXT,
                    ts          TEXT NOT NULL,
                    UNIQUE (session_key, seq)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    outbox_id TEXT PRIMARY KEY,
                    session_key TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_no INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT NOT NULL,
                    lease_expires_at TEXT,
                    worker_id TEXT,
                    last_error TEXT,
                    remote_message_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_outbox_status_available
                ON outbox(status, available_at, updated_at)
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_outbox_session_message
                ON outbox(session_key, message_id)
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS message_generations (
                    generation_id TEXT PRIMARY KEY,
                    session_key TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_streamed_offset INTEGER NOT NULL DEFAULT 0,
                    partial_content TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    aborted_at TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_message_generations_status
                ON message_generations(status, updated_at)
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turn_runs (
                    turn_run_id TEXT PRIMARY KEY,
                    session_key TEXT NOT NULL,
                    user_message_id TEXT,
                    assistant_message_id TEXT,
                    status TEXT NOT NULL,
                    current_step_id TEXT,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    lease_version INTEGER NOT NULL DEFAULT 0,
                    blocked_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_turn_runs_status_lease
                ON turn_runs(status, lease_expires_at, updated_at)
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_turn_runs_session
                ON turn_runs(session_key, updated_at)
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS react_steps (
                    step_id TEXT PRIMARY KEY,
                    turn_run_id TEXT NOT NULL,
                    step_no INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    model_input_json TEXT NOT NULL DEFAULT '[]',
                    assistant_tool_call_json TEXT,
                    tool_result_message_id TEXT,
                    assistant_message_id TEXT,
                    error_code TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(turn_run_id, step_no),
                    FOREIGN KEY(turn_run_id) REFERENCES turn_runs(turn_run_id) ON DELETE CASCADE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_invocation_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    turn_run_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    arguments_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    recovery_ref TEXT,
                    pollable INTEGER NOT NULL DEFAULT 0,
                    idempotent INTEGER NOT NULL DEFAULT 0,
                    side_effect INTEGER NOT NULL DEFAULT 1,
                    result_message_id TEXT,
                    result_preview TEXT NOT NULL DEFAULT '',
                    error_code TEXT NOT NULL DEFAULT '',
                    owner_instance_id TEXT,
                    lease_expires_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(turn_run_id, tool_call_id),
                    FOREIGN KEY(turn_run_id) REFERENCES turn_runs(turn_run_id) ON DELETE CASCADE,
                    FOREIGN KEY(step_id) REFERENCES react_steps(step_id) ON DELETE CASCADE
                )
                """
            )
            self._ensure_next_seq_values()
            self._ensure_fts()
            self._conn.commit()

    def _ensure_session_columns(self) -> None:
        rows = self._conn.execute("PRAGMA table_info(sessions)").fetchall()
        existing = {str(row["name"]) for row in rows}
        if "last_user_at" not in existing:
            self._conn.execute(
                "ALTER TABLE sessions ADD COLUMN last_user_at TEXT"
            )
        if "last_proactive_at" not in existing:
            self._conn.execute(
                "ALTER TABLE sessions ADD COLUMN last_proactive_at TEXT"
            )
        if "next_seq" not in existing:
            self._conn.execute(
                "ALTER TABLE sessions ADD COLUMN next_seq INTEGER NOT NULL DEFAULT 0"
            )

    def _ensure_next_seq_values(self) -> None:
        rows = self._conn.execute(
            "SELECT key, next_seq FROM sessions"
        ).fetchall()
        for row in rows:
            session_key = str(row["key"])
            current = int(row["next_seq"] or 0)
            seq_row = self._conn.execute(
                "SELECT COALESCE(MAX(seq) + 1, 0) AS next_seq FROM messages WHERE session_key = ?",
                (session_key,),
            ).fetchone()
            required = int((seq_row["next_seq"] if seq_row else 0) or 0)
            if current < required:
                self._conn.execute(
                    "UPDATE sessions SET next_seq = ? WHERE key = ?",
                    (required, session_key),
                )

    def _ensure_fts(self) -> None:
        try:
            # Migrate to trigram tokenizer if the table exists without it.
            # trigram supports CJK substring matching; the old unicode61 default does not.
            existing = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages_fts'"
            ).fetchone()
            if existing:
                try:
                    cfg = dict(
                        self._conn.execute("SELECT * FROM messages_fts_config").fetchall()
                    )
                    is_trigram = "trigram" in cfg.get("tokenize", "")
                except sqlite3.OperationalError:
                    is_trigram = False
                if not is_trigram:
                    self._conn.execute("DROP TABLE IF EXISTS messages_fts")
                    for trig in ("messages_ai", "messages_ad", "messages_au"):
                        self._conn.execute(f"DROP TRIGGER IF EXISTS {trig}")

            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content,
                    content='messages',
                    content_rowid='rowid',
                    tokenize='trigram'
                )
                """
            )
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
                END
                """
            )
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content)
                    VALUES('delete', old.rowid, old.content);
                END
                """
            )
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content)
                    VALUES('delete', old.rowid, old.content);
                    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
                END
                """
            )
            # Rebuild index so existing messages are covered by trigram.
            self._conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
            self._conn.commit()
            self._has_fts = True
        except sqlite3.OperationalError:
            self._has_fts = False

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _now(self, value: datetime | None = None) -> str:
        return (value or datetime.now().astimezone()).isoformat()

    def _row_to_turn_run(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "turn_run_id": row["turn_run_id"],
            "session_key": row["session_key"],
            "user_message_id": row["user_message_id"],
            "assistant_message_id": row["assistant_message_id"],
            "status": row["status"],
            "current_step_id": row["current_step_id"],
            "lease_owner": row["lease_owner"],
            "lease_expires_at": row["lease_expires_at"],
            "lease_version": int(row["lease_version"] or 0),
            "blocked_reason": row["blocked_reason"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_react_step(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "step_id": row["step_id"],
            "turn_run_id": row["turn_run_id"],
            "step_no": int(row["step_no"] or 0),
            "status": row["status"],
            "model_input_json": row["model_input_json"],
            "assistant_tool_call_json": row["assistant_tool_call_json"],
            "tool_result_message_id": row["tool_result_message_id"],
            "assistant_message_id": row["assistant_message_id"],
            "error_code": row["error_code"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_tool_invocation_attempt(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "attempt_id": row["attempt_id"],
            "turn_run_id": row["turn_run_id"],
            "step_id": row["step_id"],
            "tool_call_id": row["tool_call_id"],
            "tool_name": row["tool_name"],
            "arguments_json": row["arguments_json"],
            "arguments_hash": row["arguments_hash"],
            "status": row["status"],
            "recovery_ref": row["recovery_ref"],
            "pollable": bool(row["pollable"]),
            "idempotent": bool(row["idempotent"]),
            "side_effect": bool(row["side_effect"]),
            "result_message_id": row["result_message_id"],
            "result_preview": row["result_preview"],
            "error_code": row["error_code"],
            "owner_instance_id": row["owner_instance_id"],
            "lease_expires_at": row["lease_expires_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def session_exists(self, key: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM sessions WHERE key = ?", (key,)
            ).fetchone()
        return row is not None

    def upsert_session(
        self,
        key: str,
        *,
        created_at: str,
        updated_at: str,
        last_consolidated: int,
        metadata: dict[str, Any],
    ) -> None:
        payload = json.dumps(metadata or {}, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sessions (key, created_at, updated_at, last_consolidated, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    last_consolidated = excluded.last_consolidated,
                    metadata = excluded.metadata
                """,
                (key, created_at, updated_at, int(last_consolidated), payload),
            )
            self._conn.commit()

    def update_last_consolidated(self, key: str, last_consolidated: int) -> None:
        now = datetime.now().astimezone().isoformat()
        with self._lock:
            self._conn.execute(
                """
                UPDATE sessions
                SET last_consolidated = ?, updated_at = ?
                WHERE key = ?
                """,
                (int(last_consolidated), now, key),
            )
            self._conn.commit()

    def get_session_meta(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT key, created_at, updated_at, last_consolidated, metadata, last_user_at, last_proactive_at FROM sessions WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_consolidated": int(row["last_consolidated"] or 0),
            "metadata": json.loads(row["metadata"] or "{}"),
            "last_user_at": row["last_user_at"],
            "last_proactive_at": row["last_proactive_at"],
        }

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT key, created_at, updated_at, last_user_at, last_proactive_at
                FROM sessions
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [
            {
                "key": str(row["key"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "last_user_at": row["last_user_at"],
                "last_proactive_at": row["last_proactive_at"],
            }
            for row in rows
        ]

    def list_sessions_for_dashboard(
        self,
        *,
        q: str = "",
        channel: str = "",
        updated_from: str = "",
        updated_to: str = "",
        has_proactive: bool | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        safe_page = max(1, int(page))
        safe_page_size = max(1, min(int(page_size), 200))
        offset = (safe_page - 1) * safe_page_size
        safe_sort_by = sort_by if sort_by in {
            "updated_at",
            "created_at",
            "last_user_at",
            "last_proactive_at",
        } else "updated_at"
        safe_sort_order = "ASC" if str(sort_order).lower() == "asc" else "DESC"

        params: list[Any] = []
        where_parts: list[str] = []
        query = (q or "").strip()
        if query:
            where_parts.append("(s.key LIKE ? OR COALESCE(s.metadata, '') LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like])
        if channel:
            where_parts.append("s.key LIKE ?")
            params.append(f"{channel}:%")
        if updated_from:
            where_parts.append("s.updated_at >= ?")
            params.append(updated_from)
        if updated_to:
            where_parts.append("s.updated_at <= ?")
            params.append(updated_to)
        if has_proactive is True:
            where_parts.append("s.last_proactive_at IS NOT NULL")
        if has_proactive is False:
            where_parts.append("s.last_proactive_at IS NULL")

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        count_sql = f"""
            SELECT COUNT(1) AS c
            FROM sessions s
            {where_sql}
        """
        data_sql = f"""
            SELECT
                s.key,
                s.created_at,
                s.updated_at,
                s.last_consolidated,
                s.metadata,
                s.last_user_at,
                s.last_proactive_at,
                COALESCE(msg.message_count, 0) AS message_count
            FROM sessions s
            LEFT JOIN (
                SELECT session_key, COUNT(1) AS message_count
                FROM messages
                GROUP BY session_key
            ) msg ON msg.session_key = s.key
            {where_sql}
            ORDER BY s.{safe_sort_by} {safe_sort_order}, s.key ASC
            LIMIT ? OFFSET ?
        """
        with self._lock:
            count_row = self._conn.execute(count_sql, tuple(params)).fetchone()
            rows = self._conn.execute(
                data_sql,
                tuple([*params, safe_page_size, offset]),
            ).fetchall()
        total = int((count_row["c"] if count_row else 0) or 0)
        return [
            {
                "key": str(row["key"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "last_consolidated": int(row["last_consolidated"] or 0),
                "metadata": json.loads(row["metadata"] or "{}"),
                "last_user_at": row["last_user_at"],
                "last_proactive_at": row["last_proactive_at"],
                "message_count": int(row["message_count"] or 0),
            }
            for row in rows
        ], total

    def create_session(
        self,
        *,
        key: str,
        metadata: dict[str, Any] | None = None,
        last_consolidated: int = 0,
        last_user_at: str | None = None,
        last_proactive_at: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now().astimezone().isoformat()
        payload = json.dumps(metadata or {}, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sessions (
                    key,
                    created_at,
                    updated_at,
                    last_consolidated,
                    metadata,
                    last_user_at,
                    last_proactive_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    now,
                    now,
                    int(last_consolidated),
                    payload,
                    last_user_at,
                    last_proactive_at,
                ),
            )
            self._conn.commit()
        meta = self.get_session_meta(key)
        if meta is None:
            raise ValueError(f"session 创建失败: {key}")
        return meta

    def update_session(
        self,
        key: str,
        *,
        metadata: dict[str, Any] | None = None,
        last_consolidated: int | None = None,
        last_user_at: str | None = None,
        last_proactive_at: str | None = None,
    ) -> dict[str, Any] | None:
        set_parts = ["updated_at = ?"]
        params: list[Any] = [datetime.now().astimezone().isoformat()]
        if metadata is not None:
            set_parts.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))
        if last_consolidated is not None:
            set_parts.append("last_consolidated = ?")
            params.append(int(last_consolidated))
        if last_user_at is not None:
            set_parts.append("last_user_at = ?")
            params.append(last_user_at)
        if last_proactive_at is not None:
            set_parts.append("last_proactive_at = ?")
            params.append(last_proactive_at)
        params.append(key)
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE sessions SET {', '.join(set_parts)} WHERE key = ?",
                tuple(params),
            )
            self._conn.commit()
        if cur.rowcount <= 0:
            return None
        return self.get_session_meta(key)

    def delete_session(self, key: str, *, cascade: bool = False) -> bool:
        with self._lock:
            if not cascade:
                row = self._conn.execute(
                    "SELECT COUNT(1) AS c FROM messages WHERE session_key = ?",
                    (key,),
                ).fetchone()
                count = int((row["c"] if row else 0) or 0)
                if count > 0:
                    raise ValueError("session 下仍有 messages，需使用 cascade 删除")
            else:
                self._conn.execute(
                    "DELETE FROM messages WHERE session_key = ?",
                    (key,),
                )
            cur = self._conn.execute(
                "DELETE FROM sessions WHERE key = ?",
                (key,),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def delete_sessions_batch(self, keys: list[str], *, cascade: bool = False) -> int:
        clean_keys = [str(key).strip() for key in keys if str(key).strip()]
        if not clean_keys:
            return 0
        placeholders = ",".join("?" for _ in clean_keys)
        with self._lock:
            if not cascade:
                row = self._conn.execute(
                    f"""
                    SELECT COUNT(1) AS c
                    FROM messages
                    WHERE session_key IN ({placeholders})
                    """,
                    tuple(clean_keys),
                ).fetchone()
                count = int((row["c"] if row else 0) or 0)
                if count > 0:
                    raise ValueError("选中的 session 中仍有 messages，需使用 cascade 删除")
            else:
                self._conn.execute(
                    f"DELETE FROM messages WHERE session_key IN ({placeholders})",
                    tuple(clean_keys),
                )
            cur = self._conn.execute(
                f"DELETE FROM sessions WHERE key IN ({placeholders})",
                tuple(clean_keys),
            )
            self._conn.commit()
        return int(cur.rowcount or 0)

    def update_presence(
        self,
        key: str,
        *,
        last_user_at: str | None = None,
        last_proactive_at: str | None = None,
    ) -> None:
        now = datetime.now().astimezone().isoformat()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO sessions (
                    key,
                    created_at,
                    updated_at,
                    last_consolidated,
                    metadata,
                    last_user_at,
                    last_proactive_at
                )
                VALUES (?, ?, ?, 0, '{}', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    last_user_at = COALESCE(excluded.last_user_at, sessions.last_user_at),
                    last_proactive_at = COALESCE(excluded.last_proactive_at, sessions.last_proactive_at)
                """,
                (key, now, now, last_user_at, last_proactive_at),
            )
            self._conn.commit()

    def get_presence(self, key: str) -> dict[str, str | None] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT last_user_at, last_proactive_at
                FROM sessions
                WHERE key = ?
                """,
                (key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "last_user_at": row["last_user_at"],
            "last_proactive_at": row["last_proactive_at"],
        }

    def list_presence(self) -> dict[str, dict[str, str | None]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT key, last_user_at, last_proactive_at
                FROM sessions
                WHERE last_user_at IS NOT NULL OR last_proactive_at IS NOT NULL
                """
            ).fetchall()
        return {
            str(row["key"]): {
                "last_user_at": row["last_user_at"],
                "last_proactive_at": row["last_proactive_at"],
            }
            for row in rows
        }

    def most_recent_user_at(self) -> str | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT MAX(last_user_at) AS last_user_at
                FROM sessions
                WHERE last_user_at IS NOT NULL
                """
            ).fetchone()
        if row is None:
            return None
        return row["last_user_at"]

    def get_channel_metadata(self, channel: str) -> list[dict[str, Any]]:
        like_key = f"{channel}:%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, metadata FROM sessions WHERE key LIKE ?", (like_key,)
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            key = str(row["key"])
            chat_id = key.split(":", 1)[-1] if ":" in key else key
            results.append(
                {
                    "key": key,
                    "chat_id": chat_id,
                    "metadata": json.loads(row["metadata"] or "{}"),
                }
            )
        return results

    def count_messages(self, session_key: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(1) AS c FROM messages WHERE session_key = ?", (session_key,)
            ).fetchone()
        return int((row["c"] if row else 0) or 0)

    def next_seq(self, session_key: str) -> int:
        with self._lock:
            meta = self._conn.execute(
                "SELECT next_seq FROM sessions WHERE key = ?",
                (session_key,),
            ).fetchone()
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq) + 1, 0) AS next_seq FROM messages WHERE session_key = ?",
                (session_key,),
            ).fetchone()
        from_messages = int((row["next_seq"] if row else 0) or 0)
        if meta is None:
            return from_messages
        return max(int(meta["next_seq"] or 0), from_messages)

    def insert_message(
        self,
        session_key: str,
        *,
        role: str,
        content: str,
        ts: str,
        seq: int,
        tool_chain: Any | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message_id = f"{session_key}:{seq}"
        tool_chain_payload = (
            json.dumps(tool_chain, ensure_ascii=False) if tool_chain is not None else None
        )
        extra_payload = json.dumps(extra or {}, ensure_ascii=False)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO messages (id, session_key, seq, role, content, tool_chain, extra, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, session_key, seq, role, content, tool_chain_payload, extra_payload, ts),
            )
            self._conn.execute(
                """
                UPDATE sessions
                SET next_seq = CASE WHEN next_seq < ? THEN ? ELSE next_seq END
                WHERE key = ?
                """,
                (int(seq) + 1, int(seq) + 1, session_key),
            )
            self._conn.commit()
        row = {
            "id": message_id,
            "session_key": session_key,
            "seq": seq,
            "role": role,
            "content": content,
            "timestamp": ts,
        }
        if tool_chain is not None:
            row["tool_chain"] = tool_chain
        if extra:
            row.update(extra)
        return row

    def create_turn_run(
        self,
        *,
        turn_run_id: str,
        session_key: str,
        user_message_id: str | None,
        now: datetime,
    ) -> dict[str, Any]:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO turn_runs (
                    turn_run_id, session_key, user_message_id, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'running', ?, ?)
                ON CONFLICT(turn_run_id) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (turn_run_id, session_key, user_message_id, now_iso, now_iso),
            )
            self._conn.commit()
        turn = self.get_turn_run(turn_run_id)
        if turn is None:
            raise KeyError(turn_run_id)
        return turn

    def get_turn_run(self, turn_run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT turn_run_id, session_key, user_message_id,
                       assistant_message_id, status, current_step_id,
                       lease_owner, lease_expires_at, lease_version,
                       blocked_reason, created_at, updated_at
                FROM turn_runs
                WHERE turn_run_id = ?
                """,
                (turn_run_id,),
            ).fetchone()
        return self._row_to_turn_run(row) if row is not None else None

    def claim_turn_run_for_recovery(
        self,
        *,
        turn_run_id: str,
        worker_id: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> bool:
        now_iso = self._now(now)
        lease_iso = self._now(lease_expires_at)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                cur = self._conn.execute(
                    """
                    UPDATE turn_runs
                    SET lease_owner = ?,
                        lease_expires_at = ?,
                        lease_version = lease_version + 1,
                        updated_at = ?
                    WHERE turn_run_id = ?
                      AND status IN (
                          'running',
                          'model_retry_pending',
                          'tool_recovery_pending',
                          'final_pending'
                      )
                      AND (
                          lease_expires_at IS NULL
                          OR lease_expires_at <= ?
                          OR lease_owner = ?
                      )
                    """,
                    (
                        worker_id,
                        lease_iso,
                        now_iso,
                        turn_run_id,
                        now_iso,
                        worker_id,
                    ),
                )
                if cur.rowcount != 1:
                    self._conn.rollback()
                    return False
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def mark_turn_run_completed(
        self,
        *,
        turn_run_id: str,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE turn_runs
                SET status = 'completed',
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE turn_run_id = ?
                """,
                (now_iso, turn_run_id),
            )
            self._conn.commit()

    def mark_turn_run_blocked(
        self,
        *,
        turn_run_id: str,
        blocked_reason: str,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE turn_runs
                SET status = 'blocked',
                    blocked_reason = ?,
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE turn_run_id = ?
                """,
                (blocked_reason, now_iso, turn_run_id),
            )
            self._conn.commit()

    def list_recoverable_turn_runs(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        now_iso = self._now(now)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT turn_run_id, session_key, user_message_id,
                       assistant_message_id, status, current_step_id,
                       lease_owner, lease_expires_at, lease_version,
                       blocked_reason, created_at, updated_at
                FROM turn_runs
                WHERE status IN (
                    'running',
                    'model_retry_pending',
                    'tool_recovery_pending',
                    'final_pending'
                )
                  AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
                ORDER BY updated_at ASC, turn_run_id ASC
                LIMIT ?
                """,
                (now_iso, int(limit)),
            ).fetchall()
        return [self._row_to_turn_run(row) for row in rows]

    def create_react_step(
        self,
        *,
        step_id: str,
        turn_run_id: str,
        step_no: int,
        model_input_json: str,
        now: datetime,
    ) -> dict[str, Any]:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO react_steps (
                    step_id, turn_run_id, step_no, status,
                    model_input_json, created_at, updated_at
                )
                VALUES (?, ?, ?, 'model_pending', ?, ?, ?)
                ON CONFLICT(step_id) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (step_id, turn_run_id, int(step_no), model_input_json, now_iso, now_iso),
            )
            self._conn.execute(
                """
                UPDATE turn_runs
                SET current_step_id = ?,
                    updated_at = ?
                WHERE turn_run_id = ?
                """,
                (step_id, now_iso, turn_run_id),
            )
            self._conn.commit()
        step = self.get_react_step(step_id)
        if step is None:
            raise KeyError(step_id)
        return step

    def get_react_step(self, step_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT step_id, turn_run_id, step_no, status,
                       model_input_json, assistant_tool_call_json,
                       tool_result_message_id, assistant_message_id,
                       error_code, created_at, updated_at
                FROM react_steps
                WHERE step_id = ?
                """,
                (step_id,),
            ).fetchone()
        return self._row_to_react_step(row) if row is not None else None

    def next_react_step_no(self, turn_run_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COALESCE(MAX(step_no) + 1, 0) AS next_step_no
                FROM react_steps
                WHERE turn_run_id = ?
                """,
                (turn_run_id,),
            ).fetchone()
        return int((row["next_step_no"] if row else 0) or 0)

    def mark_react_step_model_running(
        self,
        *,
        step_id: str,
        runtime_instance_id: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> bool:
        del runtime_instance_id, lease_expires_at
        now_iso = self._now(now)
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE react_steps
                SET status = 'model_running',
                    updated_at = ?
                WHERE step_id = ?
                  AND status IN ('model_pending', 'model_retry_pending')
                """,
                (now_iso, step_id),
            )
            self._conn.commit()
        return cur.rowcount == 1

    def mark_react_step_tool_pending(
        self,
        *,
        step_id: str,
        assistant_tool_call_json: str,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE react_steps
                SET status = 'tool_pending',
                    assistant_tool_call_json = ?,
                    updated_at = ?
                WHERE step_id = ?
                """,
                (assistant_tool_call_json, now_iso, step_id),
            )
            self._conn.commit()

    def mark_react_step_final_pending(
        self,
        *,
        step_id: str,
        assistant_message_id: str | None,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE react_steps
                SET status = 'final_pending',
                    assistant_message_id = ?,
                    updated_at = ?
                WHERE step_id = ?
                """,
                (assistant_message_id, now_iso, step_id),
            )
            self._conn.execute(
                """
                UPDATE turn_runs
                SET assistant_message_id = COALESCE(?, assistant_message_id),
                    status = 'final_pending',
                    updated_at = ?
                WHERE turn_run_id = (
                    SELECT turn_run_id FROM react_steps WHERE step_id = ?
                )
                """,
                (assistant_message_id, now_iso, step_id),
            )
            self._conn.commit()

    def persist_react_tool_call(
        self,
        *,
        turn_run_id: str,
        step_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments_json: str,
        arguments_hash: str,
        recovery_ref: str,
        pollable: bool,
        idempotent: bool,
        side_effect: bool,
        now: datetime,
    ) -> dict[str, Any]:
        now_iso = self._now(now)
        attempt_id = f"tool_{turn_run_id}_{tool_call_id}"
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO tool_invocation_attempts (
                    attempt_id, turn_run_id, step_id, tool_call_id,
                    tool_name, arguments_json, arguments_hash, status,
                    recovery_ref, pollable, idempotent, side_effect,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(turn_run_id, tool_call_id) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (
                    attempt_id,
                    turn_run_id,
                    step_id,
                    tool_call_id,
                    tool_name,
                    arguments_json,
                    arguments_hash,
                    recovery_ref,
                    1 if pollable else 0,
                    1 if idempotent else 0,
                    1 if side_effect else 0,
                    now_iso,
                    now_iso,
                ),
            )
            self._conn.execute(
                """
                UPDATE react_steps
                SET status = 'tool_pending',
                    updated_at = ?
                WHERE step_id = ?
                """,
                (now_iso, step_id),
            )
            self._conn.commit()
        attempt = self.get_tool_invocation_attempt(attempt_id)
        if attempt is None:
            raise KeyError(attempt_id)
        return attempt

    def get_tool_invocation_attempt(
        self,
        attempt_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT attempt_id, turn_run_id, step_id, tool_call_id,
                       tool_name, arguments_json, arguments_hash, status,
                       recovery_ref, pollable, idempotent, side_effect,
                       result_message_id, result_preview, error_code,
                       owner_instance_id, lease_expires_at, started_at,
                       finished_at, created_at, updated_at
                FROM tool_invocation_attempts
                WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()
        return self._row_to_tool_invocation_attempt(row) if row is not None else None

    def claim_tool_invocation(
        self,
        *,
        attempt_id: str,
        turn_run_id: str,
        worker_id: str,
        lease_expires_at: datetime,
        now: datetime,
    ) -> bool:
        now_iso = self._now(now)
        lease_iso = self._now(lease_expires_at)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                turn = self._conn.execute(
                    """
                    SELECT 1
                    FROM turn_runs
                    WHERE turn_run_id = ?
                      AND lease_owner = ?
                      AND lease_expires_at > ?
                      AND status IN (
                          'running',
                          'model_retry_pending',
                          'tool_recovery_pending',
                          'final_pending'
                      )
                    """,
                    (turn_run_id, worker_id, now_iso),
                ).fetchone()
                if turn is None:
                    self._conn.rollback()
                    return False
                cur = self._conn.execute(
                    """
                    UPDATE tool_invocation_attempts
                    SET status = 'running',
                        owner_instance_id = ?,
                        lease_expires_at = ?,
                        started_at = COALESCE(started_at, ?),
                        updated_at = ?
                    WHERE attempt_id = ?
                      AND turn_run_id = ?
                      AND (
                          status = 'pending'
                          OR (status = 'running' AND lease_expires_at <= ?)
                      )
                    """,
                    (
                        worker_id,
                        lease_iso,
                        now_iso,
                        now_iso,
                        attempt_id,
                        turn_run_id,
                        now_iso,
                    ),
                )
                if cur.rowcount != 1:
                    self._conn.rollback()
                    return False
                self._conn.execute(
                    """
                    UPDATE react_steps
                    SET status = 'tool_running',
                        updated_at = ?
                    WHERE step_id = (
                        SELECT step_id
                        FROM tool_invocation_attempts
                        WHERE attempt_id = ?
                    )
                    """,
                    (now_iso, attempt_id),
                )
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def mark_tool_invocation_succeeded(
        self,
        *,
        attempt_id: str,
        result_message_id: str,
        result_preview: str,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE tool_invocation_attempts
                SET status = 'succeeded',
                    result_message_id = ?,
                    result_preview = ?,
                    finished_at = ?,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE attempt_id = ?
                """,
                (result_message_id, result_preview, now_iso, now_iso, attempt_id),
            )
            self._conn.execute(
                """
                UPDATE react_steps
                SET status = 'tool_succeeded',
                    tool_result_message_id = ?,
                    updated_at = ?
                WHERE step_id = (
                    SELECT step_id
                    FROM tool_invocation_attempts
                    WHERE attempt_id = ?
                )
                """,
                (result_message_id, now_iso, attempt_id),
            )
            self._conn.commit()

    def mark_tool_invocation_failed(
        self,
        *,
        attempt_id: str,
        error_code: str,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE tool_invocation_attempts
                SET status = 'failed',
                    error_code = ?,
                    finished_at = ?,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE attempt_id = ?
                """,
                (error_code, now_iso, now_iso, attempt_id),
            )
            self._conn.commit()

    def mark_tool_invocation_blocked(
        self,
        *,
        attempt_id: str,
        error_code: str,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE tool_invocation_attempts
                SET status = 'blocked',
                    error_code = ?,
                    finished_at = ?,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE attempt_id = ?
                """,
                (error_code, now_iso, now_iso, attempt_id),
            )
            self._conn.commit()

    def mark_tool_invocation_pending(
        self,
        *,
        attempt_id: str,
        now: datetime,
    ) -> None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE tool_invocation_attempts
                SET status = 'pending',
                    owner_instance_id = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE attempt_id = ?
                """,
                (now_iso, attempt_id),
            )
            self._conn.commit()

    def enqueue_outbox(
        self,
        *,
        session_key: str,
        message_id: str,
        channel: str,
        chat_id: str,
        now: datetime | None = None,
        available_at: datetime | None = None,
        outbox_id: str | None = None,
    ) -> dict[str, Any]:
        outbox_id = outbox_id or f"outbox_{session_key.replace(':', '_')}_{message_id.rsplit(':', 1)[-1]}"
        created_at = self._now(now)
        available = self._now(available_at or now)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO outbox (
                    outbox_id, session_key, message_id, channel, chat_id,
                    status, attempt_no, available_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)
                ON CONFLICT(outbox_id) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (
                    outbox_id,
                    session_key,
                    message_id,
                    channel,
                    chat_id,
                    available,
                    created_at,
                    created_at,
                ),
            )
            self._conn.commit()
        return self.get_outbox(outbox_id) or {"outbox_id": outbox_id}

    def get_outbox(self, outbox_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT outbox_id, session_key, message_id, channel, chat_id,
                       status, attempt_no, available_at, lease_expires_at,
                       worker_id, last_error, remote_message_id,
                       created_at, updated_at
                FROM outbox
                WHERE outbox_id = ?
                """,
                (outbox_id,),
            ).fetchone()
        if row is None:
            return None
        payload = {
            "outbox_id": row["outbox_id"],
            "session_key": row["session_key"],
            "message_id": row["message_id"],
            "channel": row["channel"],
            "chat_id": row["chat_id"],
            "status": row["status"],
            "attempt_no": int(row["attempt_no"] or 0),
            "available_at": row["available_at"],
            "lease_expires_at": row["lease_expires_at"],
            "worker_id": row["worker_id"],
            "last_error": row["last_error"],
            "remote_message_id": row["remote_message_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        message = self.get_message(str(row["message_id"]))
        if message is not None:
            payload["message"] = message
        return payload

    def list_outbox(
        self,
        *,
        session_key: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where_parts: list[str] = []
        if session_key:
            where_parts.append("session_key = ?")
            params.append(session_key)
        if status:
            where_parts.append("status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        sql = f"""
            SELECT outbox_id, session_key, message_id, channel, chat_id,
                   status, attempt_no, available_at, lease_expires_at,
                   worker_id, last_error, remote_message_id,
                   created_at, updated_at
            FROM outbox
            {where_sql}
            ORDER BY created_at ASC
            LIMIT ?
        """
        with self._lock:
            rows = self._conn.execute(sql, tuple([*params, int(limit)])).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = {
                "outbox_id": row["outbox_id"],
                "session_key": row["session_key"],
                "message_id": row["message_id"],
                "channel": row["channel"],
                "chat_id": row["chat_id"],
                "status": row["status"],
                "attempt_no": int(row["attempt_no"] or 0),
                "available_at": row["available_at"],
                "lease_expires_at": row["lease_expires_at"],
                "worker_id": row["worker_id"],
                "last_error": row["last_error"],
                "remote_message_id": row["remote_message_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            message = self.get_message(str(row["message_id"]))
            if message is not None:
                item["message"] = message
            result.append(item)
        return result

    def claim_next_outbox(
        self,
        *,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        now_iso = self._now(now)
        lease_expires_at = self._now(now + timedelta(seconds=lease_seconds))
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """
                    SELECT outbox_id
                    FROM outbox
                    WHERE status = 'pending' AND available_at <= ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (now_iso,),
                ).fetchone()
                if row is None:
                    self._conn.rollback()
                    return None
                outbox_id = str(row["outbox_id"])
                cur = self._conn.execute(
                    """
                    UPDATE outbox
                    SET status = 'sending',
                        attempt_no = attempt_no + 1,
                        worker_id = ?,
                        lease_expires_at = ?,
                        updated_at = ?
                    WHERE outbox_id = ? AND status = 'pending' AND available_at <= ?
                    """,
                    (worker_id, lease_expires_at, now_iso, outbox_id, now_iso),
                )
                if cur.rowcount != 1:
                    self._conn.rollback()
                    return None
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get_outbox(outbox_id)

    def mark_outbox_sent(
        self,
        outbox_id: str,
        *,
        remote_message_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE outbox
                SET status = 'sent',
                    remote_message_id = ?,
                    last_error = NULL,
                    worker_id = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE outbox_id = ?
                """,
                (remote_message_id, now_iso, outbox_id),
            )
            self._conn.commit()
        return self.get_outbox(outbox_id)

    def mark_outbox_unknown(
        self,
        outbox_id: str,
        *,
        remote_message_id: str,
        error: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE outbox
                SET status = 'unknown',
                    remote_message_id = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE outbox_id = ?
                """,
                (remote_message_id, error, now_iso, outbox_id),
            )
            self._conn.commit()
        return self.get_outbox(outbox_id)

    def mark_outbox_failed(
        self,
        outbox_id: str,
        *,
        error: str,
        now: datetime | None = None,
        retry_after_seconds: int = 30,
    ) -> dict[str, Any] | None:
        now_iso = self._now(now)
        retry_at = self._now((now or datetime.now().astimezone()) + timedelta(seconds=retry_after_seconds))
        with self._lock:
            self._conn.execute(
                """
                UPDATE outbox
                SET status = 'failed',
                    last_error = ?,
                    available_at = ?,
                    updated_at = ?
                WHERE outbox_id = ?
                """,
                (error, retry_at, now_iso, outbox_id),
            )
            self._conn.commit()
        return self.get_outbox(outbox_id)

    def reconcile_unknown_outbox(
        self,
        outbox_id: str,
        *,
        delivered: bool,
        now: datetime | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        now_iso = self._now(now)
        with self._lock:
            row = self._conn.execute(
                "SELECT remote_message_id FROM outbox WHERE outbox_id = ?",
                (outbox_id,),
            ).fetchone()
            if row is None:
                return None
            status = "sent" if delivered else "failed"
            self._conn.execute(
                """
                UPDATE outbox
                SET status = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE outbox_id = ?
                """,
                (status, error, now_iso, outbox_id),
            )
            self._conn.commit()
        return self.get_outbox(outbox_id)

    def create_message_generation(
        self,
        *,
        session_key: str,
        message_id: str,
        generation_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO message_generations (
                    generation_id, session_key, message_id, status,
                    last_streamed_offset, partial_content, started_at, updated_at
                )
                VALUES (?, ?, ?, 'streaming', 0, '', ?, ?)
                ON CONFLICT(generation_id) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (generation_id, session_key, message_id, now_iso, now_iso),
            )
            self._conn.commit()
        return self.get_message_generation(generation_id) or {
            "generation_id": generation_id,
            "session_key": session_key,
            "message_id": message_id,
            "status": "streaming",
        }

    def update_message_generation_progress(
        self,
        generation_id: str,
        *,
        partial_content: str,
        last_streamed_offset: int,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE message_generations
                SET partial_content = ?,
                    last_streamed_offset = ?,
                    updated_at = ?
                WHERE generation_id = ?
                """,
                (partial_content, int(last_streamed_offset), now_iso, generation_id),
            )
            self._conn.commit()
        return self.get_message_generation(generation_id)

    def finish_message_generation(
        self,
        generation_id: str,
        *,
        final_content: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        now_iso = self._now(now)
        with self._lock:
            self._conn.execute(
                """
                UPDATE message_generations
                SET status = 'finished',
                    partial_content = ?,
                    last_streamed_offset = ?,
                    finished_at = ?,
                    last_error = NULL,
                    updated_at = ?
                WHERE generation_id = ?
                """,
                (
                    final_content,
                    len(final_content),
                    now_iso,
                    now_iso,
                    generation_id,
                ),
            )
            self._conn.commit()
        return self.get_message_generation(generation_id)

    def abort_stale_message_generations(
        self,
        *,
        now: datetime | None = None,
        suffix: str = "",
    ) -> list[dict[str, Any]]:
        now_iso = self._now(now)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT generation_id, message_id, partial_content
                FROM message_generations
                WHERE status = 'streaming'
                """
            ).fetchall()
            results: list[dict[str, Any]] = []
            for row in rows:
                content = str(row["partial_content"] or "")
                message_content = content + ("\n\n" + suffix if suffix else "")
                self._conn.execute(
                    """
                    UPDATE messages
                    SET content = ?
                    WHERE id = ?
                    """,
                    (message_content, str(row["message_id"])),
                )
                self._conn.execute(
                    """
                    UPDATE message_generations
                    SET status = 'aborted',
                        aborted_at = ?,
                        updated_at = ?
                    WHERE generation_id = ?
                    """,
                    (now_iso, now_iso, str(row["generation_id"])),
                )
                results.append(
                    {
                        "generation_id": str(row["generation_id"]),
                        "message_id": str(row["message_id"]),
                        "status": "aborted",
                        "partial_content": content,
                        "last_streamed_offset": 0,
                        "updated_at": now_iso,
                    }
                )
            self._conn.commit()
        return results

    def get_message_generation(self, generation_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT generation_id, session_key, message_id, status,
                       last_streamed_offset, partial_content, started_at,
                       finished_at, aborted_at, last_error, updated_at
                FROM message_generations
                WHERE generation_id = ?
                """,
                (generation_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "generation_id": row["generation_id"],
            "session_key": row["session_key"],
            "message_id": row["message_id"],
            "status": row["status"],
            "last_streamed_offset": int(row["last_streamed_offset"] or 0),
            "partial_content": row["partial_content"] or "",
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "aborted_at": row["aborted_at"],
            "last_error": row["last_error"],
            "updated_at": row["updated_at"],
        }

    def fetch_session_messages(self, session_key: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, session_key, seq, role, content, tool_chain, extra, ts
                FROM messages
                WHERE session_key = ?
                ORDER BY seq ASC
                """,
                (session_key,),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def list_messages_for_dashboard(
        self,
        *,
        session_key: str | None = None,
        q: str = "",
        role: str = "",
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "ts",
        sort_order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        safe_page = max(1, int(page))
        safe_page_size = max(1, min(int(page_size), 200))
        offset = (safe_page - 1) * safe_page_size
        safe_sort = "ASC" if str(sort_order).lower() == "asc" else "DESC"
        safe_sort_by = sort_by if sort_by in {"ts", "seq", "role", "session_key"} else "ts"

        params: list[Any] = []
        where_parts: list[str] = []
        if session_key:
            where_parts.append("session_key = ?")
            params.append(session_key)
        term = (q or "").strip()
        if term:
            where_parts.append("content LIKE ?")
            params.append(f"%{term}%")
        if role:
            where_parts.append("role = ?")
            params.append(role)
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        count_sql = f"SELECT COUNT(1) AS c FROM messages {where_sql}"
        data_sql = f"""
            SELECT id, session_key, seq, role, content, tool_chain, extra, ts
            FROM messages
            {where_sql}
            ORDER BY {safe_sort_by} {safe_sort}, seq {safe_sort}, id ASC
            LIMIT ? OFFSET ?
        """
        with self._lock:
            count_row = self._conn.execute(count_sql, tuple(params)).fetchone()
            rows = self._conn.execute(
                data_sql,
                tuple([*params, safe_page_size, offset]),
            ).fetchall()
        total = int((count_row["c"] if count_row else 0) or 0)
        return [self._row_to_message(row) for row in rows], total

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, session_key, seq, role, content, tool_chain, extra, ts
                FROM messages
                WHERE id = ?
                """,
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_message(row)

    def update_message(
        self,
        message_id: str,
        *,
        role: str | None = None,
        content: str | None = None,
        tool_chain: Any | None = None,
        extra: dict[str, Any] | None = None,
        ts: str | None = None,
    ) -> dict[str, Any] | None:
        set_parts: list[str] = []
        params: list[Any] = []
        if role is not None:
            set_parts.append("role = ?")
            params.append(role)
        if content is not None:
            set_parts.append("content = ?")
            params.append(content)
        if tool_chain is not None:
            set_parts.append("tool_chain = ?")
            params.append(json.dumps(tool_chain, ensure_ascii=False))
        if extra is not None:
            set_parts.append("extra = ?")
            params.append(json.dumps(extra, ensure_ascii=False))
        if ts is not None:
            set_parts.append("ts = ?")
            params.append(ts)
        if not set_parts:
            return self.get_message(message_id)

        with self._lock:
            row = self._conn.execute(
                "SELECT session_key FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return None
            session_key = str(row["session_key"])
            params.append(message_id)
            cur = self._conn.execute(
                f"UPDATE messages SET {', '.join(set_parts)} WHERE id = ?",
                tuple(params),
            )
            self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE key = ?",
                (datetime.now().astimezone().isoformat(), session_key),
            )
            self._conn.commit()
        if cur.rowcount <= 0:
            return None
        return self.get_message(message_id)

    def delete_message(self, message_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT session_key FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return False
            session_key = str(row["session_key"])
            cur = self._conn.execute(
                "DELETE FROM messages WHERE id = ?",
                (message_id,),
            )
            self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE key = ?",
                (datetime.now().astimezone().isoformat(), session_key),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def delete_messages_batch(self, ids: list[str]) -> int:
        clean_ids = [str(message_id).strip() for message_id in ids if str(message_id).strip()]
        if not clean_ids:
            return 0
        placeholders = ",".join("?" for _ in clean_ids)
        now = datetime.now().astimezone().isoformat()
        with self._lock:
            rows = self._conn.execute(
                f"SELECT DISTINCT session_key FROM messages WHERE id IN ({placeholders})",
                tuple(clean_ids),
            ).fetchall()
            cur = self._conn.execute(
                f"DELETE FROM messages WHERE id IN ({placeholders})",
                tuple(clean_ids),
            )
            for row in rows:
                self._conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE key = ?",
                    (now, str(row["session_key"])),
                )
            self._conn.commit()
        return int(cur.rowcount or 0)

    def delete_session_messages_and_update_cursor(
        self,
        session_key: str,
        *,
        ids: list[str],
        last_consolidated: int,
    ) -> int:
        clean_ids = [str(message_id).strip() for message_id in ids if str(message_id).strip()]
        if not clean_ids:
            return 0
        placeholders = ",".join("?" for _ in clean_ids)
        now = datetime.now().astimezone().isoformat()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                seq_rows = self._conn.execute(
                    f"""
                    SELECT seq
                    FROM messages
                    WHERE session_key = ? AND id IN ({placeholders})
                    """,
                    tuple([session_key, *clean_ids]),
                ).fetchall()
                next_seq = (
                    max(int(row["seq"]) for row in seq_rows) + 1
                    if seq_rows
                    else 0
                )
                cur = self._conn.execute(
                    f"""
                    DELETE FROM messages
                    WHERE session_key = ? AND id IN ({placeholders})
                    """,
                    tuple([session_key, *clean_ids]),
                )
                self._conn.execute(
                    """
                    UPDATE sessions
                    SET last_consolidated = ?,
                        updated_at = ?,
                        next_seq = CASE WHEN next_seq < ? THEN ? ELSE next_seq END
                    WHERE key = ?
                    """,
                    (int(last_consolidated), now, next_seq, next_seq, session_key),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return int(cur.rowcount or 0)

    def fetch_by_ids_with_context(self, ids: list[str], context: int) -> list[dict[str, Any]]:
        """Fetch messages by ID, expanding each hit by ±context rows in its session.

        Returns messages ordered by (session_key, seq).
        Each dict includes ``in_source_ref: bool`` to distinguish hits from context.
        """
        if not ids:
            return []
        if context == 0:
            result = self.fetch_by_ids(ids)
            for m in result:
                m["in_source_ref"] = True
            return result

        id_set = set(ids)
        session_seqs: dict[str, set[int]] = {}
        for msg_id in ids:
            parts = msg_id.rsplit(":", 1)
            if len(parts) != 2:
                continue
            sk, seq_str = parts
            try:
                seq = int(seq_str)
            except ValueError:
                continue
            if sk not in session_seqs:
                session_seqs[sk] = set()
            session_seqs[sk].add(seq)

        if not session_seqs:
            return []

        results: list[dict[str, Any]] = []
        with self._lock:
            for sk, seqs in session_seqs.items():
                expanded: set[int] = set()
                for seq in seqs:
                    for s in range(max(0, seq - context), seq + context + 1):
                        expanded.add(s)
                placeholders = ",".join("?" * len(expanded))
                rows = self._conn.execute(
                    f"SELECT id, session_key, seq, role, content, tool_chain, extra, ts "
                    f"FROM messages WHERE session_key = ? AND seq IN ({placeholders}) ORDER BY seq",
                    [sk, *expanded],
                ).fetchall()
                for row in rows:
                    msg = self._row_to_message(row)
                    msg["in_source_ref"] = msg["id"] in id_set
                    results.append(msg)
        return results

    def fetch_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        order_expr = " ".join(f"WHEN ? THEN {i}" for i in range(len(ids)))
        sql = (
            "SELECT id, session_key, seq, role, content, tool_chain, extra, ts FROM messages "
            f"WHERE id IN ({placeholders}) ORDER BY CASE id {order_expr} END"
        )
        with self._lock:
            rows = self._conn.execute(sql, tuple(ids + ids)).fetchall()
        return [self._row_to_message(row) for row in rows]

    def search_messages(
        self,
        query: str,
        *,
        session_key: str | None = None,
        role: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        params: list[Any] = []
        where_parts: list[str] = []
        if session_key:
            where_parts.append("m.session_key = ?")
            params.append(session_key)
        if role:
            where_parts.append("m.role = ?")
            params.append(role)
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        # Split into individual terms for both FTS and LIKE paths.
        terms = [t for t in query.split() if t]
        if not terms:
            terms = [query]

        term_conditions_or = " OR ".join("m.content LIKE ?" for _ in terms)
        score_expr = " + ".join(
            f"(CASE WHEN m.content LIKE ? THEN 1 ELSE 0 END)" for _ in terms
        )
        if self._has_fts:
            # 长词走 FTS，短词继续走 LIKE，再把两路结果合并去重。
            fts_terms = [t for t in terms if len(t) >= 3]
            if fts_terms:
                fts_query = " OR ".join(fts_terms)
                connector = "AND" if where_sql else "WHERE"
                count_params = [fts_query] + params[:]
                count_sql = (
                    "SELECT COUNT(1) AS c "
                    "FROM messages m "
                    "LEFT JOIN ("
                    "    SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?"
                    ") fts ON m.rowid = fts.rowid "
                    f"{where_sql} {connector} (fts.rowid IS NOT NULL OR ({term_conditions_or})) "
                )
                count_params.extend(f"%{t}%" for t in terms)
                fts_params: list[Any] = []
                fts_sql = (
                    "SELECT m.id, m.session_key, m.seq, m.role, m.content, m.tool_chain, m.extra, m.ts, "
                    f"({score_expr}) AS match_score, "
                    "fts.rank_score AS rank_score "
                    "FROM messages m "
                    "LEFT JOIN ("
                    "    SELECT rowid, bm25(messages_fts) AS rank_score "
                    "    FROM messages_fts WHERE messages_fts MATCH ?"
                    ") fts ON m.rowid = fts.rowid "
                    f"{where_sql} {connector} (fts.rowid IS NOT NULL OR ({term_conditions_or})) "
                    "ORDER BY match_score DESC, "
                    "CASE WHEN rank_score IS NULL THEN 1 ELSE 0 END ASC, "
                    "rank_score ASC, m.seq DESC LIMIT ? OFFSET ?"
                )
                fts_params.extend(f"%{t}%" for t in terms)
                fts_params.append(fts_query)
                fts_params.extend(params[:])
                fts_params.extend(f"%{t}%" for t in terms)
                fts_params.extend([limit, offset])
                try:
                    with self._lock:
                        count_row = self._conn.execute(count_sql, tuple(count_params)).fetchone()
                        rows = self._conn.execute(fts_sql, tuple(fts_params)).fetchall()
                    total = int((count_row["c"] if count_row else 0) or 0)
                    return [self._row_to_message(row) for row in rows], total
                except sqlite3.OperationalError:
                    pass

        # LIKE fallback: OR across all terms so any hit surfaces; rank by match count descending.
        like_params = params[:]
        count_params = params[:]
        connector = "AND" if where_sql else "WHERE"
        count_sql = f"SELECT COUNT(1) AS c FROM messages m {where_sql} {connector} ({term_conditions_or}) "
        count_params.extend(f"%{t}%" for t in terms)
        like_sql = (
            f"SELECT m.id, m.session_key, m.seq, m.role, m.content, m.tool_chain, m.extra, m.ts, "
            f"({score_expr}) AS match_score "
            f"FROM messages m {where_sql} {connector} ({term_conditions_or}) "
            f"ORDER BY match_score DESC, m.seq DESC LIMIT ? OFFSET ?"
        )
        # score_expr binds: one %t% per term; term_conditions_or binds: one %t% per term
        like_params.extend(f"%{t}%" for t in terms)  # for score_expr
        like_params.extend(f"%{t}%" for t in terms)  # for WHERE OR
        like_params.extend([limit, offset])
        with self._lock:
            count_row = self._conn.execute(count_sql, tuple(count_params)).fetchone()
            rows = self._conn.execute(like_sql, tuple(like_params)).fetchall()
        total = int((count_row["c"] if count_row else 0) or 0)
        return [self._row_to_message(row) for row in rows], total

    def _row_to_message(self, row: sqlite3.Row) -> dict[str, Any]:
        message: dict[str, Any] = {
            "id": row["id"],
            "session_key": row["session_key"],
            "seq": int(row["seq"]),
            "role": row["role"],
            "content": row["content"] or "",
            "timestamp": row["ts"],
        }
        tool_chain = row["tool_chain"]
        if tool_chain:
            message["tool_chain"] = json.loads(tool_chain)
        extra = json.loads(row["extra"] or "{}")
        if extra:
            message.update(extra)
        return message
