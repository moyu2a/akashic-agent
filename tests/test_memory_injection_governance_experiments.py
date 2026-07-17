from __future__ import annotations

from memory2.injection_governance_experiments import (
    build_injection_governance_shadow_result,
)


def test_injection_governance_prefers_rules_and_drops_weak_history() -> None:
    result = build_injection_governance_shadow_result(
        baseline_items=[
            {
                "id": "e1",
                "memory_type": "event",
                "summary": "用户很久之前随口提到一个临时安排",
                "score": 0.51,
            },
            {
                "id": "p1",
                "memory_type": "procedure",
                "summary": "回答架构问题时先给技术版再给易懂版",
                "score": 0.8,
                "source_ref": "cli:local:1",
                "extra_json": {"tool_requirement": "none"},
            },
        ],
        baseline_injected_ids=["e1", "p1"],
        baseline_text_block="old block",
        candidate_items=[
            {
                "id": "p1",
                "memory_type": "procedure",
                "summary": "回答架构问题时先给技术版再给易懂版",
                "experimental_score": 1.2,
                "score": 0.8,
                "source_ref": "cli:local:1",
            },
            {
                "id": "e1",
                "memory_type": "event",
                "summary": "用户很久之前随口提到一个临时安排",
                "experimental_score": 0.2,
                "score": 0.51,
            },
        ],
        max_chars=400,
        max_items=4,
    )

    assert result.baseline_result["baseline_injected_ids"] == ["e1", "p1"]
    assert result.experimental_result["experimental_injected_ids"] == ["p1"]
    assert result.experimental_result["drop_reasons"]["e1"] in {
        "low_confidence",
        "weak_relevance",
    }
    assert result.experimental_result["inject_reasons"]["p1"] == "high_value_rule"
    assert result.metrics["low_confidence_injected_count"] == 1


def test_injection_governance_enforces_character_budget() -> None:
    result = build_injection_governance_shadow_result(
        baseline_items=[],
        baseline_injected_ids=[],
        baseline_text_block="",
        candidate_items=[
            {
                "id": "long",
                "memory_type": "preference",
                "summary": "x" * 1000,
                "experimental_score": 1.0,
                "score": 0.9,
                "source_ref": "cli:local:1",
            },
            {
                "id": "short",
                "memory_type": "preference",
                "summary": "用户希望中文回答",
                "experimental_score": 0.9,
                "score": 0.8,
                "source_ref": "cli:local:2",
            },
        ],
        max_chars=120,
        max_items=4,
    )

    assert result.experimental_result["experimental_injected_ids"] == ["short"]
    assert result.experimental_result["drop_reasons"]["long"] == "over_budget"
    assert result.metrics["experimental_injected_count"] == 1
