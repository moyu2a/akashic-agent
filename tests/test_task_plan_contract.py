from __future__ import annotations

import json

import pytest

from agent.policies.task_plan_contract import (
    TaskPlanTurnContract,
    infer_task_plan_turn_decision,
)


@pytest.mark.parametrize(
    ("text", "active", "action", "context", "required", "allowed", "budget", "completion"),
    [
        (
            "制定一个三步计划",
            False,
            "plan_create",
            "none",
            {"task_plan.create"},
            {"task_plan.create"},
            0,
            "task_plan.create",
        ),
        (
            "制定一个三步计划",
            True,
            "plan_create",
            "none",
            {"task_plan.create"},
            {"task_plan.create", "task_plan.inspect"},
            0,
            "task_plan.create",
        ),
        (
            "结合我的长期偏好制定计划",
            False,
            "plan_create",
            "long_term_memory",
            {"task_plan.create"},
            {"task_plan.create", "memory.recall"},
            1,
            "task_plan.create",
        ),
        (
            "按照我们上次讨论制定计划",
            False,
            "plan_create",
            "session_history",
            {"task_plan.create"},
            {"task_plan.create", "history.search"},
            1,
            "task_plan.create",
        ),
        (
            "当前任务做到哪一步了？",
            True,
            "plan_inspect",
            "none",
            {"task_plan.inspect"},
            {"task_plan.inspect"},
            0,
            "task_plan.inspect",
        ),
        (
            "把第一步标记为完成",
            True,
            "plan_update",
            "none",
            {"task_plan.update"},
            {"task_plan.inspect", "task_plan.update"},
            0,
            "task_plan.update",
        ),
    ],
)
def test_task_plan_contract_matrix(
    text: str,
    active: bool,
    action: str,
    context: str,
    required: set[str],
    allowed: set[str],
    budget: int,
    completion: str,
) -> None:
    decision = infer_task_plan_turn_decision(text, has_active_task=active)
    contract = decision.contract

    assert decision.background_mode == "none"
    assert contract.action == action
    assert contract.context_requirement == context
    assert contract.required_capabilities == frozenset(required)
    assert contract.allowed_capabilities == frozenset(allowed)
    assert contract.retrieval_budget == budget
    assert contract.completion_capability == completion
    assert contract.active is True


@pytest.mark.parametrize(
    "text",
    [
        "为修复 Document RAG 成本制定三步计划，只创建计划",
        "为当前项目制定计划",
        "为修复问题创建计划",
    ],
)
def test_topic_words_do_not_enable_context_retrieval(text: str) -> None:
    contract = infer_task_plan_turn_decision(
        text,
        has_active_task=False,
    ).contract

    assert contract.context_requirement == "none"
    assert contract.retrieval_budget == 0
    assert "memory.recall" not in contract.allowed_capabilities
    assert "history.search" not in contract.allowed_capabilities


def test_no_retrieval_phrase_overrides_history_and_memory_signals() -> None:
    contract = infer_task_plan_turn_decision(
        "结合我的偏好和上次讨论制定计划，但不要查询历史或记忆",
        has_active_task=False,
    ).contract

    assert contract.action == "plan_create"
    assert contract.context_requirement == "none"
    assert contract.allowed_capabilities == frozenset({"task_plan.create"})
    assert contract.retrieval_budget == 0


@pytest.mark.parametrize(
    "text",
    [
        "先只记住这段讨论，不创建计划",
        "暂不创建计划",
        "先不制定计划",
        "无需创建计划",
        "别创建计划",
        "先别制定计划",
        "不用创建计划",
        "不必制定计划",
        "无须制定计划",
        "请勿创建计划",
        "不要再创建计划",
    ],
)
def test_explicit_no_create_action_does_not_activate_task_plan(text: str) -> None:
    contract = infer_task_plan_turn_decision(
        text,
        has_active_task=False,
    ).contract

    assert contract.active is False
    assert contract.reason == "explicit_no_task_plan_action"


def test_no_create_phrase_does_not_hide_explicit_update_action() -> None:
    contract = infer_task_plan_turn_decision(
        "不要创建计划，把第一步标记为完成",
        has_active_task=True,
    ).contract

    assert contract.action == "plan_update"


