from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.lifecycle.types import TurnState
from agent.plugins.context import PluginContext, PluginKVStore
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.shell_sandbox_runner import SandboxRunResult
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerEvent,
    ToolAuditLedgerStore,
)
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore
from bus.events import InboundMessage
from plugins.status_commands.plugin import StatusCommands, ToolApprovalCommandModule


@dataclass
class RecordingSandboxRunner:
    called: bool = False

    def backend_name(self) -> str:
        return "podman"

    def run(self, preview, command: str) -> SandboxRunResult:
        self.called = True
        return SandboxRunResult(
            ok=True,
            reason="sandbox_executed",
            exit_code=0,
            stdout_path="stdout.txt",
            stderr_path="stderr.txt",
            stdout_hash="stdout-hash",
            stderr_hash="stderr-hash",
            stdout_bytes=3,
            stderr_bytes=0,
            stdout_truncated=False,
            stderr_truncated=False,
            duration_ms=100,
        )


def _approval_runtime(workspace: Path) -> ToolApprovalRuntime:
    return ToolApprovalRuntime(
        ToolApprovalStore(ToolApprovalRuntime.approval_db_path_from_workspace(workspace)),
        side_effect_vault=SideEffectPayloadVault(
            SideEffectPayloadVault.root_for_workspace(workspace)
        ),
        now_factory=lambda: datetime.now(UTC),
        approval_ttl=timedelta(minutes=15),
    )


async def _run_command(
    module: ToolApprovalCommandModule,
    content: str,
    *,
    session_key: str = "cli:local",
):
    msg = InboundMessage(
        channel="cli",
        sender="user",
        chat_id="local",
        content=content,
        timestamp=datetime(2026, 7, 26, 9, 2, tzinfo=UTC),
    )
    state = TurnState(msg=msg, session_key=session_key, dispatch_outbound=True)
    frame = SimpleNamespace(slots={}, input=state)
    await module.run(frame)
    ctx = frame.slots["session:ctx"]
    assert ctx.abort is True
    assert "raw-secret-content" not in ctx.abort_reply
    return ctx


def _approved_file(
    runtime: ToolApprovalRuntime,
    *,
    tool_name: str = "write_file",
    arguments: dict[str, object] | None = None,
) -> str:
    args = arguments or {"path": "notes.md", "content": "after\n"}
    record = runtime.record_defer_request(
        request_id="call-1",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name=tool_name,
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments=args,
    )
    runtime.record_managed_side_effect_payload(record, arguments=args)
    runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=datetime.now(UTC),
    )
    return record.approval_request_id


@pytest.mark.asyncio
async def test_prepare_and_run_approved_tool_commands_apply_file_change(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    (workspace / "notes.md").write_text("before\n", encoding="utf-8")
    runtime = _approval_runtime(workspace)
    approval_id = _approved_file(runtime)
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
    )

    prepared = await _run_command(module, f"/prepare_tool {approval_id}")
    ran = await _run_command(module, f"/run_approved_tool {approval_id}")

    assert "-before" in prepared.abort_reply
    assert "+after" in prepared.abort_reply
    assert "file_change_applied" in ran.abort_reply
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "after\n"
    assert "approved_side_effect_lifecycle" in ran.extra_metadata


@pytest.mark.asyncio
async def test_rollback_tool_command_restores_snapshot(tmp_path: Path) -> None:
    workspace = tmp_path
    (workspace / "notes.md").write_text("before\n", encoding="utf-8")
    runtime = _approval_runtime(workspace)
    approval_id = _approved_file(runtime)
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
    )
    await _run_command(module, f"/run_approved_tool {approval_id}")

    rolled_back = await _run_command(module, f"/rollback_tool {approval_id}")

    assert "snapshot_restored" in rolled_back.abort_reply
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "before\n"


