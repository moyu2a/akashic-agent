from __future__ import annotations

import pytest

from agent.governance.eval_switch import (
    TOOL_GOVERNANCE_EVAL_PROFILE_KEY,
    resolve_tool_governance_eval_switch,
)
from agent.policies.evidence_contract import (
    EvidenceAssessment,
    EvidenceSufficiency,
    TaskEvidenceRequirement,
)
from agent.policies.react_boundary import ReactBoundaryManager
from agent.policies.tool_access_types import ToolAccessContext
from agent.policies.tool_boundary import TurnToolBoundaryManager
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord
from agent.policies.turn_completion import TurnCompletionController


def _access_context(profile: str) -> ToolAccessContext:
    return ToolAccessContext(
        session_key="s1",
        user_text="根据项目文档回答工具治理链路，并展开原文证据。",
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset({"shell", "read_file"}),
        disabled_tools=frozenset(),
        turn_metadata={TOOL_GOVERNANCE_EVAL_PROFILE_KEY: profile},
        registered_tools=frozenset(
            {"tool_search", "search_docs", "fetch_doc_chunk", "shell", "read_file"}
        ),
        tool_capabilities={
            name: frozenset()
            for name in (
                "tool_search",
                "search_docs",
                "fetch_doc_chunk",
                "shell",
                "read_file",
            )
        },
        tool_risks={
            "tool_search": "read",
            "search_docs": "read",
            "fetch_doc_chunk": "read",
            "shell": "write",
            "read_file": "read",
        },
        tool_discovery_enabled=True,
    )


def _ledger_with_doc_evidence() -> ToolCallLedger:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=0,
            visible_before_call=True,
            decision_action="allow",
            decision_reason="within_budget",
            execution_status="success",
            result_ok=True,
            hit_count=1,
            citation_refs=("doc.md:1",),
            result_has_evidence=True,
            result_has_citation=True,
            result_text="citation doc.md:1",
        )
    )
    ledger.add_record(
        ToolCallRecord(
            tool_name="fetch_doc_chunk",
            tool_class="evidence_expand",
            args_hash="h2",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            decision_action="allow",
            decision_reason="within_budget",
            execution_status="success",
            result_ok=True,
            citation_refs=("doc.md:10",),
            result_has_evidence=True,
            result_has_citation=True,
            result_text="citation doc.md:10",
        )
    )
    return ledger


def _complete_evidence() -> EvidenceAssessment:
    return EvidenceAssessment(
        requirement=TaskEvidenceRequirement(task_type="doc_qa_with_evidence"),
        items=(),
        sufficiency=EvidenceSufficiency(
            tool_stop_allowed=True,
            answer_ready=True,
            reason="unit_complete",
        ),
        constraints=(),
    )


def test_eval_switch_profiles_resolve_expected_controls() -> None:
    baseline = resolve_tool_governance_eval_switch(
        {TOOL_GOVERNANCE_EVAL_PROFILE_KEY: "baseline_open"}
    )
    intent = resolve_tool_governance_eval_switch(
        {TOOL_GOVERNANCE_EVAL_PROFILE_KEY: "intent_scope_only"}
    )
    full = resolve_tool_governance_eval_switch(
        {TOOL_GOVERNANCE_EVAL_PROFILE_KEY: "full_governance"}
    )
    production = resolve_tool_governance_eval_switch({})

    assert baseline.to_trace() == {
        "active": True,
        "profile": "baseline_open",
        "hard_safety_enabled": True,
        "intent_scope_enabled": False,
        "tool_budget_enabled": False,
        "evidence_completion_enabled": False,
        "react_boundary_enabled": False,
    }
    assert intent.intent_scope_enabled is True
    assert intent.tool_budget_enabled is False
    assert intent.evidence_completion_enabled is False
    assert intent.react_boundary_enabled is False
    assert full.intent_scope_enabled is True
    assert full.tool_budget_enabled is True
    assert full.evidence_completion_enabled is True
    assert full.react_boundary_enabled is True
    assert production.active is False
    assert production.tool_budget_enabled is True


def test_eval_switch_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="unknown tool governance eval profile"):
        resolve_tool_governance_eval_switch(
            {TOOL_GOVERNANCE_EVAL_PROFILE_KEY: "unsafe_open_all"}
        )


def test_baseline_profile_disables_intent_scope_but_keeps_registered_visibility() -> (
    None
):
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_access_context("baseline_open"))

    assert context.governance_switch.profile == "baseline_open"
    assert context.access_plan.reason == "tool_governance_eval_intent_scope_disabled"
    assert context.access_plan.visible_suppress == frozenset()
    assert manager.compute_visible_names(context) == {
        "tool_search",
        "shell",
        "read_file",
    }


def test_full_profile_keeps_doc_rag_intent_scope() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_access_context("full_governance"))

    assert context.governance_switch.profile == "full_governance"
    assert context.access_plan.reason == "doc_rag_block_local_file_tools"
    assert {"search_docs", "fetch_doc_chunk"} <= context.access_plan.visible_add
    assert {"shell", "read_file"} <= context.access_plan.visible_suppress
    assert manager.compute_visible_names(context) == {
        "tool_search",
        "search_docs",
        "fetch_doc_chunk",
    }


def test_baseline_profile_does_not_soft_stop_repeated_doc_fetch() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_access_context("baseline_open"))
    context.ledger = _ledger_with_doc_evidence()

    decision = manager.evaluate_tool_call(
        context,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "doc-1"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    assert decision.execute is True
    assert decision.action == "allow"
    assert decision.reason == "tool_governance_eval_budget_disabled"


def test_full_profile_soft_stops_repeated_doc_fetch() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_access_context("full_governance"))
    context.ledger = _ledger_with_doc_evidence()

    decision = manager.evaluate_tool_call(
        context,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "doc-1"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    assert decision.execute is False
    assert decision.action == "soft_stop"


def test_react_and_completion_respect_disabled_evidence_profile() -> None:
    switch = resolve_tool_governance_eval_switch(
        {TOOL_GOVERNANCE_EVAL_PROFILE_KEY: "baseline_open"}
    )
    ledger = _ledger_with_doc_evidence()
    evidence = _complete_evidence()

    react = ReactBoundaryManager().evaluate_after_tool_result(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        evidence_assessment=evidence,
        governance_switch=switch,
    )
    completion = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        boundary_decisions=(),
        evidence_assessment=evidence,
        proactive_allowed=True,
        governance_switch=switch,
    )

    assert react.recommend_final_only is False
    assert react.reason == "tool_governance_eval_react_boundary_disabled"
    assert completion.action == "continue_react"
    assert completion.reason == "tool_governance_eval_evidence_completion_disabled"
