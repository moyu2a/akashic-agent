from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from agent.core.runtime_support import TurnRunResult
from agent.lifecycle.phase import Phase
from agent.lifecycle.phases.after_reasoning import (
    AfterReasoningFrame,
    default_after_reasoning_modules,
)
from agent.lifecycle.types import AfterReasoningInput, TurnState
from agent.looping.core import AgentLoop
from agent.looping.interrupt import TurnInterruptState
from agent.looping.ports import SessionServices
from bus.event_bus import EventBus
from bus.events import InboundMessage
from session.manager import SessionManager


def _inbound() -> InboundMessage:
    return InboundMessage(
        channel="telegram",
        sender="hua",
        chat_id="123",
        content="你好",
        timestamp=datetime.now().astimezone(),
    )


def _loop_with_session_manager(manager: SessionManager) -> AgentLoop:
    loop = cast(AgentLoop, AgentLoop.__new__(AgentLoop))
    loop._session_services = SessionServices(session_manager=manager, presence=None)
    loop._active_turn_states = {}
    return loop


def test_stream_delta_persists_user_assistant_and_generation(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("telegram:123")
    manager.save(session)
    loop = _loop_with_session_manager(manager)
    loop._active_turn_states[session.key] = TurnInterruptState(
        session_key=session.key,
        original_user_message="你好",
    )

    loop._append_partial_reply(session.key, "半截")
    loop._append_partial_reply(session.key, "回复")

    state = loop._active_turn_states[session.key]
    assert state.stream_user_message_id
    assert state.stream_message_id
    assert state.stream_generation_id

    messages = manager._store.fetch_session_messages(session.key)
    assert [(msg["role"], msg["content"]) for msg in messages] == [
        ("user", "你好"),
        ("assistant", "半截回复"),
    ]
    generation = manager._store.get_message_generation(state.stream_generation_id)
    assert generation is not None
    assert generation["status"] == "streaming"
    assert generation["message_id"] == state.stream_message_id
    assert generation["partial_content"] == "半截回复"
    assert generation["last_streamed_offset"] == len("半截回复")


@pytest.mark.asyncio
async def test_after_reasoning_reuses_streaming_message_without_duplicate(
    tmp_path: Path,
) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("telegram:123")
    manager.save(session)
    loop = _loop_with_session_manager(manager)
    loop._active_turn_states[session.key] = TurnInterruptState(
        session_key=session.key,
        original_user_message="你好",
    )
    loop._append_partial_reply(session.key, "半截")
    stream_state = loop._active_turn_states[session.key]

    state = TurnState(msg=_inbound(), session_key=session.key, dispatch_outbound=True)
    state.session = session
    turn_result = TurnRunResult(
        reply="完整回复",
        streamed=True,
        context_retry={
            "streaming_user_message_id": stream_state.stream_user_message_id,
            "streaming_user_seq": stream_state.stream_user_seq,
            "streaming_message_id": stream_state.stream_message_id,
            "streaming_message_seq": stream_state.stream_message_seq,
            "streaming_generation_id": stream_state.stream_generation_id,
        },
    )
    phase = Phase(
        default_after_reasoning_modules(
            EventBus(),
            cast(Any, SessionServices(session_manager=manager, presence=None)),
        ),
        frame_factory=AfterReasoningFrame,
    )

    await phase.run(AfterReasoningInput(state=state, turn_result=turn_result))

    messages = manager._store.fetch_session_messages(session.key)
    assert [(msg["role"], msg["content"]) for msg in messages] == [
        ("user", "你好"),
        ("assistant", "完整回复"),
    ]
    assert session.messages[-2]["id"] == stream_state.stream_user_message_id
    assert session.messages[-1]["id"] == stream_state.stream_message_id
    generation = manager._store.get_message_generation(stream_state.stream_generation_id)
    assert generation is not None
    assert generation["status"] == "finished"
    assert generation["partial_content"] == "完整回复"
