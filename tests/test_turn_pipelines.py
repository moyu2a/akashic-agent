import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.core.runtime_support import SessionLike, TurnRunResult
from agent.looping.core import AgentLoop, _supports_stream_events
from agent.looping.interrupt import TurnInterruptState
from agent.lifecycle.facade import TurnLifecycle
from agent.looping.ports import (
    AgentLoopConfig,
    AgentLoopDeps,
    MemoryConfig,
    MemoryServices,
)
from agent.provider import LLMResponse
from agent.retrieval.default_pipeline import DefaultMemoryRetrievalPipeline
from agent.retrieval.protocol import (
    MemoryRetrievalPipeline,
    RetrievalRequest,
    RetrievalResult,
)
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from bus.event_bus import EventBus
from bus.events import InboundMessage, OutboundMessage
from bus.events_lifecycle import TurnCommitted
from core.memory.engine import MemoryEngineRetrieveRequest, MemoryEngineRetrieveResult
from bootstrap.wiring import wire_turn_lifecycle


class _NoopTool(Tool):
    @property
    def name(self) -> str:
        return "noop"

    @property
    def description(self) -> str:
        return "noop"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> str:
        return "ok"


class _Provider:
    async def chat(self, **kwargs):
        return LLMResponse(content="ok", tool_calls=[])


class _PendingTask:
    def __init__(self) -> None:
        self.cancelled = False

    def done(self) -> bool:
        return False

    def cancel(self) -> None:
        self.cancelled = True


class _CustomRetrieval(MemoryRetrievalPipeline):
    def __init__(self, block: str) -> None:
        self._block = block
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.requests.append(request)
        return RetrievalResult(block=self._block)


class _FakeMemoryEngine:
    def read_self(self) -> str:
        return ""

    def read_recent_context(self) -> str:
        return ""

    def get_memory_context(self) -> str:
        return ""

    def has_long_term_memory(self) -> bool:
        return False

    async def retrieve(self, request) -> MemoryEngineRetrieveResult:
        return MemoryEngineRetrieveResult(text_block="", hits=[], raw={})

    async def refresh_recent_turns(self, request) -> None:
        return None

    async def consolidate(self, request) -> None:
        return None


class _RecordingMemoryEngine:
    def __init__(self) -> None:
        self.requests: list[MemoryEngineRetrieveRequest] = []

    async def retrieve(
        self, request: MemoryEngineRetrieveRequest
    ) -> MemoryEngineRetrieveResult:
        self.requests.append(request)
        mode = str(request.hints.get("safe_version_governed_mode") or "off")
        raw = {}
        if mode in {"shadow", "replace"}:
            raw["safe_version_governed_metadata"] = {
                "mode": mode,
                "contract_generation_success": True,
            }
        return MemoryEngineRetrieveResult(text_block="baseline memory", hits=[], raw=raw)


def _retrieval_request(message: str) -> RetrievalRequest:
    return RetrievalRequest(
        message=message,
        session_key="cli:1",
        channel="cli",
        chat_id="1",
        history=[],
        session_metadata={},
    )


def test_stream_events_only_support_telegram_private_chat():
    assert _supports_stream_events("telegram", "123")
    assert not _supports_stream_events("telegram", "-1001")
    assert not _supports_stream_events("telegram", "@alice")
    assert not _supports_stream_events("qq", "123")
    assert not _supports_stream_events("cli", "direct")


def test_stream_event_sink_respects_suppression_flag():
    loop = object.__new__(AgentLoop)
    loop._event_bus = EventBus()
    msg = InboundMessage(
        channel="telegram",
        sender="u",
        chat_id="123",
        content="hello",
        metadata={"suppress_stream_events": True},
    )

    assert AgentLoop._build_stream_event_sink(loop, msg) is None


@pytest.mark.asyncio
async def test_process_direct_suppresses_stream_and_memory_when_requested():
    loop = object.__new__(AgentLoop)
    loop._process = AsyncMock(
        return_value=OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="ok",
        )
    )

    result = await AgentLoop.process_direct(
        loop,
        content="天气",
        session_key="scheduler:job",
        channel="telegram",
        chat_id="123",
        omit_user_turn=True,
        skip_post_memory=True,
        disabled_tools=["message_push"],
    )

    msg = loop._process.await_args.args[0]
    assert result == "ok"
    assert msg.metadata == {
        "omit_user_turn": True,
        "skip_post_memory": True,
        "suppress_stream_events": True,
        "disabled_tools": ["message_push"],
    }
    assert loop._process.await_args.kwargs["dispatch_outbound"] is False


