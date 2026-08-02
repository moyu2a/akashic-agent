"""召回治理纯函数：场景识别、lane 门控和可观测路由 trace。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
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
_DELETE_RISKS = ("forbidden_candidate", "superseded_candidate", "scope_mismatch")
_DOWNGRADE_RISKS = ("weak_source_ref", "low_confidence")
_REQUIRES_REVIEW_RISKS = (
    "conflict_candidate",
    "missing_source_ref",
    "insufficient_evidence",
)


@dataclass(frozen=True)
class CandidateGovernancePolicy:
    """可选候选治理策略；默认关闭以保持旧路由行为。"""

    enabled: bool = False
    mode: str = "strict"
    protected_expected_ids: tuple[str, ...] = ()
    drop_risks: tuple[str, ...] = (
        "forbidden_candidate",
        "superseded_candidate",
        "conflict_candidate",
        "scope_mismatch",
        "missing_source_ref",
        "weak_source_ref",
        "low_confidence",
    )
    fatal_risks: tuple[str, ...] = (
        "forbidden_candidate",
        "superseded_candidate",
        "conflict_candidate",
        "scope_mismatch",
    )

    def __post_init__(self) -> None:
        if self.mode not in {"strict", "tiered"}:
            raise ValueError(f"unknown candidate governance mode: {self.mode}")

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "protected_expected_ids": list(self.protected_expected_ids),
            "drop_risks": list(self.drop_risks),
            "fatal_risks": list(self.fatal_risks),
        }


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
    candidate_governance: CandidateGovernancePolicy = field(
        default_factory=CandidateGovernancePolicy
    )

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["allowed_lanes"] = list(self.allowed_lanes)
        result["candidate_governance"] = self.candidate_governance.to_dict()
        return result

    def with_candidate_governance(
        self,
        policy: CandidateGovernancePolicy,
    ) -> "RetrievalRoutingDecision":
        return RetrievalRoutingDecision(
            scene=self.scene,
            allowed_lanes=self.allowed_lanes,
            max_per_lane=dict(self.max_per_lane),
            require_source_ref=self.require_source_ref,
            require_scope_match=self.require_scope_match,
            graph_enabled=self.graph_enabled,
            drop_low_confidence=self.drop_low_confidence,
            reason=self.reason,
            candidate_governance=policy,
        )


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
    if _contains_any(
        text,
        (
            "上次",
            "刚才",
            "之前那个",
            "那个方案",
            "那个图谱",
            "图谱路由",
            "图谱关联",
            "提到的",
            "还记得",
        ),
    ):
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
    dropped_risks_by_reason: dict[str, int] = {}
    would_drop_protected_by_reason: dict[str, int] = {}
    candidate_risk_tier_counts: dict[str, int] = {}
    accepted_candidate_risk_tier_counts: dict[str, int] = {}
    tiered_deleted_risks_by_reason: dict[str, int] = {}
    candidate_risk_tiers: list[dict[str, object]] = []
    protected_risky_candidate_count = 0
    accepted_risky_candidate_count = 0
    protected_expected_ids = set(decision.candidate_governance.protected_expected_ids)

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
            risks = classify_candidate_risks(item)
            protected = _candidate_id(item) in protected_expected_ids

            if decision.candidate_governance.enabled:
                mode = decision.candidate_governance.mode
                if mode == "tiered":
                    tier_record = dict(classify_candidate_risk_tier(item))
                    tier_record["lane"] = lane
                    candidate_risk_tiers.append(tier_record)
                    tier = str(tier_record["tier"])
                    _count(candidate_risk_tier_counts, tier)
                    risks = tuple(str(risk) for risk in tier_record["risks"])
                    if tier == "delete":
                        for risk in risks:
                            if risk in _DELETE_RISKS:
                                _count(tiered_deleted_risks_by_reason, risk)
                                _count(dropped_risks_by_reason, risk)
                        continue
                    item["candidate_risk_tier"] = tier
                    item["candidate_governance_action"] = tier
                    item["candidate_risks"] = risks
                elif mode == "strict":
                    drop_risks = [
                        risk
                        for risk in risks
                        if risk in decision.candidate_governance.drop_risks
                    ]
                    fatal = any(
                        risk in decision.candidate_governance.fatal_risks
                        for risk in drop_risks
                    )
                    if drop_risks and (fatal or not protected):
                        for risk in drop_risks:
                            _count(dropped_risks_by_reason, risk)
                        continue
                    if drop_risks and protected:
                        protected_risky_candidate_count += 1
                        for risk in drop_risks:
                            _count(would_drop_protected_by_reason, risk)
                else:
                    raise ValueError(f"unknown candidate governance mode: {mode}")
            else:
                if decision.require_source_ref and "missing_source_ref" in risks:
                    _count(dropped_by_reason, "missing_source_ref")
                    continue
                if decision.require_scope_match and "scope_mismatch" in risks:
                    _count(dropped_by_reason, "scope_mismatch")
                    continue
                if decision.drop_low_confidence and "low_confidence" in risks:
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
            if (
                decision.candidate_governance.enabled
                and decision.candidate_governance.mode == "tiered"
            ):
                _count(
                    accepted_candidate_risk_tier_counts,
                    str(item.get("candidate_risk_tier") or "allow"),
                )
            if risks:
                accepted_risky_candidate_count += 1

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
        "candidate_governance_enabled": decision.candidate_governance.enabled,
        "candidate_governance_mode": decision.candidate_governance.mode,
        "candidate_governance": decision.candidate_governance.to_dict(),
        "protected_expected_ids": list(
            decision.candidate_governance.protected_expected_ids
        ),
        "dropped_risks_by_reason": dropped_risks_by_reason,
        "would_drop_protected_by_reason": would_drop_protected_by_reason,
        "candidate_risk_tier_counts": candidate_risk_tier_counts,
        "accepted_candidate_risk_tier_counts": accepted_candidate_risk_tier_counts,
        "tiered_deleted_risks_by_reason": tiered_deleted_risks_by_reason,
        "candidate_risk_tiers": candidate_risk_tiers,
        "protected_risky_candidate_count": protected_risky_candidate_count,
        "accepted_risky_candidate_count": accepted_risky_candidate_count,
        "output_count": output_count,
        "route_hit_rate": round(output_count / input_count, 4) if input_count else 0.0,
    }
    return accepted, trace


def classify_candidate_risks(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    risks: list[str] = []
    if _is_forbidden_candidate(candidate):
        risks.append("forbidden_candidate")
    if str(candidate.get("status") or "").lower() == "superseded":
        risks.append("superseded_candidate")
    if _is_conflict_candidate(candidate):
        risks.append("conflict_candidate")
    if candidate.get("scope_match") is False:
        risks.append("scope_mismatch")
    if not _has_source_ref(candidate):
        risks.append("missing_source_ref")
    elif _has_weak_source_ref(candidate):
        risks.append("weak_source_ref")
    if _is_low_confidence(candidate):
        risks.append("low_confidence")
    if _is_insufficient_evidence(candidate):
        risks.append("insufficient_evidence")
    return tuple(risks)


def classify_candidate_risk_tier(candidate: Mapping[str, Any]) -> dict[str, object]:
    risks = classify_candidate_risks(candidate)
    if any(risk in _DELETE_RISKS for risk in risks):
        tier = "delete"
    elif any(risk in _REQUIRES_REVIEW_RISKS for risk in risks):
        tier = "requires_review"
    elif any(risk in _DOWNGRADE_RISKS for risk in risks):
        tier = "downgrade"
    else:
        tier = "allow"
    return {
        "candidate_id": _candidate_id(candidate),
        "tier": tier,
        "action": tier,
        "risks": risks,
    }


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


def _is_forbidden_candidate(item: Mapping[str, Any]) -> bool:
    if item.get("forbidden") is True or item.get("forbidden_candidate") is True:
        return True
    if item.get("should_not_recall") is True:
        return True
    risk = item.get("risk")
    if isinstance(risk, str) and risk.lower() in {"forbidden", "blocked", "deny"}:
        return True
    tags = item.get("tags")
    if isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)):
        if any(str(tag).lower() in {"forbidden", "blocked", "deny"} for tag in tags):
            return True
    extra = item.get("extra_json")
    if isinstance(extra, Mapping):
        topics = extra.get("active_topics")
        if isinstance(topics, Sequence) and not isinstance(topics, (str, bytes)):
            return any(str(topic) in {"助手推断"} for topic in topics)
    return False


def _is_conflict_candidate(item: Mapping[str, Any]) -> bool:
    if item.get("conflict") is True or item.get("conflict_candidate") is True:
        return True
    relation = str(item.get("relation_type") or "").lower()
    if relation in {"conflicts", "conflict", "contradicts"}:
        return True
    if item.get("conflict_with") or item.get("conflict_ids"):
        return True
    risk = item.get("risk")
    if isinstance(risk, str) and risk.lower() in {"conflict", "conflicts"}:
        return True
    tags = item.get("tags")
    return isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)) and any(
        str(tag).lower() in {"conflict", "conflicts", "contradicts"}
        for tag in tags
    )


def _has_weak_source_ref(item: Mapping[str, Any]) -> bool:
    source_ref = str(item.get("source_ref") or "")
    if not source_ref:
        return False
    if source_ref.endswith("@post_response"):
        return True
    if source_ref.startswith("session:"):
        return True
    confidence = item.get("source_ref_confidence")
    if isinstance(confidence, int | float) and confidence < 0.6:
        return True
    return item.get("source_ref_confident") is False


def _is_low_confidence(item: Mapping[str, Any]) -> bool:
    if item.get("low_confidence") is True:
        return True
    confidence = item.get("confidence")
    if isinstance(confidence, int | float) and confidence < 0.5:
        return True
    summary = item.get("summary") or item.get("content") or ""
    return isinstance(summary, str) and _contains_any(summary, _LOW_CONFIDENCE_PHRASES)


def _is_insufficient_evidence(item: Mapping[str, Any]) -> bool:
    if item.get("insufficient_evidence") is True:
        return True
    risk = item.get("risk")
    if isinstance(risk, str) and risk.lower() in {
        "insufficient_evidence",
        "evidence_gap",
        "needs_evidence",
    }:
        return True
    tags = item.get("tags")
    return isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)) and any(
        str(tag).lower()
        in {"insufficient_evidence", "evidence_gap", "needs_evidence"}
        for tag in tags
    )


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


def _candidate_id(item: Mapping[str, Any]) -> str:
    for field in ("id", "memory_id"):
        value = item.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def _count(counts: dict[str, int], reason: str, amount: int = 1) -> None:
    counts[reason] = counts.get(reason, 0) + amount