def test_no_create_phrase_does_not_turn_background_observe_into_start() -> None:
    decision = infer_task_plan_turn_decision(
        "不要创建计划，查看后台任务状态",
        has_active_task=True,
    )

    assert decision.background_mode == "observe"
    assert decision.contract.active is False


def test_explicit_background_create_survives_no_create_plan_phrase() -> None:
    decision = infer_task_plan_turn_decision(
        "不要创建计划，请创建一个新的后台任务",
        has_active_task=True,
    )

    assert decision.background_mode == "start"
    assert decision.contract.active is False


def test_background_runtime_status_is_observe_not_start() -> None:
    decision = infer_task_plan_turn_decision(
        "查看后台任务运行状态",
        has_active_task=True,
    )

    assert decision.background_mode == "observe"


@pytest.mark.parametrize(
    "text",
    [
        "不要创建后台任务，只查看状态",
        "不要启动后台任务，只查看状态",
        "不要运行后台任务，查看状态",
    ],
)
def test_negated_background_start_falls_through_to_observe(text: str) -> None:
    decision = infer_task_plan_turn_decision(
        text,
        has_active_task=True,
    )

    assert decision.background_mode == "observe"


def test_later_positive_background_start_survives_earlier_negation() -> None:
    decision = infer_task_plan_turn_decision(
        "不要启动旧后台任务，然后启动一个新的后台任务",
        has_active_task=True,
    )

    assert decision.background_mode == "start"


@pytest.mark.parametrize(
    "text",
    [
        "不得不启动后台任务",
        "不能不运行后台任务",
        "必须创建一个新的后台任务",
    ],
)
def test_required_background_start_is_not_treated_as_negated(text: str) -> None:
    decision = infer_task_plan_turn_decision(
        text,
        has_active_task=True,
    )

    assert decision.background_mode == "start"


@pytest.mark.parametrize(
    "text",
    [
        "不得不创建计划",
        "不能不制定计划",
        "必须创建计划",
        "务必制定计划",
    ],
)
def test_required_create_phrases_are_not_treated_as_no_create(text: str) -> None:
    contract = infer_task_plan_turn_decision(
        text,
        has_active_task=False,
    ).contract

    assert contract.action == "plan_create"


def test_session_history_wins_over_long_term_memory() -> None:
    contract = infer_task_plan_turn_decision(
        "结合我的偏好，按照我们上次讨论制定计划",
        has_active_task=False,
    ).contract

    assert contract.context_requirement == "session_history"
    assert "history.search" in contract.allowed_capabilities
    assert "memory.recall" not in contract.allowed_capabilities


@pytest.mark.parametrize(
    ("text", "mode"),
    [
        ("启动后台任务分析日志", "start"),
        ("查看后台任务状态", "observe"),
        ("查看后台任务输出", "output"),
        ("取消后台任务", "cancel"),
    ],
)
def test_background_modes_bypass_task_plan_contract(text: str, mode: str) -> None:
    decision = infer_task_plan_turn_decision(text, has_active_task=True)

    assert decision.background_mode == mode
    assert decision.contract == TaskPlanTurnContract.inactive(
        reason=f"background_{mode}_passthrough",
        matched_terms=decision.contract.matched_terms,
    )
    assert decision.contract.active is False


def test_current_task_output_is_inspect_not_background() -> None:
    decision = infer_task_plan_turn_decision(
        "当前任务输出是什么？",
        has_active_task=True,
    )

    assert decision.background_mode == "none"
    assert decision.contract.action == "plan_inspect"


def test_update_without_active_task_degrades_to_inspect() -> None:
    contract = infer_task_plan_turn_decision(
        "把第一步标记为完成",
        has_active_task=False,
    ).contract

    assert contract.action == "plan_inspect"
    assert contract.completion_capability == "task_plan.inspect"


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("更新任务计划", "plan_update"),
        ("当前任务计划做到哪一步", "plan_inspect"),
    ],
)
def test_specific_state_action_is_not_swallowed_by_task_plan_noun(
    text: str,
    action: str,
) -> None:
    contract = infer_task_plan_turn_decision(
        text,
        has_active_task=True,
    ).contract

    assert contract.action == action


