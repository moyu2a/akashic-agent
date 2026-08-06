from __future__ import annotations

from eval.agent_harness.environments import DeterministicFakeEnvironment


def test_fake_environment_reset_snapshot_restore_and_state_inspection() -> None:
    environment = DeterministicFakeEnvironment(
        initial_state={"counter": 0},
        tool_results={"list_dir": {"entries": ["agent"]}},
    )

    environment.reset(seed=11)
    environment.mutate({"counter": 1, "last_tool": "list_dir"})
    snapshot = environment.snapshot()
    environment.mutate({"counter": 9})
    environment.restore(snapshot)

    assert environment.inspect_state() == {
        "counter": 1,
        "last_tool": "list_dir",
    }
    assert environment.tool_result("list_dir") == {"entries": ["agent"]}


def test_fake_environment_reset_restores_initial_state() -> None:
    environment = DeterministicFakeEnvironment(initial_state={"status": "new"})
    environment.mutate({"status": "changed"})

    environment.reset(seed=42)

    assert environment.inspect_state() == {"status": "new"}
    assert environment.seed == 42
