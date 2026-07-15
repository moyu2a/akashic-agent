from __future__ import annotations

from dataclasses import replace

import pytest

from agent.task_plan.execution_models import (
    ACTIVE_ATTEMPT_STATUSES,
    TERMINAL_ATTEMPT_STATUSES,
    TaskExecutionAttempt,
    validate_attempt_status,
    validate_attempt_transition,
)


def test_attempt_terminal_state_cannot_transition() -> None:
    with pytest.raises(ValueError, match="terminal attempt"):
        validate_attempt_transition("succeeded", "running")


def test_attempt_to_dict_deep_copies_nested_metadata() -> None:
    attempt = replace(
        TaskExecutionAttempt.new(
            task_id="task-1",
            step_id="step-1",
            session_key="cli:s1",
            request_id="req-1",
            idempotency_key="idem-1",
            attempt_no=1,
            owner_instance_id="runtime-1",
            lease_expires_at="2026-07-15T01:00:00+00:00",
        ),
        metadata={"nested": {"value": "original"}},
    )
    payload = attempt.to_dict()
    payload["metadata"]["nested"]["value"] = "changed"
    assert attempt.metadata["nested"]["value"] == "original"


def test_waiting_attempt_can_only_cancel_in_la002() -> None:
    validate_attempt_transition("waiting_authorization", "cancelled")
    with pytest.raises(ValueError, match="invalid attempt transition"):
        validate_attempt_transition("waiting_authorization", "pending")


def test_attempt_serialization_returns_copies() -> None:
    attempt = TaskExecutionAttempt.new(
        task_id="task_1",
        step_id="step_1",
        session_key="cli:s1",
        request_id="req_1",
        idempotency_key="idem_1",
        attempt_no=1,
        owner_instance_id="runtime_1",
        lease_expires_at="2026-07-15T01:00:00+00:00",
    )
    payload = attempt.to_dict()
    payload["metadata"]["mutated"] = True
    assert attempt.metadata == {}
    assert replace(attempt, status="pending").status == "pending"


def test_attempt_serialization_redacts_nested_execution_payloads() -> None:
    attempt = replace(
        TaskExecutionAttempt.new(
            task_id="task_1",
            step_id="step_1",
            session_key="cli:s1",
            request_id="req_1",
            idempotency_key="idem_1",
            attempt_no=1,
            owner_instance_id="runtime_1",
            lease_expires_at="2026-07-15T01:00:00+00:00",
        ),
        requested_arguments={
            "path": "README.md",
            "headers": {"Authorization": "Bearer request-secret"},
            "nested": [{"token": "request-token"}],
        },
        metadata={
            "source": "cli",
            "nested": {"api_key": "metadata-secret"},
        },
    )

    payload = attempt.to_dict()

    assert payload["requested_arguments"]["path"] == "README.md"
    assert payload["requested_arguments"]["headers"]["Authorization"] == "[REDACTED]"
    assert payload["requested_arguments"]["nested"][0]["token"] == "[REDACTED]"
    assert payload["metadata"]["source"] == "cli"
    assert payload["metadata"]["nested"]["api_key"] == "[REDACTED]"
    assert attempt.requested_arguments["headers"]["Authorization"] == (
        "Bearer request-secret"
    )
    assert attempt.metadata["nested"]["api_key"] == "metadata-secret"


def test_attempt_status_sets_and_validator_match_contract() -> None:
    assert ACTIVE_ATTEMPT_STATUSES == {
        "pending",
        "running",
        "waiting_authorization",
    }
    assert TERMINAL_ATTEMPT_STATUSES == {
        "succeeded",
        "failed",
        "blocked",
        "cancelled",
    }
    assert validate_attempt_status("blocked") == "blocked"
    with pytest.raises(ValueError, match="invalid attempt status"):
        validate_attempt_status("unknown")
