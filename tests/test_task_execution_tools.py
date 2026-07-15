from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from agent.config_models import TaskExecutionConfig
from agent.task_plan.execution_models import TaskExecutionSnapshot
from agent.task_plan.execution_service import TaskExecutionService
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore
from agent.tools.base import Tool
from agent.tools.execution_context import ToolExecutionContext
from agent.tools.filesystem import ReadFileTool
from agent.tools.registry import ToolRegistry
from bootstrap.toolsets.protocol import ToolsetDeps
from bootstrap.toolsets.task_plan import TaskPlanToolsetProvider


class UnclassifiedTool(Tool):
    name = "unclassified"
    description = "Test tool with no risk classification."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **_: Any) -> str:
        return "ok"


@dataclass
class _InspectCall:
    attempt_id: str | None


class _RecordingExecutionService:
    def __init__(self, plan_service: TaskPlanService) -> None:
        self.plan_service = plan_service
        self.store = plan_service.store
        self.inspect_calls: list[_InspectCall] = []

    def inspect(
        self, *, session_key: str, attempt_id: str | None = None
    ) -> TaskExecutionSnapshot:
        self.inspect_calls.append(_InspectCall(attempt_id=attempt_id))
        return TaskExecutionSnapshot(attempt=None)


@dataclass
class ExecutionToolset:
    registry: ToolRegistry
    inspect_calls: list[_InspectCall]


@pytest.fixture
def execution_toolset(tmp_path: Path) -> ExecutionToolset:
    plan_service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    execution_service = _RecordingExecutionService(plan_service)
    registry = ToolRegistry()
    registry.register(ReadFileTool(allowed_dir=tmp_path), risk="read-only")
    TaskPlanToolsetProvider(
        plan_service,
        execution_service=execution_service,  # type: ignore[arg-type]
    ).register(registry, ToolsetDeps(config=None, workspace=tmp_path))
    return ExecutionToolset(
        registry=registry, inspect_calls=execution_service.inspect_calls
    )


def test_execution_tools_hide_protected_identity(
    execution_toolset: ExecutionToolset,
) -> None:
    schemas = execution_toolset.registry.get_schemas()
    by_name = {item["function"]["name"]: item for item in schemas}
    begin = by_name["begin_task_step_execution"]
    finish = by_name["finish_task_step_execution"]
    assert (
        "_task_execution_request_id"
        not in begin["function"]["parameters"]["properties"]
    )
    assert (
        "_task_execution_attempt_id"
        not in finish["function"]["parameters"]["properties"]
    )


def test_execution_tools_are_non_lru(execution_toolset: ExecutionToolset) -> None:
    assert {
        "begin_task_step_execution",
        "finish_task_step_execution",
        "request_task_step_authorization",
        "inspect_task_execution",
        "abort_task_step_execution",
    } <= execution_toolset.registry.get_non_lru_names()


def test_registry_risk_snapshot_is_internal_and_stable(
    execution_toolset: ExecutionToolset,
) -> None:
    risks = execution_toolset.registry.get_risks_by_name()
    assert risks["read_file"] == "read-only"
    risks["read_file"] = "write"
    assert execution_toolset.registry.get_risks_by_name()["read_file"] == "read-only"


def test_unclassified_tool_is_unknown_not_read_only(
    execution_toolset: ExecutionToolset,
) -> None:
    execution_toolset.registry.register(UnclassifiedTool())
    assert execution_toolset.registry.get_risks_by_name()["unclassified"] == "unknown"


@pytest.mark.asyncio
async def test_execution_identity_is_ephemeral_per_call(
    execution_toolset: ExecutionToolset,
) -> None:
    first = ToolExecutionContext(
        protected={
            "_task_execution_request_id": "req-1",
            "_task_execution_attempt_id": "attempt-1",
        },
        propagate_tool_errors=True,
    )
    await execution_toolset.registry.execute(
        "inspect_task_execution",
        {},
        execution_context=first,
    )
    await execution_toolset.registry.execute(
        "inspect_task_execution",
        {},
        execution_context=ToolExecutionContext(
            protected={},
            propagate_tool_errors=True,
        ),
    )
    assert execution_toolset.inspect_calls[-1].attempt_id is None
    assert "_task_execution_attempt_id" not in execution_toolset.registry.get_context()


@pytest.mark.asyncio
async def test_begin_rejects_model_action_without_protected_action(
    tmp_path: Path,
) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    service = TaskPlanService(store)
    execution = TaskExecutionService(
        store=store,
        plan_service=service,
        runtime_instance_id="runtime-test",
        config=TaskExecutionConfig(),
        clock=lambda: datetime.now(UTC),
    )
    registry = ToolRegistry()
    TaskPlanToolsetProvider(service, execution_service=execution).register(
        registry,
        ToolsetDeps(config=None, workspace=tmp_path),
    )

    result = await registry.execute(
        "begin_task_step_execution",
        {"action": "continue"},
        execution_context=ToolExecutionContext(
            protected={"_session_key": "cli:s1", "_task_execution_request_id": "r1"},
            propagate_tool_errors=True,
        ),
    )

    assert getattr(result, "ok") is False
    assert getattr(result, "error_code") == "missing_execution_action"


