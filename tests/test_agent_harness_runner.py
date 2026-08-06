from __future__ import annotations

import asyncio

from eval.agent_harness.adapters import DeterministicFakeAdapter
from eval.agent_harness.environments import DeterministicFakeEnvironment
from eval.agent_harness.runner import HarnessRunner
from eval.agent_harness.protocol import TaskSpec


def test_runner_expands_repeats_and_returns_summary() -> None:
    tasks = [
        TaskSpec(
            case_id="runner-001",
            category="tool",
            repeat_count=3,
            expected_outcome={"state": {"completed": True}},
        )
    ]
    runner = HarnessRunner(
        adapter=DeterministicFakeAdapter(),
        environment_factory=DeterministicFakeEnvironment,
        git_sha="abc123",
        dataset_version="test",
        model="fake-model",
        provider="fake",
        governance_profile="full_governance",
    )

    report = asyncio.run(runner.run(tasks, seed=9))

    assert len(report.results) == 3
    assert report.summary["episode_count"] == 3
    assert report.summary["passed_count"] == 3
    assert {result.metrics["repeat_index"] for result in report.results} == {0, 1, 2}
