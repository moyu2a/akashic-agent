from __future__ import annotations

import pytest

from agent.policies.tool_risk_strategy import (
    DefaultToolRiskStrategy,
    RiskStrategyContext,
    RiskStrategyDecision,
)


def _decision(
    risk: str,
    *,
    source: str = "passive",
    capabilities: frozenset[str] = frozenset(),
) -> RiskStrategyDecision:
    return DefaultToolRiskStrategy().evaluate(
        RiskStrategyContext(
            tool_name="candidate_tool",
            registry_risk=risk,
            source=source,
            capabilities=capabilities,
        )
    )


def test_passive_read_only_is_allowed() -> None:
    decision = _decision("read-only")

    assert decision.action == "allow"
    assert decision.reason == "risk_strategy_read_only_allowed"


def test_passive_write_requires_approval() -> None:
    decision = _decision("write")

    assert decision.action == "defer"
    assert decision.reason == "risk_strategy_write_requires_approval"
    assert decision.approval_scope == "tool_call"


def test_passive_shell_requires_approval_even_if_registered() -> None:
    decision = DefaultToolRiskStrategy().evaluate(
        RiskStrategyContext(
            tool_name="shell",
            registry_risk="read-only",
            source="passive",
            capabilities=frozenset({"shell.execute"}),
        )
    )

    assert decision.action == "defer"
    assert decision.reason == "risk_strategy_shell_requires_approval"


def test_passive_read_only_process_capability_requires_approval() -> None:
    decision = DefaultToolRiskStrategy().evaluate(
        RiskStrategyContext(
            tool_name="execute_python",
            registry_risk="read-only",
            source="passive",
            capabilities=frozenset({"process.execute"}),
        )
    )

    assert decision.action == "defer"
    assert decision.reason == "risk_strategy_shell_requires_approval"


def test_task_plan_control_capability_is_allowed() -> None:
    decision = DefaultToolRiskStrategy().evaluate(
        RiskStrategyContext(
            tool_name="create_task_plan",
            registry_risk="write",
            source="passive",
            capabilities=frozenset({"task_plan.create"}),
        )
    )

    assert decision.action == "allow"
    assert decision.reason == "risk_strategy_task_plan_control_allowed"


def test_external_side_effect_requires_approval() -> None:
    decision = _decision("external-side-effect")

    assert decision.action == "defer"
    assert decision.reason == "risk_strategy_external_side_effect_requires_approval"


def test_unknown_requires_approval() -> None:
    decision = _decision("unknown")

    assert decision.action == "defer"
    assert decision.reason == "risk_strategy_unknown_requires_approval"


def test_destructive_is_denied_by_strategy_when_reached_directly() -> None:
    decision = _decision("destructive")

    assert decision.action == "deny"
    assert decision.reason == "risk_strategy_destructive_denied"


def test_non_passive_source_is_not_applicable() -> None:
    decision = _decision("write", source="subagent")

    assert decision.action == "not_applicable"
    assert decision.effective is False


def test_task_execution_is_not_applicable() -> None:
    decision = DefaultToolRiskStrategy().evaluate(
        RiskStrategyContext(
            tool_name="write_file",
            registry_risk="write",
            source="passive",
            task_execution_active=True,
            task_execution_phase="work",
        )
    )

    assert decision.action == "not_applicable"
    assert decision.effective is False


def test_rejects_invalid_action() -> None:
    with pytest.raises(ValueError, match="unsupported risk strategy action"):
        RiskStrategyDecision(
            action="sandbox",  # type: ignore[arg-type]
            reason="invalid",
            risk="unknown",
        )
