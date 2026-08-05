from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from agent.core.passive_turn import DefaultReasoner
from agent.core.runtime_support import LLMServices, ToolDiscoveryState, TurnRunResult
from agent.core.types import ContextRenderResult, ContextRequest
from agent.governance.metrics_eval import (
    DEFAULT_TOOL_GOVERNANCE_CASES,
    TOOL_GOVERNANCE_EVAL_PROFILE_KEY,
    ToolGovernanceEvalRecord,
    ToolGovernanceRealTurnSpec,
    build_real_llm_turn_specs,
    record_from_turn_result,
    run_tool_governance_real_eval,
)
from agent.governance.real_runtime import EvalRuntimeConfig, ToolGovernanceEvalRuntime
from agent.looping.ports import LLMConfig
from agent.provider import LLMResponse, ToolCall
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from agent.tools.tool_search import ToolSearchTool


class _RecordingTool(Tool):
    def __init__(
        self,
        name: str,
        result: str,
        *,
        parameters: dict[str, object] | None = None,
    ) -> None:
        self._name = name
        self._result = result
        self._parameters = parameters or {
            "type": "object",
            "properties": {},
            "required": [],
        }
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name

    @property
    def parameters(self) -> dict[str, object]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> str:
        self.calls.append(dict(kwargs))
        return self._result


class _Provider:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(dict(kwargs))
        if not self._responses:
            raise AssertionError("provider.chat called more than expected")
        return self._responses.pop(0)


def _msg(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        media=[],
        channel="cli",
        chat_id="1",
        timestamp=datetime.now(timezone.utc),
        metadata={},
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        key="cli:toolgov-real",
        messages=[],
        metadata={},
        get_history=lambda max_messages=40, *, start_index=None: [],
        last_consolidated=0,
    )


def _reasoner(provider: _Provider, workspace: Path) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.register(ToolSearchTool(tools), always_on=True, risk="read-only")
    tools.register(
        _RecordingTool(
            "search_docs",
            json.dumps(
                {
                    "ok": True,
                    "hit_count": 1,
                    "hits": [
                        {
                            "chunk_id": "c1",
                            "citation": "my_md/doc.md > Tool Governance",
                        }
                    ],
                }
            ),
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        risk="read-only",
    )
    tools.register(
        _RecordingTool(
            "fetch_doc_chunk",
            json.dumps(
                {
                    "ok": True,
                    "chunk": {
                        "chunk_id": "c1",
                        "citation": "my_md/doc.md > Tool Governance",
                        "text": "Tool governance constrains tool scope and budgets.",
                    },
                }
            ),
            parameters={
                "type": "object",
                "properties": {"chunk_id": {"type": "string"}},
                "required": ["chunk_id"],
            },
        ),
        risk="read-only",
    )
    tools.register(
        _RecordingTool("read_file", "file"), always_on=True, risk="read-only"
    )
    tools.register(
        _RecordingTool("shell", "shell"),
        always_on=True,
        risk="write",
        capabilities={"shell.execute"},
    )

    def _render(request: ContextRequest, **_kwargs: object) -> ContextRenderResult:
        return ContextRenderResult(
            system_prompt="",
            turn_injection_context={
                "turn_injection": request.turn_injection_prompt or ""
            },
            messages=[{"role": "user", "content": request.current_message}],
            debug_breakdown=[],
        )

    return DefaultReasoner(
        llm=cast(Any, LLMServices(provider=provider, light_provider=provider)),
        llm_config=LLMConfig(model="m", max_iterations=12, max_tokens=512),
        tools=tools,
        discovery=ToolDiscoveryState(),
        tool_search_enabled=True,
        memory_window=10,
        context=cast(Any, SimpleNamespace(render=_render, workspace=workspace)),
        session_manager=cast(
            Any, SimpleNamespace(save_async=lambda *_args, **_kw: None)
        ),
    )


def _doc_spec(profile: str) -> ToolGovernanceRealTurnSpec:
    case = DEFAULT_TOOL_GOVERNANCE_CASES[1]
    return ToolGovernanceRealTurnSpec(
        run_id="unit-real",
        profile=profile,
        case_id=case.case_id,
        scenario=case.scenario,
        prompt=case.prompt,
        expected_tools=case.expected_tools,
        forbidden_tools=case.forbidden_tools,
        expected_policy_actions=case.expected_policy_actions,
        expected_approval=case.expected_approval,
        expected_invoker_reached=case.expected_invoker_reached,
        success_criteria=case.success_criteria,
        turn_metadata={
            TOOL_GOVERNANCE_EVAL_PROFILE_KEY: profile,
            "tool_governance_eval_case_id": case.case_id,
            "tool_governance_eval_scenario": case.scenario,
        },
        max_react_iterations=12,
    )


@pytest.mark.asyncio
async def test_real_adapter_runs_reasoner_with_profile_metadata(tmp_path: Path) -> None:
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("s1", "search_docs", {"query": "governance"})],
                usage={"prompt_tokens": 10, "total_tokens": 20},
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"})],
                usage={"prompt_tokens": 11, "total_tokens": 21},
            ),
            LLMResponse(
                content="final answer",
                tool_calls=[],
                usage={"prompt_tokens": 12, "total_tokens": 22},
            ),
        ]
    )
    spec = _doc_spec("full_governance")

    record = await run_tool_governance_real_eval(
        run_id="unit-real",
        max_react_iterations=12,
        runtime_adapter=lambda turn_spec: _reasoner(provider, tmp_path).run_turn(
            msg=_msg(turn_spec.prompt),
            session=cast(Any, _session()),
            turn_metadata=turn_spec.turn_metadata,
        ),
        specs=(spec,),
    )

    assert record.metrics["mode"] == "real_llm"
    assert record.metrics["turn_count"] == 1
    row = record.records[0]
    assert row.profile == "full_governance"
    assert row.actual_prompt_tokens_sum == 33
    assert row.actual_total_tokens_sum == 63
    assert row.react_iteration_count == 3
    assert row.actual_tools == ("search_docs", "fetch_doc_chunk")
    assert row.soft_stop_count == 0


