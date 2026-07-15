from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from agent.core.passive_turn import DefaultReasoner
from agent.core.runtime_support import LLMServices, ToolDiscoveryState
from agent.core.types import ContextRenderResult, ContextRequest
from agent.looping.ports import LLMConfig
from agent.provider import LLMResponse, ToolCall
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore
from agent.tool_hooks.base import ToolHook
from agent.tool_hooks.types import HookContext, HookOutcome
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from agent.tools.task_plan import (
    CreateTaskPlanTool,
    InspectTaskPlanTool,
    UpdateTaskStepTool,
)
from agent.tools.tool_search import ToolSearchTool
from agent.policies.task_execution_contract import TaskExecutionTurnContract


class _RecordingTool(Tool):
    def __init__(
        self,
        name: str,
        result: str | None = None,
        *,
        capabilities: frozenset[str] = frozenset(),
    ) -> None:
        self._name = name
        self._result = result or f"{name}-ok"
        self.capabilities = capabilities
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self._result


class _RecordingToolSearch(ToolSearchTool):
    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__(registry)
        self.calls: list[dict[str, Any]] = []
        self.raw_results: list[str] = []

    async def execute(self, **kwargs: Any) -> str:
        self.calls.append(dict(kwargs))
        result = await super().execute(**kwargs)
        self.raw_results.append(result)
        return result


class _Provider:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("provider.chat called more than expected")
        return self._responses.pop(0)


class _DenyToolHook(ToolHook):
    name = "deny_tool_for_test"
    event = "pre_tool_use"

    def __init__(self, tool_name: str, reason: str = "denied") -> None:
        self._tool_name = tool_name
        self._reason = reason

    def matches(self, ctx: HookContext) -> bool:
        return ctx.request.tool_name == self._tool_name

    async def run(self, ctx: HookContext) -> HookOutcome:
        return HookOutcome(decision="deny", reason=self._reason)


class _ErrorToolHook(_DenyToolHook):
    name = "error_tool_for_test"

    async def run(self, ctx: HookContext) -> HookOutcome:
        raise RuntimeError("hook failed")


def _msg(
    content: str, *, metadata: dict[str, object] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        media=[],
        channel="cli",
        chat_id="1",
        timestamp=datetime.now(timezone.utc),
        metadata=metadata or {},
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        key="cli:1",
        messages=[],
        metadata={},
        get_history=lambda max_messages=40, *, start_index=None: [],
        last_consolidated=0,
    )


def _make_reasoner(
    provider: _Provider,
    *,
    read_file: _RecordingTool | None = None,
    extra_tools: list[Tool] | None = None,
    extra_tool_risks: dict[str, str] | None = None,
    discovery: ToolDiscoveryState | None = None,
    task_plan_service: TaskPlanService | None = None,
    recall_memory: _RecordingTool | None = None,
    search_messages: _RecordingTool | None = None,
    tool_search_enabled: bool = True,
    render_requests: list[ContextRequest] | None = None,
    tool_search_type: type[ToolSearchTool] = ToolSearchTool,
) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.set_context(_session_key="cli:1")
    tools.register(tool_search_type(tools), always_on=True, risk="read-only")
    tools.register(_RecordingTool("search_docs"))
    tools.register(_RecordingTool("fetch_doc_chunk"))
    tools.register(read_file or _RecordingTool("read_file"), always_on=True)
    tools.register(_RecordingTool("shell"), always_on=True)
    tools.register(_RecordingTool("list_dir"), always_on=True)
    tools.register(
        recall_memory
        or _RecordingTool(
            "recall_memory",
            '{"ok": true, "memories": []}',
            capabilities=frozenset({"memory.recall"}),
        )
    )
    tools.register(
        search_messages
        or _RecordingTool(
            "search_messages",
            '{"ok": true, "messages": []}',
            capabilities=frozenset({"history.search"}),
        )
    )
    if task_plan_service is not None:
        tools.register(CreateTaskPlanTool(task_plan_service))
        tools.register(UpdateTaskStepTool(task_plan_service))
        tools.register(InspectTaskPlanTool(task_plan_service))
    for tool in extra_tools or []:
        tools.register(tool, risk=(extra_tool_risks or {}).get(tool.name, "unknown"))

    def _render(request: ContextRequest, **_kwargs: object) -> ContextRenderResult:
        if render_requests is not None:
            render_requests.append(request)
        return ContextRenderResult(
            system_prompt="",
            turn_injection_context={
                "turn_injection": request.turn_injection_prompt or ""
            },
            messages=[{"role": "user", "content": request.current_message}],
            debug_breakdown=[],
        )

    return DefaultReasoner(
        llm=cast(
            Any,
            LLMServices(provider=provider, light_provider=provider),
        ),
        llm_config=LLMConfig(model="m", max_iterations=4, max_tokens=256),
        tools=tools,
        discovery=discovery or ToolDiscoveryState(),
        tool_search_enabled=tool_search_enabled,
        memory_window=10,
        context=cast(Any, SimpleNamespace(render=_render)),
        session_manager=cast(Any, SimpleNamespace(save_async=lambda *_args, **_kw: None)),
        task_plan_service=task_plan_service,
    )


