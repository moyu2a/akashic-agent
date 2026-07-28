from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent.policies.approved_side_effect_store import ApprovedSideEffectStore


def test_side_effect_store_tracks_payload_preview_execute_and_rollback(
    tmp_path: Path,
) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")

    payload = store.record_payload(
        approval_request_id="approval-1",
        request_id="call-1",
        session_key="cli:test",
        tool_name="write_file",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )
    preview = store.record_preview(
        approval_request_id="approval-1",
        preview_id="preview-1",
        target_path_hash="path-hash",
        before_hash="before",
        after_hash="after",
        diff_ref="artifacts/preview-1/change.diff",
        diff_truncated=False,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
    )
    executed = store.mark_executed(
        approval_request_id="approval-1",
        rollback_id="rollback-1",
        execution_status="executed",
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 2, tzinfo=UTC),
    )
    rolled_back = store.mark_rolled_back(
        approval_request_id="approval-1",
        rollback_status="rolled_back",
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 3, tzinfo=UTC),
    )

    assert payload.status == "payload_recorded"
    assert preview.status == "preview_ready"
    assert executed.status == "executed"
    assert rolled_back.status == "rolled_back"
    assert store.get_by_approval_id("approval-1").status == "rolled_back"
    events = store.list_audit_events("approval-1")
    assert [event.event_type for event in events] == [
        "payload_recorded",
        "preview_ready",
        "executed",
        "rolled_back",
    ]


def test_side_effect_store_does_not_store_raw_arguments(tmp_path: Path) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")
    store.record_payload(
        approval_request_id="approval-1",
        request_id="call-1",
        session_key="cli:test",
        tool_name="write_file",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )

    raw_db = (tmp_path / "side_effects.db").read_bytes()

    assert b"raw-secret-content" not in raw_db
    assert b"payloads/approval-1.json" in raw_db


def test_side_effect_store_tracks_shell_preview_and_execution_without_raw_command(
    tmp_path: Path,
) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")
    store.record_payload(
        approval_request_id="approval-shell-1",
        request_id="call-shell-1",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-shell-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )

    store.record_shell_preview(
        approval_request_id="approval-shell-1",
        preview_id="shell-preview-1",
        command_hash="command-hash",
        sandbox_backend="podman",
        sandbox_image="python:3.14-slim",
        sandbox_user="65532:65532",
        sandbox_memory_limit="512m",
        sandbox_cpus="1.0",
        sandbox_pids_limit=128,
        network_mode="none",
        workspace_mount_mode="ro",
        timeout_seconds=30,
        background_requested=False,
        background_allowed=False,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
    )
    record = store.mark_shell_executed(
        approval_request_id="approval-shell-1",
        execution_status="sandbox_executed",
        exit_code=0,
        stdout_ref="artifacts/stdout.txt",
        stderr_ref="artifacts/stderr.txt",
        stdout_hash="stdout-hash",
        stderr_hash="stderr-hash",
        stdout_bytes=5,
        stderr_bytes=0,
        stdout_truncated=False,
        stderr_truncated=False,
        duration_ms=120,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 2, tzinfo=UTC),
    )

    assert record.status == "executed"
    assert record.command_hash == "command-hash"
    assert record.sandbox_backend == "podman"
    assert record.exit_code == 0
    raw_db = (tmp_path / "side_effects.db").read_bytes()
    assert b"pytest tests" not in raw_db
    assert [event.event_type for event in store.list_audit_events("approval-shell-1")] == [
        "payload_recorded",
        "shell_preview_ready",
        "shell_executed",
    ]


def test_side_effect_store_persists_shell_backend_basename(
    tmp_path: Path,
) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")
    store.record_payload(
        approval_request_id="approval-shell-1",
        request_id="call-shell-1",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-shell-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )

    record = store.record_shell_preview(
        approval_request_id="approval-shell-1",
        preview_id="shell-preview-1",
        command_hash="command-hash",
        sandbox_backend="/usr/bin/podman",
        sandbox_image="python:3.14-slim",
        sandbox_user="65532:65532",
        sandbox_memory_limit="512m",
        sandbox_cpus="1.0",
        sandbox_pids_limit=128,
        network_mode="none",
        workspace_mount_mode="ro",
        timeout_seconds=30,
        background_requested=False,
        background_allowed=False,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
    )

    assert record.sandbox_backend == "podman"
    assert store.get_by_approval_id("approval-shell-1").sandbox_backend == "podman"


