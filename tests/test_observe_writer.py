import asyncio
from contextlib import suppress
import importlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from bus.events_lifecycle import TurnCommitted

_observe_db = importlib.import_module("plugins.observe.db")
_observe_events = importlib.import_module("plugins.observe.events")
_observe_migration = importlib.import_module("plugins.observe.migrate_legacy_rag")
_observe_retention = importlib.import_module("plugins.observe.retention")
_observe_writer = importlib.import_module("plugins.observe.writer")
_observe_plugin = importlib.import_module("plugins.observe.plugin")

open_db = cast(Callable[[Path], sqlite3.Connection], getattr(_observe_db, "open_db"))
RagHitLog = getattr(_observe_events, "RagHitLog")
RagQueryLog = getattr(_observe_events, "RagQueryLog")
TurnTrace = getattr(_observe_events, "TurnTrace")
migrate_legacy_rag_tables = getattr(_observe_migration, "migrate_legacy_rag_tables")
_run_cleanup = cast(Callable[[Path], None], getattr(_observe_retention, "_run_cleanup"))
_write_turn = getattr(_observe_writer, "_write_turn")
TraceWriter = getattr(_observe_writer, "TraceWriter")
_emit_turn_trace = getattr(_observe_plugin, "_emit_turn_trace")
_slim_tool_calls = getattr(_observe_plugin, "_slim_tool_calls")
_slim_tool_chain = getattr(_observe_plugin, "_slim_tool_chain")


class _RecordingObserveWriter:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


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


def test_observe_slim_trace_preserves_bounded_audit_metadata() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "write_file",
                    "arguments": {"path": "notes.md"},
                    "status": "deferred",
                    "result": '{"ok": false, "error_code": "risk_strategy_write_requires_approval"}',
                    "audit_trace": {
                        "event_type": "tool_invocation_policy_decision",
                        "request_id": "call_1",
                        "session_key": "cli:1",
                        "channel": "cli",
                        "chat_id": "1",
                        "tool_name": "write_file",
                        "source": "passive",
                        "risk": "write",
                        "policy_action": "defer",
                        "policy_reason": "risk_strategy_write_requires_approval",
                        "args_hash": "abc123",
                        "args_summary": {"content": {"sha256": "secret"}},
                        "invoker_reached": False,
                        "invoker_succeeded": False,
                    },
                }
            ],
        }
    ]

    slim_chain = _slim_tool_chain(tool_chain)
    slim_calls = _slim_tool_calls(tool_chain)

    audit = slim_chain[0]["calls"][0]["audit_trace"]
    flat_audit = slim_calls[0]["audit_trace"]
    assert audit["policy_action"] == "defer"
    assert audit["policy_reason"] == "risk_strategy_write_requires_approval"
    assert audit["args_hash"] == "abc123"
    assert audit["invoker_reached"] is False
    assert "args_summary" not in audit
    assert flat_audit["tool_name"] == "write_file"


def test_observe_slim_trace_preserves_approval_lifecycle_fields_without_args_summary() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "write_file",
                    "arguments": {"path": "notes.md"},
                    "status": "deferred",
                    "result": '{"ok": false}',
                    "approval_lifecycle": [
                        {
                            "event_type": "tool_approval_lifecycle",
                            "approval_request_id": "approval-1",
                            "request_id": "call-1",
                            "session_key": "cli:1",
                            "actor": "status_command",
                            "source": "passive",
                            "tool_name": "write_file",
                            "risk": "write",
                            "approval_scope": "tool_call",
                            "policy_reason": "risk_strategy_write_requires_approval",
                            "status": "requested",
                            "args_hash": "abc123",
                            "created_at": "2026-07-24T01:00:00+00:00",
                            "decided_at": "",
                            "consumed_at": "",
                            "executed_at": "",
                            "args_summary": {"content": {"sha256": "secret"}},
                            "command": "rm file.txt",
                            "content": "raw secret",
                        }
                    ],
                }
            ],
        }
    ]

    slim_chain = _slim_tool_chain(tool_chain)
    slim_calls = _slim_tool_calls(tool_chain)

    event = slim_chain[0]["calls"][0]["approval_lifecycle"][0]
    flat_event = slim_calls[0]["approval_lifecycle"][0]
    assert event["event_type"] == "tool_approval_lifecycle"
    assert event["approval_request_id"] == "approval-1"
    assert event["status"] == "requested"
    assert event["args_hash"] == "abc123"
    assert "args_summary" not in event
    assert "command" not in event
    assert "content" not in event
    assert flat_event["tool_name"] == "write_file"