def _tool_names(call: dict[str, Any]) -> set[str]:
    return {schema["function"]["name"] for schema in call["tools"]}


def _execution_work_contract() -> TaskExecutionTurnContract:
    return TaskExecutionTurnContract(
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


async def _run_reasoner_visibility_case(
    prompt: str,
    *,
    discovery: ToolDiscoveryState | None = None,
) -> tuple[Any, _Provider]:
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "trace1",
                        "inspect_turn_trace",
                        {"selector": "previous_completed"},
                    )
                ],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        extra_tools=[
            _RecordingTool(
                "inspect_turn_trace",
                result='{"ok": true, "summary": {"real_tools": {"read_file": 3}}}',
            )
        ],
        discovery=discovery,
    )

    result = await reasoner.run_turn(
        msg=_msg(prompt),
        session=cast(Any, _session()),
    )
    return result, provider


@pytest.mark.parametrize(
    "prompt",
    [
        "刚才第二个问题你用了哪些工具？",
        "刚才项目文档那个问题用了哪些工具？",
    ],
)
@pytest.mark.asyncio
async def test_reasoner_exposes_trace_tool_for_tool_history_prompts(prompt: str) -> None:
    result, provider = await _run_reasoner_visibility_case(prompt)

    names = _tool_names(provider.calls[0])
    assert "inspect_turn_trace" in names
    assert "search_docs" not in names
    assert "fetch_doc_chunk" not in names
    assert "inspect_turn_trace" in result.tools_used


@pytest.mark.asyncio
async def test_reasoner_does_not_add_trace_tool_to_lru() -> None:
    discovery = ToolDiscoveryState()

    result, _provider = await _run_reasoner_visibility_case(
        "刚才第二个问题你用了哪些工具？",
        discovery=discovery,
    )

    assert "inspect_turn_trace" in result.tools_used
    assert "inspect_turn_trace" not in discovery.get_preloaded("cli:1")


def test_strong_doc_prompt_suppresses_local_file_schemas_even_if_always_on() -> None:
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(provider)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    names = _tool_names(provider.calls[0])
    assert {"search_docs", "fetch_doc_chunk", "tool_search"} <= names
    assert names.isdisjoint({"read_file", "shell", "list_dir"})


