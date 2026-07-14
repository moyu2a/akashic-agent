from __future__ import annotations

from pathlib import Path

from agent.config import load_config
from agent.config_models import WiringConfig
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
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))

    result = TaskPlanToolsetProvider(service).register(
        registry,
        ToolsetDeps(config=None, workspace=tmp_path),
    )

    assert result.source_name == "task_plan"
    assert sorted(result.tool_names) == [
        "create_task_plan",
        "inspect_task_plan",
        "update_task_step",
    ]
    assert result.always_on_names == []
    assert set(result.tool_names) <= registry.get_non_lru_names()
    docs = {doc.name: doc for doc in registry.get_documents()}
    assert docs["create_task_plan"].risk == "write"
    assert docs["update_task_step"].risk == "write"
    assert docs["inspect_task_plan"].risk == "read-only"
