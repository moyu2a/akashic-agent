from __future__ import annotations

from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore
from agent.tools.registry import ToolRegistry
from agent.tools.task_plan import (
    CreateTaskPlanTool,
    InspectTaskPlanTool,
    UpdateTaskStepTool,
)
from bootstrap.toolsets.protocol import (
    ToolsetDeps,
    ToolsetProvider,
    build_registration_result,
)


class TaskPlanToolsetProvider(ToolsetProvider):
    def __init__(self, service: TaskPlanService | None = None) -> None:
        self._service = service

    def register(self, registry: ToolRegistry, deps: ToolsetDeps):
        before = set(registry.get_registered_names())
        service = self._service or TaskPlanService(
            TaskPlanStore(deps.workspace / "task_plans.db")
        )
        tool_specs = (
            (CreateTaskPlanTool(service), "write"),
            (UpdateTaskStepTool(service), "write"),
            (InspectTaskPlanTool(service), "read-only"),
        )
        for tool, risk in tool_specs:
            registry.register(
                tool,
                always_on=False,
                risk=risk,
                search_hint="任务 计划 步骤 进度 下一步 继续 task plan",
                non_lru=True,
            )
        return build_registration_result(
            registry=registry,
            source_name="task_plan",
            before=before,
            extras={"task_plan_service": service},
        )
