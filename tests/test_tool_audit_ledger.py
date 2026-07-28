from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerEvent,
    ToolAuditLedgerQuery,
    ToolAuditLedgerStore,
    record_tool_audit_event_fail_open,
    sanitize_tool_audit_metadata,
)


def _event(**overrides: object) -> ToolAuditLedgerEvent:
    values = {
        "created_at": datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
        "event_type": "tool_invocation_policy_decision",
        "session_key": "cli:one",
        "request_id": "call-1",
        "tool_name": "write_file",
        "source": "passive",
        "risk": "write",
        "policy_action": "defer",
        "policy_reason": "risk_strategy_write_requires_approval",
        "args_hash": "hash-1",
        "metadata": {"resource_type": "workspace"},
    }
    values.update(overrides)
    return ToolAuditLedgerEvent(**values)


def test_ledger_records_and_queries_by_core_fields(tmp_path) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")
    assert store._connect().execute("PRAGMA user_version").fetchone()[0] == 1
    recorded = store.record_event(_event(approval_request_id="approval-1"))
    store.record_event(
        _event(
            request_id="call-2",
            approval_request_id="approval-2",
            tool_name="shell",
            event_type="tool_approval_consumed",
        )
    )

    assert recorded.event_id
    assert store.query_events(ToolAuditLedgerQuery(session_key="cli:one", limit=10))[0].event_id
    assert [event.request_id for event in store.query_events(ToolAuditLedgerQuery(request_id="call-1"))] == ["call-1"]
    assert [event.approval_request_id for event in store.query_events(ToolAuditLedgerQuery(approval_request_id="approval-2"))] == ["approval-2"]
    assert [event.tool_name for event in store.query_events(ToolAuditLedgerQuery(tool_name="shell"))] == ["shell"]
    assert [event.event_type for event in store.query_events(ToolAuditLedgerQuery(event_type="tool_approval_consumed"))] == ["tool_approval_consumed"]


def test_ledger_sanitizes_metadata_allowlist(tmp_path) -> None:
    metadata = sanitize_tool_audit_metadata(
        {
            "resource_type": "workspace",
            "exit_code": 2,
            "stdout_hash": "a" * 64,
            "command": "rm -rf secret",
            "path": "/tmp/secret.txt",
            "content": "secret body",
            "payload_path": "/vault/payload.json",
            "authorization": "Bearer secret",
            "cookie": "session=secret",
            "nested": {"token": "secret"},
        }
    )
    assert metadata == {
        "resource_type": "workspace",
        "exit_code": 2,
        "stdout_hash": "a" * 64,
    }

    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")
    store.record_event(_event(metadata=metadata))
    raw = store._connect().execute("SELECT metadata_json FROM tool_audit_events").fetchone()[0]
    serialized = json.dumps(json.loads(raw), sort_keys=True)
    assert "rm -rf" not in serialized
    assert "secret.txt" not in serialized
    assert "secret body" not in serialized
    assert "Bearer secret" not in serialized


def test_ledger_rejects_sensitive_values_even_under_allowlisted_keys(tmp_path) -> None:
    metadata = sanitize_tool_audit_metadata(
        {
            "stdout_ref": "/tmp/raw-output.txt",
            "stderr_ref": "../payloads/stderr.txt",
            "preview_id": "preview_../../secret",
            "rollback_id": "rollback_/tmp/secret",
            "command_hash": "echo raw-secret",
            "stdout_hash": "Bearer token-secret",
            "resource_decision": "https://example.test/path?token=secret",
            "resource_type": "credentials/token.txt",
            "error_code": "raw stdout account 1234",
            "sandbox_backend": "printf private data",
            "sandbox_image": "python:3.11",
            "timeout_seconds": 30,
        }
    )
    assert metadata == {
        "sandbox_image": "python:3.11",
        "timeout_seconds": 30,
    }


def test_ledger_sanitizes_unsafe_top_level_fields_and_preserves_safe_refs(
    tmp_path,
) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")

    store.record_event(
        ToolAuditLedgerEvent(
            event_type="tool_approval_requested; cat /tmp/secret",
            session_key="ghp_AbCd1234567890",
            request_id="../payloads/raw-args.json",
            tool_name="write_file",
            policy_action="defer",
            policy_reason="Bearer token-secret",
            approval_request_id="approval-1",
            approval_status="Bearer_token_secret",
            side_effect_status="raw stdout account 1234",
            execution_status="root",
            metadata={
                "stdout_ref": "artifacts/preview-1/stdout.txt",
                "stderr_ref": "artifacts/preview-1/stderr.txt",
                "rollback_id": "home/user/data",
                "error_code": "raw stdout account 1234",
                "sandbox_backend": "printf private data",
                "stdout_hash": "stdout-hash",
                "stderr_hash": "sk-proj-AbCd1234567890-hash",
            },
        )
    )

    event = store.query_events(ToolAuditLedgerQuery(limit=1))[0]
    raw = store.db_path.read_text(encoding="utf-8", errors="ignore")
    assert event.event_type == ""
    assert event.session_key == ""
    assert event.request_id == ""
    assert event.policy_reason == ""
    assert event.approval_status == ""
    assert event.side_effect_status == ""
    assert event.execution_status == ""
    assert event.metadata == {
        "stderr_ref": "artifacts/preview-1/stderr.txt",
        "stdout_hash": "stdout-hash",
        "stdout_ref": "artifacts/preview-1/stdout.txt",
    }
    assert "cat /tmp/secret" not in raw
    assert "../payloads/raw-args.json" not in raw
    assert "Bearer token-secret" not in raw
    assert "Bearer_token_secret" not in raw
    assert "ghp_AbCd1234567890" not in raw
    assert "sk-proj-AbCd1234567890" not in raw
    assert "raw stdout account" not in raw
    assert "printf private data" not in raw
    assert "home/user/data" not in raw


