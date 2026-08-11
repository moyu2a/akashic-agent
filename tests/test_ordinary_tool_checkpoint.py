from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from agent.config_models import OptimizationConfig
from agent.core.passive_turn import DefaultReasoner
from agent.core.runtime_support import LLMServices, ToolDiscoveryState
from agent.looping.ports import LLMConfig
from agent.provider import LLMResponse, ToolCall
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from session.store import SessionStore


NOW = datetime(2031, 1, 1, tzinfo=UTC)


class _Provider:
    def __init__(self) -> None:
        self._responses = [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("call-1", "checkpoint_probe", {"value": "x"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]

    async def chat(self, **kwargs: Any) -> LLMResponse:
        if not self._responses:
            raise AssertionError("provider called too many times")
        return self._responses.pop(0)


class _CheckpointProbeTool(Tool):
    name = "checkpoint_probe"
    description = "checkpoint_probe"
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(self, store: SessionStore) -> None:
        self._store = store
        self.running_seen = False

    async def execute(self, **kwargs: Any) -> str:
        with sqlite3.connect(self._store.db_path) as conn:
            row = conn.execute(
                """
                SELECT status
                FROM tool_invocation_attempts
                WHERE tool_call_id = 'call-1'
                """
            ).fetchone()
        self.running_seen = bool(row is not None and row[0] == "running")
        return "tool-result"


def _reasoner(store: SessionStore, tool: Tool) -> DefaultReasoner:
    provider = _Provider()
    tools = ToolRegistry()
    tools.register(tool, always_on=True, risk="read-only")
    return DefaultReasoner(
        llm=cast(Any, LLMServices(provider=cast(Any, provider), light_provider=cast(Any, provider))),
        llm_config=LLMConfig(model="m", max_iterations=4, max_tokens=512),
        tools=tools,
        discovery=ToolDiscoveryState(),
        tool_search_enabled=False,
        memory_window=40,
        optimization=OptimizationConfig(enabled=False),
        session_manager=cast(Any, SimpleNamespace(_store=store)),
    )


def test_ordinary_tool_attempt_is_running_before_invoker(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    tool = _CheckpointProbeTool(store)

    result = asyncio.run(
        _reasoner(store, tool).run(
            [{"role": "user", "content": "use tool"}],
            tool_event_session_key="cli:s1",
            tool_event_channel="cli",
            tool_event_chat_id="s1",
        )
    )

    assert result.reply == "final"
    assert tool.running_seen is True


def test_ordinary_tool_attempt_is_succeeded_after_success(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    tool = _CheckpointProbeTool(store)

    asyncio.run(
        _reasoner(store, tool).run(
            [{"role": "user", "content": "use tool"}],
            tool_event_session_key="cli:s1",
            tool_event_channel="cli",
            tool_event_chat_id="s1",
        )
    )

    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            """
            SELECT status, result_message_id, side_effect, idempotent
            FROM tool_invocation_attempts
            WHERE tool_call_id = 'call-1'
            """
        ).fetchone()

    assert row is not None
    assert row[0] == "succeeded"
    assert row[2:] == (0, 1)
    assert store.get_message(row[1])["content"] == "tool-result"


def test_task_execution_turn_does_not_write_ordinary_tool_attempt(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    tool = _CheckpointProbeTool(store)

    asyncio.run(
        _reasoner(store, tool).run(
            [{"role": "user", "content": "use tool"}],
            tool_event_session_key="cli:s1",
            tool_event_channel="cli",
            tool_event_chat_id="s1",
            task_execution_turn=cast(Any, SimpleNamespace(request_id="task-1")),
        )
    )

    with sqlite3.connect(store.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM tool_invocation_attempts").fetchone()[0]

    assert count == 0
