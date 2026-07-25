from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from memory2.retriever import _KEYWORD_RRF_WEIGHT


@dataclass(frozen=True)
class RetrievalLaneResult:
    lane_name: str
    items: list[dict[str, object]]


def _hit_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "").strip()


def _item_score(item: dict[str, object]) -> float:
    for key in ("score", "rrf_score", "keyword_score", "provenance_score"):
        if key not in item:
            continue
        try:
            return float(item.get(key) or 0.0)
        except (TypeError, ValueError):
            continue
    return 0.0


def rrf_fuse_lanes(
    lanes: list[RetrievalLaneResult],
    *,
    top_n: int,
    k: int = 60,
    weights: dict[str, float] | None = None,
) -> list[dict[str, object]]:
    safe_top_n = max(1, int(top_n))
    lane_weights = {"keyword": _KEYWORD_RRF_WEIGHT, **(weights or {})}
    id_to_item: dict[str, dict[str, object]] = {}
    id_to_lanes: dict[str, list[str]] = {}
    id_to_rrf: dict[str, float] = {}
    id_to_best_score: dict[str, float] = {}

    for lane in lanes:
        weight = float(lane_weights.get(lane.lane_name, 1.0))
        seen_in_lane: set[str] = set()
        for index, item in enumerate(lane.items):
            item_id = _hit_id(item)
            if not item_id or item_id in seen_in_lane:
                continue
            seen_in_lane.add(item_id)
            id_to_item.setdefault(item_id, dict(item))
            id_to_lanes.setdefault(item_id, []).append(lane.lane_name)
            id_to_rrf[item_id] = id_to_rrf.get(item_id, 0.0) + weight / (
                k + index + 1
            )
            id_to_best_score[item_id] = max(
                id_to_best_score.get(item_id, 0.0),
                _item_score(item),
            )

    ordered = sorted(
        id_to_rrf,
        key=lambda item_id: (
            id_to_rrf[item_id],
            len(id_to_lanes.get(item_id, [])),
            id_to_best_score.get(item_id, 0.0),
            item_id,
        ),
        reverse=True,
    )
    fused: list[dict[str, object]] = []
    for item_id in ordered[:safe_top_n]:
        item = dict(id_to_item[item_id])
        item["rrf_score"] = round(id_to_rrf[item_id], 6)
        item["lane_hits"] = id_to_lanes[item_id]
        fused.append(item)
    return fused


_FUZZY_REFERENCE_MARKERS = (
    "上次",
    "之前",
    "刚才",
    "那个",
    "前面",
    "以前",
    "last time",
    "previous",
    "that",
)


def _contains_fuzzy_reference(query: str) -> bool:
    text = str(query or "").lower()
    return any(marker in text for marker in _FUZZY_REFERENCE_MARKERS)


def _terms(text: str) -> set[str]:
    raw = str(text or "").lower()
    ascii_terms = set(re.findall(r"[a-z0-9_]+", raw))
    cjk_terms = {raw[idx : idx + 2] for idx in range(max(0, len(raw) - 1))}
    return {term for term in ascii_terms | cjk_terms if term.strip()}


def build_provenance_lane(
    query: str,
    active_items: list[dict[str, object]],
    *,
    scope_channel: str = "",
    scope_chat_id: str = "",
    limit: int = 20,
) -> RetrievalLaneResult:
    query_terms = _terms(query)
    fuzzy = _contains_fuzzy_reference(query)
    scored: list[tuple[float, str, dict[str, object]]] = []
    for index, item in enumerate(active_items):
        item_id = _hit_id(item)
        source_ref = str(item.get("source_ref") or "").strip()
        if not item_id or not source_ref:
            continue
        summary_terms = _terms(str(item.get("summary") or ""))
        overlap = len(query_terms & summary_terms)
        scope_match = (
            bool(scope_channel or scope_chat_id)
            and str(item.get("scope_channel") or "") == str(scope_channel or "")
            and str(item.get("scope_chat_id") or "") == str(scope_chat_id or "")
        )
        score = 0.0
        if overlap:
            score += min(1.0, overlap / max(1, len(query_terms)))
        if fuzzy:
            score += 0.35
        if scope_match:
            score += 0.25
        if not (overlap or fuzzy or scope_match):
            continue
        score += max(0.0, 0.1 - index * 0.001)
        if score <= 0.0:
            continue
        lane_item = dict(item)
        lane_item["provenance_score"] = round(score, 4)
        scored.append((score, item_id, lane_item))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return RetrievalLaneResult(
        lane_name="provenance",
        items=[item for _, _, item in scored[: max(1, int(limit))]],
    )


