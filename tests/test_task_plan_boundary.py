from __future__ import annotations

from dataclasses import replace

from agent.policies.task_plan_boundary import (
    SPAWN_TOOL_NAMES,
    TaskPlanAccessPolicy,
    infer_task_plan_intent,
)
from agent.policies.tool_access import ToolAccessGateway
from agent.policies.tool_access_types import ToolAccessContext


def _ctx(
    text: str,
    *,
    has_active_task: bool = False,
    lru: set[str] | None = None,
    disabled: set[str] | None = None,
    capabilities: dict[str, frozenset[str]] | None = None,
) -> ToolAccessContext:
    registered = {
        "tool_search",
        "create_task_plan",
        "inspect_task_plan",
        "update_task_step",
        "spawn",
        "spawn_manage",
        "task_output",
        "search_docs",
        "fetch_doc_chunk",
        "read_file",
        "list_dir",
        "shell",
        "recall_memory",
        "search_messages",
        "inspect_turn_trace",
    }
    tool_capabilities = {
        "create_task_plan": frozenset({"task_plan.create"}),
        "inspect_task_plan": frozenset({"task_plan.inspect"}),
        "update_task_step": frozenset({"task_plan.update"}),
        "recall_memory": frozenset({"memory.recall"}),
        "search_messages": frozenset({"history.search"}),
    }
    if capabilities is not None:
        tool_capabilities = capabilities
    return ToolAccessContext(
        session_key="cli:s1",
        user_text=text,
        always_on_tools=frozenset(
            {"tool_search", "spawn", "spawn_manage", "task_output"}
        ),
        lru_preloaded_tools=frozenset(lru or set()),
        disabled_tools=frozenset(disabled or set()),
        turn_metadata={"has_active_task": has_active_task},
        registered_tools=frozenset(registered),
        tool_capabilities=tool_capabilities,
    )


def test_plan_create_intent_wins_over_document_rag_terms() -> None:
    intent = infer_task_plan_intent(
        "为修复 Document RAG 成本问题制定一个三步计划",
        has_active_task=False,
    )

    assert intent.kind == "plan_create"
    assert "三步计划" in intent.matched_terms


def test_explicit_background_job_intent_wins_over_task_terms() -> None:
    intent = infer_task_plan_intent(
        "查看后台任务状态和任务输出",
        has_active_task=True,
    )

    assert intent.kind == "background_job"


def test_current_task_output_is_task_plan_inspect_not_background() -> None:
    intent = infer_task_plan_intent(
        "当前任务输出是什么？",
        has_active_task=True,
    )

    assert intent.kind == "plan_inspect"


def test_plan_create_suppresses_spawn_rag_and_local_tools() -> None:
    ctx = _ctx("为修复 Document RAG 成本问题制定一个三步计划")
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert visible == {"create_task_plan"}
    assert visible.isdisjoint(SPAWN_TOOL_NAMES)
    assert "search_docs" not in visible
    assert "fetch_doc_chunk" not in visible
    assert "read_file" not in visible
    assert "list_dir" not in visible
    assert "shell" not in visible
    assert {"spawn", "spawn_manage", "task_output"} <= plan.execution_block
    assert {"search_docs", "fetch_doc_chunk"} <= plan.execution_block


def test_default_gateway_plan_create_suppresses_rag_local_and_spawn() -> None:
    ctx = _ctx(
        "为修复 Document RAG 文档检索成本问题制定一个三步计划",
        lru={"search_docs", "fetch_doc_chunk"},
    )
    gateway = ToolAccessGateway()

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert visible == {"create_task_plan"}
    assert "search_docs" not in visible
    assert "fetch_doc_chunk" not in visible
    assert "read_file" not in visible
    assert "shell" not in visible
    assert visible.isdisjoint(SPAWN_TOOL_NAMES)
    assert "TaskPlanAccessPolicy" in plan.policies


def test_plan_inspect_suppresses_spawn_when_active_task_exists() -> None:
    ctx = _ctx("当前任务做到哪一步了？", has_active_task=True)
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert "inspect_task_plan" in visible
    assert "spawn_manage" not in visible
    assert "task_output" not in visible
    assert "spawn_manage" in plan.execution_block


def test_plan_update_exposes_update_and_suppresses_spawn() -> None:
    ctx = _ctx("把第一步标记为完成，说明已经查看日志", has_active_task=True)
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert {"inspect_task_plan", "update_task_step"} <= visible
    assert visible.isdisjoint(SPAWN_TOOL_NAMES)
    assert SPAWN_TOOL_NAMES <= plan.execution_block


def test_background_job_intent_allows_spawn_tools() -> None:
    ctx = _ctx("查看后台任务状态和任务输出", has_active_task=True)
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert {"spawn_manage", "task_output"} <= visible
    assert not (SPAWN_TOOL_NAMES & plan.execution_block)


def test_non_task_prompt_returns_empty_plan() -> None:
    ctx = _ctx("今天杭州天气如何？")

    plan = TaskPlanAccessPolicy().build_plan(ctx)

    assert plan.visible_add == frozenset()
    assert plan.reason == "no_tool_access_policy"


def test_active_create_allows_optional_inspect() -> None:
    plan = TaskPlanAccessPolicy().build_plan(
        _ctx("制定一个三步计划", has_active_task=True)
    )

    assert plan.visible_add == frozenset(
        {"create_task_plan", "inspect_task_plan"}
    )
    assert plan.strict_capability_scope is True


