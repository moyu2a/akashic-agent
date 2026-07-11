from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

from agent.core.passive_turn import DefaultReasoner
from agent.core.runtime_support import LLMServices, ToolDiscoveryState
from agent.core.types import ContextRenderResult, ContextRequest, ReasonerResult
from agent.looping.ports import LLMConfig
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from agent.tools.tool_search import ToolSearchTool


class _DummyTool(Tool):
    def __init__(self, name: str) -> None:
        self._name = name

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
        return f"{self._name}-ok"


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


def _make_reasoner(discovery: ToolDiscoveryState) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.register(ToolSearchTool(tools), always_on=True, risk="read-only")
    tools.register(_DummyTool("search_docs"))
    tools.register(_DummyTool("fetch_doc_chunk"))
    tools.register(_DummyTool("recall_memory"))

    def _render(request: ContextRequest, **_kwargs: object) -> ContextRenderResult:
        return ContextRenderResult(
            system_prompt="",
            turn_injection_context={
                "turn_injection": request.turn_injection_prompt or ""
            },
            messages=[{"role": "user", "content": request.current_message}],
            debug_breakdown=[],
        )

    reasoner = DefaultReasoner(
        llm=cast(
            Any,
            LLMServices(
                provider=SimpleNamespace(chat=AsyncMock()),
                light_provider=SimpleNamespace(chat=AsyncMock()),
            ),
        ),
        llm_config=LLMConfig(model="m", max_iterations=4, max_tokens=256),
        tools=tools,
        discovery=discovery,
        tool_search_enabled=True,
        memory_window=10,
        context=cast(Any, SimpleNamespace(render=_render)),
        session_manager=cast(Any, SimpleNamespace(save_async=AsyncMock())),
    )
    reasoner.run = AsyncMock(
        return_value=ReasonerResult(
            reply="ok",
            metadata={"tools_used": [], "tool_chain": []},
        )
    )
    return reasoner


def test_run_turn_preloads_search_docs_for_strong_doc_intent() -> None:
    discovery = ToolDiscoveryState()
    reasoner = _make_reasoner(discovery)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("请从文档知识库中检索 agent runtime 负责什么"),
            session=cast(Any, _session()),
        )
    )

    kwargs = reasoner.run.call_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["preloaded_tools"] == {"search_docs"}
    assert discovery.get_preloaded("cli:1") == set()


def test_run_turn_preloads_fetch_doc_chunk_for_doc_evidence_intent() -> None:
    discovery = ToolDiscoveryState()
    reasoner = _make_reasoner(discovery)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    kwargs = reasoner.run.call_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["preloaded_tools"] == {"search_docs", "fetch_doc_chunk"}
    assert discovery.get_preloaded("cli:1") == set()


def test_memory_after_doc_lru_suppresses_doc_rag_for_current_turn_only() -> None:
    discovery = ToolDiscoveryState()
    discovery._unlocked["cli:1"] = OrderedDict(
        [("search_docs", None), ("fetch_doc_chunk", None), ("recall_memory", None)]
    )
    reasoner = _make_reasoner(discovery)
    session = _session()

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("你还记得我之前说过我的偏好吗？"),
            session=cast(Any, session),
        )
    )

    kwargs = reasoner.run.call_args.kwargs  # type: ignore[attr-defined]
    assert kwargs["preloaded_tools"] == {"recall_memory"}
    assert discovery.get_preloaded("cli:1") == {
        "search_docs",
        "fetch_doc_chunk",
        "recall_memory",
    }