@pytest.mark.asyncio
async def test_process_direct_accepts_explicit_message_timestamp():
    loop = object.__new__(AgentLoop)
    loop._process = AsyncMock(
        return_value=OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="ok",
        )
    )
    timestamp = datetime.fromisoformat("2024-02-03T00:00:00+00:00")

    await AgentLoop.process_direct(
        loop,
        content="What happened yesterday?",
        session_key="eval:case",
        channel="public_long_memory_eval",
        chat_id="case",
        message_timestamp=timestamp,
    )

    msg = loop._process.await_args.args[0]
    assert msg.timestamp == timestamp


def _make_loop(
    tmp_path: Path,
    *,
    retrieval_pipeline: MemoryRetrievalPipeline | None = None,
) -> AgentLoop:
    tools = ToolRegistry()
    tools.register(_NoopTool())
    return AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=cast(Any, _Provider()),
            light_provider=cast(Any, _Provider()),
            tools=tools,
            session_manager=MagicMock(),
            workspace=tmp_path,
            memory_services=MemoryServices(engine=cast(Any, _FakeMemoryEngine())),
            retrieval_pipeline=retrieval_pipeline,
        ),
        AgentLoopConfig(),
    )


def test_agent_loop_uses_custom_retrieval_pipeline(tmp_path: Path):
    custom_retrieval = _CustomRetrieval(block="MEM_BLOCK")
    loop = _make_loop(
        tmp_path,
        retrieval_pipeline=custom_retrieval,
    )
    session = MagicMock()
    session.key = "cli:1"
    session.messages = []
    session.metadata = {}
    session.get_history = MagicMock(
        return_value=[{"role": "user", "content": f"m{i}"} for i in range(200)]
    )
    session.add_message = MagicMock()
    loop.session_manager.get_or_create.return_value = session
    loop.session_manager.append_messages = AsyncMock(return_value=None)
    loop._reasoner.run_turn = AsyncMock(return_value=TurnRunResult(reply="ok"))

    msg = InboundMessage(channel="cli", sender="u", chat_id="1", content="hello")
    asyncio.run(loop._core_runner.process(msg, msg.session_key))

    assert custom_retrieval.requests
    assert custom_retrieval.requests[0].message == "hello"
    run_kwargs = loop._reasoner.run_turn.await_args.kwargs
    assert "base_history" in run_kwargs
    assert run_kwargs["base_history"] is None


def test_agent_loop_fanouts_turn_committed_from_passive_turn(tmp_path: Path):
    loop = _make_loop(
        tmp_path,
        retrieval_pipeline=_CustomRetrieval(block="MEM_BLOCK"),
    )
    turn_events: list[TurnCommitted] = []
    loop._event_bus.on(TurnCommitted, lambda event: turn_events.append(event))
    session = MagicMock()
    session.key = "cli:1"
    session.messages = []
    session.metadata = {}
    session.get_history = MagicMock(return_value=[])
    session.add_message = MagicMock(
        side_effect=lambda role, content, **kwargs: session.messages.append(
            {"role": role, "content": content, **kwargs}
        )
    )
    loop.session_manager.get_or_create.return_value = session
    loop.session_manager.append_messages = AsyncMock(return_value=None)
    loop._reasoner.run_turn = AsyncMock(
        return_value=TurnRunResult(
            reply="ok",
            tool_chain=[
                {
                    "text": "",
                    "calls": [
                        {
                            "name": "noop",
                            "arguments": {"x": 1},
                            "result": "done",
                        }
                    ],
                }
            ],
            context_retry={
                "react_stats": {
                    "iteration_count": 1,
                    "turn_input_sum_tokens": 100,
                }
            },
        )
    )

    msg = InboundMessage(channel="cli", sender="u", chat_id="1", content="hello")

    async def _process_and_drain() -> None:
        await loop._core_runner.process(msg, msg.session_key)
        await loop._event_bus.drain()
        await loop._event_bus.aclose()

    asyncio.run(_process_and_drain())

    assert turn_events
    turn_event = turn_events[0]
    assert turn_event.session_key == "cli:1"
    assert turn_event.persisted_user_message == "hello"
    assert turn_event.assistant_response == "ok"
    assert turn_event.tool_chain_raw[0]["calls"][0]["name"] == "noop"
    assert turn_event.react_stats["iteration_count"] == 1
    assert turn_event.react_stats["turn_input_sum_tokens"] == 100