def test_record_from_turn_result_extracts_security_and_budget_metrics() -> None:
    spec = build_real_llm_turn_specs(run_id="unit-real")[0]
    result = TurnRunResult(
        reply="final",
        tools_used=["search_docs"],
        tool_chain=[
            {
                "calls": [
                    {
                        "name": "search_docs",
                        "status": "success",
                        "boundary_action": "allow",
                        "boundary_reason": "within_budget",
                    },
                    {
                        "name": "shell",
                        "status": "blocked_by_tool_boundary",
                        "boundary_action": "block",
                        "boundary_reason": "tool_invocation_destructive_denied",
                    },
                ]
            }
        ],
        context_retry={
            "react_stats": {
                "actual_prompt_tokens_sum": 10,
                "actual_total_tokens_sum": 15,
                "llm_duration_ms_sum": 7,
                "iteration_count": 2,
            },
            "tool_boundary": {
                "decisions": [
                    {"tool": "search_docs", "action": "allow", "execute": True},
                    {
                        "tool": "shell",
                        "action": "block",
                        "execute": False,
                        "reason": "tool_invocation_destructive_denied",
                    },
                    {
                        "tool": "fetch_doc_chunk",
                        "action": "soft_stop",
                        "execute": False,
                        "reason": "document_rag_evidence_complete",
                    },
                ]
            },
            "turn_completion": {"metadata": {"batch_skip_count": 1}},
        },
    )

    record = record_from_turn_result(spec, result, turn_duration_ms=123)

    assert isinstance(record, ToolGovernanceEvalRecord)
    assert record.mode == "real_llm"
    assert record.correctness == "PASS"
    assert record.tool_call_count == 2
    assert record.executed_tool_count == 1
    assert record.forbidden_tool_call_count == 1
    assert record.forbidden_tool_executed_count == 0
    assert record.soft_stop_count == 1
    assert record.batch_skip_count == 1
    assert record.deny_count == 1
    assert record.invoker_reached_when_denied_count == 0
    assert record.audit_event_coverage_passed is True


def test_record_from_turn_result_counts_deferred_expected_tool_as_attempted() -> None:
    spec = build_real_llm_turn_specs(
        run_id="unit-real",
        cases=(DEFAULT_TOOL_GOVERNANCE_CASES[10],),
        profiles=("full_governance",),
    )[0]
    result = TurnRunResult(
        reply="需要审批后才能写入。",
        tools_used=[],
        tool_chain=[
            {
                "calls": [
                    {
                        "name": "write_file",
                        "status": "deferred",
                        "arguments": {"path": "governance_eval.txt"},
                        "audit_trace": {
                            "policy_action": "defer",
                            "policy_reason": "risk_strategy_write_requires_approval",
                            "invoker_reached": False,
                        },
                        "approval_lifecycle": [{"status": "requested"}],
                    }
                ]
            }
        ],
        context_retry={
            "react_stats": {
                "actual_prompt_tokens_sum": 100,
                "actual_total_tokens_sum": 120,
                "llm_duration_ms_sum": 50,
                "iteration_count": 1,
            },
            "tool_boundary": {"decisions": []},
        },
    )

    record = record_from_turn_result(spec, result, turn_duration_ms=200)

    assert record.actual_tools == ("write_file",)
    assert record.expected_tool_missing_count == 0
    assert record.executed_tool_count == 0
    assert record.defer_count == 1
    assert record.approval_created_count == 1
    assert record.correctness == "PASS"


@pytest.mark.asyncio
async def test_real_runtime_preloads_expected_high_risk_tool(tmp_path: Path) -> None:
    spec = build_real_llm_turn_specs(
        run_id="unit-real",
        cases=(DEFAULT_TOOL_GOVERNANCE_CASES[10],),
        profiles=("full_governance",),
    )[0]
    provider = _Provider(
        [
            LLMResponse(
                content="不能直接写入，需审批。",
                tool_calls=[],
                usage={"prompt_tokens": 10, "total_tokens": 12},
            )
        ]
    )
    runtime = ToolGovernanceEvalRuntime(
        provider=provider,
        config=EvalRuntimeConfig(
            workspace=tmp_path,
            model="m",
            max_react_iterations=12,
            max_tokens=512,
        ),
    )

    await runtime.run_turn(spec)

    first_tools = provider.calls[0]["tools"]
    names = {
        item["function"]["name"]
        for item in first_tools
        if isinstance(item, dict) and isinstance(item.get("function"), dict)
    }
    assert "write_file" in names
