from __future__ import annotations

from memory2.retriever import _KEYWORD_RRF_WEIGHT
from memory2.retrieval_experiments import (
    RetrievalLaneResult,
    build_provenance_lane,
    build_tri_retrieval_shadow_result,
    rrf_fuse_lanes,
)


def test_rrf_fuse_lanes_rewards_items_seen_in_multiple_lanes() -> None:
    semantic = RetrievalLaneResult(
        lane_name="semantic",
        items=[
            {"id": "semantic_only", "score": 0.99, "summary": "semantic"},
            {"id": "shared", "score": 0.70, "summary": "shared"},
        ],
    )
    keyword = RetrievalLaneResult(
        lane_name="keyword",
        items=[
            {"id": "shared", "keyword_score": 1.0, "summary": "shared"},
            {"id": "keyword_only", "keyword_score": 0.9, "summary": "keyword"},
        ],
    )
    provenance = RetrievalLaneResult(
        lane_name="provenance",
        items=[
            {"id": "shared", "provenance_score": 1.0, "summary": "shared"},
        ],
    )

    fused = rrf_fuse_lanes([semantic, keyword, provenance], top_n=3)

    assert [item["id"] for item in fused][:1] == ["shared"]
    shared = fused[0]
    assert shared["lane_hits"] == ["semantic", "keyword", "provenance"]
    assert shared["rrf_score"] > fused[1]["rrf_score"]


def test_rrf_fuse_lanes_uses_keyword_weight_compatible_with_baseline() -> None:
    fused = rrf_fuse_lanes(
        [
            RetrievalLaneResult(
                lane_name="semantic",
                items=[{"id": "semantic", "score": 0.9, "summary": "semantic"}],
            ),
            RetrievalLaneResult(
                lane_name="keyword",
                items=[{"id": "keyword", "keyword_score": 1.0, "summary": "keyword"}],
            ),
        ],
        top_n=2,
    )

    assert [item["id"] for item in fused] == ["semantic", "keyword"]
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]
    assert fused[1]["rrf_score"] == round(_KEYWORD_RRF_WEIGHT / 61, 6)


def test_build_provenance_lane_prefers_source_ref_and_scope_for_fuzzy_query() -> None:
    lane = build_provenance_lane(
        "上次那个记忆优化方案是什么",
        [
            {
                "id": "m1",
                "summary": "记忆优化 Phase 1b 写入价值评分",
                "source_ref": "cli:local:10",
                "scope_channel": "cli",
                "scope_chat_id": "local",
            },
            {
                "id": "m2",
                "summary": "无来源的普通偏好",
                "source_ref": "",
                "scope_channel": "cli",
                "scope_chat_id": "local",
            },
            {
                "id": "m3",
                "summary": "其他会话的记忆优化内容",
                "source_ref": "telegram:1:10",
                "scope_channel": "telegram",
                "scope_chat_id": "1",
            },
        ],
        scope_channel="cli",
        scope_chat_id="local",
    )

    assert lane.lane_name == "provenance"
    assert [item["id"] for item in lane.items][:1] == ["m1"]
    assert lane.items[0]["provenance_score"] > 0.0


def test_build_provenance_lane_returns_empty_without_provenance_signal() -> None:
    lane = build_provenance_lane(
        "完全无关的问题",
        [{"id": "m1", "summary": "记忆优化", "source_ref": "cli:local:1"}],
    )

    assert lane.items == []


def test_build_tri_retrieval_shadow_result_outputs_metrics() -> None:
    result = build_tri_retrieval_shadow_result(
        query="记忆优化",
        baseline_items=[{"id": "m1"}],
        semantic_items=[{"id": "m1", "score": 0.9}],
        keyword_items=[{"id": "m2", "keyword_score": 1.0}],
        provenance_items=[{"id": "m1", "provenance_score": 0.8}],
        latency_ms=12.3,
        top_n=3,
    )

    assert result.baseline_result["baseline_hit_count"] == 1
    assert result.experimental_result["semantic_hit_count"] == 1
    assert result.experimental_result["keyword_hit_count"] == 1
    assert result.experimental_result["provenance_hit_count"] == 1
    assert result.experimental_result["fused_hit_count"] == 2
    assert result.metrics["lane_contribution"]["semantic"] == 1
    assert result.metrics["lane_contribution"]["provenance"] == 1
    assert result.metrics["lane_count"] == 3
    assert result.metrics["rerank_changed_count"] >= 0
    assert "baseline_experimental_overlap_rate" in result.metrics
    assert result.metrics["retrieval_latency_ms"] == 12.3


def test_build_tri_retrieval_shadow_result_sorts_semantic_like_baseline() -> None:
    result = build_tri_retrieval_shadow_result(
        query="记忆优化",
        baseline_items=[{"id": "high"}, {"id": "low"}],
        semantic_items=[
            {"id": "low", "score": 0.1},
            {"id": "high", "score": 0.9},
        ],
        keyword_items=[],
        provenance_items=[],
        latency_ms=1.0,
        top_n=2,
    )

    assert result.experimental_result["semantic_ids"] == ["high", "low"]
    assert result.experimental_result["fused_ids"] == ["high", "low"]
