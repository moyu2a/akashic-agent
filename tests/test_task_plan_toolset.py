from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agent.config import load_config
from agent.config_models import WiringConfig
from agent.config_models import TaskExecutionConfig
from agent.task_plan.execution_service import TaskExecutionService
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore
from agent.tools.registry import ToolRegistry
from bootstrap.toolsets.protocol import ToolsetDeps
from bootstrap.toolsets.task_plan import TaskPlanToolsetProvider
from bootstrap.wiring import resolve_toolset_provider


def test_task_plan_is_in_default_toolsets() -> None:
    assert "task_plan" in WiringConfig().toolsets


def test_loaded_config_defaults_include_task_plan_toolset(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
provider = "openai"

[llm.main]
model = "m"
api_key = "k"

[agent]
system_prompt = "s"
""",
        encoding="utf-8",
    )

    cfg = load_config(config_path)

    assert "task_plan" in cfg.wiring.toolsets


def test_task_plan_wiring_resolves_provider() -> None:
    assert isinstance(resolve_toolset_provider("task_plan"), TaskPlanToolsetProvider)


def test_task_plan_toolset_registers_deferred_non_lru_tools(tmp_path: Path) -> None:
    registry = ToolRegistry()
    store = TaskPlanStore(tmp_path / "task_plans.db")
    service = TaskPlanService(store)
    execution_service = TaskExecutionService(
        store=store,
        plan_service=service,
        runtime_instance_id="test-runtime",
        config=TaskExecutionConfig(),
        clock=lambda: datetime.now(UTC),
    )

    result = TaskPlanToolsetProvider(
        service, execution_service=execution_service
    ).register(
        registry,
        ToolsetDeps(config=None, workspace=tmp_path),
    )

    assert result.source_name == "task_plan"
    assert set(result.tool_names) == {
        "abort_task_step_execution",
        "begin_task_step_execution",
        "create_task_plan",
        "finish_task_step_execution",
        "inspect_task_execution",
        "inspect_task_plan",
        "request_task_step_authorization",
        "update_task_step",
    }
    assert result.always_on_names == []
    assert set(result.tool_names) <= registry.get_non_lru_names()
    docs = {doc.name: doc for doc in registry.get_documents()}
    assert docs["create_task_plan"].risk == "write"
    assert docs["update_task_step"].risk == "write"
    assert docs["inspect_task_plan"].risk == "read-only"
    assert docs["begin_task_step_execution"].risk == "write"
    assert docs["inspect_task_execution"].risk == "read-only"
    assert result.extras["task_plan_service"] is service
    assert result.extras["task_execution_service"] is execution_service
    assert execution_service.plan_service is service
