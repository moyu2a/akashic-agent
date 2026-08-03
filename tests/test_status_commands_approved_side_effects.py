from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.core.response_parser import ResponseMetadata
from agent.lifecycle.types import AfterReasoningCtx, AfterReasoningInput
from agent.lifecycle.types import TurnState
from agent.plugins.context import PluginContext, PluginKVStore
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.shell_sandbox_runner import SandboxRunResult
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerEvent,
    ToolAuditLedgerQuery,
    ToolAuditLedgerStore,
)
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore
from agent.tool_hooks import ToolExecutionRequest, ToolExecutor
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from bus.events import InboundMessage
from plugins.status_commands.plugin import (
    ApprovalReminderAfterReasoningModule,
    StatusCommands,
    ToolApprovalCommandModule,
)


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


class RecordingPluginWriteTool(Tool):
    name = "save_content_item"
    description = "save a content item"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["url"],
    }

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs):
        self.calls.append(dict(kwargs))
        return json.dumps(
            {"status": "created", "url": kwargs.get("url", "")},
            ensure_ascii=False,
        )


def _approval_runtime(workspace: Path) -> ToolApprovalRuntime:
    return ToolApprovalRuntime(
        ToolApprovalStore(
            ToolApprovalRuntime.approval_db_path_from_workspace(workspace)
        ),
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


async def _run_command_frame(
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
    return await module.run(frame)


async def _run_approval_reminder(
    module: ApprovalReminderAfterReasoningModule,
    *,
    session,
    reply: str,
    tool_chain: tuple[dict[str, object], ...] = (),
) -> AfterReasoningCtx:
    msg = InboundMessage(
        channel="cli",
        sender="user",
        chat_id="local",
        content="普通对话",
        timestamp=datetime(2026, 7, 26, 9, 2, tzinfo=UTC),
    )
    state = TurnState(msg=msg, session_key=session.key, dispatch_outbound=True)
    state.session = session
    ctx = AfterReasoningCtx(
        session_key=session.key,
        channel="cli",
        chat_id="local",
        tools_used=(),
        thinking=None,
        response_metadata=ResponseMetadata(raw_text=reply),
        streamed=False,
        tool_chain=tool_chain,
        context_retry={},
        reply=reply,
    )
    frame = SimpleNamespace(
        slots={"reasoning:ctx": ctx},
        input=AfterReasoningInput(state=state, turn_result=SimpleNamespace()),
    )
    await module.run(frame)
    return frame.slots["reasoning:ctx"]


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
async def test_run_approved_tool_executes_approved_non_managed_write_plugin_tool(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    registry = ToolRegistry()
    tool = RecordingPluginWriteTool()
    registry.register(tool, risk="write")
    registry.set_context(channel="cli", chat_id="local", session_key="cli:local")
    arguments = {
        "url": "https://www.bilibili.com/video/BV1DEgZ6rE6y/",
        "note": "raw-secret-content",
    }
    metadata = registry.get_invocation_metadata("save_content_item")

    async def invoke(tool_name: str, args: dict[str, object]) -> object:
        return await registry.execute(tool_name, args)

    deferred = await ToolExecutor(approval_runtime=runtime).execute(
        ToolExecutionRequest(
            call_id="call-plugin-write",
            tool_name="save_content_item",
            arguments=arguments,
            source="passive",
            session_key="cli:local",
            channel="cli",
            chat_id="local",
            registered=bool(metadata["registered"]),
            registry_risk=str(metadata["registry_risk"]),
            registry_capabilities=metadata["registry_capabilities"],
        ),
        invoke,
    )
    approval_id = json.loads(deferred.output)["approval_request"]["approval_request_id"]
    runtime.store.approve_request(
        approval_request_id=approval_id,
        request_id="call-plugin-write",
        session_key="cli:local",
        tool_name="save_content_item",
        approval_scope="tool_call",
        args_hash=runtime.store.get_request(approval_id).args_hash,
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
        tool_registry=registry,
    )

    ran = await _run_command(module, f"/run_approved_tool {approval_id}")

    assert "created" in ran.abort_reply
    assert tool.calls == [
        {
            "channel": "cli",
            "chat_id": "local",
            "session_key": "cli:local",
            "url": "https://www.bilibili.com/video/BV1DEgZ6rE6y/",
            "note": "raw-secret-content",
        }
    ]
    assert runtime.store.get_request(approval_id).status == "executed"
    assert "raw-secret-content" not in ran.abort_reply
    assert b"raw-secret-content" not in (
        ToolApprovalRuntime.approval_db_path_from_workspace(workspace).read_bytes()
    )


@pytest.mark.asyncio
async def test_approve_last_approves_and_executes_latest_plugin_write_tool(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    registry = ToolRegistry()
    tool = RecordingPluginWriteTool()
    registry.register(tool, risk="write")
    registry.set_context(channel="cli", chat_id="local", session_key="cli:local")
    metadata = registry.get_invocation_metadata("save_content_item")

    async def invoke(tool_name: str, args: dict[str, object]) -> object:
        return await registry.execute(tool_name, args)

    first = await ToolExecutor(approval_runtime=runtime).execute(
        ToolExecutionRequest(
            call_id="call-plugin-write-1",
            tool_name="save_content_item",
            arguments={
                "url": "https://www.bilibili.com/video/BV111/",
                "note": "first-secret-content",
            },
            source="passive",
            session_key="cli:local",
            channel="cli",
            chat_id="local",
            registered=bool(metadata["registered"]),
            registry_risk=str(metadata["registry_risk"]),
            registry_capabilities=metadata["registry_capabilities"],
        ),
        invoke,
    )
    second = await ToolExecutor(approval_runtime=runtime).execute(
        ToolExecutionRequest(
            call_id="call-plugin-write-2",
            tool_name="save_content_item",
            arguments={
                "url": "https://www.bilibili.com/video/BV222/",
                "note": "latest-secret-content",
            },
            source="passive",
            session_key="cli:local",
            channel="cli",
            chat_id="local",
            registered=bool(metadata["registered"]),
            registry_risk=str(metadata["registry_risk"]),
            registry_capabilities=metadata["registry_capabilities"],
        ),
        invoke,
    )
    first_id = json.loads(first.output)["approval_request"]["approval_request_id"]
    second_id = json.loads(second.output)["approval_request"]["approval_request_id"]
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
        tool_registry=registry,
    )

    ran = await _run_command(module, "/approve_last")

    assert "save_content_item" in ran.abort_reply
    assert "created" in ran.abort_reply
    assert tool.calls == [
        {
            "channel": "cli",
            "chat_id": "local",
            "session_key": "cli:local",
            "url": "https://www.bilibili.com/video/BV222/",
            "note": "latest-secret-content",
        }
    ]
    assert runtime.store.get_request(first_id).status == "pending"
    assert runtime.store.get_request(second_id).status == "executed"
    assert "latest-secret-content" not in ran.abort_reply


@pytest.mark.asyncio
async def test_numeric_choice_approves_and_executes_latest_plugin_write_tool(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    registry = ToolRegistry()
    tool = RecordingPluginWriteTool()
    registry.register(tool, risk="write")
    registry.set_context(channel="cli", chat_id="local", session_key="cli:local")
    metadata = registry.get_invocation_metadata("save_content_item")

    async def invoke(tool_name: str, args: dict[str, object]) -> object:
        return await registry.execute(tool_name, args)

    deferred = await ToolExecutor(approval_runtime=runtime).execute(
        ToolExecutionRequest(
            call_id="call-plugin-write-choice",
            tool_name="save_content_item",
            arguments={
                "url": "https://www.bilibili.com/video/BV333/",
                "note": "choice-secret-content",
            },
            source="passive",
            session_key="cli:local",
            channel="cli",
            chat_id="local",
            registered=bool(metadata["registered"]),
            registry_risk=str(metadata["registry_risk"]),
            registry_capabilities=metadata["registry_capabilities"],
        ),
        invoke,
    )
    approval_id = json.loads(deferred.output)["approval_request"]["approval_request_id"]
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
        tool_registry=registry,
    )

    ran = await _run_command(module, "1")

    assert "save_content_item" in ran.abort_reply
    assert "created" in ran.abort_reply
    assert tool.calls == [
        {
            "channel": "cli",
            "chat_id": "local",
            "session_key": "cli:local",
            "url": "https://www.bilibili.com/video/BV333/",
            "note": "choice-secret-content",
        }
    ]
    assert runtime.store.get_request(approval_id).status == "executed"
    assert "choice-secret-content" not in ran.abort_reply


@pytest.mark.asyncio
async def test_numeric_choice_approves_first_pending_plugin_write_tool(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    registry = ToolRegistry()
    tool = RecordingPluginWriteTool()
    registry.register(tool, risk="write")
    registry.set_context(channel="cli", chat_id="local", session_key="cli:local")
    metadata = registry.get_invocation_metadata("save_content_item")

    async def invoke(tool_name: str, args: dict[str, object]) -> object:
        return await registry.execute(tool_name, args)

    first = await ToolExecutor(approval_runtime=runtime).execute(
        ToolExecutionRequest(
            call_id="call-plugin-write-first",
            tool_name="save_content_item",
            arguments={
                "url": "https://www.bilibili.com/video/BV-FIRST/",
                "note": "first-choice-content",
            },
            source="passive",
            session_key="cli:local",
            channel="cli",
            chat_id="local",
            registered=bool(metadata["registered"]),
            registry_risk=str(metadata["registry_risk"]),
            registry_capabilities=metadata["registry_capabilities"],
        ),
        invoke,
    )
    second = await ToolExecutor(approval_runtime=runtime).execute(
        ToolExecutionRequest(
            call_id="call-plugin-write-second",
            tool_name="save_content_item",
            arguments={
                "url": "https://www.bilibili.com/video/BV-SECOND/",
                "note": "second-choice-content",
            },
            source="passive",
            session_key="cli:local",
            channel="cli",
            chat_id="local",
            registered=bool(metadata["registered"]),
            registry_risk=str(metadata["registry_risk"]),
            registry_capabilities=metadata["registry_capabilities"],
        ),
        invoke,
    )
    first_id = json.loads(first.output)["approval_request"]["approval_request_id"]
    second_id = json.loads(second.output)["approval_request"]["approval_request_id"]
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=runtime.side_effect_vault,
        tool_registry=registry,
    )

    ran = await _run_command(module, "1")

    assert tool.calls == [
        {
            "channel": "cli",
            "chat_id": "local",
            "session_key": "cli:local",
            "url": "https://www.bilibili.com/video/BV-FIRST/",
            "note": "first-choice-content",
        }
    ]
    assert runtime.store.get_request(first_id).status == "executed"
    assert runtime.store.get_request(second_id).status == "pending"
    assert "剩余待审批 1 项" in ran.abort_reply
    assert "下一项：save_content_item" in ran.abort_reply


@pytest.mark.asyncio
async def test_numeric_choice_denies_latest_pending_request(tmp_path: Path) -> None:
    runtime = _approval_runtime(tmp_path)
    record = runtime.record_defer_request(
        request_id="call-deny-choice",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/secret"},
    )
    module = ToolApprovalCommandModule("status_commands", runtime.store)

    denied = await _run_command(module, "2")

    assert "status: denied" in denied.abort_reply
    assert record.approval_request_id in denied.abort_reply
    assert runtime.store.get_request(record.approval_request_id).status == "denied"


@pytest.mark.asyncio
async def test_numeric_choice_denies_first_pending_request_only(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    first = runtime.record_defer_request(
        request_id="call-deny-first",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/first"},
    )
    second = runtime.record_defer_request(
        request_id="call-deny-second",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="memorize",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"summary": "second"},
    )
    module = ToolApprovalCommandModule("status_commands", runtime.store)

    denied = await _run_command(module, "2")

    assert runtime.store.get_request(first.approval_request_id).status == "denied"
    assert runtime.store.get_request(second.approval_request_id).status == "pending"
    assert "剩余待审批 1 项" in denied.abort_reply
    assert "下一项：memorize" in denied.abort_reply


@pytest.mark.asyncio
async def test_numeric_choice_lists_pending_details(tmp_path: Path) -> None:
    runtime = _approval_runtime(tmp_path)
    record = runtime.record_defer_request(
        request_id="call-details-choice",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/secret"},
    )
    module = ToolApprovalCommandModule("status_commands", runtime.store)

    details = await _run_command(module, "3")

    assert "Tool approvals" in details.abort_reply
    assert record.approval_request_id in details.abort_reply
    assert "1. 批准" in details.abort_reply


@pytest.mark.asyncio
async def test_numeric_choice_lists_pending_details_marks_first_item_current(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    first = runtime.record_defer_request(
        request_id="call-details-first",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/first"},
    )
    second = runtime.record_defer_request(
        request_id="call-details-second",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="memorize",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"summary": "second"},
    )
    module = ToolApprovalCommandModule("status_commands", runtime.store)

    details = await _run_command(module, "3")

    assert first.approval_request_id in details.abort_reply
    assert second.approval_request_id in details.abort_reply
    assert "current: yes" in details.abort_reply
    assert "queue: waiting_for_previous_approval" in details.abort_reply


@pytest.mark.asyncio
async def test_numeric_choice_without_pending_request_does_not_intercept(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    module = ToolApprovalCommandModule("status_commands", runtime.store)

    frame = await _run_command_frame(module, "1")

    assert "session:ctx" not in frame.slots


@pytest.mark.asyncio
async def test_pending_request_does_not_intercept_regular_message(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    runtime.record_defer_request(
        request_id="call-regular-message",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/secret"},
    )
    module = ToolApprovalCommandModule("status_commands", runtime.store)

    frame = await _run_command_frame(module, "继续聊别的")

    assert "session:ctx" not in frame.slots


@pytest.mark.asyncio
async def test_numeric_choice_for_file_write_approves_without_applying_file(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    record = runtime.record_defer_request(
        request_id="call-file-choice",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"path": "notes.md", "content": "raw-secret-content"},
    )
    runtime.record_managed_side_effect_payload(
        record, arguments={"path": "notes.md", "content": "raw-secret-content"}
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

    approved = await _run_command(module, "1")

    assert "status: approved" in approved.abort_reply
    assert "/prepare_tool" in approved.abort_reply
    assert "/run_approved_tool" in approved.abort_reply
    assert runtime.store.get_request(record.approval_request_id).status == "approved"
    assert not (workspace / "notes.md").exists()
    assert "raw-secret-content" not in approved.abort_reply


@pytest.mark.asyncio
async def test_approve_last_refuses_managed_file_write_without_raw_content(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    runtime = _approval_runtime(workspace)
    record = runtime.record_defer_request(
        request_id="call-file-write",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"path": "notes.md", "content": "raw-secret-content"},
    )
    runtime.record_managed_side_effect_payload(
        record, arguments={"path": "notes.md", "content": "raw-secret-content"}
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

    ran = await _run_command(module, "/approve_last")

    assert "approve_last_unsupported_tool" in ran.abort_reply
    assert "/approve_tool" in ran.abort_reply
    assert "/run_approved_tool" in ran.abort_reply
    assert "raw-secret-content" not in ran.abort_reply
    assert runtime.store.get_request(record.approval_request_id).status == "pending"


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
            metadata={"command": "echo secret", "command_hash": "a" * 64},
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
    assert "a" * 64 in reply
    assert "echo secret" not in reply


@pytest.mark.asyncio
async def test_tool_audit_command_never_prints_credential_prefix_metadata(
    tmp_path: Path,
) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    ledger.record_event(
        ToolAuditLedgerEvent(
            event_type="approved_side_effect_preview_ready",
            session_key="cli:s",
            tool_name="write_file",
            metadata={
                "resource_type": "ghp_AbCd1234567890",
                "preview_id": "sk-proj-AbCd1234567890",
                "rollback_id": "cred_live_AbCd1234567890",
            },
        )
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        ToolApprovalStore(tmp_path / "approvals.db"),
        audit_ledger_store=ledger,
    )

    ctx = await _run_command(
        module, "/tool_audit tool write_file 5", session_key="cli:s"
    )
    reply = ctx.abort_reply

    assert "approved_side_effect_preview_ready" in reply
    assert "ghp_AbCd1234567890" not in reply
    assert "sk-proj-AbCd1234567890" not in reply
    assert "cred_live_AbCd1234567890" not in reply


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


@pytest.mark.asyncio
async def test_approve_tool_expiration_records_tool_audit_event(tmp_path: Path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    runtime = ToolApprovalRuntime(
        ToolApprovalStore(tmp_path / "approvals.db"),
        now_factory=lambda: datetime.fromtimestamp(0, UTC),
        approval_ttl=timedelta(seconds=1),
        audit_ledger_store=ledger,
    )
    record = runtime.record_defer_request(
        request_id="call-expire",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"path": "notes.md", "content": "after\n"},
    )
    module = ToolApprovalCommandModule(
        "status_commands",
        runtime.store,
        audit_ledger_store=ledger,
    )

    ctx = await _run_command(module, f"/approve_tool {record.approval_request_id}")

    events = ledger.query_events(
        ToolAuditLedgerQuery(
            approval_request_id=record.approval_request_id,
            event_type="tool_approval_expired",
        )
    )
    assert "expired" in ctx.abort_reply
    assert runtime.store.get_request(record.approval_request_id).status == "expired"
    assert len(events) == 1
    assert events[0].approval_status == "expired"


@pytest.mark.asyncio
async def test_approval_reminder_appends_once_for_pending_request(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    record = runtime.record_defer_request(
        request_id="call-reminder",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/secret"},
    )
    session = SimpleNamespace(key="cli:local", metadata={})
    module = ApprovalReminderAfterReasoningModule("status_commands", runtime.store)

    first = await _run_approval_reminder(module, session=session, reply="这是新的回答")
    second = await _run_approval_reminder(module, session=session, reply="第二次回答")

    assert "这是新的回答" in first.reply
    assert "还有 1 个待审批操作" in first.reply
    assert "当前项：save_content_item" in first.reply
    assert "可回复 1 批准当前项、2 拒绝当前项、3 查看详情" in first.reply
    assert "第二次回答" == second.reply
    assert session.metadata["approval_choice_reminder"]["approval_id"] == record.approval_request_id
    assert session.metadata["approval_choice_reminder"]["reminded"] is True


@pytest.mark.asyncio
async def test_approval_reminder_reports_multiple_pending_current_item(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    runtime.record_defer_request(
        request_id="call-reminder-first",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/first"},
    )
    runtime.record_defer_request(
        request_id="call-reminder-second",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="memorize",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"summary": "second"},
    )
    session = SimpleNamespace(key="cli:local", metadata={})
    module = ApprovalReminderAfterReasoningModule("status_commands", runtime.store)

    result = await _run_approval_reminder(module, session=session, reply="继续回答")

    assert "还有 2 个待审批操作" in result.reply
    assert "当前项：save_content_item" in result.reply
    assert "可回复 1 批准当前项、2 拒绝当前项、3 查看详情" in result.reply


@pytest.mark.asyncio
async def test_approval_reminder_adds_authoritative_block_for_new_multiple_pending(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    first = runtime.record_defer_request(
        request_id="call-initial-first",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/first"},
    )
    runtime.record_defer_request(
        request_id="call-initial-second",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="memorize",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"summary": "second"},
    )
    session = SimpleNamespace(key="cli:local", metadata={})
    module = ApprovalReminderAfterReasoningModule("status_commands", runtime.store)

    result = await _run_approval_reminder(
        module,
        session=session,
        reply="两个操作可以直接回 1 一起批准",
        tool_chain=(
            {
                "calls": [
                    {
                        "result": json.dumps(
                            {
                                "approval_request": {
                                    "approval_request_id": first.approval_request_id
                                }
                            }
                        )
                    }
                ]
            },
        ),
    )

    assert "当前处理第 1/2 项：save_content_item" in result.reply
    assert "审批按顺序逐项处理，不会一次批准全部待审批操作。" in result.reply
    assert "可回复 1 批准当前项、2 拒绝当前项、3 查看详情。" in result.reply


@pytest.mark.asyncio
async def test_approval_reminder_skips_after_request_is_no_longer_pending(
    tmp_path: Path,
) -> None:
    runtime = _approval_runtime(tmp_path)
    record = runtime.record_defer_request(
        request_id="call-reminder-approved",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
        source="passive",
        tool_name="save_content_item",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"url": "https://example.com/secret"},
    )
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
    session = SimpleNamespace(key="cli:local", metadata={})
    module = ApprovalReminderAfterReasoningModule("status_commands", runtime.store)

    result = await _run_approval_reminder(module, session=session, reply="已继续")

    assert result.reply == "已继续"
    assert "approval_choice_reminder" not in session.metadata


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


def test_status_commands_plugin_wires_workspace_approval_reminder(
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

    modules = plugin.after_reasoning_modules()

    reminder_modules = [
        module
        for module in modules
        if isinstance(module, ApprovalReminderAfterReasoningModule)
    ]
    assert len(reminder_modules) == 1
    assert (
        reminder_modules[0]._approval_store.db_path
        == ToolApprovalRuntime.approval_db_path_from_workspace(tmp_path)
    )