def test_tool_search_result_is_filtered_before_model_can_see_blocked_tool() -> None:
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("s1", "tool_search", {"query": "select:read_file"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    tool_result_messages = [
        msg for msg in provider.calls[1]["messages"] if msg.get("role") == "tool"
    ]
    assert tool_result_messages
    payload = json.loads(tool_result_messages[-1]["content"])
    assert payload["matched"] == []
    assert payload["blocked_by_tool_access_gateway"] == ["read_file"]
    assert result.context_retry["tool_access"]["visible_suppress"] == [
        "list_dir",
        "read_file",
        "shell",
    ]


def test_execution_work_tool_search_uses_protected_read_only_scope() -> None:
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "s1",
                        "tool_search",
                        {"query": "select:write_file", "allowed_risk": ["write"]},
                    )
                ],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        extra_tools=[
            _RecordingTool(
                "finish_task_step_execution",
                capabilities=frozenset({"task_execution.finish"}),
            ),
            _RecordingTool("write_file"),
        ],
        extra_tool_risks={"write_file": "write"},
        tool_search_type=_RecordingToolSearch,
    )

    asyncio.run(
        reasoner.run_turn(
            msg=_msg(
                "continue execution",
                metadata={"task_execution_contract": _execution_work_contract()},
            ),
            session=cast(Any, _session()),
        )
    )

    tool_search = cast(_RecordingToolSearch, reasoner._tool_search_tool)
    assert tool_search.calls[0]["_task_execution_read_only"] is True
    assert tool_search.calls[0]["_session_key"] == "cli:1"
    assert json.loads(tool_search.raw_results[0])["matched"] == []


def test_gateway_blocked_tool_call_does_not_execute_or_count_as_used() -> None:
    read_file = _RecordingTool("read_file")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("r1", "read_file", {"path": "README.md"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider, read_file=read_file)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    assert read_file.calls == []
    assert result.tools_used == []
    call = result.tool_chain[0]["calls"][0]
    assert call["name"] == "read_file"
    assert call["status"] == "blocked_by_tool_boundary"
    assert call["boundary_action"] == "block"
    assert call["boundary_reason"] == "tool_blocked_by_doc_rag_policy"
    assert "tool_blocked_by_doc_rag_policy" in call["result"]


def test_explicit_source_request_keeps_local_file_schemas_available() -> None:
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(provider)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档和源码回答，请读取 agent/core/passive_turn.py"),
            session=cast(Any, _session()),
        )
    )

    names = _tool_names(provider.calls[0])
    assert {"search_docs", "read_file"} <= names


def test_ordinary_task_plan_turn_remains_la001(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    service.create_task_plan(
        session_key="cli:1",
        title="Fix RAG tool cost",
        steps=["Inspect logs", "Patch boundary", "Run tests"],
    )
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(provider, task_plan_service=service)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("标记当前任务第一步已完成"),
            session=cast(Any, _session()),
        )
    )

    names = _tool_names(provider.calls[0])
    assert "inspect_task_plan" in names
    assert "update_task_step" in names
    assert "create_task_plan" not in names


def test_task_plan_create_success_switches_to_final_only(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "c1",
                        "create_task_plan",
                        {
                            "title": "Document RAG 成本分析",
                            "steps": [
                                "分析证据合同",
                                "分析边界策略",
                                "提出优化方案",
                            ],
                        },
                    )
                ],
            ),
            LLMResponse(content="计划已创建。", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider, task_plan_service=service)
    caplog.set_level(logging.INFO, logger="agent.core.passive_turn")

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("为修复 Document RAG 成本问题制定一个三步计划"),
            session=cast(Any, _session()),
        )
    )

    assert result.tools_used == ["create_task_plan"]
    assert provider.calls[1]["tools"] == []
    assert result.context_retry["turn_completion"]["reason"] == (
        "task_plan_completion_capability_satisfied"
    )
    plan = service.get_active_task_plan(session_key="cli:1")
    assert plan is not None
    assert len(plan.steps) == 3
    assert (
        "[turn_completion] scheduled final_only "
        "reason=task_plan_completion_capability_satisfied"
    ) in caplog.text


def test_task_plan_inspect_success_switches_to_final_only(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    service.create_task_plan(
        session_key="cli:1",
        title="Document RAG 成本分析",
        steps=["分析证据合同", "分析边界策略", "提出优化方案"],
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("i1", "inspect_task_plan", {})],
            ),
            LLMResponse(content="当前任务在第 1 步。", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider, task_plan_service=service)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("当前任务做到哪一步了？"),
            session=cast(Any, _session()),
        )
    )

    assert result.tools_used == ["inspect_task_plan"]
    assert provider.calls[1]["tools"] == []
    assert result.context_retry["turn_completion"]["reason"] == (
        "task_plan_completion_capability_satisfied"
    )


