from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path


_CREATE_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS tool_audit_events (
    event_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    session_key TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    chat_id TEXT NOT NULL DEFAULT '',
    request_id TEXT NOT NULL DEFAULT '',
    turn_id TEXT NOT NULL DEFAULT '',
    tool_name TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    risk TEXT NOT NULL DEFAULT '',
    policy_action TEXT NOT NULL DEFAULT '',
    policy_reason TEXT NOT NULL DEFAULT '',
    approval_request_id TEXT NOT NULL DEFAULT '',
    approval_scope TEXT NOT NULL DEFAULT '',
    approval_status TEXT NOT NULL DEFAULT '',
    side_effect_status TEXT NOT NULL DEFAULT '',
    execution_status TEXT NOT NULL DEFAULT '',
    rollback_status TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    args_hash TEXT NOT NULL DEFAULT '',
    invoker_reached INTEGER NOT NULL DEFAULT 0,
    invoker_succeeded INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}'
)
"""

_CREATE_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_tool_audit_events_created_at "
    "ON tool_audit_events (created_at, event_id)",
    "CREATE INDEX IF NOT EXISTS idx_tool_audit_events_session_key "
    "ON tool_audit_events (session_key, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tool_audit_events_request_id "
    "ON tool_audit_events (request_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tool_audit_events_approval_request_id "
    "ON tool_audit_events (approval_request_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tool_audit_events_tool_name "
    "ON tool_audit_events (tool_name, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tool_audit_events_event_type "
    "ON tool_audit_events (event_type, created_at)",
)

_METADATA_ALLOWLIST = frozenset(
    {
        "resource_type",
        "resource_decision",
        "sandbox_backend",
        "sandbox_image",
        "network_mode",
        "workspace_mount_mode",
        "timeout_seconds",
        "exit_code",
        "stdout_ref",
        "stderr_ref",
        "stdout_hash",
        "stderr_hash",
        "stdout_bytes",
        "stderr_bytes",
        "stdout_truncated",
        "stderr_truncated",
        "duration_ms",
        "target_path_hash",
        "before_hash",
        "after_hash",
        "diff_truncated",
        "rollback_id",
        "error_code",
        "command_hash",
        "preview_id",
        "background_requested",
        "background_allowed",
    }
)
_REF_METADATA_KEYS = frozenset({"stdout_ref", "stderr_ref", "preview_id", "rollback_id"})
_HASH_METADATA_KEYS = frozenset(
    {"stdout_hash", "stderr_hash", "target_path_hash", "before_hash", "after_hash", "command_hash"}
)
_NUMBER_METADATA_KEYS = frozenset(
    {"timeout_seconds", "exit_code", "stdout_bytes", "stderr_bytes", "duration_ms"}
)
_BOOLEAN_METADATA_KEYS = frozenset(
    {
        "stdout_truncated",
        "stderr_truncated",
        "diff_truncated",
        "background_requested",
        "background_allowed",
    }
)
_SENSITIVE_VALUE_MARKERS = (
    "token",
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "bearer",
    "private_key",
    "payload",
    "command=",
    "?",
)
_REF_RE = re.compile(r"^[A-Za-z0-9._/-]{1,160}$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_COMMAND_PREFIXES = ("echo ", "rm ", "python ", "bash ", "sh ")


@dataclass(frozen=True)
class ToolAuditLedgerEvent:
    event_type: str
    created_at: datetime | str | None = None
    event_id: str = ""
    session_key: str = ""
    channel: str = ""
    chat_id: str = ""
    request_id: str = ""
    turn_id: str = ""
    tool_name: str = ""
    source: str = ""
    risk: str = ""
    policy_action: str = ""
    policy_reason: str = ""
    approval_request_id: str = ""
    approval_scope: str = ""
    approval_status: str = ""
    side_effect_status: str = ""
    execution_status: str = ""
    rollback_status: str = ""
    actor: str = ""
    args_hash: str = ""
    invoker_reached: bool = False
    invoker_succeeded: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolAuditLedgerQuery:
    session_key: str = ""
    request_id: str = ""
    approval_request_id: str = ""
    tool_name: str = ""
    event_type: str = ""
    since: datetime | str | None = None
    until: datetime | str | None = None
    limit: int = 50


class ToolAuditLedgerStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @staticmethod
    def db_path_from_workspace(workspace: str | Path) -> Path:
        return Path(workspace).expanduser().resolve() / "tool_audit" / "tool_audit.db"

    def record_event(self, event: ToolAuditLedgerEvent) -> ToolAuditLedgerEvent:
        recorded = replace(
            event,
            event_id=event.event_id or uuid.uuid4().hex,
            created_at=_to_iso(event.created_at),
            metadata=sanitize_tool_audit_metadata(event.metadata),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_audit_events (
                    event_id, created_at, event_type, session_key, channel, chat_id,
                    request_id, turn_id, tool_name, source, risk, policy_action,
                    policy_reason, approval_request_id, approval_scope, approval_status,
                    side_effect_status, execution_status, rollback_status, actor,
                    args_hash, invoker_reached, invoker_succeeded, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recorded.event_id,
                    recorded.created_at,
                    recorded.event_type,
                    recorded.session_key,
                    recorded.channel,
                    recorded.chat_id,
                    recorded.request_id,
                    recorded.turn_id,
                    recorded.tool_name,
                    recorded.source,
                    recorded.risk,
                    recorded.policy_action,
                    recorded.policy_reason,
                    recorded.approval_request_id,
                    recorded.approval_scope,
                    recorded.approval_status,
                    recorded.side_effect_status,
                    recorded.execution_status,
                    recorded.rollback_status,
                    recorded.actor,
                    recorded.args_hash,
                    int(recorded.invoker_reached),
                    int(recorded.invoker_succeeded),
                    json.dumps(recorded.metadata, sort_keys=True, separators=(",", ":")),
                ),
            )
        return recorded

    def query_events(self, query: ToolAuditLedgerQuery) -> list[ToolAuditLedgerEvent]:
        clauses: list[str] = []
        values: list[object] = []
        for column, value in (
            ("session_key", query.session_key),
            ("request_id", query.request_id),
            ("approval_request_id", query.approval_request_id),
            ("tool_name", query.tool_name),
            ("event_type", query.event_type),
        ):
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        if query.since is not None:
            clauses.append("created_at >= ?")
            values.append(_to_iso(query.since))
        if query.until is not None:
            clauses.append("created_at <= ?")
            values.append(_to_iso(query.until))

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(query.limit, 200)))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_audit_events"
                f"{where} ORDER BY created_at DESC, event_id DESC LIMIT ?",
                values,
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def prune(self, *, before: datetime | None, max_rows: int | None) -> int:
        with self._connect() as conn:
            deleted = 0
            if before is not None:
                result = conn.execute(
                    "DELETE FROM tool_audit_events WHERE created_at < ?", (_to_iso(before),)
                )
                deleted += result.rowcount
            if max_rows is not None:
                result = conn.execute(
                    """
                    DELETE FROM tool_audit_events
                    WHERE event_id IN (
                        SELECT event_id FROM tool_audit_events
                        ORDER BY created_at DESC, event_id DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (max(0, max_rows),),
                )
                deleted += result.rowcount
        return deleted

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_EVENTS_SQL)
            for statement in _CREATE_INDEXES_SQL:
                conn.execute(statement)
            conn.execute("PRAGMA user_version = 1")


