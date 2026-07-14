from __future__ import annotations

from agent.core.runtime_support import ToolDiscoveryState
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore
from agent.tools.registry import ToolRegistry
from agent.tools.task_plan import InspectTaskPlanTool


def test_registry_tracks_non_lru_tools(tmp_path) -> None:
    registry = ToolRegistry()
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    registry.register(InspectTaskPlanTool(service), non_lru=True)

    assert "inspect_task_plan" in registry.get_non_lru_names()


def test_tool_discovery_state_skips_non_lru_tools() -> None:
    state = ToolDiscoveryState()

    state.update(
        "cli:s1",
        ["inspect_task_plan", "search_docs"],
        always_on={"tool_search"},
        non_lru={"inspect_task_plan"},
    )

    assert state.get_preloaded("cli:s1") == {"search_docs"}


def test_existing_trace_tool_stays_non_lru_without_metadata() -> None:
    state = ToolDiscoveryState()

    state.update(
        "cli:s1",
        ["inspect_turn_trace", "search_docs"],
        always_on={"tool_search"},
    )

    assert state.get_preloaded("cli:s1") == {"search_docs"}