@dataclass(frozen=True)
class TriRetrievalShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def _ids(items: list[dict[str, object]]) -> list[str]:
    return [item_id for item in items if (item_id := _hit_id(item))]


def _rerank_changed_count(
    baseline_ids: list[str],
    fused_ids: list[str],
) -> int:
    baseline_pos = {item_id: index for index, item_id in enumerate(baseline_ids)}
    fused_pos = {item_id: index for index, item_id in enumerate(fused_ids)}
    all_ids = set(baseline_ids) | set(fused_ids)
    return sum(1 for item_id in all_ids if baseline_pos.get(item_id) != fused_pos.get(item_id))


def _overlap_rate(left_ids: list[str], right_ids: list[str]) -> float:
    if not left_ids and not right_ids:
        return 1.0
    denominator = max(1, len(set(left_ids) | set(right_ids)))
    return round(len(set(left_ids) & set(right_ids)) / denominator, 4)


def build_tri_retrieval_shadow_result(
    *,
    query: str,
    baseline_items: list[dict[str, object]],
    semantic_items: list[dict[str, object]],
    keyword_items: list[dict[str, object]],
    provenance_items: list[dict[str, object]],
    latency_ms: float,
    top_n: int,
) -> TriRetrievalShadowResult:
    sorted_semantic_items = sorted(semantic_items, key=_item_score, reverse=True)
    lanes = [
        RetrievalLaneResult("semantic", sorted_semantic_items),
        RetrievalLaneResult("keyword", keyword_items),
        RetrievalLaneResult("provenance", provenance_items),
    ]
    fused = rrf_fuse_lanes(lanes, top_n=top_n)
    baseline_ids = _ids(baseline_items)
    fused_ids = _ids(fused)
    lane_contribution = {
        lane.lane_name: len({_hit_id(item) for item in lane.items if _hit_id(item)})
        for lane in lanes
    }
    return TriRetrievalShadowResult(
        baseline_result={
            "query": query,
            "baseline_hit_count": len(baseline_items),
            "baseline_ids": baseline_ids,
        },
        experimental_result={
            "semantic_hit_count": len(semantic_items),
            "keyword_hit_count": len(keyword_items),
            "provenance_hit_count": len(provenance_items),
            "fused_hit_count": len(fused),
            "semantic_ids": _ids(sorted_semantic_items),
            "keyword_ids": _ids(keyword_items),
            "provenance_ids": _ids(provenance_items),
            "fused_ids": fused_ids,
            "fused_items": fused,
        },
        metrics={
            "lane_count": len(lanes),
            "lane_contribution": lane_contribution,
            "rerank_changed_count": _rerank_changed_count(baseline_ids, fused_ids),
            "baseline_experimental_overlap_rate": _overlap_rate(baseline_ids, fused_ids),
            "retrieval_latency_ms": round(float(latency_ms), 4),
            "rrf_score_distribution": [
                round(float(item.get("rrf_score") or 0.0), 6) for item in fused
            ],
            "source_ref_coverage": _source_ref_coverage(fused),
            "rrf_weights": {
                "semantic": 1.0,
                "keyword": _KEYWORD_RRF_WEIGHT,
                "provenance": 1.0,
            },
        },
    )


def _source_ref_coverage(items: list[dict[str, object]]) -> float:
    if not items:
        return 0.0
    with_source = sum(1 for item in items if str(item.get("source_ref") or "").strip())
    return round(with_source / len(items), 4)
