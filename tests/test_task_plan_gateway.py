from __future__ import annotations

from agent.policies.tool_access import ToolAccessContext, ToolAccessGateway

TASK_TOOLS = {"create_task_plan", "update_task_step", "inspect_task_plan"}
ALL_REGISTERED = {
    "tool_search",
    "create_task_plan",
    "update_task_step",
    "inspect_task_plan",
    "recall_memory",
    "search_messages",
    "search_docs",
    "fetch_doc_chunk",
    "shell",
    "read_file",
    "list_dir",
    "inspect_turn_trace",
}
CAPABILITIES = {
    "create_task_plan": frozenset({"task_plan.create"}),
    "update_task_step": frozenset({"task_plan.update"}),
    "inspect_task_plan": frozenset({"task_plan.inspect"}),
    "recall_memory": frozenset({"memory.recall"}),
    "search_messages": frozenset({"history.search"}),
}


def _ctx(
    text: str,
    *,
    lru: set[str] | None = None,
    has_active_task: bool = False,
    registered_tools: set[str] | None = None,
) -> ToolAccessContext:
    return ToolAccessContext(
        session_key="cli:s1",
        user_text=text,
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset(lru or set()),
        disabled_tools=frozenset(),
        turn_metadata={"has_active_task": has_active_task},
        registered_tools=frozenset(
            ALL_REGISTERED if registered_tools is None else registered_tools
        ),
        tool_capabilities=CAPABILITIES,
    )


def test_task_plan_create_intent_exposes_task_tools_and_suppresses_doc_rag() -> None:
    ctx = _ctx("为修复 Document RAG 成本问题制定一个三步计划")
    gateway = ToolAccessGateway()

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert visible == {"create_task_plan"}
    assert "TaskPlanAccessPolicy" in plan.policies
    assert "search_docs" not in visible
    assert "fetch_doc_chunk" not in visible


def test_task_plan_progress_intent_exposes_update_tools_when_active() -> None:
    ctx = _ctx("当前任务做到哪一步了？继续下一步", has_active_task=True)
    gateway = ToolAccessGateway()

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert {"inspect_task_plan", "update_task_step"} <= visible


def test_task_plan_progress_without_active_task_only_exposes_inspect() -> None:
    ctx = _ctx("当前任务做到哪一步了？继续下一步", has_active_task=False)
    gateway = ToolAccessGateway()

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert "inspect_task_plan" in visible
    assert "update_task_step" not in visible


def test_task_policy_does_not_expose_unregistered_task_tools() -> None:
    ctx = _ctx(
        "当前任务做到哪一步了？继续下一步",
        has_active_task=True,
        registered_tools={"tool_search", "search_docs"},
    )
    gateway = ToolAccessGateway()

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert visible == set()
    assert plan.reason == "task_plan_required_capability_missing"


def test_non_task_doc_prompt_does_not_expose_task_tools() -> None:
    ctx = _ctx("请从文档知识库中检索agent runtime负责什么？回答必须带文档引用")
    gateway = ToolAccessGateway()

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert visible.isdisjoint(TASK_TOOLS)
    assert "search_docs" in visible


def test_tool_history_priority_bypasses_task_plan_scope() -> None:
    ctx = _ctx(
        "刚才那个任务用了哪些工具？",
        lru={"search_docs", "fetch_doc_chunk"},
        has_active_task=True,
    )
    gateway = ToolAccessGateway()

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert "inspect_turn_trace" in visible
    assert "inspect_task_plan" not in visible
    assert "search_docs" not in visible
    assert "fetch_doc_chunk" not in visible
    assert plan.strict_capability_scope is False
