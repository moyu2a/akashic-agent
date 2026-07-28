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
            "stdout_hash": "abc",
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
        "stdout_hash": "abc",
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
            "error_code": "ls -la /private",
            "sandbox_image": "python:3.11",
            "timeout_seconds": 30,
        }
    )
    assert metadata == {
        "sandbox_image": "python:3.11",
        "timeout_seconds": 30,
    }


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