def sanitize_tool_audit_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in metadata.items():
        if key not in _METADATA_ALLOWLIST:
            continue
        if key in _NUMBER_METADATA_KEYS:
            if isinstance(value, int) and not isinstance(value, bool):
                sanitized[key] = value
            continue
        if key in _BOOLEAN_METADATA_KEYS:
            if isinstance(value, bool):
                sanitized[key] = value
            continue
        if not isinstance(value, str) or not _is_safe_string(value):
            continue
        if key in _REF_METADATA_KEYS and not _is_safe_ref(value):
            continue
        if key in _HASH_METADATA_KEYS and not _is_safe_hash(value):
            continue
        sanitized[key] = value
    return sanitized


def record_tool_audit_event_fail_open(
    store: ToolAuditLedgerStore, event: ToolAuditLedgerEvent, logger: logging.Logger
) -> ToolAuditLedgerEvent | None:
    try:
        return store.record_event(event)
    except Exception:
        logger.warning("failed to record tool audit event", exc_info=True)
        return None


def _event_from_row(row: sqlite3.Row) -> ToolAuditLedgerEvent:
    metadata = json.loads(row["metadata_json"])
    return ToolAuditLedgerEvent(
        event_id=row["event_id"],
        created_at=row["created_at"],
        event_type=row["event_type"],
        session_key=row["session_key"],
        channel=row["channel"],
        chat_id=row["chat_id"],
        request_id=row["request_id"],
        turn_id=row["turn_id"],
        tool_name=row["tool_name"],
        source=row["source"],
        risk=row["risk"],
        policy_action=row["policy_action"],
        policy_reason=row["policy_reason"],
        approval_request_id=row["approval_request_id"],
        approval_scope=row["approval_scope"],
        approval_status=row["approval_status"],
        side_effect_status=row["side_effect_status"],
        execution_status=row["execution_status"],
        rollback_status=row["rollback_status"],
        actor=row["actor"],
        args_hash=row["args_hash"],
        invoker_reached=bool(row["invoker_reached"]),
        invoker_succeeded=bool(row["invoker_succeeded"]),
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _to_iso(value: datetime | str | None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("timestamp must be a datetime, ISO string, or None")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _is_safe_string(value: str) -> bool:
    lower = value.lower()
    return (
        len(value) <= 240
        and not any(marker in lower for marker in _SENSITIVE_VALUE_MARKERS)
        and not value.startswith("/")
        and not any(segment in {".", ".."} for segment in value.replace("\\", "/").split("/"))
        and not lower.startswith(_COMMAND_PREFIXES)
    )


def _is_safe_ref(value: str) -> bool:
    return _REF_RE.fullmatch(value) is not None and all(
        segment not in {".", ".."} for segment in value.split("/")
    )


def _is_safe_hash(value: str) -> bool:
    lower = value.lower()
    return bool(_HEX_RE.fullmatch(value) or value.endswith("-hash")) and not lower.startswith(
        _COMMAND_PREFIXES
    )
