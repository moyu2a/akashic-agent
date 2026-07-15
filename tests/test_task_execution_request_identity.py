from __future__ import annotations

from agent.task_plan.request_identity import derive_task_execution_idempotency_key


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