def test_task_plan_update_success_switches_to_final_only(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    plan = service.create_task_plan(
        session_key="cli:1",
        title="Document RAG 成本分析",
        steps=["分析证据合同", "分析边界策略", "提出优化方案"],
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "u1",
                        "update_task_step",
                        {
                            "task_id": plan.task_id,
                            "step_index": 1,
                            "status": "completed",
                            "result_summary": "已查看日志",
                        },
                    )
                ],
            ),
            LLMResponse(content="第一步已完成。", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider, task_plan_service=service)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("把第一步标记为完成，说明已经查看日志"),
            session=cast(Any, _session()),
        )
    )

    assert result.tools_used == ["update_task_step"]
    assert provider.calls[1]["tools"] == []
    assert result.context_retry["turn_completion"]["reason"] == (
        "task_plan_completion_capability_satisfied"
    )


def test_task_plan_create_blocks_spawn_even_if_model_calls_it(
    tmp_path: Path,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    spawn = _RecordingTool("spawn")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("s1", "spawn", {"task": "run analysis"})],
            ),
            LLMResponse(content="我会先创建计划。", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        extra_tools=[spawn],
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("为修复 Document RAG 成本问题制定一个三步计划"),
            session=cast(Any, _session()),
        )
    )

    assert spawn.calls == []
    assert result.tools_used == []
    assert result.tool_chain[0]["calls"][0]["status"] == "blocked_by_tool_boundary"
    assert result.tool_chain[0]["calls"][0]["boundary_reason"] == (
        "tool_blocked_by_task_plan_policy"
    )


def test_background_job_prompt_keeps_spawn_manage_available(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    service.create_task_plan(
        session_key="cli:1",
        title="Fix RAG",
        steps=["Read logs"],
    )
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        extra_tools=[_RecordingTool("spawn_manage"), _RecordingTool("task_output")],
    )

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("查看后台任务状态"),
            session=cast(Any, _session()),
        )
    )

    names = _tool_names(provider.calls[0])
    assert "spawn_manage" in names
    assert "task_output" not in names
    assert "inspect_task_plan" not in names


