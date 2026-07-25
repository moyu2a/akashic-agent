from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from memory2.eval_sleep_hygiene_cases import (
    build_sleep_hygiene_cases,
    flatten_sleep_hygiene_memory_items,
)
from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)


def test_sleep_hygiene_cases_are_balanced_and_deterministic() -> None:
    cases = build_sleep_hygiene_cases(
        duplicate_groups=3,
        stale_count=4,
        low_value_count=5,
        retained_count=6,
        missing_source_count=2,
    )

    labels = Counter(case.label for case in cases)

    assert labels == {
        "duplicate": 3,
        "stale": 4,
        "low_value": 5,
        "retained": 6,
    }
    assert [case.case_id for case in cases[:4]] == [
        "dup_group_000",
        "dup_group_001",
        "dup_group_002",
        "stale_000",
    ]


def test_sleep_hygiene_flattened_items_have_required_fields_and_unique_ids() -> None:
    cases = build_sleep_hygiene_cases(
        duplicate_groups=2,
        stale_count=2,
        low_value_count=2,
        retained_count=2,
        missing_source_count=1,
    )

    items = flatten_sleep_hygiene_memory_items(cases)
    ids = [str(item["id"]) for item in items]

    assert len(ids) == len(set(ids))
    assert all(item["status"] == "active" for item in items)
    assert all(item["scope_channel"] == "cli" for item in items)
    assert all(str(item["scope_chat_id"]).strip() for item in items)
    assert sum(1 for item in items if not item["source_ref"]) == 1


def test_sleep_hygiene_cases_isolate_scopes_to_avoid_cross_case_duplicates() -> None:
    cases = build_sleep_hygiene_cases(
        duplicate_groups=3,
        stale_count=2,
        low_value_count=2,
        retained_count=2,
        missing_source_count=0,
    )

    for case in cases:
        scopes = {
            (str(item["scope_channel"]), str(item["scope_chat_id"]))
            for item in case.memory_items
        }
        assert len(scopes) == 1

    duplicate_case = cases[0]
    assert duplicate_case.label == "duplicate"
    assert len(duplicate_case.memory_items) == 2
    assert (
        duplicate_case.memory_items[0]["scope_chat_id"]
        == duplicate_case.memory_items[1]["scope_chat_id"]
    )

    retained_cases = [case for case in cases if case.label == "retained"]
    retained_scopes = {
        str(case.memory_items[0]["scope_chat_id"]) for case in retained_cases
    }
    assert len(retained_scopes) == len(retained_cases)


def test_sleep_hygiene_hard_cases_cover_adversarial_scenarios_with_item_states() -> None:
    cases = build_sleep_hygiene_cases(
        case_set="hard",
        hard_per_scenario=2,
        missing_source_count=1,
    )

    scenarios = Counter(case.scenario for case in cases)

    assert scenarios == {
        "near_merge_not_duplicate": 2,
        "old_high_value": 2,
        "temporary_but_pinned": 2,
        "cross_scope_identical": 2,
        "opposite_preference_conflict": 2,
        "multi_duplicate_pairwise": 2,
        "missing_source_but_important": 2,
        "mixed_signal_low_value": 2,
    }
    assert {case.case_set for case in cases} == {"hard"}
    assert all(case.expected_item_states for case in cases)
    assert all(
        set(case.evaluated_item_ids()) == set(case.expected_item_states or {})
        for case in cases
    )
    assert any(
        "merged" in set(case.expected_item_states.values())
        for case in cases
        if case.expected_item_states
    )
    assert any(
        "low_value_removed" in set(case.expected_item_states.values())
        for case in cases
        if case.expected_item_states
    )
    assert any(
        set(case.expected_item_states.values()) == {"active"}
        for case in cases
        if case.expected_item_states
    )
    assert sum(
        1
        for item in flatten_sleep_hygiene_memory_items(cases)
        if not item["source_ref"]
    ) >= 1


def test_sleep_hygiene_all_case_set_combines_standard_and_hard() -> None:
    cases = build_sleep_hygiene_cases(
        case_set="all",
        duplicate_groups=3,
        stale_count=4,
        low_value_count=5,
        retained_count=6,
        hard_per_scenario=2,
    )

    assert Counter(case.case_set for case in cases) == {
        "standard": 18,
        "hard": 16,
    }


def test_sleep_hygiene_hard_cases_encode_shadow_behavior_boundaries() -> None:
    cases = build_sleep_hygiene_cases(
        case_set="hard",
        hard_per_scenario=1,
        missing_source_count=1,
    )
    result = build_sleep_consolidation_shadow_result(
        memory_items=flatten_sleep_hygiene_memory_items(cases),
        now=datetime(2026, 7, 17, tzinfo=timezone.utc),
        max_duplicate_groups=10_000,
        max_merge_candidates=10_000,
        max_stale_candidates=10_000,
        max_low_value_candidates=10_000,
        max_conflict_candidates=10_000,
    )
    duplicate_pairs = {
        tuple(group["item_ids"])
        for group in result.experimental_result["duplicate_groups"]
    }
    merge_pairs = {
        tuple(candidate["item_ids"])
        for candidate in result.experimental_result["merge_candidates"]
    }
    stale_ids = set(result.experimental_result["stale_candidate_ids"])
    low_value_ids = set(result.experimental_result["low_value_candidate_ids"])
    conflict_pairs = {
        tuple(candidate["item_ids"])
        for candidate in result.experimental_result["conflict_candidates"]
    }

    by_scenario = {case.scenario: case for case in cases}

    near = by_scenario["near_merge_not_duplicate"]
    near_ids = tuple(sorted(near.evaluated_item_ids()))
    assert near_ids not in duplicate_pairs
    assert near_ids in merge_pairs

    cross = by_scenario["cross_scope_identical"]
    cross_ids = tuple(sorted(cross.evaluated_item_ids()))
    assert cross_ids not in duplicate_pairs
    assert cross_ids not in merge_pairs

    conflict = by_scenario["opposite_preference_conflict"]
    conflict_ids = tuple(sorted(conflict.evaluated_item_ids()))
    assert conflict_ids in conflict_pairs
    assert conflict_ids not in duplicate_pairs
    assert conflict_ids not in merge_pairs

    for scenario in (
        "old_high_value",
        "temporary_but_pinned",
        "missing_source_but_important",
    ):
        item_id = by_scenario[scenario].evaluated_item_ids()[0]
        assert item_id not in stale_ids
        assert item_id not in low_value_ids

    mixed = by_scenario["mixed_signal_low_value"].evaluated_item_ids()[0]
    assert mixed in stale_ids
    assert mixed in low_value_ids
