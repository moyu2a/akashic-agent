from __future__ import annotations

from memory2.rerank_experiments import build_rerank_shadow_result


def test_build_rerank_shadow_result_prefers_scoped_procedure_with_source() -> None:
    result = build_rerank_shadow_result(
        query="以后查资料怎么处理",
        baseline_items=[
            {
                "id": "m1",
                "memory_type": "event",
                "summary": "用户昨天讨论了资料检索",
                "score": 0.88,
                "scope_channel": "cli",
                "scope_chat_id": "local",
                "source_ref": "cli:local:1",
            },
            {
                "id": "m2",
                "memory_type": "procedure",
                "summary": "查资料时优先交叉验证多个来源",
                "score": 0.72,
                "scope_channel": "cli",
                "scope_chat_id": "local",
                "source_ref": "cli:local:2",
                "extra_json": {"tool_requirement": "web"},
            },
        ],
        semantic_items=[{"id": "m1", "score": 0.88}, {"id": "m2", "score": 0.72}],
        keyword_items=[],
        provenance_items=[{"id": "m2", "provenance_score": 0.85}],
        graph_items=[],
        scope_channel="cli",
        scope_chat_id="local",
        top_n=2,
    )

    assert result.baseline_result["baseline_ids"] == ["m1", "m2"]
    assert result.experimental_result["reranked_ids"][0] == "m2"
    assert result.metrics["rerank_changed_count"] == 2
    first = result.experimental_result["ranked_items"][0]
    assert first["id"] == "m2"
    assert first["score_breakdown"]["type_weight"] > 0
    assert first["score_breakdown"]["source_ref_weight"] > 0
    assert first["rank_delta"] < 0


def test_build_rerank_shadow_result_penalizes_low_confidence_and_long_items() -> None:
    result = build_rerank_shadow_result(
        query="项目偏好",
        baseline_items=[
            {
                "id": "long",
                "memory_type": "profile",
                "summary": "x" * 900,
                "score": 0.51,
                "scope_channel": "cli",
                "scope_chat_id": "local",
            },
            {
                "id": "short",
                "memory_type": "preference",
                "summary": "用户希望回答尽量使用中文",
                "score": 0.7,
                "scope_channel": "cli",
                "scope_chat_id": "local",
                "source_ref": "cli:local:3",
            },
        ],
        semantic_items=[],
        keyword_items=[],
        provenance_items=[],
        graph_items=[],
        scope_channel="cli",
        scope_chat_id="local",
        top_n=2,
    )

    assert result.experimental_result["reranked_ids"] == ["short", "long"]
    long_item = next(
        item for item in result.experimental_result["ranked_items"] if item["id"] == "long"
    )
    assert long_item["score_breakdown"]["low_confidence_penalty"] < 0
    assert long_item["score_breakdown"]["length_penalty"] < 0
    assert result.metrics["baseline_experimental_overlap_rate"] == 1.0