def test_memory_create_only_allows_recall_and_create() -> None:
    ctx = _ctx("结合我的偏好制定计划")
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))
    plan = gateway.build_plan(ctx)

    assert gateway.compute_visible_names(ctx, plan) == {
        "create_task_plan",
        "recall_memory",
    }
    assert plan.context_retrieval_tools == frozenset({"recall_memory"})


def test_session_create_only_allows_search_and_create() -> None:
    ctx = _ctx("按照我们上次讨论制定计划")
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))
    plan = gateway.build_plan(ctx)

    assert gateway.compute_visible_names(ctx, plan) == {
        "create_task_plan",
        "search_messages",
    }
    assert plan.context_retrieval_tools == frozenset({"search_messages"})


def test_missing_required_create_capability_fails_closed() -> None:
    ctx = _ctx("制定一个三步计划", capabilities={})
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))
    plan = gateway.build_plan(ctx)

    assert gateway.compute_visible_names(ctx, plan) == set()
    assert plan.strict_capability_scope is True
    assert plan.filter_error is True
    assert plan.reason == "task_plan_required_capability_missing"
    assert "create_task_plan" in plan.execution_block
    assert plan.model_hints
    assert "plan_create" in plan.model_hints[0]
    assert "task_plan.create" in plan.model_hints[0]


def test_missing_optional_memory_capability_degrades_to_create_only() -> None:
    ctx = _ctx(
        "结合我的偏好制定计划",
        capabilities={
            "create_task_plan": frozenset({"task_plan.create"}),
        },
    )
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))
    plan = gateway.build_plan(ctx)

    assert gateway.compute_visible_names(ctx, plan) == {"create_task_plan"}
    metadata = plan.policy_metadata["task_plan"]
    assert metadata["optional_capability_unavailable"] == ["memory.recall"]
    assert plan.model_hints


def test_disabled_optional_retrieval_degrades_to_required_scope() -> None:
    ctx = _ctx("结合我的偏好制定计划", disabled={"recall_memory"})
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))
    plan = gateway.build_plan(ctx)

    assert gateway.compute_visible_names(ctx, plan) == {"create_task_plan"}
    assert plan.context_retrieval_tools == frozenset()
    assert plan.policy_metadata["task_plan"][
        "optional_capability_unavailable"
    ] == ["memory.recall"]


def test_disabled_required_provider_fails_closed() -> None:
    ctx = _ctx("制定一个三步计划", disabled={"create_task_plan"})
    plan = TaskPlanAccessPolicy().build_plan(ctx)

    assert plan.reason == "task_plan_required_capability_missing"
    assert plan.strict_capability_scope is True
    assert plan.filter_error is True


def test_unrelated_empty_capabilities_are_valid_and_suppressed() -> None:
    ctx = _ctx("制定一个三步计划")
    plan = TaskPlanAccessPolicy().build_plan(ctx)

    assert "shell" in plan.visible_suppress
    assert plan.filter_error is False


def test_background_start_is_non_strict_passthrough() -> None:
    plan = TaskPlanAccessPolicy().build_plan(_ctx("启动后台任务分析日志"))

    assert plan.visible_add == frozenset({"spawn"})
    assert plan.strict_capability_scope is False
    assert plan.task_plan_contract is None


def test_background_modes_expose_expected_non_strict_tools() -> None:
    expected = {
        "查看后台任务状态": {"spawn_manage"},
        "查看后台任务输出": {"spawn_manage", "task_output"},
        "取消后台任务": {"spawn_manage"},
    }

    for text, tools in expected.items():
        plan = TaskPlanAccessPolicy().build_plan(_ctx(text))
        assert plan.visible_add == frozenset(tools)
        assert plan.strict_capability_scope is False
        assert plan.task_plan_contract is None


def test_doc_rag_and_explicit_source_policies_cannot_reopen_strict_scope() -> None:
    ctx = _ctx(
        "根据项目文档和源码，为修复成本制定一个三步计划",
    )
    gateway = ToolAccessGateway()
    plan = gateway.build_plan(ctx)

    assert gateway.compute_visible_names(ctx, plan) == {"create_task_plan"}
    assert plan.local_source_allowed is False
    assert {"search_docs", "read_file", "shell"} <= plan.execution_block


def test_lru_and_tool_search_unlocks_cannot_reopen_strict_scope() -> None:
    ctx = _ctx(
        "制定一个三步计划",
        lru={"search_docs", "fetch_doc_chunk", "recall_memory", "shell"},
    )
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))
    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert visible == {"create_task_plan"}
    assert gateway.merge_tool_search_unlocks(
        visible,
        {"search_docs", "read_file", "recall_memory"},
        ctx,
        plan,
    ) == {"create_task_plan"}


def test_trace_metadata_cannot_replace_typed_contract() -> None:
    plan = TaskPlanAccessPolicy().build_plan(_ctx("制定一个三步计划"))
    tampered = replace(
        plan,
        policy_metadata={"task_plan": {"action": "plan_update"}},
    )

    assert tampered.task_plan_contract is plan.task_plan_contract
    assert tampered.task_plan_contract is not None
    assert tampered.task_plan_contract.action == "plan_create"


def test_inspect_scope_block_message_only_recommends_inspect() -> None:
    ctx = _ctx("当前任务做到哪一步", has_active_task=True)
    gateway = ToolAccessGateway(policies=(TaskPlanAccessPolicy(),))
    plan = gateway.build_plan(ctx)

    gate = gateway.check_tool_call(plan, "create_task_plan", {})

    assert gate.allowed is False
    assert gate.recommended_tools == ("inspect_task_plan",)
    assert "inspect_task_plan" in gate.message
    assert "create_task_plan" not in gate.message
    assert "update_task_step" not in gate.message
    assert "spawn" not in gate.message
