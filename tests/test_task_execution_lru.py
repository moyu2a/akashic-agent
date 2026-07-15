from __future__ import annotations

from agent.core.runtime_support import TurnRunResult


def test_turn_result_carries_execution_non_lru_names() -> None:
    result = TurnRunResult(reply="done")
    assert hasattr(
        result, "non_lru_tools"
    ), "turn-local execution LRU exclusion is not integrated"
    assert result.non_lru_tools == set()