def test_request_interrupt_uses_active_turn_state_snapshot(tmp_path: Path):
    loop = _make_loop(tmp_path)
    session_key = "telegram:123"
    pending = _PendingTask()
    loop._active_tasks[session_key] = pending  # type: ignore[attr-defined]
    loop._active_turn_states[session_key] = TurnInterruptState(  # type: ignore[attr-defined]
        session_key=session_key,
        original_user_message="原始消息 A",
    )

    result = loop.request_interrupt(session_key, sender="1", command="/stop")

    assert result.status == "interrupted"
    assert pending.cancelled is True
    assert loop._interrupt_states[session_key].original_user_message == "原始消息 A"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_resumed_interrupt_state_completes_normally(tmp_path: Path):
    loop = _make_loop(tmp_path)
    session_key = "telegram:123"
    loop._interrupt_states[session_key] = TurnInterruptState(  # type: ignore[attr-defined]
        session_key=session_key,
        original_user_message="原始消息 A",
        partial_reply="半截回答",
    )
    async def _slow_process(*args, **kwargs):
        await asyncio.sleep(0.05)
        return MagicMock(content="ok")

    loop._core_runner.process = _slow_process  # type: ignore[attr-defined]

    msg = InboundMessage(
        channel="telegram",
        sender="1",
        chat_id="123",
        content="补充 B",
    )
    outbound = await loop._process(msg)

    assert outbound.content == "ok"
    assert session_key not in loop._interrupt_states  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_agent_loop_afterstep_fires_with_turn_lifecycle_wiring(tmp_path: Path):
    loop = _make_loop(tmp_path)
    session_key = "cli:123"
    loop._active_turn_states[session_key] = TurnInterruptState(
        session_key=session_key,
        original_user_message="hello",
    )
    wire_turn_lifecycle(
        lifecycle=TurnLifecycle(loop._event_bus),
        active_turn_states=loop.active_turn_states,
    )
    msg = InboundMessage(channel="cli", sender="u", chat_id="123", content="你好")
    session = SimpleNamespace(
        key=session_key,
        messages=[],
        metadata={},
        last_consolidated=0,
        get_history=MagicMock(return_value=[]),
        add_message=MagicMock(),
    )
    loop.session_manager.get_or_create.return_value = session

    await loop._reasoner.run_turn(
        msg=msg,
        session=cast(SessionLike, session),
        base_history=[],
    )

    state = loop._active_turn_states[session_key]
    assert state.partial_reply == "ok"
    assert state.tools_used == []
    assert state.tool_chain_partial == []


@pytest.mark.asyncio
async def test_retrieval_pipeline_defaults_safe_version_mode_off() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(MemoryServices(engine=engine))

    result = await pipeline.retrieve(_retrieval_request("请记得我的测试偏好"))

    assert "safe_version_governed_mode" not in engine.requests[-1].hints
    assert "safe_version_governed_replace_allowed" not in engine.requests[-1].hints
    assert "safe_version_governed_mode" not in result.metadata


@pytest.mark.asyncio
async def test_retrieval_pipeline_passes_safe_version_mode_from_config() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="shadow",
    )

    result = await pipeline.retrieve(_retrieval_request("请记得我的测试偏好"))

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert result.metadata.get("safe_version_governed_mode") == "shadow"


@pytest.mark.asyncio
async def test_retrieval_pipeline_allows_session_metadata_shadow_override_for_tests() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="off",
    )
    request = _retrieval_request("请记得我的测试偏好")
    request.session_metadata["safe_version_governed_mode"] = "shadow"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is False


@pytest.mark.asyncio
async def test_retrieval_pipeline_rejects_session_metadata_replace_without_allow_gate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="off",
        safe_version_governed_replace_allowed=False,
    )
    request = _retrieval_request("请记得我的测试偏好")
    request.session_metadata["safe_version_governed_mode"] = "replace"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is False


@pytest.mark.asyncio
async def test_retrieval_pipeline_rejects_session_metadata_replace_even_when_allow_flag_true() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="off",
        safe_version_governed_replace_allowed=True,
    )
    request = _retrieval_request("请记得我的测试偏好")
    request.session_metadata["safe_version_governed_mode"] = "replace"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is False


