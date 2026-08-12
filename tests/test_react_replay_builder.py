from __future__ import annotations

import pytest
from datetime import UTC, datetime
from pathlib import Path

from agent.recovery.react_replay import ReactReplayBlocked, ReactReplayBuilder
from session.store import SessionStore


NOW = datetime(2031, 1, 1, tzinfo=UTC)


def _seed_turn(store: SessionStore, *, tool_call_id: str = "call-1") -> str:
    user = store.insert_message(
        "cli:s1",
        role="user",
        content="use tool",
        ts=NOW.isoformat(),
        seq=0,
    )
    store.create_turn_run(
        turn_run_id="turn-1",
        session_key="cli:s1",
        user_message_id=user["id"],
        now=NOW,
    )
    step = store.create_react_step(
        step_id="step-1",
        turn_run_id="turn-1",
        step_no=0,
        model_input_json="[]",
        now=NOW,
    )
    store.mark_react_step_tool_pending(
        step_id=step["step_id"],
        assistant_tool_call_json=(
            f'[{{"id":"{tool_call_id}","name":"read_file","arguments":{{"path":"README.md"}}}}]'
        ),
        now=NOW,
    )
    attempt = store.persist_react_tool_call(
        turn_run_id="turn-1",
        step_id=step["step_id"],
        tool_call_id=tool_call_id,
        tool_name="read_file",
        arguments_json='{"path":"README.md"}',
        arguments_hash="hash-1",
        recovery_ref=tool_call_id,
        pollable=False,
        idempotent=True,
        side_effect=False,
        now=NOW,
    )
    result = store.insert_message(
        "cli:s1",
        role="tool",
        content="README contents",
        ts=NOW.isoformat(),
        seq=1,
        extra={"tool_call_id": tool_call_id},
    )
    store.mark_tool_invocation_succeeded(
        attempt_id=attempt["attempt_id"],
        result_message_id=result["id"],
        result_preview="README contents",
        now=NOW,
    )
    return "turn-1"


def test_replay_builder_reconstructs_valid_tool_call_and_result(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    turn_run_id = _seed_turn(store)

    messages = ReactReplayBuilder(store).build_messages(
        session_key="cli:s1",
        turn_run_id=turn_run_id,
    )

    assert messages == [
        {"role": "user", "content": "use tool"},
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
        {"role": "tool", "tool_call_id": "call-1", "content": "README contents"},
    ]


def test_replay_builder_uses_model_input_when_user_message_was_not_committed(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    store.create_turn_run(
        turn_run_id="turn-1",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )
    step = store.create_react_step(
        step_id="step-1",
        turn_run_id="turn-1",
        step_no=0,
        model_input_json='[{"role":"system","content":"sys"},{"role":"user","content":"use tool"}]',
        now=NOW,
    )
    store.mark_react_step_tool_pending(
        step_id=step["step_id"],
        assistant_tool_call_json=(
            '[{"id":"call-1","name":"read_file","arguments":{"path":"README.md"}}]'
        ),
        now=NOW,
    )
    attempt = store.persist_react_tool_call(
        turn_run_id="turn-1",
        step_id=step["step_id"],
        tool_call_id="call-1",
        tool_name="read_file",
        arguments_json='{"path":"README.md"}',
        arguments_hash="hash-1",
        recovery_ref="call-1",
        pollable=False,
        idempotent=True,
        side_effect=False,
        now=NOW,
    )
    result = store.insert_message(
        "cli:s1",
        role="tool",
        content="README contents",
        ts=NOW.isoformat(),
        seq=0,
        extra={"tool_call_id": "call-1"},
    )
    store.mark_tool_invocation_succeeded(
        attempt_id=attempt["attempt_id"],
        result_message_id=result["id"],
        result_preview="README contents",
        now=NOW,
    )

    messages = ReactReplayBuilder(store).build_messages(
        session_key="cli:s1",
        turn_run_id="turn-1",
    )

    assert messages[:2] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "use tool"},
    ]


def test_replay_builder_reconstructs_valid_multi_tool_batch(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    turn_run_id = _seed_turn(store)
    step = store.get_react_step("step-1")
    assert step is not None
    store.mark_react_step_tool_pending(
        step_id="step-1",
        assistant_tool_call_json=(
            '[{"id":"call-1","name":"read_file","arguments":{"path":"README.md"}},'
            '{"id":"call-2","name":"read_file","arguments":{"path":"pyproject.toml"}}]'
        ),
        now=NOW,
    )
    attempt = store.persist_react_tool_call(
        turn_run_id=turn_run_id,
        step_id="step-1",
        tool_call_id="call-2",
        tool_name="read_file",
        arguments_json='{"path":"pyproject.toml"}',
        arguments_hash="hash-2",
        recovery_ref="call-2",
        pollable=False,
        idempotent=True,
        side_effect=False,
        now=NOW,
    )
    result = store.insert_message(
        "cli:s1",
        role="tool",
        content="pyproject contents",
        ts=NOW.isoformat(),
        seq=2,
        extra={"tool_call_id": "call-2"},
    )
    store.mark_tool_invocation_succeeded(
        attempt_id=attempt["attempt_id"],
        result_message_id=result["id"],
        result_preview="pyproject contents",
        now=NOW,
    )

    messages = ReactReplayBuilder(store).build_messages(
        session_key="cli:s1",
        turn_run_id=turn_run_id,
    )

    tool_ids = [
        message["tool_call_id"]
        for message in messages
        if message["role"] == "tool"
    ]
    assert tool_ids == ["call-1", "call-2"]


def test_replay_builder_blocks_tool_result_without_matching_tool_call(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    turn_run_id = _seed_turn(store, tool_call_id="call-1")
    with store._conn:  # noqa: SLF001 - white-box corruption for recovery test.
        store._conn.execute(
            """
            UPDATE tool_invocation_attempts
            SET tool_call_id = 'wrong-call'
            WHERE turn_run_id = ?
            """,
            (turn_run_id,),
        )

    with pytest.raises(ReactReplayBlocked) as exc:
        ReactReplayBuilder(store).build_messages(
            session_key="cli:s1",
            turn_run_id=turn_run_id,
        )

    assert exc.value.reason == "blocked_replay_tool_call_mismatch"


def test_replay_builder_blocks_missing_tool_result_message(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    turn_run_id = _seed_turn(store)
    with store._conn:  # noqa: SLF001 - white-box corruption for recovery test.
        store._conn.execute("DELETE FROM messages WHERE role = 'tool'")

    with pytest.raises(ReactReplayBlocked) as exc:
        ReactReplayBuilder(store).build_messages(
            session_key="cli:s1",
            turn_run_id=turn_run_id,
        )

    assert exc.value.reason == "blocked_replay_missing_tool_result"