def test_ledger_rejects_credential_prefixes_in_generic_metadata_and_ids(tmp_path) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")

    store.record_event(
        _event(
            metadata={
                "resource_type": "ghp_AbCd1234567890",
                "resource_decision": "sk-proj-AbCd1234567890",
                "sandbox_backend": "cred_live_AbCd1234567890",
                "preview_id": "ghp_AbCd1234567890",
                "rollback_id": "sk-proj-AbCd1234567890",
                "error_code": "cred_live_AbCd1234567890",
            },
        )
    )

    event = store.query_events(ToolAuditLedgerQuery(limit=1))[0]
    raw = store.db_path.read_text(encoding="utf-8", errors="ignore")
    assert event.metadata == {}
    assert "ghp_AbCd1234567890" not in raw
    assert "sk-proj-AbCd1234567890" not in raw
    assert "cred_live_AbCd1234567890" not in raw


def test_ledger_preserves_valid_short_channels_model_actor_and_proactive_source(
    tmp_path,
) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")

    store.record_event(
        _event(
            channel="cli",
            chat_id="test",
            source="proactive",
            actor="model",
        )
    )

    event = store.query_events(ToolAuditLedgerQuery(limit=1))[0]
    assert event.channel == "cli"
    assert event.chat_id == "test"
    assert event.source == "proactive"
    assert event.actor == "model"


def test_ledger_preserves_current_file_and_shell_lifecycle_statuses(tmp_path) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")

    for index, status in enumerate(
        (
            "snapshot_conflict",
            "created_file_removed",
            "sandbox_exit_nonzero",
            "shell_sandbox_image_unavailable",
            "shell_sandbox_launch_failed",
            "shell_sandbox_policy_invalid",
            "shell_artifact_path_invalid",
        )
    ):
        store.record_event(
            _event(
                request_id=f"call-status-{index}",
                execution_status=status,
                rollback_status=status,
                side_effect_status=status,
            )
        )

    events = store.query_events(ToolAuditLedgerQuery(limit=20))
    by_request = {event.request_id: event for event in events}
    assert by_request["call-status-0"].execution_status == "snapshot_conflict"
    assert by_request["call-status-1"].rollback_status == "created_file_removed"
    assert by_request["call-status-2"].execution_status == "sandbox_exit_nonzero"
    assert by_request["call-status-3"].execution_status == "shell_sandbox_image_unavailable"
    assert by_request["call-status-4"].execution_status == "shell_sandbox_launch_failed"
    assert by_request["call-status-5"].execution_status == "shell_sandbox_policy_invalid"
    assert by_request["call-status-6"].execution_status == "shell_artifact_path_invalid"


def test_ledger_preserves_canonical_hashes_and_rejects_noncanonical_refs(tmp_path) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")
    args_hash = "0" * 64

    store.record_event(
        _event(
            args_hash=args_hash,
            metadata={
                "stdout_ref": "artifacts/preview-1/stdout.txt",
                "stderr_ref": "artifacts/preview-1/stderr.txt",
                "rollback_id": "rollback-1",
                "stdout_hash": "a" * 64,
                "stderr_hash": "b" * 64,
            },
        )
    )
    store.record_event(
        _event(
            request_id="call-bad-ref",
            metadata={
                "stdout_ref": "artifacts/preview-1/stdout.txt/",
                "stderr_ref": "artifacts/preview-1//stderr.txt",
                "rollback_id": "home/user/data",
            },
        )
    )

    events = store.query_events(ToolAuditLedgerQuery(session_key="cli:one", limit=10))
    valid = next(event for event in events if event.args_hash == args_hash)
    invalid = next(event for event in events if event.request_id == "call-bad-ref")
    assert valid.metadata == {
        "rollback_id": "rollback-1",
        "stderr_hash": "b" * 64,
        "stderr_ref": "artifacts/preview-1/stderr.txt",
        "stdout_hash": "a" * 64,
        "stdout_ref": "artifacts/preview-1/stdout.txt",
    }
    assert invalid.metadata == {}


class _FailingLedger:
    def record_event(self, _event: ToolAuditLedgerEvent) -> ToolAuditLedgerEvent:
        raise RuntimeError("ledger down")


def test_record_event_fail_open_logs_and_returns_none(caplog) -> None:
    caplog.set_level(logging.WARNING)

    recorded = record_tool_audit_event_fail_open(
        _FailingLedger(),
        _event(),
        logging.getLogger("tests.tool_audit_ledger"),
    )

    assert recorded is None
    assert "failed to record tool audit event" in caplog.text


def test_ledger_enforces_limit_and_prunes(tmp_path) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")
    base = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    for index in range(6):
        store.record_event(_event(created_at=base + timedelta(minutes=index), request_id=f"call-{index}"))

    assert len(store.query_events(ToolAuditLedgerQuery(limit=500))) == 6
    assert [event.request_id for event in store.query_events(ToolAuditLedgerQuery(limit=2))] == ["call-5", "call-4"]
    assert store.prune(before=base + timedelta(minutes=2), max_rows=None) == 2
    assert len(store.query_events(ToolAuditLedgerQuery(limit=20))) == 4
    assert store.prune(before=None, max_rows=2) == 2
    assert [event.request_id for event in store.query_events(ToolAuditLedgerQuery(limit=20))] == ["call-5", "call-4"]
