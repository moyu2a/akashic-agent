from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import networkx as nx

from memory2.retrieval_experiments import RetrievalLaneResult, rrf_fuse_lanes


@dataclass(frozen=True)
class GraphRetrievalShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


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
_STOP_TERMS = {
    "完全",
    "问题",
    "无关",
    "相关",
    "其他",
    "那个",
    "这个",
    "the",
    "and",
    "for",
    "with",
}


def _hit_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "").strip()


def _ids(items: list[dict[str, object]]) -> list[str]:
    return [item_id for item in items if (item_id := _hit_id(item))]


def _terms(text: object) -> set[str]:
    raw = str(text or "").lower()
    ascii_terms = set(re.findall(r"[a-z0-9_]+", raw))
    cjk_terms = {raw[idx : idx + 2] for idx in range(max(0, len(raw) - 1))}
    terms = {term.strip() for term in ascii_terms | cjk_terms if term.strip()}
    return {term for term in terms if term not in _STOP_TERMS and len(term) >= 2}


def _active_topics(item: dict[str, object]) -> list[str]:
    extra = item.get("extra_json")
    if not isinstance(extra, dict):
        return []
    topics = extra.get("active_topics")
    if not isinstance(topics, list):
        return []
    return [str(topic) for topic in topics if str(topic).strip()]


def _contains_fuzzy_reference(query: str) -> bool:
    text = str(query or "").lower()
    return any(marker in text for marker in _FUZZY_REFERENCE_MARKERS)


def build_entity_graph(
    active_items: list[dict[str, object]],
    *,
    scope_channel: str = "",
    scope_chat_id: str = "",
    max_nodes: int = 400,
) -> nx.Graph:
    graph = nx.Graph()
    safe_max_nodes = max(1, int(max_nodes))
    scope_node = ""
    if scope_channel or scope_chat_id:
        scope_node = f"scope:{scope_channel}:{scope_chat_id}"
        graph.add_node(scope_node, kind="scope")

    for index, item in enumerate(active_items):
        item_id = _hit_id(item)
        if not item_id:
            continue
        if graph.number_of_nodes() >= safe_max_nodes:
            break
        item_node = f"item:{item_id}"
        graph.add_node(item_node, kind="item", item_id=item_id, item=dict(item))
        if scope_node:
            graph.add_edge(scope_node, item_node, relation="scope", weight=0.2)

        raw_parts = [
            str(item.get("summary") or ""),
            str(item.get("source_ref") or ""),
            *_active_topics(item),
        ]
        terms = sorted({term for part in raw_parts for term in _terms(part)})
        for term in terms:
            if graph.number_of_nodes() >= safe_max_nodes:
                break
            entity_node = f"entity:{term}"
            graph.add_node(entity_node, kind="entity", term=term)
            graph.add_edge(
                item_node,
                entity_node,
                relation="mentions",
                weight=max(0.1, 1.0 - index * 0.001),
            )
    return graph


def build_graph_lane(
    query: str,
    active_items: list[dict[str, object]],
    *,
    scope_channel: str = "",
    scope_chat_id: str = "",
    limit: int = 20,
    max_hops: int = 2,
    max_nodes: int = 400,
) -> RetrievalLaneResult:
    graph = build_entity_graph(
        active_items,
        scope_channel=scope_channel,
        scope_chat_id=scope_chat_id,
        max_nodes=max_nodes,
    )
    query_terms = _terms(query)
    if not query_terms:
        return RetrievalLaneResult(lane_name="graph", items=[])

    query_node = "query:current"
    graph.add_node(query_node, kind="query")
    matched_query_terms = 0
    for term in query_terms:
        entity_node = f"entity:{term}"
        if graph.has_node(entity_node):
            graph.add_edge(query_node, entity_node, relation="query", weight=1.0)
            matched_query_terms += 1
    if matched_query_terms == 0:
        return RetrievalLaneResult(lane_name="graph", items=[])

    fuzzy = _contains_fuzzy_reference(query)
    safe_max_hops = max(1, int(max_hops))
    scored: list[tuple[float, float, str, dict[str, object]]] = []
    for node, data in graph.nodes(data=True):
        if data.get("kind") != "item":
            continue
        try:
            path_length = float(nx.shortest_path_length(graph, query_node, node))
        except nx.NetworkXNoPath, nx.NodeNotFound:
            continue
        if path_length > safe_max_hops:
            continue

        item_terms = {
            str(graph.nodes[neighbor].get("term") or "")
            for neighbor in graph.neighbors(node)
            if graph.nodes[neighbor].get("kind") == "entity"
        }
        entity_match_count = len(query_terms & item_terms)
        if entity_match_count <= 0:
            continue
        if not fuzzy and entity_match_count < 2:
            continue

        item = dict(data.get("item") or {})
        scope_match = (
            bool(scope_channel or scope_chat_id)
            and str(item.get("scope_channel") or "") == str(scope_channel or "")
            and str(item.get("scope_chat_id") or "") == str(scope_chat_id or "")
        )
        overlap_score = entity_match_count / max(1, len(query_terms))
        distance_score = max(
            0.0, (safe_max_hops + 1 - path_length) / (safe_max_hops + 1)
        )
        score = min(
            1.0, overlap_score + distance_score * 0.4 + (0.15 if scope_match else 0.0)
        )
        item["graph_score"] = round(score, 4)
        item["graph_path_length"] = path_length
        item["entity_match_count"] = entity_match_count
        item["graph_path_count"] = entity_match_count
        scored.append((score, path_length, str(data.get("item_id") or ""), item))

    scored.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
    safe_limit = max(1, int(limit))
    return RetrievalLaneResult(
        lane_name="graph",
        items=[item for _, _, _, item in scored[:safe_limit]],
    )


