from __future__ import annotations

import asyncio
import json
import logging
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
        self._result = result or json.dumps({"ok": True})
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
    search_docs: _RecordingTool,
    fetch_doc_chunk: _RecordingTool,
    read_file: _RecordingTool | None = None,
) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.register(ToolSearchTool(tools), always_on=True, risk="read-only")
    tools.register(search_docs)
    tools.register(fetch_doc_chunk)
    tools.register(read_file or _RecordingTool("read_file"), always_on=True)
    tools.register(_RecordingTool("shell"), always_on=True)
    tools.register(_RecordingTool("list_dir"), always_on=True)

    def _render(request: ContextRequest, **_kwargs: object) -> ContextRenderResult:
        return ContextRenderResult(
            system_prompt="",
            turn_injection_context={"turn_injection": request.turn_injection_prompt or ""},
            messages=[{"role": "user", "content": request.current_message}],
            debug_breakdown=[],
        )

    return DefaultReasoner(
        llm=cast(Any, LLMServices(provider=provider, light_provider=provider)),
        llm_config=LLMConfig(model="m", max_iterations=6, max_tokens=256),
        tools=tools,
        discovery=ToolDiscoveryState(),
        tool_search_enabled=True,
        memory_window=10,
        context=cast(Any, SimpleNamespace(render=_render)),
        session_manager=cast(Any, SimpleNamespace(save_async=lambda *_args, **_kw: None)),
    )


def test_doc_rag_evidence_complete_switches_next_call_to_final_only(caplog) -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "my_md/doc.md > Agent Runtime"}],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool(
        "fetch_doc_chunk",
        json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                    "text": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            }
        ),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f2", "fetch_doc_chunk", {"chunk_id": "c2"})],
            ),
            LLMResponse(content="final answer with citation", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    with caplog.at_level(logging.INFO):
        result = asyncio.run(
            reasoner.run_turn(
                msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
                session=cast(Any, _session()),
            )
        )

    assert result.reply == "final answer with citation"
    assert len(search_docs.calls) == 1
    assert len(fetch_doc_chunk.calls) == 1
    assert result.tools_used == ["search_docs", "fetch_doc_chunk"]
    assert result.context_retry["turn_completion"]["action"] == "final_only"
    assert result.context_retry["turn_completion"]["reason"] == (
        "document_rag_evidence_complete"
    )
    assert result.context_retry["tool_boundary"]["ledger_summary"][
        "has_successful_retrieval"
    ] is True
    assert result.context_retry["tool_boundary"]["ledger_summary"][
        "has_citation_evidence"
    ] is True
    assert result.context_retry["turn_completion"]["metadata"]["soft_stop_count"] >= 1
    assert provider.calls[-1]["tools"] == []
    assert (
        "[tool_boundary] soft_stop tool=fetch_doc_chunk "
        "reason=document_rag_evidence_complete"
    ) in caplog.text
    assert (
        "[turn_completion] final_only reason=document_rag_evidence_complete"
    ) in caplog.text


def test_no_hit_retrieval_does_not_switch_to_final_only() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps({"ok": True, "hit_count": 0, "hits": []}),
    )
    fetch_doc_chunk = _RecordingTool("fetch_doc_chunk")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "missing"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q2", "search_docs", {"query": "try again"})],
            ),
            LLMResponse(content="final without final-only", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    assert result.reply == "final without final-only"
    assert len(search_docs.calls) == 1
    assert result.context_retry.get("turn_completion", {}).get("action") != "final_only"
    assert provider.calls[-1]["tools"] != []


def test_chunk_without_citation_does_not_switch_to_final_only() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "my_md/doc.md > Agent Runtime"}],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool(
        "fetch_doc_chunk",
        json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "content": "text without citation",
                },
            }
        ),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f2", "fetch_doc_chunk", {"chunk_id": "c2"})],
            ),
            LLMResponse(content="final without citation final-only", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    assert result.reply == "final without citation final-only"
    assert len(fetch_doc_chunk.calls) == 2
    assert result.context_retry.get("turn_completion", {}).get("action") != "final_only"
    assert provider.calls[-1]["tools"] != []


def test_explicit_local_source_request_does_not_switch_to_final_only() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "my_md/doc.md > Agent Runtime"}],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool(
        "fetch_doc_chunk",
        json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                    "text": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            }
        ),
    )
    read_file = _RecordingTool("read_file", "source text")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f2", "fetch_doc_chunk", {"chunk_id": "c2"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "r1",
                        "read_file",
                        {"path": "agent/core/passive_turn.py", "limit": 20},
                    )
                ],
            ),
            LLMResponse(content="final with source", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
        read_file=read_file,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg(
                "根据项目文档和源码回答，并展开原文证据，请读取 "
                "agent/core/passive_turn.py"
            ),
            session=cast(Any, _session()),
        )
    )

    assert result.reply == "final with source"
    assert len(fetch_doc_chunk.calls) == 1
    assert len(read_file.calls) == 1
    assert result.context_retry.get("turn_completion", {}).get("action") != "final_only"
    assert provider.calls[3]["tools"] != []


def test_final_only_ignores_tool_calls_returned_by_provider() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "my_md/doc.md > Agent Runtime"}],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool(
        "fetch_doc_chunk",
        json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                    "text": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            }
        ),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f2", "fetch_doc_chunk", {"chunk_id": "c2"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("bad", "search_docs", {"query": "again"})],
            ),
            LLMResponse(content="summary after ignored tool call", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    assert len(search_docs.calls) == 1
    assert len(fetch_doc_chunk.calls) == 1
    assert result.context_retry["turn_completion"]["action"] == "final_only"
    assert "final_only_tool_call" in result.reply
    assert provider.calls[3]["tools"] == []
    assert provider.calls[4]["tools"] == []
