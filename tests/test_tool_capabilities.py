from __future__ import annotations

from typing import Any

import pytest

from agent.tools.base import Tool
from agent.tools.message_lookup import FetchMessagesTool, SearchMessagesTool
from agent.tools.recall_memory import RecallMemoryTool
from agent.tools.registry import ToolRegistry
from agent.tools.search_backend import SearchBackend
from agent.tools.task_plan import (
    CreateTaskPlanTool,
    InspectTaskPlanTool,
    UpdateTaskStepTool,
)


class _NoCapabilityTool(Tool):
    name = "no_capability"
    description = "no capability"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **_: Any) -> str:
        return "ok"


class _DeclaredCapabilityTool(Tool):
    name = "declared_capability"
    description = "declared capability"
    parameters = {"type": "object", "properties": {}}
    capabilities = frozenset({"test.declared"})

    async def execute(self, **_: Any) -> str:
        return "ok"


class _FailingBackend(SearchBackend):
    def rebuild(self, documents: list[Any]) -> None:
        return None

    def add(self, document: Any) -> None:
        raise RuntimeError("backend add failed")

    def remove(self, name: str) -> None:
        return None

    def search(
        self,
        query: str,
        top_k: int = 5,
        allowed_risk: list[str] | None = None,
        excluded_names: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        return []


def test_registry_defaults_missing_capabilities_to_empty() -> None:
    registry = ToolRegistry()
    registry.register(_NoCapabilityTool())

    assert registry.get_capabilities_by_name() == {
        "no_capability": frozenset()
    }


def test_registry_uses_tool_declared_capabilities() -> None:
    registry = ToolRegistry()
    registry.register(_DeclaredCapabilityTool())

    assert registry.get_capabilities_by_name()["declared_capability"] == frozenset(
        {"test.declared"}
    )


def test_explicit_registration_capabilities_override_tool_declaration() -> None:
    registry = ToolRegistry()
    registry.register(
        _DeclaredCapabilityTool(),
        capabilities={"test.override"},
    )

    assert registry.get_capabilities_by_name()["declared_capability"] == frozenset(
        {"test.override"}
    )


def test_explicit_empty_capabilities_clear_tool_declaration() -> None:
    registry = ToolRegistry()
    registry.register(_DeclaredCapabilityTool(), capabilities=frozenset())

    assert registry.get_capabilities_by_name()["declared_capability"] == frozenset()


def test_capability_mapping_is_a_defensive_copy() -> None:
    registry = ToolRegistry()
    registry.register(_DeclaredCapabilityTool())

    first = registry.get_capabilities_by_name()
    first["declared_capability"] = frozenset({"tampered"})

    assert registry.get_capabilities_by_name()["declared_capability"] == frozenset(
        {"test.declared"}
    )


def test_invalid_capability_registration_is_atomic() -> None:
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="capabilities"):
        registry.register(_NoCapabilityTool(), capabilities={""})

    assert registry.has_tool("no_capability") is False
    assert registry.get_capabilities_by_name() == {}


def test_backend_failure_does_not_leave_partial_registration() -> None:
    registry = ToolRegistry(backend=_FailingBackend())

    with pytest.raises(RuntimeError, match="backend add failed"):
        registry.register(_DeclaredCapabilityTool())

    assert registry.has_tool("declared_capability") is False
    assert registry.get_registered_names() == set()
    assert registry.get_capabilities_by_name() == {}
    assert registry.get_documents() == []


def test_capabilities_do_not_leak_into_model_schema() -> None:
    registry = ToolRegistry()
    registry.register(_DeclaredCapabilityTool())

    schema = registry.get_schemas({"declared_capability"})[0]

    assert "capabilities" not in schema
    assert "capabilities" not in schema["function"]


def test_capabilities_do_not_leak_into_search_documents_or_results() -> None:
    registry = ToolRegistry()
    registry.register(_DeclaredCapabilityTool())

    document = registry.get_documents()[0]
    result = registry.search("declared capability")[0]

    assert not hasattr(document, "capabilities")
    assert "capabilities" not in result


def test_core_tools_declare_task_plan_context_capabilities() -> None:
    assert CreateTaskPlanTool.capabilities == frozenset({"task_plan.create"})
    assert InspectTaskPlanTool.capabilities == frozenset({"task_plan.inspect"})
    assert UpdateTaskStepTool.capabilities == frozenset({"task_plan.update"})
    assert RecallMemoryTool.capabilities == frozenset({"memory.recall"})
    assert SearchMessagesTool.capabilities == frozenset({"history.search"})
    assert FetchMessagesTool.capabilities == frozenset()