def test_observe_slim_trace_preserves_approved_side_effect_lifecycle_without_sensitive_fields() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "write_file",
                    "arguments": {"path": "notes.md", "content": "raw-secret-content"},
                    "status": "deferred",
                    "result": '{"ok": false}',
                    "approved_side_effect_lifecycle": [
                        {
                            "event_type": "approved_side_effect_lifecycle",
                            "approval_request_id": "approval-1",
                            "request_id": "call-1",
                            "session_key": "cli:1",
                            "actor": "status_command",
                            "tool_name": "write_file",
                            "approval_scope": "tool_call",
                            "args_hash": "abc123",
                            "status": "preview_ready",
                            "preview_id": "preview-1",
                            "target_path_hash": "path-hash",
                            "before_hash": "before",
                            "after_hash": "after",
                            "diff_truncated": False,
                            "rollback_id": "rollback-1",
                            "execution_status": "applied",
                            "rollback_status": "available",
                            "created_at": "2026-07-26T01:00:00+00:00",
                            "diff_ref": "tool_side_effects/artifacts/preview/change.diff",
                            "path": "notes.md",
                            "target_path": "/tmp/workspace/notes.md",
                            "before_path": "/tmp/workspace/.before",
                            "after_path": "/tmp/workspace/.after",
                            "payload_path": "/tmp/workspace/tool_side_effects/payloads/a.json",
                            "content": "raw-secret-content",
                            "args_summary": {"content": {"preview": "raw-secret-content"}},
                            "command": "rm file.txt",
                            "body": "secret-body",
                            "cookie": "secret-cookie",
                            "token": "secret-token",
                            "diff_text": "-before\n+raw-secret-content\n",
                        }
                    ],
                }
            ],
        }
    ]

    slim_chain = _slim_tool_chain(tool_chain)
    slim_calls = _slim_tool_calls(tool_chain)

    event = slim_chain[0]["calls"][0]["approved_side_effect_lifecycle"][0]
    flat_event = slim_calls[0]["approved_side_effect_lifecycle"][0]
    encoded = json.dumps(event, ensure_ascii=False)
    assert event["event_type"] == "approved_side_effect_lifecycle"
    assert event["approval_request_id"] == "approval-1"
    assert event["status"] == "preview_ready"
    assert event["args_hash"] == "abc123"
    assert event["preview_id"] == "preview-1"
    assert event["target_path_hash"] == "path-hash"
    assert event["diff_truncated"] is False
    assert "raw-secret-content" not in encoded
    for key in (
        "content",
        "args_summary",
        "command",
        "body",
        "cookie",
        "token",
        "diff_ref",
        "diff_text",
        "path",
        "target_path",
        "before_path",
        "after_path",
        "payload_path",
    ):
        assert key not in event
    assert flat_event["tool_name"] == "write_file"


def test_observe_slim_trace_preserves_shell_sandbox_lifecycle_without_raw_command() -> None:
    raw_command = "echo secret-token-value"
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "approved_side_effect_lifecycle",
                    "arguments": {},
                    "result": "",
                    "approved_side_effect_lifecycle": [
                        {
                            "event_type": "approved_side_effect_lifecycle",
                            "approval_request_id": "approval-shell-1",
                            "request_id": "call-shell-1",
                            "session_key": "cli:1",
                            "actor": "status_command",
                            "tool_name": "shell",
                            "approval_scope": "tool_call",
                            "args_hash": "args-hash",
                            "status": "executed",
                            "preview_id": "shell-preview-1",
                            "command_hash": "command-hash",
                            "sandbox_backend": "podman",
                            "sandbox_image": "python:3.14-slim",
                            "network_mode": "none",
                            "workspace_mount_mode": "ro",
                            "timeout_seconds": 30,
                            "exit_code": 0,
                            "stdout_hash": "stdout-hash",
                            "stderr_hash": "stderr-hash",
                            "stdout_bytes": 5,
                            "stderr_bytes": 0,
                            "stdout_truncated": False,
                            "stderr_truncated": False,
                            "duration_ms": 120,
                            "command": raw_command,
                            "stdout_text": "secret-token-value",
                            "stderr_text": "secret-token-value",
                            "command_ref": "tool_side_effects/payloads/a.json",
                            "stdout_ref": "tool_side_effects/artifacts/stdout.txt",
                            "stderr_ref": "tool_side_effects/artifacts/stderr.txt",
                            "payload_path": "/tmp/workspace/tool_side_effects/payloads/a.json",
                        }
                    ],
                }
            ],
        }
    ]

    event = _slim_tool_chain(tool_chain)[0]["calls"][0][
        "approved_side_effect_lifecycle"
    ][0]
    encoded = json.dumps(event, ensure_ascii=False)

    assert event["tool_name"] == "shell"
    assert event["command_hash"] == "command-hash"
    assert event["network_mode"] == "none"
    assert event["workspace_mount_mode"] == "ro"
    assert event["exit_code"] == 0
    assert raw_command not in encoded
    assert "secret-token-value" not in encoded
    for key in (
        "command",
        "stdout_text",
        "stderr_text",
        "command_ref",
        "stdout_ref",
        "stderr_ref",
        "payload_path",
    ):
        assert key not in event