@pytest.mark.asyncio
async def test_execution_tool_rejects_model_forged_protected_context(
    tmp_path: Path,
) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    service = TaskPlanService(store)
    execution = TaskExecutionService(
        store=store,
        plan_service=service,
        runtime_instance_id="runtime-test",
        config=TaskExecutionConfig(),
        clock=lambda: datetime.now(UTC),
    )
    registry = ToolRegistry()
    TaskPlanToolsetProvider(service, execution_service=execution).register(
        registry,
        ToolsetDeps(config=None, workspace=tmp_path),
    )

    result = await registry.execute(
        "begin_task_step_execution",
        {
            "_session_key": "cli:forged",
            "_task_execution_request_id": "forged-request",
            "_task_execution_action": "continue",
        },
    )

    assert getattr(result, "ok") is False
    assert getattr(result, "error_code") == "missing_execution_context"


@pytest.mark.asyncio
async def test_begin_retry_ignores_forged_action_and_target_with_partial_context(
    tmp_path: Path,
) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    service = TaskPlanService(store)
    execution = TaskExecutionService(
        store=store,
        plan_service=service,
        runtime_instance_id="runtime-test",
        config=TaskExecutionConfig(),
        clock=lambda: datetime.now(UTC),
    )
    registry = ToolRegistry()
    TaskPlanToolsetProvider(service, execution_service=execution).register(
        registry,
        ToolsetDeps(config=None, workspace=tmp_path),
    )

    result = await registry.execute(
        "begin_task_step_execution",
        {
            "_task_execution_action": "continue",
            "_task_execution_target_step_id": "forged-step",
            "_task_execution_attempt_id": "forged-attempt",
            "_tool_execution_context_active": True,
        },
        execution_context=ToolExecutionContext(
            protected={
                "_session_key": "cli:s1",
                "_task_execution_request_id": "runtime-request",
                "_task_execution_action": "retry",
            },
            propagate_tool_errors=True,
        ),
    )

    assert getattr(result, "ok") is False
    assert getattr(result, "error_code") == "missing_retry_target"


@pytest.mark.asyncio
async def test_execution_context_strips_forged_session_with_partial_context(
    tmp_path: Path,
) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    service = TaskPlanService(store)
    execution = TaskExecutionService(
        store=store,
        plan_service=service,
        runtime_instance_id="runtime-test",
        config=TaskExecutionConfig(),
        clock=lambda: datetime.now(UTC),
    )
    registry = ToolRegistry()
    registry.set_context(_session_key="stale-global-session")
    TaskPlanToolsetProvider(service, execution_service=execution).register(
        registry,
        ToolsetDeps(config=None, workspace=tmp_path),
    )

    result = await registry.execute(
        "begin_task_step_execution",
        {"_session_key": "forged-session"},
        execution_context=ToolExecutionContext(
            protected={
                "_task_execution_request_id": "runtime-request",
                "_task_execution_action": "continue",
            },
            propagate_tool_errors=True,
        ),
    )

    assert getattr(result, "ok") is False
    assert getattr(result, "error_code") == "missing_session_context"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("finish_task_step_execution", {"success": False, "result_summary": "x"}),
        (
            "request_task_step_authorization",
            {
                "tool_name": "write_file",
                "requested_arguments": {},
                "requested_capabilities": [],
                "reason": "authorization required",
            },
        ),
        ("abort_task_step_execution", {"reason": "stop"}),
    ],
)
async def test_attempt_controls_ignore_forged_attempt_with_partial_context(
    tmp_path: Path,
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    service = TaskPlanService(store)
    execution = TaskExecutionService(
        store=store,
        plan_service=service,
        runtime_instance_id="runtime-test",
        config=TaskExecutionConfig(),
        clock=lambda: datetime.now(UTC),
    )
    registry = ToolRegistry()
    TaskPlanToolsetProvider(service, execution_service=execution).register(
        registry,
        ToolsetDeps(config=None, workspace=tmp_path),
    )

    result = await registry.execute(
        tool_name,
        {**arguments, "_task_execution_attempt_id": "forged-attempt"},
        execution_context=ToolExecutionContext(
            protected={"_session_key": "cli:s1"},
            propagate_tool_errors=True,
        ),
    )

    assert getattr(result, "ok") is False
    assert getattr(result, "error_code") == "missing_execution_attempt"
