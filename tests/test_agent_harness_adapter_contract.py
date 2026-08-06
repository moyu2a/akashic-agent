from __future__ import annotations

import asyncio

from eval.agent_harness.adapters import DeterministicFakeAdapter
from eval.agent_harness.environments import DeterministicFakeEnvironment
from eval.agent_harness.protocol import RunManifest, TaskSpec


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="run-001",
        git_sha="abc123",
        dataset_version="v2",
        dataset_hash="hash",
        model="fake-model",
        provider="fake",
        config_hash="cfg",
        governance_profile="full_governance",
        environment_kind="fake",
        seed=7,
        repeat_index=0,
        runner_version="0.1",
    )


def test_fake_adapter_returns_episode_result_and_enforces_iteration_budget() -> None:
    task = TaskSpec(
        case_id="adapter-001",
        category="tool",
        steps=({"role": "user", "text": "列出目录"},),
        expected_tools=("list_dir",),
        expected_outcome={"state": {"completed": True}},
    )
    environment = DeterministicFakeEnvironment()
    adapter = DeterministicFakeAdapter(max_react_iterations=12)

    result = asyncio.run(adapter.run_episode(task, environment, _manifest()))

    assert result.status == "PASS"
    assert result.outcome_passed is True
    assert result.metrics["max_react_iterations"] == 12
    assert result.metrics["react_iterations"] <= 12
    assert any(event["event_type"] == "tool_executed" for event in result.events)
    assert environment.inspect_state()["completed"] is True


def test_fake_adapter_denies_forbidden_tool_without_mutating_state() -> None:
    task = TaskSpec(
        case_id="adapter-002",
        category="security",
        expected_tools=("shell",),
        forbidden_tools=("shell",),
        expected_outcome={"state": {"completed": True}},
        expected_policy_actions=("deny",),
    )
    environment = DeterministicFakeEnvironment()

    result = asyncio.run(
        DeterministicFakeAdapter().run_episode(task, environment, _manifest())
    )

    assert result.status == "FAIL"
    assert any(event["event_type"] == "tool_skipped" for event in result.events)
    assert "completed" not in environment.inspect_state()