def test_inactive_contract_has_canonical_empty_shape() -> None:
    contract = TaskPlanTurnContract.inactive()

    assert contract.action == "none"
    assert contract.context_requirement == "none"
    assert contract.required_capabilities == frozenset()
    assert contract.allowed_capabilities == frozenset()
    assert contract.retrieval_budget == 0
    assert contract.completion_capability is None
    assert contract.active is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"context_requirement": "session_history"},
        {"required_capabilities": frozenset({"task_plan.create"})},
        {"allowed_capabilities": frozenset({"task_plan.create"})},
        {"retrieval_budget": 1},
        {"completion_capability": "task_plan.create"},
    ],
)
def test_invalid_inactive_contract_is_rejected(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "action": "none",
        "context_requirement": "none",
        "required_capabilities": frozenset(),
        "allowed_capabilities": frozenset(),
        "retrieval_budget": 0,
        "completion_capability": None,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match="inactive"):
        TaskPlanTurnContract(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "action": "plan_create",
            "context_requirement": "none",
            "required_capabilities": frozenset({"task_plan.create"}),
            "allowed_capabilities": frozenset(),
            "retrieval_budget": 0,
            "completion_capability": "task_plan.create",
        },
        {
            "action": "plan_update",
            "context_requirement": "none",
            "required_capabilities": frozenset({"task_plan.update"}),
            "allowed_capabilities": frozenset({"task_plan.update"}),
            "retrieval_budget": 0,
            "completion_capability": "task_plan.inspect",
        },
        {
            "action": "plan_create",
            "context_requirement": "long_term_memory",
            "required_capabilities": frozenset({"task_plan.create"}),
            "allowed_capabilities": frozenset(
                {"task_plan.create", "memory.recall"}
            ),
            "retrieval_budget": 0,
            "completion_capability": "task_plan.create",
        },
    ],
)
def test_invalid_active_contract_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        TaskPlanTurnContract(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "typo"},
        {"context_requirement": "typo"},
        {"retrieval_budget": False},
        {"allowed_capabilities": frozenset({"task_plan.create", "memory.recall"})},
        {"allowed_capabilities": frozenset({"task_plan.create", "unknown.cap"})},
    ],
)
def test_active_contract_rejects_runtime_type_and_scope_gaps(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "action": "plan_create",
        "context_requirement": "none",
        "required_capabilities": frozenset({"task_plan.create"}),
        "allowed_capabilities": frozenset({"task_plan.create"}),
        "retrieval_budget": 0,
        "completion_capability": "task_plan.create",
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        TaskPlanTurnContract(**values)  # type: ignore[arg-type]


def test_capability_inputs_are_normalized_to_immutable_sets() -> None:
    required = {"task_plan.create"}
    allowed = {"task_plan.create"}
    contract = TaskPlanTurnContract(
        action="plan_create",
        context_requirement="none",
        required_capabilities=required,  # type: ignore[arg-type]
        allowed_capabilities=allowed,  # type: ignore[arg-type]
        retrieval_budget=0,
        completion_capability="task_plan.create",
    )

    required.add("unknown.cap")
    allowed.add("unknown.cap")

    assert contract.required_capabilities == frozenset({"task_plan.create"})
    assert contract.allowed_capabilities == frozenset({"task_plan.create"})


def test_common_no_retrieval_phrase_forces_none() -> None:
    contract = infer_task_plan_turn_decision(
        "结合我的偏好制定计划，但不需要查询历史或记忆",
        has_active_task=False,
    ).contract

    assert contract.context_requirement == "none"
    assert contract.retrieval_budget == 0


@pytest.mark.parametrize(
    ("text", "mode"),
    [
        ("取消后台 job", "cancel"),
        ("查看后台 job 输出", "output"),
        ("启动后台 job", "start"),
    ],
)
def test_background_operation_priority_supports_mixed_job_terms(
    text: str,
    mode: str,
) -> None:
    decision = infer_task_plan_turn_decision(text, has_active_task=True)

    assert decision.background_mode == mode
    assert decision.contract.active is False


def test_trace_metadata_is_json_safe_and_one_way() -> None:
    contract = infer_task_plan_turn_decision(
        "按照上次讨论制定计划",
        has_active_task=False,
    ).contract

    metadata = contract.to_trace_metadata()

    assert json.loads(json.dumps(metadata, ensure_ascii=False)) == metadata
    assert metadata["allowed_capabilities"] == [
        "history.search",
        "task_plan.create",
    ]
    assert not hasattr(TaskPlanTurnContract, "from_metadata")
