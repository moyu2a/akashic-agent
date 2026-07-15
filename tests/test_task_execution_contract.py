from __future__ import annotations

import pytest

import agent.policies.task_execution_contract as execution_contract_module

from agent.policies.task_execution_contract import (
    TaskExecutionTurnContract,
    infer_task_execution_contract,
)


def _detect_task_execution_intent(text: str) -> bool:
    detector = getattr(
        execution_contract_module,
        "detect_task_execution_intent",
        None,
    )
    assert detector is not None, "canonical execution intent detector is missing"
    return bool(detector(text))


def test_continue_requires_active_task_and_enabled_execution() -> None:
    inactive = infer_task_execution_contract(
        "继续执行下一步",
        {"has_active_task": False, "task_execution_enabled": True},
    )
    active = infer_task_execution_contract(
        "继续执行下一步",
        {"has_active_task": True, "task_execution_enabled": True},
    )

    assert inactive.active is False
    assert active.action == "continue"
    assert active.phase == "claim"
    assert active.required_capabilities == frozenset({"task_execution.begin"})
    assert active.allowed_capabilities == frozenset(
        {"task_execution.begin", "task_execution.inspect"}
    )


def test_explicit_task_update_beats_ambiguous_continue() -> None:
    contract = infer_task_execution_contract(
        "不要继续执行，把第一步标记完成",
        {"has_active_task": True, "task_execution_enabled": True},
    )

    assert contract.active is False


def test_retry_uses_only_runtime_resolved_target() -> None:
    no_target = infer_task_execution_contract(
        "重试刚才被中断的步骤",
        {"has_active_task": True, "task_execution_enabled": True},
    )
    target = infer_task_execution_contract(
        "重试刚才被中断的步骤",
        {
            "has_active_task": True,
            "task_execution_enabled": True,
            "latest_retryable_step_id": "step-1",
            "step_id": "model-controlled-step",
        },
    )

    assert no_target.active is False
    assert target.action == "retry"
    assert target.target_step_id == "step-1"


def test_runtime_replay_is_active_without_active_plan() -> None:
    execution = infer_task_execution_contract(
        "继续执行下一步",
        {
            "has_active_task": False,
            "task_execution_enabled": True,
            "request_replay_attempt_id": "attempt-final",
        },
    )

    assert execution.active is True
    assert execution.action == "replay"
    assert execution.phase == "terminal"
    assert execution.attempt_id == "attempt-final"


@pytest.mark.parametrize(
    "text",
    [
        "不要继续执行",
        "不要重试刚才的步骤",
        "不要终止执行",
        "查看后台任务状态",
    ],
)
def test_negated_or_background_intent_does_not_activate_execution(text: str) -> None:
    contract = infer_task_execution_contract(
        text,
        {
            "has_active_task": True,
            "task_execution_enabled": True,
            "latest_retryable_step_id": "step-1",
        },
    )

    assert contract == TaskExecutionTurnContract.inactive()


def test_feature_disabled_fails_closed_even_for_runtime_replay() -> None:
    contract = infer_task_execution_contract(
        "继续执行下一步",
        {
            "has_active_task": True,
            "task_execution_enabled": False,
            "request_replay_attempt_id": "attempt-final",
        },
    )

    assert contract == TaskExecutionTurnContract.inactive()


@pytest.mark.parametrize(
    "text",
    [
        "执行下一步",
        "取消执行",
        "abort",
        "retry",
        "inspect execution",
    ],
)
def test_canonical_execution_intent_detector_accepts_supported_terms(text: str) -> None:
    assert _detect_task_execution_intent(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "不要执行下一步",
        "do not retry",
        "不要查看执行状态",
        "聊聊天",
        "查看当前任务",
    ],
)
def test_canonical_execution_intent_detector_rejects_negation_and_chat(
    text: str,
) -> None:
    assert _detect_task_execution_intent(text) is False


def test_inactive_contract_must_use_empty_state() -> None:
    with pytest.raises(ValueError, match="inactive"):
        TaskExecutionTurnContract(
            active=False,
            action="inactive",
            phase="inactive",
            attempt_id=None,
            target_step_id=None,
            required_capabilities=frozenset(),
            allowed_capabilities=frozenset({"task_execution.inspect"}),
            allowed_risks=frozenset(),
            work_call_budget=0,
            tool_search_budget=0,
            completion_capability=None,
            reason="bad",
            matched_terms=(),
        )


def test_retry_contract_requires_runtime_resolved_target() -> None:
    with pytest.raises(ValueError, match="retry"):
        TaskExecutionTurnContract(
            active=True,
            action="retry",
            phase="claim",
            attempt_id=None,
            target_step_id=None,
            required_capabilities=frozenset({"task_execution.begin"}),
            allowed_capabilities=frozenset({"task_execution.begin"}),
            allowed_risks=frozenset(),
            work_call_budget=0,
            tool_search_budget=0,
            completion_capability="task_execution.begin",
            reason="retry",
            matched_terms=("重试",),
        )


def test_work_contract_allows_exact_read_only_risk_and_work_budget() -> None:
    contract = TaskExecutionTurnContract(
        active=True,
        action="continue",
        phase="work",
        attempt_id="attempt-1",
        target_step_id="step-1",
        required_capabilities=frozenset({"task_execution.finish"}),
        allowed_capabilities=frozenset(
            {
                "task_execution.finish",
                "task_execution.defer",
                "task_execution.abort",
            }
        ),
        allowed_risks=frozenset({"read-only"}),
        work_call_budget=3,
        tool_search_budget=1,
        completion_capability="task_execution.finish",
        reason="attempt_running",
        matched_terms=(),
    )

    assert contract.allowed_risks == frozenset({"read-only"})


@pytest.mark.parametrize(
    ("phase", "allowed_risks", "work_call_budget", "tool_search_budget"),
    [
        ("work", frozenset({"write"}), 1, 1),
        ("waiting_authorization", frozenset({"read-only"}), 1, 0),
        ("terminal", frozenset({"read-only"}), 1, 0),
    ],
)
def test_non_work_or_unsafe_work_contracts_reject_work_state(
    phase: str,
    allowed_risks: frozenset[str],
    work_call_budget: int,
    tool_search_budget: int,
) -> None:
    with pytest.raises(ValueError):
        TaskExecutionTurnContract(
            active=True,
            action="abort" if phase == "waiting_authorization" else "continue",
            phase=phase,  # type: ignore[arg-type]
            attempt_id="attempt-1",
            target_step_id=None,
            required_capabilities=frozenset({"task_execution.abort"}),
            allowed_capabilities=frozenset({"task_execution.abort"}),
            allowed_risks=allowed_risks,
            work_call_budget=work_call_budget,
            tool_search_budget=tool_search_budget,
            completion_capability="task_execution.abort",
            reason="bad",
            matched_terms=(),
        )
