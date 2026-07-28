from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent.policies.approved_side_effect_runtime import ApprovedSideEffectRuntime
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore
from tests.test_task_execution_reasoner import (
    ReasonerExecutionFixture,
    _WorkTool,
    final_reply,
    tool_call,
)


def _approve_pending_request(workspace: Path, approval_id: str) -> ToolApprovalStore:
    store = ToolApprovalStore(ToolApprovalRuntime.approval_db_path_from_workspace(workspace))
    record = store.get_request(approval_id)
    assert record is not None
    store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=datetime.now(UTC),
    )
    return store


def _side_effect_runtime(
    fixture: ReasonerExecutionFixture,
    workspace: Path,
    store: ToolApprovalStore,
) -> ApprovedSideEffectRuntime:
    return ApprovedSideEffectRuntime(
        approval_runtime=ToolApprovalRuntime(
            store,
            side_effect_vault=SideEffectPayloadVault(
                SideEffectPayloadVault.root_for_workspace(workspace)
            ),
            now_factory=fixture.clock,
        ),
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        task_execution_service=fixture.execution_service,
    )


@pytest.mark.asyncio
async def test_task_execution_file_side_effect_resume_marks_waiting_attempt_succeeded(
    tmp_path: Path,
) -> None:
    fixture = ReasonerExecutionFixture(tmp_path)
    fixture.reasoner._context.workspace = tmp_path
    fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("write_file", {"path": "x.txt", "content": "raw-secret-content"}),
        final_reply("Waiting for authorization"),
    ]
    await fixture.run_turn("继续执行下一步")
    attempt = fixture.latest_attempt()
    approval_id = str(attempt.requested_arguments["approval_request_id"])
    store = _approve_pending_request(tmp_path, approval_id)
    runtime = _side_effect_runtime(fixture, tmp_path, store)

    applied = runtime.apply(
        approval_request_id=approval_id,
        session_key=fixture.session_key,
        actor="status_command",
        workspace_root=tmp_path,
        resource_roots=(str(tmp_path),),
    )

    assert applied.ok is True
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "raw-secret-content"
    latest = fixture.execution_service.store.get_execution_attempt(attempt.attempt_id)
    assert latest is not None
    assert latest.status == "succeeded"
    events = fixture.execution_service.store.list_execution_events(attempt.attempt_id)
    assert any(event.tool_name == "write_file" and event.invoker_succeeded for event in events)


@pytest.mark.asyncio
async def test_task_execution_edit_file_side_effect_resume_marks_waiting_attempt_succeeded(
    tmp_path: Path,
) -> None:
    fixture = ReasonerExecutionFixture(tmp_path)
    fixture.reasoner._context.workspace = tmp_path
    fixture.registry.register(_WorkTool("edit_file", []), always_on=True, risk="write")
    (tmp_path / "x.txt").write_text("before\n", encoding="utf-8")
    fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call(
            "edit_file",
            {"path": "x.txt", "old_text": "before\n", "new_text": "after\n"},
        ),
        final_reply("Waiting for authorization"),
    ]
    await fixture.run_turn("继续执行下一步")
    attempt = fixture.latest_attempt()
    approval_id = str(attempt.requested_arguments["approval_request_id"])
    store = _approve_pending_request(tmp_path, approval_id)
    runtime = _side_effect_runtime(fixture, tmp_path, store)

    applied = runtime.apply(
        approval_request_id=approval_id,
        session_key=fixture.session_key,
        actor="status_command",
        workspace_root=tmp_path,
        resource_roots=(str(tmp_path),),
    )

    assert applied.ok is True
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "after\n"
    latest = fixture.execution_service.store.get_execution_attempt(attempt.attempt_id)
    assert latest is not None
    assert latest.status == "succeeded"


@pytest.mark.asyncio
async def test_task_execution_shell_approval_still_does_not_resume(
    tmp_path: Path,
) -> None:
    fixture = ReasonerExecutionFixture(tmp_path)
    fixture.reasoner._context.workspace = tmp_path
    fixture.registry.register(_WorkTool("shell", []), always_on=True, risk="write")
    fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("shell", {"command": "echo hi"}),
        final_reply("Waiting for authorization"),
    ]
    await fixture.run_turn("继续执行下一步")
    attempt = fixture.latest_attempt()

    assert attempt.status == "waiting_authorization"
    assert attempt.requested_tool_name == "shell"
    assert not (tmp_path / "shell-output.txt").exists()
