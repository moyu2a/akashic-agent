from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore
from tests.test_task_execution_reasoner import (
    ReasonerExecutionFixture,
    final_reply,
    tool_call,
)


@pytest.fixture
def reasoner_fixture(tmp_path: Path) -> ReasonerExecutionFixture:
    return ReasonerExecutionFixture(tmp_path)


def _workspace(reasoner_fixture: ReasonerExecutionFixture, tmp_path: Path) -> Path:
    reasoner_fixture.reasoner._context.workspace = tmp_path
    return tmp_path


async def _defer_write(
    reasoner_fixture: ReasonerExecutionFixture,
    *,
    arguments: dict[str, object] | None = None,
):
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call(
            "write_file",
            arguments
            if arguments is not None
            else {"path": "x.txt", "content": "raw-secret-content"},
        ),
        final_reply("Waiting for authorization"),
    ]
    await reasoner_fixture.run_turn("继续执行下一步")
    assert reasoner_fixture.attempt_status() == "waiting_authorization"
    return reasoner_fixture.latest_attempt()


@pytest.mark.asyncio
async def test_task_execution_waiting_authorization_persists_structured_request_metadata(
    reasoner_fixture: ReasonerExecutionFixture,
    tmp_path: Path,
) -> None:
    _workspace(reasoner_fixture, tmp_path)

    attempt = await _defer_write(reasoner_fixture)

    requested = attempt.requested_arguments
    assert attempt.requested_tool_name == "write_file"
    assert requested["approval_request_id"]
    assert requested["expires_at"]
    assert requested["approval_scope"] == "task_execution_step"
    assert requested["args_hash"]
    assert requested["policy_reason"] == "task_execution_authorization_required"
    assert requested["args_summary"]["content"]["kind"] == "text"
    assert "file.write" in attempt.requested_capabilities


@pytest.mark.asyncio
async def test_task_execution_authorization_metadata_does_not_store_raw_content_or_command(
    reasoner_fixture: ReasonerExecutionFixture,
    tmp_path: Path,
) -> None:
    _workspace(reasoner_fixture, tmp_path)

    attempt = await _defer_write(
        reasoner_fixture,
        arguments={
            "path": "x.txt",
            "content": "raw-secret-content",
            "command": "rm file.txt",
        },
    )

    encoded = json.dumps(attempt.requested_arguments, ensure_ascii=False)
    assert "raw-secret-content" not in encoded
    assert "rm file.txt" not in encoded
    assert "args_summary" in attempt.requested_arguments


@pytest.mark.asyncio
async def test_task_execution_approval_metadata_does_not_enable_side_effect_resume(
    reasoner_fixture: ReasonerExecutionFixture,
    tmp_path: Path,
) -> None:
    workspace = _workspace(reasoner_fixture, tmp_path)
    attempt = await _defer_write(reasoner_fixture)
    store = ToolApprovalStore(
        ToolApprovalRuntime.approval_db_path_from_workspace(workspace)
    )
    approval_request_id = str(attempt.requested_arguments["approval_request_id"])
    record = store.get_request(approval_request_id)
    assert record is not None
    store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="user",
        now=reasoner_fixture.clock(),
    )

    assert reasoner_fixture.write_executor_calls == []
    assert reasoner_fixture.latest_attempt().status == "waiting_authorization"


@pytest.mark.asyncio
async def test_task_execution_waiting_authorization_links_approval_store_record(
    reasoner_fixture: ReasonerExecutionFixture,
    tmp_path: Path,
) -> None:
    workspace = _workspace(reasoner_fixture, tmp_path)

    attempt = await _defer_write(reasoner_fixture)

    store = ToolApprovalStore(
        ToolApprovalRuntime.approval_db_path_from_workspace(workspace)
    )
    record = store.get_request(str(attempt.requested_arguments["approval_request_id"]))
    assert record is not None
    assert record.status == "pending"
    assert record.session_key == reasoner_fixture.session_key
    assert record.tool_name == "write_file"
    assert record.approval_scope == "task_execution_step"
    assert record.args_hash == attempt.requested_arguments["args_hash"]
