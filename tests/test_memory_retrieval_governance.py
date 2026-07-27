"""memory2 召回治理层的纯函数契约测试。"""

from __future__ import annotations

import json

from memory2.retrieval_governance import (
    apply_retrieval_route,
    build_retrieval_routing_decision,
    classify_retrieval_scene,
)


def _candidate(
    item_id: str, *, score: float = 0.9, **extra: object
) -> dict[str, object]:
    return {"id": item_id, "summary": item_id, "score": score, **extra}


def test_fuzzy_reference_enables_graph_and_keeps_graph_candidates() -> None:
    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [_candidate("semantic-1")],
            "graph": [_candidate("graph-1")],
        },
    )

    assert decision.scene == "fuzzy_reference"
    assert decision.graph_enabled is True
    assert "graph" in decision.allowed_lanes
    assert [item["id"] for item in candidates] == ["semantic-1", "graph-1"]
    assert trace["scene"] == "fuzzy_reference"
    assert trace["accepted_by_lane"]["graph"] == 1


def test_tool_preference_routes_to_semantic_and_keyword_without_graph() -> None:
    decision = build_retrieval_routing_decision("以后遇到网页搜索时优先用哪个工具？")
    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [_candidate("semantic-1")],
            "keyword": [_candidate("keyword-1")],
            "provenance": [_candidate("source-1", source_ref="msg-1")],
            "graph": [_candidate("graph-1")],
        },
    )

    assert decision.scene == "tool_preference"
    assert decision.allowed_lanes == ("semantic", "keyword")
    assert [item["id"] for item in candidates] == ["semantic-1", "keyword-1"]
    assert trace["dropped_by_reason"]["lane_not_allowed"] == 2


def test_route_applies_per_lane_cap_and_records_it_in_trace() -> None:
    decision = build_retrieval_routing_decision("以后遇到网页搜索时优先用哪个工具？")
    candidates, trace = apply_retrieval_route(
        decision,
        {"semantic": [_candidate(f"semantic-{index}") for index in range(5)]},
    )

    assert decision.max_per_lane["semantic"] == 4
    assert [item["id"] for item in candidates] == [
        "semantic-0",
        "semantic-1",
        "semantic-2",
        "semantic-3",
    ]
    assert trace["dropped_by_reason"]["lane_cap"] == 1


def test_partial_conflict_prefers_provenance_and_requires_evidence() -> None:
    decision = build_retrieval_routing_decision("之前说用 A，现在又说用 B，到底哪个才对？")
    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [_candidate("semantic-without-source")],
            "provenance": [_candidate("evidence-1", source_ref="msg-8", scope_match=True)],
            "keyword": [
                _candidate("keyword-wrong-scope", source_ref="msg-9", scope_match=False)
            ],
        },
    )

    assert decision.scene == "partial_conflict"
    assert decision.require_source_ref is True
    assert decision.require_scope_match is True
    assert [item["id"] for item in candidates] == ["evidence-1"]
    assert trace["lane_order"][:1] == ["provenance"]
    assert trace["dropped_by_reason"]["missing_source_ref"] == 1
    assert trace["dropped_by_reason"]["scope_mismatch"] == 1


def test_graph_is_rejected_outside_fuzzy_reference() -> None:
    decision = build_retrieval_routing_decision("精确找一下 Python 版本")
    candidates, trace = apply_retrieval_route(
        decision,
        {"graph": [_candidate("graph-1")], "keyword": [_candidate("keyword-1")]},
    )

    assert decision.scene == "exact_recall"
    assert decision.graph_enabled is False
    assert [item["id"] for item in candidates] == ["keyword-1"]
    assert trace["dropped_by_reason"]["lane_not_allowed"] == 1


def test_source_lookup_prioritizes_provenance_and_deduplicates_candidates() -> None:
    decision = build_retrieval_routing_decision("这条记忆的来源是什么？")
    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [_candidate("same", source_ref="msg-1")],
            "provenance": [
                _candidate("same", source_ref="msg-1"),
                _candidate("source-2", source_ref="msg-2"),
            ],
            "keyword": [_candidate("keyword-no-source")],
        },
    )

    assert decision.scene == "source_lookup"
    assert [item["id"] for item in candidates] == ["same", "source-2"]
    assert trace["lane_order"][:1] == ["provenance"]
    assert trace["dropped_by_reason"]["duplicate"] == 1
    assert trace["dropped_by_reason"]["missing_source_ref"] == 1
    json.dumps(trace)


def test_scene_classifier_covers_exact_source_and_unknown_queries() -> None:
    assert classify_retrieval_scene("精确找一下 git rebase 命令") == "exact_recall"
    assert classify_retrieval_scene("请查找这段话的消息来源") == "source_lookup"
    assert classify_retrieval_scene("今天怎么样") == "unknown"