@pytest.mark.asyncio
async def test_retrieval_pipeline_allows_replace_only_from_config_gate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
    )

    await pipeline.retrieve(_retrieval_request("请记得我的测试偏好"))

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is True


@pytest.mark.asyncio
async def test_retrieval_pipeline_passes_safe_version_guidance_only_from_config() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=True,
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.session_metadata["safe_version_answer_guidance_enabled"] = False

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is True
    assert engine.requests[-1].hints["safe_version_answer_guidance_enabled"] is True


@pytest.mark.asyncio
async def test_retrieval_pipeline_ignores_session_guidance_escalation() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.session_metadata["safe_version_answer_guidance_enabled"] = True

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_guidance_enabled" not in engine.requests[-1].hints


@pytest.mark.asyncio
async def test_retrieval_pipeline_ignores_extra_guidance_escalation() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.extra["safe_version_answer_guidance_enabled"] = True

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_guidance_enabled" not in engine.requests[-1].hints


@pytest.mark.parametrize(
    "prompt_variant",
    ["structured_guided", "schema_first_shadow"],
)
@pytest.mark.asyncio
async def test_safe_version_answer_prompt_variant_flows_from_config_only(
    prompt_variant: str,
) -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=True,
        safe_version_answer_prompt_variant=prompt_variant,
    )
    request = _retrieval_request("我默认用什么测试框架？")

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert engine.requests[-1].hints["safe_version_answer_guidance_enabled"] is True
    assert engine.requests[-1].hints["safe_version_answer_prompt_variant"] == prompt_variant


@pytest.mark.asyncio
async def test_safe_version_answer_prompt_variant_extra_cannot_escalate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
        safe_version_answer_prompt_variant="standard",
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.extra["safe_version_answer_prompt_variant"] = "schema_first_shadow"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_prompt_variant" not in engine.requests[-1].hints


@pytest.mark.asyncio
async def test_safe_version_answer_prompt_variant_session_metadata_cannot_escalate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
        safe_version_answer_prompt_variant="standard",
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.session_metadata["safe_version_answer_prompt_variant"] = "schema_first_shadow"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_prompt_variant" not in engine.requests[-1].hints


@pytest.mark.asyncio
async def test_safe_version_answer_prompt_variant_requires_guidance_gate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
        safe_version_answer_prompt_variant="structured_guided",
    )

    await pipeline.retrieve(_retrieval_request("我默认用什么测试框架？"))

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_guidance_enabled" not in engine.requests[-1].hints
    assert "safe_version_answer_prompt_variant" not in engine.requests[-1].hints


@pytest.mark.asyncio
async def test_retrieval_pipeline_ignores_extra_safe_version_replace_escalation() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="off",
        safe_version_governed_replace_allowed=False,
        safe_version_answer_guidance_enabled=True,
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.extra["safe_version_governed_mode"] = "replace"
    request.extra["safe_version_governed_replace_allowed"] = True
    request.extra["safe_version_answer_guidance_enabled"] = True

    await pipeline.retrieve(request)

    assert "safe_version_governed_mode" not in engine.requests[-1].hints
    assert "safe_version_governed_replace_allowed" not in engine.requests[-1].hints
    assert "safe_version_answer_guidance_enabled" not in engine.requests[-1].hints


def test_agent_loop_passes_safe_version_config_to_default_retrieval_pipeline(
    tmp_path: Path,
) -> None:
    tools = ToolRegistry()
    tools.register(_NoopTool())

    loop = AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=cast(Any, _Provider()),
            light_provider=cast(Any, _Provider()),
            tools=tools,
            session_manager=MagicMock(),
            workspace=tmp_path,
            memory_services=MemoryServices(engine=cast(Any, _FakeMemoryEngine())),
            retrieval_pipeline=None,
        ),
        AgentLoopConfig(
            memory=MemoryConfig(
                safe_version_governed_mode="replace",
                safe_version_governed_replace_allowed=True,
                safe_version_answer_guidance_enabled=True,
            )
        ),
    )

    assert isinstance(loop._retrieval_pipeline, DefaultMemoryRetrievalPipeline)
    assert loop._retrieval_pipeline._safe_version_governed_mode == "replace"
    assert loop._retrieval_pipeline._safe_version_governed_replace_allowed is True
    assert loop._retrieval_pipeline._safe_version_answer_guidance_enabled is True
