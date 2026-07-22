from __future__ import annotations

from collections import Counter

from memory2.eval_sleep_hygiene_cases import (
    build_sleep_hygiene_cases,
    flatten_sleep_hygiene_memory_items,
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