@pytest.mark.asyncio
async def test_edit_file_commands_apply_and_rollback_file_change(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    (workspace / "notes.md").write_text("alpha\nbeta\n", encoding="utf-8")
    runtime = _approval_runtime(workspace)
    approval_id = _approved_file(
        runtime,
        tool_name="edit_file",
        arguments={
            "path": "notes.md",
            "old_text": "beta\n",
            "new_text": "gamma\n",
        },
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
    )

    prepared = await _run_command(module, f"/prepare_tool {approval_id}")
    ran = await _run_command(module, f"/run_approved_tool {approval_id}")
    rolled_back = await _run_command(module, f"/rollback_tool {approval_id}")

    assert "-beta" in prepared.abort_reply
    assert "+gamma" in prepared.abort_reply
    assert "file_change_applied" in ran.abort_reply
    assert "snapshot_restored" in rolled_back.abort_reply
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "alpha\nbeta\n"


@pytest.mark.asyncio
async def test_run_approved_tool_shell_uses_sandbox_runtime_without_raw_command(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    args = {"command": "echo hi", "description": "say hi"}
    record = runtime.record_defer_request(
        request_id="call-shell",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="shell",
        risk="external-side-effect",
        approval_scope="tool_call",
        policy_reason="risk_strategy_shell_requires_approval",
        arguments=args,
    )
    runtime.record_managed_side_effect_payload(record, arguments=args)
    runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=runtime._now(),
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
        shell_sandbox_runner=RecordingSandboxRunner(),
    )

    ran = await _run_command(module, f"/run_approved_tool {record.approval_request_id}")

    assert "sandbox_executed" in ran.abort_reply
    assert "echo hi" not in ran.abort_reply
    assert "approved_side_effect_lifecycle" in ran.extra_metadata
    encoded_metadata = json.dumps(ran.extra_metadata, ensure_ascii=False)
    assert "echo hi" not in encoded_metadata
    assert "stdout_text" not in encoded_metadata
    assert "stderr_text" not in encoded_metadata
    assert "payload_path" not in encoded_metadata


@pytest.mark.asyncio
async def test_prepare_tool_shell_routes_to_sandbox_runtime_without_raw_command(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    command = "echo prepare-secret-token"
    approval_id = _approved_file(
        runtime,
        tool_name="shell",
        arguments={"command": command, "description": "say hi"},
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
        shell_sandbox_runner=RecordingSandboxRunner(),
    )

    prepared = await _run_command(module, f"/prepare_tool {approval_id}")

    assert "shell_sandbox_preview_ready" in prepared.abort_reply
    assert command not in prepared.abort_reply
    assert command not in json.dumps(prepared.extra_metadata, ensure_ascii=False)


@pytest.mark.asyncio
async def test_run_approved_shell_fails_closed_without_runner_without_raw_command(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    command = "echo unavailable-secret-token"
    approval_id = _approved_file(
        runtime,
        tool_name="shell",
        arguments={"command": command, "description": "say hi"},
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
        shell_sandbox_runner=None,
    )

    ran = await _run_command(module, f"/run_approved_tool {approval_id}")

    assert "shell_sandbox_unavailable" in ran.abort_reply
    assert command not in ran.abort_reply
    assert command not in json.dumps(ran.extra_metadata, ensure_ascii=False)
    assert runtime.store.get_request(approval_id).status == "approved"


@pytest.mark.asyncio
async def test_rollback_tool_shell_is_unsupported_without_raw_command_leakage(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    command = "echo rollback-secret-token"
    args = {"command": command, "description": "say hi"}
    record = runtime.record_defer_request(
        request_id="call-shell-rollback",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="shell",
        risk="external-side-effect",
        approval_scope="tool_call",
        policy_reason="risk_strategy_shell_requires_approval",
        arguments=args,
    )
    runtime.record_managed_side_effect_payload(record, arguments=args)
    runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=runtime._now(),
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
        shell_sandbox_runner=RecordingSandboxRunner(),
    )

    await _run_command(module, f"/run_approved_tool {record.approval_request_id}")
    rolled_back = await _run_command(
        module, f"/rollback_tool {record.approval_request_id}"
    )

    assert "rollback_not_supported_for_shell" in rolled_back.abort_reply
    assert command not in rolled_back.abort_reply
    assert command not in json.dumps(rolled_back.extra_metadata, ensure_ascii=False)


@pytest.mark.asyncio
async def test_tool_audit_command_lists_current_session_events(tmp_path: Path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    ledger.record_event(
        ToolAuditLedgerEvent(
            event_type="tool_invocation_policy_decision",
            session_key="cli:s",
            request_id="call-1",
            tool_name="write_file",
            policy_action="defer",
            policy_reason="risk_strategy_write_requires_approval",
        )
    )
    ledger.record_event(
        ToolAuditLedgerEvent(
            event_type="tool_invocation_policy_decision",
            session_key="cli:other",
            request_id="call-2",
            tool_name="shell",
            policy_action="defer",
            policy_reason="risk_strategy_shell_requires_approval",
        )
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        ToolApprovalStore(tmp_path / "approvals.db"),
        audit_ledger_store=ledger,
    )

    ctx = await _run_command(module, "/tool_audit 10", session_key="cli:s")
    reply = ctx.abort_reply

    assert "tool_invocation_policy_decision" in reply
    assert "write_file" in reply
    assert "call-1" in reply
    assert "call-2" not in reply


@pytest.mark.asyncio
async def test_tool_audit_command_never_prints_raw_metadata(tmp_path: Path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    ledger.record_event(
        ToolAuditLedgerEvent(
            event_type="approved_shell_sandbox_executed",
            session_key="cli:s",
            tool_name="shell",
            metadata={"command": "echo secret", "command_hash": "abc"},
        )
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        ToolApprovalStore(tmp_path / "approvals.db"),
        audit_ledger_store=ledger,
    )

    ctx = await _run_command(module, "/tool_audit tool shell 5", session_key="cli:s")
    reply = ctx.abort_reply

    assert "command_hash" in reply
    assert "abc" in reply
    assert "echo secret" not in reply


@pytest.mark.asyncio
async def test_tool_audit_command_filters_request_approval_and_event_with_session_scope(
    tmp_path: Path,
) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    ledger.record_event(
        ToolAuditLedgerEvent(
            event_type="tool_approval_requested",
            session_key="cli:s",
            request_id="call-1",
            approval_request_id="approval-1",
            tool_name="write_file",
        )
    )
    ledger.record_event(
        ToolAuditLedgerEvent(
            event_type="tool_approval_requested",
            session_key="cli:other",
            request_id="call-1",
            approval_request_id="approval-other",
            tool_name="shell",
        )
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        ToolApprovalStore(tmp_path / "approvals.db"),
        audit_ledger_store=ledger,
    )

    request_reply = (
        await _run_command(module, "/tool_audit request call-1", session_key="cli:s")
    ).abort_reply
    approval_reply = (
        await _run_command(
            module, "/tool_audit approval approval-1", session_key="cli:s"
        )
    ).abort_reply
    event_reply = (
        await _run_command(
            module,
            "/tool_audit event tool_approval_requested 10",
            session_key="cli:s",
        )
    ).abort_reply

    assert "approval-1" in request_reply
    assert "approval-other" not in request_reply
    assert "approval-1" in approval_reply
    assert "approval-other" not in approval_reply
    assert "tool_approval_requested" in event_reply
    assert "approval-other" not in event_reply


def test_status_commands_plugin_wires_workspace_tool_audit_ledger(
    tmp_path: Path,
) -> None:
    plugin = StatusCommands()
    plugin.context = PluginContext(
        event_bus=None,
        tool_registry=None,
        plugin_id="status_commands",
        plugin_dir=tmp_path,
        kv_store=PluginKVStore(tmp_path / "kv.json"),
        workspace=tmp_path,
    )

    modules = plugin.before_turn_modules()
    approval_module = next(
        module for module in modules if isinstance(module, ToolApprovalCommandModule)
    )

    assert approval_module._audit_ledger_store is not None
    assert (
        approval_module._audit_ledger_store.db_path
        == ToolAuditLedgerStore.db_path_from_workspace(tmp_path)
    )
