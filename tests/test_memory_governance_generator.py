from __future__ import annotations

from collections import Counter

from memory2.eval_memory_governance_dataset import validate_memory_governance_cases
from memory2.eval_memory_governance_generator import generate_memory_governance_dataset


def test_generator_is_deterministic_for_same_seed() -> None:
    assert generate_memory_governance_dataset(seed=42) == generate_memory_governance_dataset(seed=42)


def test_generator_produces_80_cases() -> None:
    assert len(generate_memory_governance_dataset(seed=42)) == 80


def test_generator_balances_8_scenarios() -> None:
    counts = Counter(case.scenario for case in generate_memory_governance_dataset(seed=42))

    assert len(counts) == 8
    assert set(counts.values()) == {10}


def test_generated_cases_pass_self_check() -> None:
    cases = generate_memory_governance_dataset(seed=42)

    assert validate_memory_governance_cases(cases) == ()


def test_generator_does_not_place_superseded_items_in_should_recall() -> None:
    cases = generate_memory_governance_dataset(seed=42)

    for case in cases:
        by_id = {str(memory["id"]): memory for memory in case.memories}
        assert all(
            by_id[item_id]["status"] != "superseded"
            for item_id in case.should_recall_ids
        )
