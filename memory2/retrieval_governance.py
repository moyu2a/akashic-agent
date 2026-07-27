"""召回治理纯函数：场景识别、lane 门控和可观测路由 trace。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import re
from typing import Any


_LANES = ("semantic", "keyword", "provenance", "graph")
_LOW_CONFIDENCE_PHRASES = (
    "未在对话中明确记录",
    "无法凭记忆确认",
    "没有记录",
    "未找到",
    "不确定",
)


@dataclass(frozen=True)
class RetrievalRoutingDecision:
    """某个查询可使用的召回通道及其治理约束。"""

    scene: str
    allowed_lanes: tuple[str, ...]
    max_per_lane: dict[str, int]
    require_source_ref: bool
    require_scope_match: bool
    graph_enabled: bool
    drop_low_confidence: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["allowed_lanes"] = list(self.allowed_lanes)
        return result


def classify_retrieval_scene(query: str) -> str:
    text = _normalize_query(query)
    if _contains_any(text, ("来源", "出处", "source", "哪条消息", "消息记录")):
        return "source_lookup"
    if _contains_any(text, ("冲突", "矛盾", "不一致", "到底哪个", "前后", "改口")):
        return "partial_conflict"
    is_preference = _contains_any(text, ("优先", "偏好", "默认", "习惯", "prefer"))
    is_tool_related = _contains_any(text, ("工具", "tool", "技能", "skill", "命令"))
    if is_preference and is_tool_related:
        return "tool_preference"
    if _contains_any(text, ("上次", "刚才", "之前那个", "那个方案", "提到的", "还记得")):
        return "fuzzy_reference"
    if _contains_any(text, ("精确", "具体", "准确", "exact", "找一下", "查找", "查询")):
        return "exact_recall"
    return "unknown"


def build_retrieval_routing_decision(query: str) -> RetrievalRoutingDecision:
    scene = classify_retrieval_scene(query)
    policy = _SCENE_POLICIES[scene]
    return RetrievalRoutingDecision(scene=scene, **policy)


def apply_retrieval_route(
    decision: RetrievalRoutingDecision,
    candidates_by_lane: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, object]]:
    lane_order = list(decision.allowed_lanes)
    dropped_by_reason: dict[str, int] = {}
    accepted_by_lane = {lane: 0 for lane in lane_order}
    accepted: list[dict[str, Any]] = []
    accepted_items_by_lane: dict[str, list[dict[str, Any]]] = {
        lane: [] for lane in lane_order
    }
    seen: set[str] = set()

    for lane, lane_candidates in candidates_by_lane.items():
        if lane not in decision.allowed_lanes or (
            lane == "graph" and not decision.graph_enabled
        ):
            _count(dropped_by_reason, "lane_not_allowed", len(lane_candidates))

    for lane in lane_order:
        lane_candidates = candidates_by_lane.get(lane, ())
        cap = decision.max_per_lane.get(lane, 0)
        retained_in_lane = 0
        for candidate in lane_candidates:
            if retained_in_lane >= cap:
                _count(dropped_by_reason, "lane_cap")
                continue
            item = dict(candidate)
            if decision.require_source_ref and not _has_source_ref(item):
                _count(dropped_by_reason, "missing_source_ref")
                continue
            if decision.require_scope_match and item.get("scope_match") is False:
                _count(dropped_by_reason, "scope_mismatch")
                continue
            if decision.drop_low_confidence and _is_low_confidence(item):
                _count(dropped_by_reason, "low_confidence")
                continue

            dedupe_key = _candidate_key(item)
            if dedupe_key in seen:
                _count(dropped_by_reason, "duplicate")
                continue
            seen.add(dedupe_key)
            accepted.append(item)
            accepted_items_by_lane[lane].append(item)
            accepted_by_lane[lane] += 1
            retained_in_lane += 1

    input_count = sum(len(candidates_by_lane.get(lane, ())) for lane in _LANES)
    output_count = len(accepted)
    trace: dict[str, object] = {
        "scene": decision.scene,
        "reason": decision.reason,
        "route_decision": decision.to_dict(),
        "allowed_lanes": lane_order,
        "lane_order": lane_order,
        "max_per_lane": dict(decision.max_per_lane),
        "require_source_ref": decision.require_source_ref,
        "require_scope_match": decision.require_scope_match,
        "graph_enabled": decision.graph_enabled,
        "drop_low_confidence": decision.drop_low_confidence,
        "input_counts": {
            lane: len(candidates_by_lane.get(lane, ())) for lane in _LANES
        },
        "accepted_by_lane": accepted_by_lane,
        "accepted_items_by_lane": accepted_items_by_lane,
        "dropped_by_reason": dropped_by_reason,
        "output_count": output_count,
        "route_hit_rate": round(output_count / input_count, 4) if input_count else 0.0,
    }
    return accepted, trace


_SCENE_POLICIES: dict[str, dict[str, object]] = {
    "fuzzy_reference": {
        "allowed_lanes": ("semantic", "keyword", "provenance", "graph"),
        "max_per_lane": {"semantic": 4, "keyword": 3, "provenance": 2, "graph": 2},
        "require_source_ref": False,
        "require_scope_match": False,
        "graph_enabled": True,
        "drop_low_confidence": True,
        "reason": "模糊指代需要语义扩展，允许少量图谱邻接候选补全上下文。",
    },
    "tool_preference": {
        "allowed_lanes": ("semantic", "keyword"),
        "max_per_lane": {"semantic": 4, "keyword": 4},
        "require_source_ref": False,
        "require_scope_match": False,
        "graph_enabled": False,
        "drop_low_confidence": True,
        "reason": "工具偏好以规则语义和字面工具名为主，避免引入图谱或来源噪声。",
    },
    "partial_conflict": {
        "allowed_lanes": ("provenance", "semantic", "keyword"),
        "max_per_lane": {"provenance": 4, "semantic": 3, "keyword": 2},
        "require_source_ref": True,
        "require_scope_match": True,
        "graph_enabled": False,
        "drop_low_confidence": True,
        "reason": "冲突判断优先保留同作用域、可追溯的来源证据。",
    },
    "exact_recall": {
        "allowed_lanes": ("keyword", "semantic"),
        "max_per_lane": {"keyword": 5, "semantic": 3},
        "require_source_ref": False,
        "require_scope_match": False,
        "graph_enabled": False,
        "drop_low_confidence": True,
        "reason": "精确检索优先字面命中，再以少量语义候选补充。",
    },
    "source_lookup": {
        "allowed_lanes": ("provenance", "keyword", "semantic"),
        "max_per_lane": {"provenance": 5, "keyword": 3, "semantic": 2},
        "require_source_ref": True,
        "require_scope_match": True,
        "graph_enabled": False,
        "drop_low_confidence": True,
        "reason": "来源查询必须可追溯，先返回同作用域的 provenance 证据。",
    },
    "unknown": {
        "allowed_lanes": ("semantic", "keyword"),
        "max_per_lane": {"semantic": 4, "keyword": 3},
        "require_source_ref": False,
        "require_scope_match": False,
        "graph_enabled": False,
        "drop_low_confidence": True,
        "reason": "未识别场景采用保守的语义和关键词双 lane。",
    },
}


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", "", query.lower())


def _contains_any(text: str, phrases: Sequence[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_source_ref(item: Mapping[str, Any]) -> bool:
    return bool(item.get("source_ref"))


def _is_low_confidence(item: Mapping[str, Any]) -> bool:
    if item.get("low_confidence") is True:
        return True
    confidence = item.get("confidence")
    if isinstance(confidence, int | float) and confidence < 0.5:
        return True
    summary = item.get("summary") or item.get("content") or ""
    return isinstance(summary, str) and _contains_any(summary, _LOW_CONFIDENCE_PHRASES)


def _candidate_key(item: Mapping[str, Any]) -> str:
    for field in ("id", "memory_id"):
        value = item.get(field)
        if value not in (None, ""):
            return f"{field}:{value}"
    source_ref = item.get("source_ref")
    if source_ref:
        return f"source_ref:{source_ref}"
    summary = item.get("summary") or item.get("content")
    if summary:
        return f"text:{summary}"
    return f"object:{repr(sorted(item.items()))}"


def _count(counts: dict[str, int], reason: str, amount: int = 1) -> None:
    counts[reason] = counts.get(reason, 0) + amount