def test_observe_turn_trace_includes_status_command_side_effect_lifecycle_without_sensitive_fields() -> None:
    writer = _RecordingObserveWriter()
    raw_secret = "raw-secret-content"
    _emit_turn_trace(
        writer,
        TurnCommitted(
            session_key="cli:1",
            channel="cli",
            chat_id="1",
            input_message="/run_approved_tool approval-1",
            persisted_user_message="/run_approved_tool approval-1",
            assistant_response="status: file_change_applied",
            tools_used=[],
            tool_chain_raw=[],
            extra={
                "approved_side_effect_lifecycle": [
                    {
                        "event_type": "approved_side_effect_lifecycle",
                        "approval_request_id": "approval-1",
                        "request_id": "call-1",
                        "session_key": "cli:1",
                        "actor": "status_command",
                        "tool_name": "write_file",
                        "approval_scope": "tool_call",
                        "args_hash": "abc123",
                        "status": "applied",
                        "preview_id": "preview-1",
                        "target_path_hash": "path-hash",
                        "before_hash": "before",
                        "after_hash": "after",
                        "diff_truncated": False,
                        "rollback_id": "rollback-1",
                        "execution_status": "applied",
                        "rollback_status": "available",
                        "created_at": "2026-07-26T01:00:00+00:00",
                        "target_path": "/tmp/workspace/notes.md",
                        "payload_path": "/tmp/workspace/tool_side_effects/payloads/a.json",
                        "diff_text": f"-before\n+{raw_secret}\n",
                        "content": raw_secret,
                        "token": "secret-token",
                    }
                ]
            },
        ),
    )

    event = writer.events[0]
    assert event.tool_calls
    assert event.tool_chain_json is not None
    encoded = json.dumps(
        {
            "tool_calls": event.tool_calls,
            "tool_chain_json": json.loads(event.tool_chain_json),
        },
        ensure_ascii=False,
    )
    assert "approved_side_effect_lifecycle" in encoded
    assert "approval-1" in encoded
    assert raw_secret not in encoded
    assert "secret-token" not in encoded
    assert "/tmp/workspace/notes.md" not in encoded
    assert "payload_path" not in encoded


def test_observe_slim_call_redacts_sensitive_tool_arguments() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "shell",
                    "arguments": {
                        "command": "echo a | xargs rm file.txt",
                        "token": "secret-token-value",
                        "content": "raw secret body",
                        "path": "notes.md",
                    },
                    "status": "deferred",
                    "result": '{"ok": false}',
                }
            ],
        }
    ]

    slim_call = _slim_tool_calls(tool_chain)[0]

    encoded_args = str(slim_call["args"])
    assert "echo a | xargs rm file.txt" not in encoded_args
    assert "secret-token-value" not in encoded_args
    assert "raw secret body" not in encoded_args
    assert "sha256" in encoded_args
    assert "notes.md" in encoded_args


