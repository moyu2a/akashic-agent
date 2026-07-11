from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast

from agent.core.passive_turn import DefaultReasoner
from agent.core.runtime_support import LLMServices, ToolDiscoveryState
from agent.core.types import ContextRenderResult, ContextRequest
from agent.looping.ports import LLMConfig
from agent.provider import LLMResponse, ToolCall
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from agent.tools.tool_search import ToolSearchTool


class _RecordingTool(Tool):
    def __init__(self, name: str, result: str | None = None) -> None:
        self._name = name
        self._result = result or f"{name}-ok"
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self._result


class _Provider:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("provider.chat called more than expected")
        return self._responses.pop(0)


def _msg(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        media=[],
        channel="cli",
        chat_id="1",
        timestamp=datetime.now(timezone.utc),
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        key="cli:1",
        messages=[],
        metadata={},
        get_history=lambda max_messages=40, *, start_index=None: [],
        last_consolidated=0,
    )


def _make_reasoner(
    provider: _Provider,
    *,
    read_file: _RecordingTool | None = None,
) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.register(ToolSearchTool(tools), always_on=True, risk="read-only")
    tools.register(_RecordingTool("search_docs"))
    tools.register(_RecordingTool("fetch_doc_chunk"))
    tools.register(read_file or _RecordingTool("read_file"), always_on=True)
    tools.register(_RecordingTool("shell"), always_on=True)
    tools.register(_RecordingTool("list_dir"), always_on=True)
    tools.register(_RecordingTool("recall_memory"))

    def _render(request: ContextRequest, **_kwargs: object) -> ContextRenderResult:
        return ContextRenderResult(
            system_prompt="",
            turn_injection_context={
                "turn_injection": request.turn_injection_prompt or ""
            },
            messages=[{"role": "user", "content": request.current_message}],
            debug_breakdown=[],
        )

    return DefaultReasoner(
        llm=cast(
            Any,
            LLMServices(provider=provider, light_provider=provider),
        ),
        llm_config=LLMConfig(model="m", max_iterations=4, max_tokens=256),
        tools=tools,
        discovery=ToolDiscoveryState(),
        tool_search_enabled=True,
        memory_window=10,
        context=cast(Any, SimpleNamespace(render=_render)),
        session_manager=cast(Any, SimpleNamespace(save_async=lambda *_args, **_kw: None)),
    )


def _tool_names(call: dict[str, Any]) -> set[str]:
    return {schema["function"]["name"] for schema in call["tools"]}


def test_strong_doc_prompt_suppresses_local_file_schemas_even_if_always_on() -> None:
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(provider)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    names = _tool_names(provider.calls[0])
    assert {"search_docs", "fetch_doc_chunk", "tool_search"} <= names
    assert names.isdisjoint({"read_file", "shell", "list_dir"})


def test_tool_search_result_is_filtered_before_model_can_see_blocked_tool() -> None:
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("s1", "tool_search", {"query": "select:read_file"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    tool_result_messages = [
        msg for msg in provider.calls[1]["messages"] if msg.get("role") == "tool"
    ]
    assert tool_result_messages
    payload = json.loads(tool_result_messages[-1]["content"])
    assert payload["matched"] == []
    assert payload["blocked_by_tool_access_gateway"] == ["read_file"]
    assert result.context_retry["tool_access"]["visible_suppress"] == [
        "list_dir",
        "read_file",
        "shell",
    ]


def test_gateway_blocked_tool_call_does_not_execute_or_count_as_used() -> None:
    read_file = _RecordingTool("read_file")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("r1", "read_file", {"path": "README.md"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider, read_file=read_file)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    assert read_file.calls == []
    assert result.tools_used == []
    call = result.tool_chain[0]["calls"][0]
    assert call["name"] == "read_file"
    assert call["status"] == "blocked_by_tool_access_gateway"
    assert "tool_blocked_by_doc_rag_policy" in call["result"]


def test_explicit_source_request_keeps_local_file_schemas_available() -> None:
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(provider)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档和源码回答，请读取 agent/core/passive_turn.py"),
            session=cast(Any, _session()),
        )
    )

    names = _tool_names(provider.calls[0])
    assert {"search_docs", "read_file"} <= names
