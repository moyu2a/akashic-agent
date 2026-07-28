from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.policies.approved_side_effect_runtime import ApprovedSideEffectRuntime
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerQuery,
    ToolAuditLedgerStore,
)
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore


def _runtime(
    workspace: Path,
    *,
    audit_ledger_store=None,
) -> ApprovedSideEffectRuntime:
    approval_runtime = ToolApprovalRuntime(
        ToolApprovalStore(ToolApprovalRuntime.approval_db_path_from_workspace(workspace)),
        side_effect_vault=SideEffectPayloadVault(
            SideEffectPayloadVault.root_for_workspace(workspace)
        ),
        audit_ledger_store=audit_ledger_store,
        now_factory=lambda: datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        approval_ttl=timedelta(minutes=15),
    )
    return ApprovedSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        audit_ledger_store=audit_ledger_store,
    )


def _defer_and_approve(runtime: ApprovedSideEffectRuntime) -> str:
    approval = runtime.approval_runtime.record_defer_request(
        request_id="call-1",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"path": "notes.md", "content": "after\n"},
    )
    runtime.approval_runtime.record_managed_side_effect_payload(
        approval,
        arguments={"path": "notes.md", "content": "after\n"},
    )
    runtime.approval_runtime.store.approve_request(
        approval_request_id=approval.approval_request_id,
        request_id=approval.request_id,
        session_key=approval.session_key,
        tool_name=approval.tool_name,
        approval_scope=approval.approval_scope,
        args_hash=approval.args_hash,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
    )
    return approval.approval_request_id


def test_runtime_prepare_apply_and_rollback_file_write(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.md").write_text("before\n", encoding="utf-8")
    runtime = _runtime(workspace)
    approval_id = _defer_and_approve(runtime)

    prepared = runtime.prepare(
        approval_request_id=approval_id,
        session_key="cli:test",
        actor="status_command",
        workspace_root=workspace,
        resource_roots=(str(workspace),),
    )
    applied = runtime.apply(
        approval_request_id=approval_id,
        session_key="cli:test",
        actor="status_command",
        workspace_root=workspace,
        resource_roots=(str(workspace),),
    )
    assert applied.ok is True
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "after\n"

    rolled_back = runtime.rollback(
        approval_request_id=approval_id,
        session_key="cli:test",
        actor="status_command",
        workspace_root=workspace,
        resource_roots=(str(workspace),),
    )

    assert prepared.ok is True
    assert "-before" in prepared.diff_text
    assert rolled_back.ok is True
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "before\n"
    assert runtime.approval_runtime.store.get_request(approval_id).status == "executed"


def test_runtime_rejects_shell_even_when_approved(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime = _runtime(workspace)
    record = runtime.approval_runtime.record_defer_request(
        request_id="shell-call",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        source="passive",
        tool_name="shell",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_shell_requires_approval",
        arguments={"command": "echo hi"},
    )
    runtime.approval_runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
    )

    prepared = runtime.prepare(
        approval_request_id=record.approval_request_id,
        session_key="cli:test",
        actor="status_command",
        workspace_root=workspace,
        resource_roots=(str(workspace),),
    )

    assert prepared.ok is False
    assert prepared.reason == "managed_side_effect_tool_unsupported"


class _FailingLedger:
    def record_event(self, _event):
        raise RuntimeError("ledger down")


def test_file_side_effect_runtime_ledger_failure_does_not_change_result(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.md").write_text("before\n", encoding="utf-8")
    runtime = _runtime(workspace, audit_ledger_store=_FailingLedger())
    approval_id = _defer_and_approve(runtime)

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    applied = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    rolled_back = runtime.rollback(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert prepared.ok is True
    assert applied.ok is True
    assert rolled_back.ok is True
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "before\n"


def test_file_side_effect_runtime_records_preview_execute_and_rollback(
    tmp_path: Path,
) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.md").write_text("before\n", encoding="utf-8")
    runtime = _runtime(workspace, audit_ledger_store=ledger)
    approval_id = _defer_and_approve(runtime)

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    applied = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    rolled_back = runtime.rollback(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert prepared.ok is True
    assert applied.ok is True
    assert rolled_back.ok is True
    events = ledger.query_events(ToolAuditLedgerQuery(approval_request_id=approval_id, limit=20))
    event_types = {event.event_type for event in events}
    assert "approved_side_effect_payload_recorded" in event_types
    assert "approved_side_effect_preview_ready" in event_types
    assert "approved_side_effect_executed" in event_types
    assert "approved_side_effect_rolled_back" in event_types
    assert all("payload_ref" not in event.metadata for event in events)