def build_graph_retrieval_shadow_result(
    *,
    query: str,
    baseline_items: list[dict[str, object]],
    semantic_items: list[dict[str, object]],
    keyword_items: list[dict[str, object]],
    provenance_items: list[dict[str, object]],
    graph_items: list[dict[str, object]],
    latency_ms: float,
    top_n: int,
) -> GraphRetrievalShadowResult:
    sorted_semantic_items = sorted(semantic_items, key=_item_score, reverse=True)
    baseline_lanes = [
        RetrievalLaneResult("semantic", sorted_semantic_items),
        RetrievalLaneResult("keyword", keyword_items),
        RetrievalLaneResult("provenance", provenance_items),
    ]
    graph_lanes = [
        *baseline_lanes,
        RetrievalLaneResult("graph", graph_items),
    ]
    safe_top_n = max(1, int(top_n))
    baseline_fused = rrf_fuse_lanes(baseline_lanes, top_n=safe_top_n)
    graph_fused = rrf_fuse_lanes(graph_lanes, top_n=safe_top_n)
    baseline_ids = _ids(baseline_items)
    baseline_fused_ids = _ids(baseline_fused)
    graph_fused_ids = _ids(graph_fused)
    lane_contribution = {
        lane.lane_name: len({_hit_id(item) for item in lane.items if _hit_id(item)})
        for lane in graph_lanes
    }
    return GraphRetrievalShadowResult(
        baseline_result={
            "query": query,
            "baseline_hit_count": len(baseline_items),
            "baseline_ids": baseline_ids,
            "baseline_fused_ids": baseline_fused_ids,
        },
        experimental_result={
            "semantic_hit_count": len(semantic_items),
            "keyword_hit_count": len(keyword_items),
            "provenance_hit_count": len(provenance_items),
            "graph_hit_count": len(graph_items),
            "semantic_ids": _ids(sorted_semantic_items),
            "keyword_ids": _ids(keyword_items),
            "provenance_ids": _ids(provenance_items),
            "graph_ids": _ids(graph_items),
            "graph_fused_hit_count": len(graph_fused),
            "graph_fused_ids": graph_fused_ids,
            "graph_fused_items": graph_fused,
        },
        metrics={
            "lane_contribution": lane_contribution,
            "graph_lane_contribution": lane_contribution,
            "graph_path_count": _graph_path_count(graph_items),
            "avg_graph_path_length": _avg_graph_path_length(graph_items),
            "entity_match_count": sum(
                int(item.get("entity_match_count") or 0) for item in graph_items
            ),
            "graph_score_distribution": [
                round(float(item.get("graph_score") or 0.0), 4) for item in graph_items
            ],
            "retrieval_latency_ms": round(float(latency_ms), 4),
            "rerank_changed_count": _rerank_changed_count(
                baseline_fused_ids, graph_fused_ids
            ),
            "baseline_graph_overlap_rate": _overlap_rate(
                baseline_fused_ids, graph_fused_ids
            ),
        },
    )


def _item_score(item: dict[str, object]) -> float:
    for key in (
        "score",
        "rrf_score",
        "keyword_score",
        "provenance_score",
        "graph_score",
    ):
        if key not in item:
            continue
        try:
            return float(item.get(key) or 0.0)
        except TypeError, ValueError:
            continue
    return 0.0


def _graph_path_count(items: list[dict[str, object]]) -> int:
    total = 0
    for item in items:
        if "graph_path_count" in item:
            total += int(item.get("graph_path_count") or 0)
        elif "graph_path_length" in item:
            total += 1
    return total


def _avg_graph_path_length(items: list[dict[str, object]]) -> float:
    lengths: list[float] = []
    for item in items:
        try:
            lengths.append(float(item.get("graph_path_length") or 0.0))
        except TypeError, ValueError:
            continue
    if not lengths:
        return 0.0
    return round(sum(lengths) / len(lengths), 4)


def _rerank_changed_count(
    baseline_ids: list[str],
    fused_ids: list[str],
) -> int:
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
