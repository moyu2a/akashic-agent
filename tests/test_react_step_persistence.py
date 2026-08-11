from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime
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


class _Tool(Tool):
    name = "step_probe"
    description = "step_probe"
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> str:
        return "tool-result"


class _InspectingProvider:
    def __init__(self, store: SessionStore, responses: list[LLMResponse]) -> None:
        self._store = store
        self._responses = list(responses)
        self.model_running_seen = False

    async def chat(self, **kwargs: Any) -> LLMResponse:
        with sqlite3.connect(self._store.db_path) as conn:
            row = conn.execute(
                "SELECT status FROM react_steps ORDER BY step_no DESC LIMIT 1"
            ).fetchone()
        self.model_running_seen = self.model_running_seen or (
            row is not None and row[0] == "model_running"
        )
        if not self._responses:
            raise AssertionError("provider called too many times")
        return self._responses.pop(0)


def _reasoner(store: SessionStore, provider: _InspectingProvider) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.register(_Tool(), always_on=True, risk="read-only")
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


def test_model_step_is_running_before_provider_call(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    provider = _InspectingProvider(store, [LLMResponse(content="final", tool_calls=[])])

    asyncio.run(
        _reasoner(store, provider).run(
            [{"role": "user", "content": "answer"}],
            tool_event_session_key="cli:s1",
            tool_event_channel="cli",
            tool_event_chat_id="s1",
        )
    )

    assert provider.model_running_seen is True


def test_tool_call_json_is_persisted_after_model_response(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    provider = _InspectingProvider(
        store,
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("call-1", "step_probe", {"value": "x"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ],
    )

    asyncio.run(
        _reasoner(store, provider).run(
            [{"role": "user", "content": "use tool"}],
            tool_event_session_key="cli:s1",
            tool_event_channel="cli",
            tool_event_chat_id="s1",
        )
    )

    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            """
            SELECT assistant_tool_call_json
            FROM react_steps
            WHERE step_no = 0
            """
        ).fetchone()

    payload = json.loads(row[0])
    assert payload == [{"id": "call-1", "name": "step_probe", "arguments": {"value": "x"}}]


def test_final_response_marks_turn_completed(tmp_path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    provider = _InspectingProvider(store, [LLMResponse(content="final", tool_calls=[])])

    asyncio.run(
        _reasoner(store, provider).run(
            [{"role": "user", "content": "answer"}],
            tool_event_session_key="cli:s1",
            tool_event_channel="cli",
            tool_event_chat_id="s1",
        )
    )

    rows = store.list_recoverable_turn_runs(now=datetime.now().astimezone())
    assert rows == []
    with sqlite3.connect(store.db_path) as conn:
        status = conn.execute("SELECT status FROM turn_runs").fetchone()[0]
    assert status == "completed"