@pytest.mark.parametrize("sandbox_backend", ["/tmp/custom-runtime", "nerdctl"])
def test_side_effect_store_rejects_unsupported_shell_backend_before_update(
    tmp_path: Path, sandbox_backend: str
) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")
    store.record_payload(
        approval_request_id="approval-shell-1",
        request_id="call-shell-1",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-shell-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="sandbox backend"):
        store.record_shell_preview(
            approval_request_id="approval-shell-1",
            preview_id="shell-preview-1",
            command_hash="command-hash",
            sandbox_backend=sandbox_backend,
            sandbox_image="python:3.14-slim",
            sandbox_user="65532:65532",
            sandbox_memory_limit="512m",
            sandbox_cpus="1.0",
            sandbox_pids_limit=128,
            network_mode="none",
            workspace_mount_mode="ro",
            timeout_seconds=30,
            background_requested=False,
            background_allowed=False,
            actor="status_command",
            now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
        )

    record = store.get_by_approval_id("approval-shell-1")
    assert record is not None
    assert record.status == "payload_recorded"
    assert record.sandbox_backend == ""
    assert [event.event_type for event in store.list_audit_events("approval-shell-1")] == [
        "payload_recorded"
    ]


def test_side_effect_store_migrates_p4a_database_for_shell_metadata(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "side_effects.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE approved_side_effects (
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
        )
        conn.execute(
            """
            CREATE TABLE approved_side_effect_audit_events (
                event_id TEXT PRIMARY KEY,
                approval_request_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO approved_side_effects (
                approval_request_id, request_id, session_key, tool_name,
                approval_scope, args_hash, status, payload_ref, created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "approval-file-1",
                "call-file-1",
                "cli:test",
                "write_file",
                "tool_call",
                "file-hash",
                "payload_recorded",
                "payloads/approval-file-1.json",
                "2026-07-26T09:00:00+00:00",
                "2026-07-26T09:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    migrated = ApprovedSideEffectStore(db_path)
    migrated.record_payload(
        approval_request_id="approval-shell-1",
        request_id="call-shell-1",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-shell-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
    )
    record = migrated.record_shell_preview(
        approval_request_id="approval-shell-1",
        preview_id="shell-preview-1",
        command_hash="command-hash",
        sandbox_backend="podman",
        sandbox_image="python:3.14-slim",
        sandbox_user="65532:65532",
        sandbox_memory_limit="512m",
        sandbox_cpus="1.0",
        sandbox_pids_limit=128,
        network_mode="none",
        workspace_mount_mode="ro",
        timeout_seconds=30,
        background_requested=False,
        background_allowed=False,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 2, tzinfo=UTC),
    )

    assert record.command_hash == "command-hash"


@pytest.mark.parametrize("artifact_ref", ["/tmp/stdout.txt", "artifacts/../stdout.txt"])
def test_side_effect_store_rejects_out_of_tree_shell_artifact_refs(
    tmp_path: Path, artifact_ref: str
) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")
    store.record_payload(
        approval_request_id="approval-shell-1",
        request_id="call-shell-1",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-shell-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="tool_side_effects/artifacts"):
        store.mark_shell_executed(
            approval_request_id="approval-shell-1",
            execution_status="sandbox_executed",
            exit_code=0,
            stdout_ref=artifact_ref,
            stderr_ref="artifacts/stderr.txt",
            stdout_hash="stdout-hash",
            stderr_hash="stderr-hash",
            stdout_bytes=5,
            stderr_bytes=0,
            stdout_truncated=False,
            stderr_truncated=False,
            duration_ms=120,
            actor="status_command",
            now=datetime(2026, 7, 26, 9, 2, tzinfo=UTC),
        )