def test_pure_create_exposes_only_create_and_blocks_memory_hard_call(
    tmp_path: Path,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    recall = _RecordingTool(
        "recall_memory",
        '{"ok": true}',
        capabilities=frozenset({"memory.recall"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("m1", "recall_memory", {"query": "prefs"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        recall_memory=recall,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("制定一个三步计划"),
            session=cast(Any, _session()),
        )
    )

    assert _tool_names(provider.calls[0]) == {"create_task_plan"}
    assert recall.calls == []
    assert result.tool_chain[0]["calls"][0]["boundary_reason"] == (
        "tool_blocked_by_task_plan_policy"
    )
    trace = result.context_retry["tool_boundary"]
    assert trace["task_plan_contract"]["completion_capability"] == (
        "task_plan.create"
    )
    assert trace["task_plan_completion"]["resolved_provider_tools"] == [
        "create_task_plan"
    ]
    assert trace["tool_access"]["policy_metadata"]["task_plan"][
        "resolved_capabilities"
    ]["task_plan.create"] == ["create_task_plan"]


def test_strict_task_plan_scope_omits_global_deferred_tool_hint(
    tmp_path: Path,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    requests: list[ContextRequest] = []
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        render_requests=requests,
    )

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("制定一个三步计划"),
            session=cast(Any, _session()),
        )
    )

    assert requests
    assert requests[0].turn_injection_prompt == ""


def test_memory_context_retires_after_one_call_then_create_finishes(
    tmp_path: Path,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    recall = _RecordingTool(
        "recall_memory",
        '{"ok": true, "memories": [{"content": "prefer concise plans"}]}',
        capabilities=frozenset({"memory.recall"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("m1", "recall_memory", {"query": "prefs"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "c1",
                        "create_task_plan",
                        {"title": "Preference plan", "steps": ["A", "B", "C"]},
                    )
                ],
            ),
            LLMResponse(content="created", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        recall_memory=recall,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("结合我的偏好制定计划"),
            session=cast(Any, _session()),
        )
    )

    assert _tool_names(provider.calls[0]) == {"recall_memory", "create_task_plan"}
    assert _tool_names(provider.calls[1]) == {"create_task_plan"}
    assert provider.calls[2]["tools"] == []
    assert len(recall.calls) == 1
    assert result.tools_used == ["recall_memory", "create_task_plan"]


def test_same_batch_memory_repeat_executes_only_once(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    recall = _RecordingTool(
        "recall_memory",
        '{"ok": false, "error_code": "unavailable"}',
        capabilities=frozenset({"memory.recall"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall("m1", "recall_memory", {"query": "prefs"}),
                    ToolCall("m2", "recall_memory", {"query": "prefs again"}),
                ],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "c1",
                        "create_task_plan",
                        {"title": "Plan", "steps": ["A"]},
                    )
                ],
            ),
            LLMResponse(content="created", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        recall_memory=recall,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("结合我的偏好制定计划"),
            session=cast(Any, _session()),
        )
    )

    assert len(recall.calls) == 1
    calls = result.tool_chain[0]["calls"]
    assert calls[1]["status"] == "soft_stopped_by_tool_boundary"
    assert calls[1]["boundary_reason"] == "task_plan_context_budget_exhausted"


def test_denied_context_attempt_consumes_same_batch_budget(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    recall = _RecordingTool(
        "recall_memory",
        '{"ok": true}',
        capabilities=frozenset({"memory.recall"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall("m1", "recall_memory", {"query": "prefs"}),
                    ToolCall("m2", "recall_memory", {"query": "again"}),
                ],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "c1",
                        "create_task_plan",
                        {"title": "Plan", "steps": ["A"]},
                    )
                ],
            ),
            LLMResponse(content="created", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        recall_memory=recall,
    )
    reasoner.add_tool_hooks([_DenyToolHook("recall_memory", '{"ok": true}')])

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("结合我的偏好制定计划"),
            session=cast(Any, _session()),
        )
    )

    assert recall.calls == []
    calls = result.tool_chain[0]["calls"]
    assert calls[0]["status"] == "denied"
    assert calls[1]["status"] == "soft_stopped_by_tool_boundary"
    assert calls[1]["boundary_reason"] == "task_plan_context_budget_exhausted"
    assert result.context_retry["tool_boundary"]["task_plan_context_budget"][
        "last_execution_status"
    ] == "denied"


def test_executor_error_context_attempt_consumes_same_batch_budget(
    tmp_path: Path,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    recall = _RecordingTool(
        "recall_memory",
        '{"ok": true}',
        capabilities=frozenset({"memory.recall"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall("m1", "recall_memory", {"query": "prefs"}),
                    ToolCall("m2", "recall_memory", {"query": "again"}),
                ],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        recall_memory=recall,
    )
    reasoner.add_tool_hooks([_ErrorToolHook("recall_memory")])

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("结合我的偏好制定计划"),
            session=cast(Any, _session()),
        )
    )

    assert recall.calls == []
    calls = result.tool_chain[0]["calls"]
    assert calls[0]["status"] == "error"
    assert calls[1]["status"] == "soft_stopped_by_tool_boundary"
    assert calls[1]["boundary_reason"] == "task_plan_context_budget_exhausted"


def test_cross_family_context_call_is_blocked_before_execution(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    recall = _RecordingTool(
        "recall_memory",
        '{"ok": true}',
        capabilities=frozenset({"memory.recall"}),
    )
    search = _RecordingTool(
        "search_messages",
        '{"ok": true}',
        capabilities=frozenset({"history.search"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall("m1", "recall_memory", {"query": "prefs"}),
                    ToolCall("s1", "search_messages", {"query": "history"}),
                ],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        recall_memory=recall,
        search_messages=search,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("结合我的偏好制定计划"),
            session=cast(Any, _session()),
        )
    )

    assert len(recall.calls) == 1
    assert search.calls == []
    assert result.tool_chain[0]["calls"][1]["boundary_reason"] == (
        "tool_blocked_by_task_plan_policy"
    )


def test_session_history_context_uses_search_once_without_fetch(
    tmp_path: Path,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    search = _RecordingTool(
        "search_messages",
        '{"ok": true, "messages": [{"content": "last discussion"}]}',
        capabilities=frozenset({"history.search"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("s1", "search_messages", {"query": "last"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "c1",
                        "create_task_plan",
                        {"title": "History plan", "steps": ["A"]},
                    )
                ],
            ),
            LLMResponse(content="created", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        search_messages=search,
    )

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("按照我们上次讨论制定计划"),
            session=cast(Any, _session()),
        )
    )

    assert _tool_names(provider.calls[0]) == {"search_messages", "create_task_plan"}
    assert _tool_names(provider.calls[1]) == {"create_task_plan"}
    assert len(search.calls) == 1


def test_same_batch_history_repeat_executes_only_once(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    search = _RecordingTool(
        "search_messages",
        '{"ok": true, "messages": []}',
        capabilities=frozenset({"history.search"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall("s1", "search_messages", {"query": "last"}),
                    ToolCall("s2", "search_messages", {"query": "again"}),
                ],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        search_messages=search,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("按照我们上次讨论制定计划"),
            session=cast(Any, _session()),
        )
    )

    assert len(search.calls) == 1
    assert result.tool_chain[0]["calls"][1]["boundary_reason"] == (
        "task_plan_context_budget_exhausted"
    )


def test_denied_completion_payload_does_not_schedule_final_only() -> None:
    create = _RecordingTool(
        "create_task_plan",
        '{"ok": true}',
        capabilities=frozenset({"task_plan.create"}),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "c1",
                        "create_task_plan",
                        {"title": "Plan", "steps": ["A"]},
                    )
                ],
            ),
            LLMResponse(content="could not create", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider, extra_tools=[create])
    reasoner.add_tool_hooks([_DenyToolHook("create_task_plan", '{"ok": true}')])

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("制定一个三步计划"),
            session=cast(Any, _session()),
        )
    )

    assert create.calls == []
    assert result.tool_chain[0]["calls"][0]["status"] == "denied"
    assert _tool_names(provider.calls[1]) == {"create_task_plan"}
    assert "turn_completion" not in result.context_retry


