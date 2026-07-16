from __future__ import annotations

from memory2.retrieval_graph_experiments import (
    build_graph_lane,
    build_graph_retrieval_shadow_result,
)


def test_build_graph_lane_prefers_connected_entity_paths() -> None:
    active_items = [
        {
            "id": "g1",
            "memory_type": "event",
            "summary": "NetworkX 实体图谱可以提升上次方案找回",
            "source_ref": "cli:local:1",
            "scope_channel": "cli",
            "scope_chat_id": "local",
            "extra_json": {"active_topics": ["NetworkX 实体图谱", "图谱找回"]},
        },
        {
            "id": "g2",
            "memory_type": "event",
            "summary": "无关记忆，但也有 source_ref",
            "source_ref": "cli:local:2",
            "scope_channel": "cli",
            "scope_chat_id": "local",
            "extra_json": {"active_topics": ["其他话题"]},
        },
    ]

    lane = build_graph_lane(
        "上次那个图谱方案还能怎么找回",
        active_items,
        scope_channel="cli",
        scope_chat_id="local",
        limit=3,
        max_hops=2,
    )

    assert lane.lane_name == "graph"
    assert [item["id"] for item in lane.items] == ["g1"]
    assert lane.items[0]["entity_match_count"] >= 1
    assert lane.items[0]["graph_path_count"] >= 1


def test_build_graph_lane_returns_empty_without_graph_signal() -> None:
    lane = build_graph_lane(
        "完全无关的问题",
        [
            {
                "id": "g1",
                "memory_type": "event",
                "summary": "图谱相关但 query 无关",
                "source_ref": "cli:local:1",
                "scope_channel": "cli",
                "scope_chat_id": "local",
                "extra_json": {"active_topics": ["图谱相关"]},
            }
        ],
    )

    assert lane.items == []


def test_build_graph_retrieval_shadow_result_outputs_graph_metrics() -> None:
    result = build_graph_retrieval_shadow_result(
        query="上次那个图谱方案",
        baseline_items=[{"id": "m1"}],
        semantic_items=[{"id": "m1", "score": 0.8}],
        keyword_items=[{"id": "m1", "keyword_score": 0.7}],
        provenance_items=[{"id": "m1", "provenance_score": 0.8}],
        graph_items=[
            {"id": "m1", "graph_score": 0.9, "graph_path_length": 2.0},
            {"id": "m2", "graph_score": 0.8, "graph_path_length": 3.0},
        ],
        latency_ms=12.3,
        top_n=3,
    )

    assert result.baseline_result["baseline_ids"] == ["m1"]
    assert result.experimental_result["graph_hit_count"] == 2
    assert result.experimental_result["graph_ids"] == ["m1", "m2"]
    assert result.experimental_result["graph_fused_ids"][0] == "m1"
    assert result.metrics["graph_lane_contribution"]["graph"] == 2
    assert result.metrics["graph_path_count"] == 2
    assert result.metrics["avg_graph_path_length"] == 2.5