def test_write_turn_persists_raw_output_and_meme_fields(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = open_db(db_path)
    try:
        _write_turn(
            conn,
            TurnTrace(
                source="agent",
                session_key="telegram:1",
                user_msg="我好喜欢你",
                llm_output="我也喜欢你。",
                raw_llm_output="我也喜欢你。 <meme:shy>",
                meme_tag="shy",
                meme_media_count=1,
            ),
            "2026-03-27T00:00:00+00:00",
        )
        row = conn.execute(
            """
            select llm_output, raw_llm_output, meme_tag, meme_media_count
            from turns
            where session_key = ?
            """,
            ("telegram:1",),
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == "我也喜欢你。"
    assert row[1] == "我也喜欢你。 <meme:shy>"
    assert row[2] == "shy"
    assert row[3] == 1


def test_write_turn_persists_context_budget_fields(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = open_db(db_path)
    try:
        _write_turn(
            conn,
            TurnTrace(
                source="agent",
                session_key="telegram:1",
                user_msg="你好",
                llm_output="收到",
                history_window=40,
                history_messages=27,
                history_chars=18234,
                history_tokens=6078,
                prompt_tokens=6607,
                next_turn_baseline_tokens=12685,
            ),
            "2026-04-12T00:00:00+00:00",
        )
        row = conn.execute(
            """
            select history_window, history_messages, history_chars,
                   history_tokens, prompt_tokens, next_turn_baseline_tokens
            from turns
            where session_key = ?
            """,
            ("telegram:1",),
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == 40
    assert row[1] == 27
    assert row[2] == 18234
    assert row[3] == 6078
    assert row[4] == 6607
    assert row[5] == 12685


def test_write_turn_persists_react_budget_fields(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = open_db(db_path)
    try:
        _write_turn(
            conn,
            TurnTrace(
                source="agent",
                session_key="telegram:1",
                user_msg="你好",
                llm_output="收到",
                react_iteration_count=3,
                react_input_sum_tokens=42100,
                react_input_peak_tokens=18800,
                react_final_input_tokens=17500,
                react_cache_prompt_tokens=32000,
                react_cache_hit_tokens=18000,
            ),
            "2026-04-12T00:00:00+00:00",
        )
        row = conn.execute(
            """
            select react_iteration_count, react_input_sum_tokens,
                   react_input_peak_tokens, react_final_input_tokens,
                   react_cache_prompt_tokens, react_cache_hit_tokens
            from turns
            where session_key = ?
            """,
            ("telegram:1",),
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == 3
    assert row[1] == 42100
    assert row[2] == 18800
    assert row[3] == 17500
    assert row[4] == 32000
    assert row[5] == 18000


def test_open_db_creates_react_budget_columns(tmp_path):
    conn = open_db(tmp_path / "observe.db")
    try:
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(turns)").fetchall()
        }
    finally:
        conn.close()

    assert "react_iteration_count" in cols
    assert "react_input_sum_tokens" in cols
    assert "react_input_peak_tokens" in cols
    assert "react_final_input_tokens" in cols
    assert "react_cache_prompt_tokens" in cols
    assert "react_cache_hit_tokens" in cols


@pytest.mark.asyncio
async def test_trace_writer_drain_waits_for_rag_query(tmp_path):
    db_path = tmp_path / "observe.db"
    writer = TraceWriter(db_path)
    task = asyncio.create_task(writer.run())
    row = None
    try:
        writer.emit(
            RagQueryLog(
                caller="passive",
                session_key="telegram:1",
                query="改写问题",
                orig_query="原问题",
                aux_queries=[],
                hits=[
                    RagHitLog(
                        item_id="m1",
                        memory_type="event",
                        score=0.9,
                        summary="记忆",
                        injected=True,
                    )
                ],
                injected_count=1,
                route_decision="RETRIEVE",
            )
        )
        await writer.drain()
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                """
                select caller, session_key, query, orig_query, injected_count,
                       route_decision, hits_json
                from rag_queries
                """
            ).fetchone()
        finally:
            conn.close()
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert row is not None
    assert row[0] == "passive"
    assert row[1] == "telegram:1"
    assert row[2] == "改写问题"
    assert row[3] == "原问题"
    assert row[4] == 1
    assert row[5] == "RETRIEVE"
    assert '"id": "m1"' in row[6]


def test_open_db_does_not_create_legacy_rag_tables(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = open_db(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert "rag_queries" in tables
    assert "rag_events" not in tables
    assert "rag_items" not in tables


def test_open_db_removes_legacy_proactive_observe_data(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = sqlite3.connect(str(db_path))
    try:
        with conn:
            conn.executescript(
                """
                create table turns (
                    id integer primary key autoincrement,
                    ts text not null,
                    source text not null,
                    session_key text not null,
                    user_msg text,
                    llm_output text not null default '',
                    error text
                );
                create table proactive_decisions (
                    id integer primary key autoincrement,
                    tick_id text unique,
                    ts text not null,
                    session_key text not null,
                    stage text not null
                );
                insert into turns(ts, source, session_key, user_msg, llm_output)
                values('2026-04-01T00:00:00+00:00', 'agent', 'cli:1', 'hi', 'ok');
                insert into turns(ts, source, session_key, user_msg, llm_output)
                values('2026-04-01T00:01:00+00:00', 'proactive', 'cli:1', '', 'push');
                insert into proactive_decisions(tick_id, ts, session_key, stage)
                values('tick-1', '2026-04-01T00:01:00+00:00', 'cli:1', 'gate');
                """
            )
    finally:
        conn.close()

    conn = open_db(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
        rows = conn.execute("select source, llm_output from turns").fetchall()
    finally:
        conn.close()

    assert "proactive_decisions" not in tables
    assert rows == [("agent", "ok")]


def test_migrate_legacy_rag_tables_moves_events_into_rag_queries(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = sqlite3.connect(str(db_path))
    try:
        with conn:
            conn.executescript(
                """
                create table rag_events (
                    id integer primary key autoincrement,
                    ts text not null,
                    source text not null,
                    session_key text not null,
                    original_query text not null,
                    query text not null,
                    route_decision text,
                    hyde_hypothesis text,
                    error text
                );
                create table rag_items (
                    id integer primary key autoincrement,
                    rag_event_id integer not null references rag_events (id),
                    item_id text not null,
                    memory_type text not null,
                    score real not null,
                    summary text not null,
                    retrieval_path text not null,
                    injected integer not null default 0
                );
                """
            )
            event_id = conn.execute(
                """
                insert into rag_events (
                    ts, source, session_key, original_query, query,
                    route_decision, hyde_hypothesis
                ) values (
                    '2026-04-01T00:00:00+00:00', 'agent', 'cli:1',
                    '原问题', '改写问题', 'RETRIEVE', '假想答案'
                )
                """
            ).lastrowid
            conn.execute(
                """
                insert into rag_items (
                    rag_event_id, item_id, memory_type, score, summary,
                    retrieval_path, injected
                ) values (?, 'm1', 'event', 0.8, '旧记忆', 'history_raw', 1)
                """,
                (event_id,),
            )
    finally:
        conn.close()

    result = migrate_legacy_rag_tables(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            """
            select ts, caller, session_key, query, orig_query,
                   aux_queries, hits_json, injected_count, route_decision
            from rag_queries
            """
        ).fetchone()
        tables = {
            r[0]
            for r in conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert result.migrated_events == 1
    assert result.migrated_hits == 1
    assert row[0] == "2026-04-01T00:00:00+00:00"
    assert row[1] == "passive"
    assert row[2] == "cli:1"
    assert row[3] == "改写问题"
    assert row[4] == "原问题"
    assert json.loads(row[5]) == ["假想答案"]
    assert json.loads(row[6]) == [
        {
            "id": "m1",
            "type": "event",
            "score": 0.8,
            "summary": "旧记忆",
            "injected": True,
        }
    ]
    assert row[7] == 1
    assert row[8] == "RETRIEVE"
    assert "rag_events" not in tables
    assert "rag_items" not in tables


def test_migrate_legacy_rag_tables_is_noop_without_legacy_tables(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = open_db(db_path)
    conn.close()

    result = migrate_legacy_rag_tables(db_path)

    assert result.migrated_events == 0
    assert result.migrated_hits == 0
    assert result.dropped_tables == ()


def test_retention_cleans_rag_queries(tmp_path):
    db_path = tmp_path / "observe.db"
    conn = open_db(db_path)
    try:
        with conn:
            conn.execute(
                """
                insert into rag_queries (
                    ts, caller, session_key, query
                ) values (
                    datetime('now', '-91 days'), 'passive', 'cli:1', '旧问题'
                )
                """
            )
            conn.execute(
                """
                insert into rag_queries (
                    ts, caller, session_key, query, error
                ) values (
                    datetime('now', '-91 days'), 'passive', 'cli:1', '错误问题', 'failed'
                )
                """
            )
    finally:
        conn.close()

    _run_cleanup(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "select query from rag_queries order by query"
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("错误问题",)]
