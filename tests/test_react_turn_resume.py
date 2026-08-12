from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

from agent.core.types import ReasonerResult
from agent.looping.core import AgentLoop
from bus.events import OutboundMessage
from session.manager import SessionManager


NOW = datetime(2031, 1, 1, tzinfo=UTC)


def _seed_succeeded_tool_turn(manager: SessionManager) -> None:
    store = manager._store
    store.create_turn_run(
        turn_run_id="turn-1",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )
    store.create_react_step(
        step_id="step-1",
        turn_run_id="turn-1",
        step_no=0,
        model_input_json="[]",
        now=NOW,
    )
    store.mark_react_step_tool_pending(
        step_id="step-1",
        assistant_tool_call_json=json.dumps(
            [{"id": "call-1", "name": "read_file", "arguments": {"path": "README.md"}}],
            ensure_ascii=False,
        ),
        now=NOW,
    )
    attempt = store.persist_react_tool_call(
        turn_run_id="turn-1",
        step_id="step-1",
        tool_call_id="call-1",
        tool_name="read_file",
        arguments_json='{"path":"README.md"}',
        arguments_hash="hash",
        recovery_ref="call-1",
        pollable=False,
        idempotent=True,
        side_effect=False,
        now=NOW,
    )
    tool_message = store.insert_message(
        "cli:s1",
        role="tool",
        content="tool-result",
        ts=NOW.isoformat(),
        seq=0,
        extra={"tool_call_id": "call-1", "tool_name": "read_file"},
    )
    store.mark_tool_invocation_succeeded(
        attempt_id=str(attempt["attempt_id"]),
        result_message_id=str(tool_message["id"]),
        result_preview="tool-result",
        now=NOW,
    )


def test_resume_react_turn_replays_tool_result_and_posts_final_reply(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    _seed_succeeded_tool_turn(manager)
    loop = AgentLoop.__new__(AgentLoop)
    captured: dict[str, object] = {}

    class _Reasoner:
        async def run(self, initial_messages, **kwargs):
            captured["initial_messages"] = initial_messages
            captured["reasoner_kwargs"] = kwargs
            return ReasonerResult(
                reply="final after recovered tool",
                metadata={
                    "tools_used": [],
                    "tool_chain": [],
                    "react_stats": {"resume": True},
                },
            )

    class _Pipeline:
        async def post_reasoning(
            self,
            msg,
            session_key,
            turn_result,
            *,
            dispatch_outbound=True,
        ):
            captured["post_msg"] = msg
            captured["post_session_key"] = session_key
            captured["post_turn_result"] = turn_result
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=str(turn_result.reply),
            )

    loop._session_services = SimpleNamespace(session_manager=manager)
    loop._reasoner = _Reasoner()
    loop._agent_core = SimpleNamespace(pipeline=_Pipeline())

    outbound = asyncio.run(loop.resume_react_turn("turn-1"))

    assert outbound.content == "final after recovered tool"
    assert captured["initial_messages"] == [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "README.md"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "tool-result"},
    ]
    reasoner_kwargs = captured["reasoner_kwargs"]
    assert reasoner_kwargs["tool_event_session_key"] == "cli:s1"
    assert reasoner_kwargs["tool_event_channel"] == "cli"
    assert reasoner_kwargs["tool_event_chat_id"] == "s1"
    assert reasoner_kwargs["react_turn_run_id"] == "turn-1"
    assert reasoner_kwargs["react_step_no_offset"] == 1
    post_msg = captured["post_msg"]
    assert post_msg.metadata["omit_user_turn"] is True
    assert post_msg.metadata["react_recovery_turn_run_id"] == "turn-1"
    assert captured["post_session_key"] == "cli:s1"
