from __future__ import annotations

from agent.task_plan.execution_redaction import (
    bounded_execution_preview,
    hash_execution_arguments,
    redact_execution_arguments,
)


def test_execution_arguments_are_recursively_redacted() -> None:
    redacted = redact_execution_arguments(
        {
            "path": "README.md",
            "headers": {"Authorization": "Bearer secret"},
            "api_key": "sk-secret",
            "nested": [{"password": "p"}, {"value": "visible"}],
        }
    )
    assert redacted["path"] == "README.md"
    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"][0]["password"] == "[REDACTED]"
    assert redacted["nested"][1]["value"] == "visible"


def test_execution_argument_hash_is_stable_for_mapping_order() -> None:
    assert hash_execution_arguments({"b": 2, "a": 1}) == hash_execution_arguments(
        {"a": 1, "b": 2}
    )


def test_execution_preview_normalizes_and_bounds_text() -> None:
    assert bounded_execution_preview(" first\n second\tthird ") == "first second third"
    assert bounded_execution_preview("abcdefgh", max_chars=7) == "abcd..."
