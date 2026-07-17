from __future__ import annotations

from datetime import datetime, timezone

from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)


NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


def _item(
    item_id: str,
    summary: str,
    *,
    memory_type: str = "preference",
    updated_at: str = "2026-07-17T00:00:00+00:00",
    reinforcement: int = 1,
    emotional_weight: int = 0,
    source_ref: str = "cli:local@post_response",
    status: str = "active",
) -> dict[str, object]:
    return {
        "id": item_id,
        "summary": summary,
        "memory_type": memory_type,
        "updated_at": updated_at,
        "reinforcement": reinforcement,
        "emotional_weight": emotional_weight,
        "source_ref": source_ref,
        "status": status,
        "scope_channel": "cli",
        "scope_chat_id": "local",
    }


def test_sleep_consolidation_detects_duplicate_groups() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户喜欢中文回答"),
            _item("m2", "用户喜欢中文回答"),
            _item("m3", "用户使用 pytest 测试"),
        ],
        now=NOW,
    )

    assert result.experimental_result["duplicate_groups"] == [
        {"item_ids": ["m1", "m2"], "reason": "near_duplicate", "similarity": 1.0}
    ]
    assert result.metrics["scanned_count"] == 3
    assert result.metrics["duplicate_group_count"] == 1
    assert result.metrics["duplicate_item_count"] == 2
    assert result.metrics["estimated_redundancy_drop"] > 0


def test_sleep_consolidation_detects_merge_candidates() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户以后代码示例优先使用 pytest"),
            _item("m2", "用户代码测试示例喜欢使用 pytest"),
            _item("m3", "用户喜欢中文回答"),
        ],
        now=NOW,
    )

    candidates = result.experimental_result["merge_candidates"]
    assert candidates
    assert candidates[0]["item_ids"] == ["m1", "m2"]
    assert candidates[0]["reason"] == "same_type_related_content"
    assert result.metrics["merge_candidate_count"] == 1


def test_sleep_consolidation_detects_stale_low_value_candidates() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item(
                "m1",
                "用户临时测试变量是 abc",
                memory_type="event",
                updated_at="2025-01-01T00:00:00+00:00",
                reinforcement=1,
                emotional_weight=0,
            ),
            _item(
                "m2",
                "用户强偏好中文回答",
                updated_at="2025-01-01T00:00:00+00:00",
                reinforcement=5,
                emotional_weight=4,
            ),
        ],
        now=NOW,
    )

    assert result.experimental_result["stale_candidate_ids"] == ["m1"]
    assert result.experimental_result["low_value_candidate_ids"] == ["m1"]
    assert result.metrics["stale_candidate_count"] == 1
    assert result.metrics["low_value_candidate_count"] == 1


def test_sleep_consolidation_detects_conflicts() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户喜欢使用中文回答"),
            _item("m2", "用户不喜欢使用中文回答"),
        ],
        now=NOW,
    )

    assert result.experimental_result["conflict_candidates"] == [
        {
            "item_ids": ["m1", "m2"],
            "reason": "opposite_preference_signal",
            "similarity": result.experimental_result["conflict_candidates"][0][
                "similarity"
            ],
        }
    ]
    assert result.metrics["conflict_candidate_count"] == 1
    assert result.experimental_result["duplicate_groups"] == []
    assert result.experimental_result["merge_candidates"] == []


def test_sleep_consolidation_limits_candidate_trace_size() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item(f"m{idx}", f"用户喜欢中文回答 {idx % 2}") for idx in range(12)
        ],
        now=NOW,
        duplicate_threshold=0.1,
        max_duplicate_groups=3,
        max_merge_candidates=3,
        max_conflict_candidates=3,
    )

    assert len(result.experimental_result["duplicate_groups"]) <= 3
    assert result.metrics["duplicate_group_truncated_count"] >= 0
    assert result.metrics["merge_candidate_truncated_count"] >= 0
    assert result.metrics["conflict_candidate_truncated_count"] >= 0


def test_sleep_consolidation_limits_stale_and_low_value_trace_size() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item(
                f"m{idx}",
                f"用户临时测试变量 {idx}",
                memory_type="event",
                updated_at="2025-01-01T00:00:00+00:00",
            )
            for idx in range(12)
        ],
        now=NOW,
        max_stale_candidates=3,
        max_low_value_candidates=2,
    )

    assert len(result.experimental_result["stale_candidate_ids"]) == 3
    assert len(result.experimental_result["low_value_candidate_ids"]) == 2
    assert result.metrics["stale_candidate_count"] == 12
    assert result.metrics["low_value_candidate_count"] == 12
    assert result.metrics["stale_candidate_truncated_count"] == 9
    assert result.metrics["low_value_candidate_truncated_count"] == 10


def test_sleep_consolidation_does_not_mark_two_negative_preferences_as_conflict() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户不喜欢使用英文回答"),
            _item("m2", "用户不喜欢使用英文回复"),
        ],
        now=NOW,
    )

    assert result.experimental_result["conflict_candidates"] == []
    assert result.metrics["conflict_candidate_count"] == 0


def test_sleep_consolidation_reports_missing_source_and_token_saving() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户喜欢中文回答", source_ref=""),
            _item("m2", "用户喜欢中文回答", source_ref=""),
        ],
        now=NOW,
    )

    assert result.metrics["missing_source_ref_count"] == 2
    assert result.metrics["estimated_token_saving"] > 0
    assert result.baseline_result == {
        "active_memory_count": 2,
        "baseline_item_ids": ["m1", "m2"],
    }
