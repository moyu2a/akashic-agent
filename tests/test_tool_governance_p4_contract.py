from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent.policies.approved_side_effect_runtime import ApprovedSideEffectRuntime
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_approval_context import trusted_approval_from_runtime
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore
from agent.tool_hooks import ToolExecutionRequest, ToolExecutor


class _RecordingInvoker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, tool_name: str, arguments: dict[str, Any]) -> object:
        self.calls.append((tool_name, dict(arguments)))
        return {"ok": True, "tool_name": tool_name}


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _runtime(workspace: Path) -> tuple[ToolApprovalRuntime, ApprovedSideEffectRuntime]:
    approval_runtime = ToolApprovalRuntime(
        ToolApprovalStore(ToolApprovalRuntime.approval_db_path_from_workspace(workspace)),
        side_effect_vault=SideEffectPayloadVault(
            SideEffectPayloadVault.root_for_workspace(workspace)
        ),
    )
    runtime = ApprovedSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
    )
    return approval_runtime, runtime


def _approved_file(
    approval_runtime: ToolApprovalRuntime,
    runtime: ApprovedSideEffectRuntime,
    *,
    tool_name: str = "write_file",
    arguments: dict[str, object] | None = None,
) -> str:
    args = arguments or {"path": "notes.md", "content": "after\n"}
    record = approval_runtime.record_defer_request(
        request_id="call-1",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        source="passive",
        tool_name=tool_name,
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments=args,
    )
    approval_runtime.record_managed_side_effect_payload(record, arguments=args)
    approval_runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=runtime.now(),
    )
    return record.approval_request_id


def _write_request(
    *,
    arguments: dict[str, object],
    approval_request_id: str | None = None,
    workspace: Path,
) -> ToolExecutionRequest:
    trusted_context = None
    if approval_request_id is not None:
        trusted_context = trusted_approval_from_runtime(
            approval_request_id=approval_request_id,
            actor="status_command",
            source="status_command",
        )
    return ToolExecutionRequest(
        call_id="call-1",
        tool_name="write_file",
        arguments=arguments,
        source="passive",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        registered=True,
        registry_risk="write",
        trusted_approval_context=trusted_context,
        resource_roots=(str(workspace),),
    )


def test_p4_executor_defer_stores_payload_and_direct_approved_file_apply_is_blocked(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    target = workspace / "notes.md"
    target.write_text("before\n", encoding="utf-8")
    approval_runtime, runtime = _runtime(workspace)
    invoker = _RecordingInvoker()
    arguments = {"path": "notes.md", "content": "after\n"}

    deferred = _run(
        ToolExecutor(approval_runtime=approval_runtime).execute(
            _write_request(arguments=arguments, workspace=workspace),
            invoker,
        )
    )
    approval_id = json.loads(deferred.output)["approval_request"][
        "approval_request_id"
    ]
    stored_payload = approval_runtime.side_effect_vault.get_payload(approval_id)
    record = approval_runtime.store.get_request(approval_id)
    assert record is not None
    approval_runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=runtime.now(),
    )

    direct = _run(
        ToolExecutor(approval_runtime=approval_runtime).execute(
            _write_request(
                arguments=arguments,
                approval_request_id=approval_id,
                workspace=workspace,
            ),
            invoker,
        )
    )
    applied = runtime.apply(
        approval_id,
        "cli:test",
        "status_command",
        workspace,
        (str(workspace),),
    )

    assert deferred.status == "deferred"
    assert stored_payload is not None
    assert stored_payload.arguments == arguments
    assert direct.status == "deferred"
    assert direct.invoker_reached is False
    assert "approved_side_effect_requires_managed_apply" in direct.output
    assert invoker.calls == []
    assert applied.ok
    assert target.read_text(encoding="utf-8") == "after\n"


def test_p4_file_approval_requires_prepare_apply_and_supports_rollback(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    (workspace / "notes.md").write_text("before\n", encoding="utf-8")
    approval_runtime, runtime = _runtime(workspace)
    approval_id = _approved_file(approval_runtime, runtime)

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    applied = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    assert prepared.ok and applied.ok
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "after\n"

    rolled_back = runtime.rollback(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert rolled_back.ok
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "before\n"


def test_p4_edit_file_approval_requires_prepare_apply_and_supports_rollback(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    (workspace / "notes.md").write_text("alpha\nbeta\n", encoding="utf-8")
    approval_runtime, runtime = _runtime(workspace)
    approval_id = _approved_file(
        approval_runtime,
        runtime,
        tool_name="edit_file",
        arguments={
            "path": "notes.md",
            "old_text": "beta\n",
            "new_text": "gamma\n",
        },
    )

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    applied = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    rolled_back = runtime.rollback(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert prepared.ok and applied.ok and rolled_back.ok
    assert "-beta" in prepared.diff_text
    assert "+gamma" in prepared.diff_text
    assert (workspace / "notes.md").read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_p4_workspace_escape_still_denied_after_approval(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    approval_runtime, runtime = _runtime(workspace)
    approval_id = _approved_file(
        approval_runtime,
        runtime,
        arguments={"path": "../outside.md", "content": "changed\n"},
    )

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert prepared.ok is False
    assert prepared.reason == "resource_policy_file_path_outside_roots"
    assert outside.read_text(encoding="utf-8") == "outside\n"
