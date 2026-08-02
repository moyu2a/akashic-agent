from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from agent.plugins.manager import PluginManager
from agent.plugins.registry import plugin_registry
from agent.tool_hooks import ToolExecutionRequest, ToolExecutor
from bus.event_bus import EventBus


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "plugins"


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    plugin_registry._handlers._handlers.clear()
    plugin_registry._classes.clear()
    plugin_registry._instances.clear()
    yield
    plugin_registry._handlers._handlers.clear()
    plugin_registry._classes.clear()
    plugin_registry._instances.clear()


def _make_manager(plugin_dirs: list[Path], *, event_bus: EventBus, tools: Any = None) -> PluginManager:
    return PluginManager(plugin_dirs=plugin_dirs, event_bus=event_bus, tool_registry=tools)


class RecordingInvoker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((tool_name, dict(arguments)))
        return {"tool": tool_name, "ok": True}


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_shell_restore_legacy_plugin_registers_no_pre_hook() -> None:
    bus = EventBus()
    mgr = _make_manager([FIXTURES_DIR], event_bus=bus)

    _run(mgr.load_all())

    assert not any("shell_restore" in hook.name for hook in mgr.tool_hooks)


def test_rm_command_is_denied_by_resource_policy_not_rewritten() -> None:
    bus = EventBus()
    mgr = _make_manager([FIXTURES_DIR], event_bus=bus)
    _run(mgr.load_all())
    invoker = RecordingInvoker()

    result = _run(
        ToolExecutor(mgr.tool_hooks).execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="shell",
                arguments={
                    "command": "rm -rf foo bar",
                    "description": "删除文件",
                },
                source="passive",
                registry_risk="read-only",
            ),
            invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    assert invoker.calls == []
    assert result.policy_trace["reason"] == "resource_policy_shell_destructive_command_denied"
    assert result.final_arguments == {}


def test_non_destructive_shell_command_is_not_rewritten_by_shell_restore() -> None:
    bus = EventBus()
    mgr = _make_manager([FIXTURES_DIR], event_bus=bus)
    _run(mgr.load_all())
    invoker = RecordingInvoker()

    result = _run(
        ToolExecutor(mgr.tool_hooks).execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="shell",
                arguments={
                    "command": "ls -la",
                    "description": "列目录",
                },
                source="passive",
                registry_risk="read-only",
            ),
            invoker,
        )
    )

    assert result.status == "deferred"
    assert result.invoker_reached is False
    assert invoker.calls == []
    assert result.policy_trace["reason"] == "risk_strategy_shell_requires_approval"
    assert result.final_arguments == {}