def test_update_inspect_first_finishes_only_after_update(tmp_path: Path) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    plan = service.create_task_plan(
        session_key="cli:1", title="Plan", steps=["A", "B"]
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("i1", "inspect_task_plan", {})],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "u1",
                        "update_task_step",
                        {
                            "task_id": plan.task_id,
                            "step_index": 1,
                            "status": "completed",
                        },
                    )
                ],
            ),
            LLMResponse(content="updated", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider, task_plan_service=service)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("把第一步标记完成"),
            session=cast(Any, _session()),
        )
    )

    assert _tool_names(provider.calls[0]) == {
        "inspect_task_plan",
        "update_task_step",
    }
    assert provider.calls[1]["tools"]
    assert provider.calls[2]["tools"] == []
    assert result.tools_used == ["inspect_task_plan", "update_task_step"]


def test_discovery_disabled_still_enforces_strict_task_plan_scope(
    tmp_path: Path,
) -> None:
    service = TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(
        provider,
        task_plan_service=service,
        tool_search_enabled=False,
    )

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("制定一个三步计划"),
            session=cast(Any, _session()),
        )
    )

    assert _tool_names(provider.calls[0]) == {"create_task_plan"}


def test_discovery_disabled_non_task_turn_keeps_all_registered_tools() -> None:
    provider = _Provider([LLMResponse(content="final", tool_calls=[])])
    reasoner = _make_reasoner(provider, tool_search_enabled=False)

    asyncio.run(
        reasoner.run_turn(
            msg=_msg("今天杭州天气如何？"),
            session=cast(Any, _session()),
        )
    )

    assert _tool_names(provider.calls[0]) == reasoner._tools.get_registered_names()
