from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from agent.subagent import SubAgent
from agent.tools.base import Tool


class _RecordingTool(Tool):
    name = "read_file"
    description = "recording file tool"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> str:
        self.calls.append(dict(kwargs))
        return f"{self.name}-ok"


class _RecordingWriteTool(_RecordingTool):
    name = "write_file"


@pytest.mark.asyncio
async def test_subagent_blocks_file_escape_with_resource_roots(tmp_path: Path) -> None:
    tool = _RecordingTool()
    subagent = SubAgent(
        provider=cast(Any, object()),
        model="m",
        tools=[tool],
        resource_roots=(str(tmp_path),),
    )

    result = await subagent._execute_tool_call(
        "call-1",
        "read_file",
        {"path": "../secret.txt"},
        session_key="subagent:test",
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    assert tool.calls == []
    assert result.policy_trace["reason"] == "resource_policy_file_path_outside_roots"


@pytest.mark.asyncio
async def test_subagent_blocks_write_inside_workspace_but_outside_task_dir_before_invoker(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    task_dir = workspace / ".agents" / "task-1"
    task_dir.mkdir(parents=True)
    tool = _RecordingWriteTool()
    subagent = SubAgent(
        provider=cast(Any, object()),
        model="m",
        tools=[tool],
        resource_roots=(str(workspace),),
        resource_roots_by_tool={"write_file": (str(task_dir),)},
    )

    result = await subagent._execute_tool_call(
        "call-2",
        "write_file",
        {"path": "../outside-task.md", "content": "x"},
        session_key="subagent:test",
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    assert tool.calls == []
    assert result.policy_trace["reason"] == "resource_policy_file_path_outside_roots"
