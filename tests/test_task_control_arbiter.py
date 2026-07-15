from __future__ import annotations

import pytest

from agent.policies.task_control_arbiter import TaskControlIntentArbiter
from agent.policies.task_execution_contract import infer_task_execution_contract
from agent.policies.task_plan_contract import infer_task_plan_turn_decision


def _resolve(text: str, metadata: dict[str, object]):
    task_plan = infer_task_plan_turn_decision(
        text,
        has_active_task=bool(metadata.get("has_active_task")),
    ).contract
    execution = infer_task_execution_contract(text, metadata)
    return TaskControlIntentArbiter().resolve(
        task_plan_contract=task_plan,
        task_execution_contract=execution,
        user_text=text,
        metadata=metadata,
    )


def test_explicit_execution_continue_beats_generic_plan_update() -> None:
    decision = _resolve(
        "继续执行下一步",
        {"has_active_task": True, "task_execution_enabled": True},
    )

    assert decision.task_plan_contract.action == "none"
    assert decision.task_execution_contract.action == "continue"


@pytest.mark.parametrize(
    ("text", "task_action"),
    [
        ("制定一个三步计划，然后继续执行", "plan_create"),
        ("当前任务做到哪一步，继续执行", "plan_inspect"),
        ("把第一步标记完成，然后继续执行", "plan_update"),
        ("跳过第一步，然后继续执行", "plan_update"),
    ],
)
def test_explicit_task_plan_commands_beat_execution_intent(
    text: str, task_action: str
) -> None:
    decision = _resolve(
        text,
        {"has_active_task": True, "task_execution_enabled": True},
    )

    assert decision.task_plan_contract.action == task_action
    assert decision.task_execution_contract.active is False


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("继续执行下一步", "continue"),
        ("重试刚才被中断的步骤", "retry"),
        ("终止当前步骤执行", "abort"),
    ],
)
def test_explicit_execution_actions_are_selected(text: str, action: str) -> None:
    decision = _resolve(
        text,
        {
            "has_active_task": True,
            "task_execution_enabled": True,
            "latest_retryable_step_id": "step-1",
        },
    )

    assert decision.task_plan_contract.action == "none"
    assert decision.task_execution_contract.action == action


def test_runtime_replay_has_priority_over_explicit_task_plan_update() -> None:
    decision = _resolve(
        "把第一步标记完成",
        {
            "has_active_task": False,
            "task_execution_enabled": True,
            "request_replay_attempt_id": "attempt-final",
        },
    )

    assert decision.task_plan_contract.action == "none"
    assert decision.task_execution_contract.action == "replay"


def test_background_passthrough_selects_no_strict_contract() -> None:
    decision = _resolve(
        "查看后台任务状态",
        {"has_active_task": True, "task_execution_enabled": True},
    )

    assert decision.task_plan_contract.action == "none"
    assert decision.task_execution_contract.active is False


def test_feature_disabled_keeps_generic_task_plan_update() -> None:
    decision = _resolve(
        "继续执行下一步",
        {"has_active_task": True, "task_execution_enabled": False},
    )

    assert decision.task_plan_contract.action == "plan_update"
    assert decision.task_execution_contract.active is False
