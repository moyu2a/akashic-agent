from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memory2.retrieval_experiments import RetrievalLaneResult, rrf_fuse_lanes


@dataclass(frozen=True)
class RerankShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_rerank_shadow_result(
    *,
    query: str,
    baseline_items: list[dict[str, object]],
    semantic_items: list[dict[str, object]],
    keyword_items: list[dict[str, object]],
    provenance_items: list[dict[str, object]],
    graph_items: list[dict[str, object]] | None = None,
    scope_channel: str = "",
    scope_chat_id: str = "",
    top_n: int = 8,
) -> RerankShadowResult:
    safe_top_n = max(1, int(top_n))
    candidate_pool = _candidate_pool(
        baseline_items=baseline_items,
        semantic_items=semantic_items,
        keyword_items=keyword_items,
        provenance_items=provenance_items,
        graph_items=graph_items or [],
        top_n=max(safe_top_n, len(baseline_items), 1),
    )
    baseline_ids = _ids(baseline_items)
    baseline_pos = {item_id: index for index, item_id in enumerate(baseline_ids)}
    ranked: list[tuple[float, str, int, dict[str, object], dict[str, float]]] = []
    for index, item in enumerate(candidate_pool):
        item_id = _hit_id(item)
        if not item_id:
            continue
        breakdown = _score_breakdown(
            item,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
        )
        final_score = round(sum(breakdown.values()), 6)
        raw_rank = baseline_pos.get(item_id, index) + 1
        ranked.append((final_score, item_id, raw_rank, dict(item), breakdown))

    ranked.sort(key=lambda entry: (entry[0], _item_score(entry[3]), entry[1]), reverse=True)
    ranked_items: list[dict[str, object]] = []
    for experimental_index, (final_score, item_id, raw_rank, item, breakdown) in enumerate(
        ranked[:safe_top_n],
        start=1,
    ):
        item["experimental_score"] = final_score
        item["raw_rank"] = raw_rank
        item["experimental_rank"] = experimental_index
        item["rank_delta"] = experimental_index - raw_rank
        item["score_breakdown"] = breakdown
        ranked_items.append(item)

    reranked_ids = _ids(ranked_items)
    return RerankShadowResult(
        baseline_result={
            "query": query,
            "baseline_hit_count": len(baseline_items),
            "baseline_ids": baseline_ids,
        },
        experimental_result={
            "candidate_count": len(candidate_pool),
            "reranked_hit_count": len(ranked_items),
            "reranked_ids": reranked_ids,
            "ranked_items": ranked_items,
        },
        metrics={
            "rerank_changed_count": _rerank_changed_count(baseline_ids, reranked_ids),
            "baseline_experimental_overlap_rate": _overlap_rate(
                baseline_ids,
                reranked_ids,
            ),
            "avg_experimental_score": _avg(
                [float(item.get("experimental_score") or 0.0) for item in ranked_items]
            ),
            "scope_match_count": sum(
                1
                for item in ranked_items
                if item.get("scope_channel") == scope_channel
                and item.get("scope_chat_id") == scope_chat_id
            ),
            "source_ref_count": sum(
                1 for item in ranked_items if str(item.get("source_ref") or "").strip()
            ),
        },
    )


def _candidate_pool(
    *,
    baseline_items: list[dict[str, object]],
    semantic_items: list[dict[str, object]],
    keyword_items: list[dict[str, object]],
    provenance_items: list[dict[str, object]],
    graph_items: list[dict[str, object]],
    top_n: int,
) -> list[dict[str, object]]:
    lanes = [
        RetrievalLaneResult("baseline", baseline_items),
        RetrievalLaneResult("semantic", sorted(semantic_items, key=_item_score, reverse=True)),
        RetrievalLaneResult("keyword", keyword_items),
        RetrievalLaneResult("provenance", provenance_items),
    ]
    if graph_items:
        lanes.append(RetrievalLaneResult("graph", graph_items))
    all_items = [
        *baseline_items,
        *semantic_items,
        *keyword_items,
        *provenance_items,
        *graph_items,
    ]
    unique_item_count = len({item_id for item in all_items if (item_id := _hit_id(item))})
    fused = rrf_fuse_lanes(
        lanes,
        top_n=max(1, int(top_n), unique_item_count),
    )
    by_id: dict[str, dict[str, object]] = {}
    for source_item in all_items:
        item_id = _hit_id(source_item)
        if not item_id:
            continue
        merged = dict(by_id.get(item_id, {}))
        merged.update(source_item)
        by_id[item_id] = merged
    for item in fused:
        item_id = _hit_id(item)
        if not item_id:
            continue
        merged = dict(by_id.get(item_id, {}))
        merged.update(item)
        by_id[item_id] = merged
    return [by_id[item_id] for item_id in _ids(fused) if item_id in by_id]


def _score_breakdown(
    item: dict[str, object],
    *,
    scope_channel: str,
    scope_chat_id: str,
) -> dict[str, float]:
    memory_type = str(item.get("memory_type") or "")
    summary = str(item.get("summary") or "")
    score = _item_score(item)
    type_weights = {
        "procedure": 0.18,
        "preference": 0.14,
        "profile": 0.08,
        "event": 0.04,
    }
    scope_match = (
        bool(scope_channel or scope_chat_id)
        and str(item.get("scope_channel") or "") == str(scope_channel or "")
        and str(item.get("scope_chat_id") or "") == str(scope_chat_id or "")
    )
    return {
        "base_score": round(score, 6),
        "rrf_weight": round(float(item.get("rrf_score") or 0.0), 6),
        "scope_weight": 0.15 if scope_match else 0.0,
        "type_weight": type_weights.get(memory_type, 0.0),
        "source_ref_weight": 0.08 if str(item.get("source_ref") or "").strip() else 0.0,
        "provenance_weight": round(
            min(0.08, float(item.get("provenance_score") or 0.0) * 0.08), 6
        ),
        "graph_weight": round(min(0.1, float(item.get("graph_score") or 0.0) * 0.1), 6),
        "low_confidence_penalty": -0.08 if score and score < 0.6 else 0.0,
        "length_penalty": -0.06 if len(summary) > 600 else 0.0,
        "missing_source_penalty": -0.04
        if not str(item.get("source_ref") or "").strip()
        else 0.0,
    }


def _hit_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "").strip()


def _ids(items: list[dict[str, object]]) -> list[str]:
    result: list[str] = []
    for item in items:
        item_id = _hit_id(item)
        if item_id:
            result.append(item_id)
    return result


def _item_score(item: dict[str, object]) -> float:
    for key in ("score", "rrf_score", "keyword_score", "provenance_score", "graph_score"):
        if key not in item:
            continue
        try:
            return float(item.get(key) or 0.0)
        except (TypeError, ValueError):
            continue
    return 0.0


def _rerank_changed_count(baseline_ids: list[str], fused_ids: list[str]) -> int:
    baseline_pos = {item_id: index for index, item_id in enumerate(baseline_ids)}
    fused_pos = {item_id: index for index, item_id in enumerate(fused_ids)}
    all_ids = set(baseline_ids) | set(fused_ids)
    return sum(
        1 for item_id in all_ids if baseline_pos.get(item_id) != fused_pos.get(item_id)
    )


def _overlap_rate(left_ids: list[str], right_ids: list[str]) -> float:
    if not left_ids and not right_ids:
        return 1.0
    denominator = max(1, len(set(left_ids) | set(right_ids)))
    return round(len(set(left_ids) & set(right_ids)) / denominator, 4)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)
