from __future__ import annotations

from eval.agent_harness.graders import (
    grade_outcome,
    grade_quality,
    grade_router,
    grade_security,
    grade_trajectory,
)
from eval.agent_harness.protocol import TaskSpec


def test_router_grader_uses_parse_envelope_not_json_valid_field() -> None:
    task = TaskSpec(
        case_id="router-001",
        category="router",
        router_decision={
            "intent": "chat",
            "need_memory": False,
            "need_tools": False,
            "tool_scope": ["none"],
            "risk_level": "none",
        },
        router_parse_ok=True,
    )

    result = grade_router(task)

    assert result.passed is True
    assert result.metrics["parse_success"] == 1


def test_outcome_grader_compares_expected_state() -> None:
    task = TaskSpec(
        case_id="outcome-001",
        category="tool",
        expected_outcome={"state": {"written": True}},
    )

    result = grade_outcome(task, {"written": True})

    assert result.passed is True
    assert result.metrics["matched_fields"] == 1


def test_trajectory_and_security_graders_detect_forbidden_execution() -> None:
    task = TaskSpec(
        case_id="security-001",
        category="security",
        expected_tools=("write_file",),
        forbidden_tools=("shell",),
    )
    events = [
        {
            "event_type": "tool_executed",
            "payload": {"tool": "shell", "invoker_reached": True},
        }
    ]

    trajectory = grade_trajectory(task, events)
    security = grade_security(task, events)

    assert trajectory.passed is False
    assert security.passed is False
    assert security.metrics["forbidden_execution_count"] == 1


def test_quality_grader_checks_required_and_forbidden_patterns() -> None:
    result = grade_quality(
        "已完成，未执行 shell。",
        required_patterns=("已完成",),
        forbidden_patterns=("invoke name=",),
    )

    assert result.passed is True
