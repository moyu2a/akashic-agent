from __future__ import annotations

from bus.events import InboundMessage
from agent.task_plan.request_identity import (
    derive_task_execution_idempotency_key,
    ensure_task_execution_request_id,
)


def test_existing_transport_request_id_is_preserved() -> None:
    msg = InboundMessage(
        channel="cli",
        sender="user",
        chat_id="s1",
        content="continue",
        metadata={"_transport_request_id": "req-transport"},
    )

    assert ensure_task_execution_request_id(msg) == "req-transport"
    assert msg.metadata["_task_execution_request_id"] == "req-transport"


def test_existing_task_execution_request_id_is_not_replaced() -> None:
    msg = InboundMessage(
        channel="cli",
        sender="user",
        chat_id="s1",
        content="continue",
        metadata={
            "_transport_request_id": "req-transport",
            "_task_execution_request_id": "runtime-existing",
        },
    )

    assert ensure_task_execution_request_id(msg) == "runtime-existing"
    assert msg.metadata["_task_execution_request_id"] == "runtime-existing"


def test_runtime_request_ids_are_distinct_for_identical_message_text() -> None:
    first = InboundMessage(
        channel="cli", sender="user", chat_id="s1", content="continue"
    )
    second = InboundMessage(
        channel="cli", sender="user", chat_id="s1", content="continue"
    )

    first_request_id = ensure_task_execution_request_id(first)
    second_request_id = ensure_task_execution_request_id(second)

    assert first_request_id.startswith("runtime-")
    assert second_request_id.startswith("runtime-")
    assert first_request_id != second_request_id


def test_idempotency_key_is_deterministic_and_scoped_to_all_request_fields() -> None:
    first = derive_task_execution_idempotency_key(
        session_key="cli:s1",
        request_id="req-1",
        task_id="task-1",
        step_id="step-1",
        action="continue",
    )

    assert first == derive_task_execution_idempotency_key(
        session_key="cli:s1",
        request_id="req-1",
        task_id="task-1",
        step_id="step-1",
        action="continue",
    )
    assert first != derive_task_execution_idempotency_key(
        session_key="cli:s1",
        request_id="req-1",
        task_id="task-1",
        step_id="step-1",
        action="retry",
    )


def test_idempotency_key_changes_for_distinct_request() -> None:
    first = derive_task_execution_idempotency_key(
        session_key="cli:s1",
        request_id="req-1",
        task_id="task-1",
        step_id="step-1",
        action="continue",
    )
    second = derive_task_execution_idempotency_key(
        session_key="cli:s1",
        request_id="req-2",
        task_id="task-1",
        step_id="step-1",
        action="continue",
    )

    assert first != second
