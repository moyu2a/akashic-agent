from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plugins.default_memory.config import MemoryExperimentsConfig


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MemoryExperimentTrace:
    run_id: str
    session_key: str
    turn_id: str
    feature_name: str
    mode: str
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    diff_json: dict[str, Any]
    metrics_json: dict[str, Any]
    created_at: str


class MemoryExperimentWriter:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, trace: MemoryExperimentTrace) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(trace), ensure_ascii=False, sort_keys=True))
            f.write("\n")


class MemoryExperimentRunner:
    def __init__(
        self,
        *,
        workspace: Path,
        config: MemoryExperimentsConfig,
        existing_memory_provider: Callable[[], list[dict[str, object]]] | None = None,
    ) -> None:
        self._workspace = workspace
        self._config = config
        self._existing_memory_provider = existing_memory_provider
        trace_path = Path(config.trace_path)
        if not trace_path.is_absolute():
            trace_path = workspace / trace_path
        self._writer = MemoryExperimentWriter(trace_path)

    @property
    def enabled(self) -> bool:
        return bool(self._config.enabled and self._config.mode != "off")

    def record(
        self,
        *,
        feature_name: str,
        session_key: str,
        turn_id: str,
        baseline_result: dict[str, Any],
        experimental_result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> MemoryExperimentTrace | None:
        if not self.enabled or not self._config.trace_enabled:
            return None
        trace = MemoryExperimentTrace(
            run_id=uuid.uuid4().hex,
            session_key=session_key,
            turn_id=turn_id,
            feature_name=feature_name,
            mode="shadow",
            baseline_result=baseline_result,
            experimental_result=experimental_result,
            diff_json=_diff_dicts(baseline_result, experimental_result),
            metrics_json=metrics,
            created_at=_now_iso(),
        )
        try:
            self._writer.write(trace)
        except Exception:
            return None
        return trace

    def record_write_value_shadow(
        self,
        *,
        session_key: str,
        turn_id: str,
        memorize_calls: list[dict[str, Any]],
    ) -> MemoryExperimentTrace | None:
        if not memorize_calls:
            return None
        baseline = extract_explicit_memorize_baseline(memorize_calls)
        summaries = [str(call.get("summary") or "") for call in memorize_calls]
        written_ids = set(
            str(item_id) for item_id in baseline.get("written_item_ids", [])
        )
        existing_memories = [
            item
            for item in self._existing_memory_snapshot()
            if str(item.get("id") or "") not in written_ids
        ]
        scored = [
            {
                "summary": summary,
                **score_write_candidate_shadow(
                    summary,
                    source_ref=turn_id,
                    existing_memories=existing_memories,
                ),
            }
            for summary in summaries
        ]
        written_candidate_indexes = _written_candidate_indexes(memorize_calls)
        allow_count = sum(1 for item in scored if item.get("decision") == "allow")
        reject_count = sum(1 for item in scored if item.get("decision") == "reject")
        review_count = sum(1 for item in scored if item.get("decision") == "review")
        reasons: dict[str, int] = {}
        for item in scored:
            reason = str(item.get("reason") or "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
        avg_score = (
            round(
                sum(float(item.get("final_score") or 0.0) for item in scored)
                / len(scored),
                4,
            )
            if scored
            else 0.0
        )
        temporary_risk_count = sum(
            1
            for item in scored
            if float(item.get("signals", {}).get("temporary_risk_score") or 0.0) >= 0.5
        )
        assistant_inference_risk_count = sum(
            1
            for item in scored
            if float(
                item.get("signals", {}).get("assistant_inference_risk_score") or 0.0
            )
            >= 0.5
        )
        duplicate_risk_count = sum(
            1
            for item in scored
            if float(item.get("signals", {}).get("duplicate_risk_score") or 0.0) >= 0.5
        )
        avg_entropy_score = _average_signal(scored, "entropy_score")
        avg_novelty_score = _average_signal(scored, "novelty_score")
        similar_memory_count = sum(
            int(item.get("similar_memory_count") or 0) for item in scored
        )
        baseline_written_count = int(baseline["baseline_written_count"])
        written_candidate_allow_count = sum(
            1
            for idx in written_candidate_indexes
            if idx < len(scored) and scored[idx].get("decision") == "allow"
        )
        write_reduction_rate = (
            round(
                max(0, baseline_written_count - written_candidate_allow_count)
                / baseline_written_count,
                4,
            )
            if baseline_written_count
            else 0.0
        )

        return self.record(
            feature_name="write_value_score",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline,
            experimental_result={
                "candidate_count": len(summaries),
                "policy_allow_count": allow_count,
                "policy_reject_count": reject_count,
                "policy_review_count": review_count,
                "candidates": scored,
            },
            metrics={
                "candidate_count": len(summaries),
                "baseline_written_count": baseline["baseline_written_count"],
                "policy_allow_count": allow_count,
                "policy_reject_count": reject_count,
                "policy_review_count": review_count,
                "avg_final_score": avg_score,
                "avg_entropy_score": avg_entropy_score,
                "avg_novelty_score": avg_novelty_score,
                "temporary_risk_count": temporary_risk_count,
                "assistant_inference_risk_count": assistant_inference_risk_count,
                "duplicate_risk_count": duplicate_risk_count,
                "existing_memory_count": len(existing_memories),
                "existing_memory_snapshot_count": len(existing_memories),
                "similar_memory_count": similar_memory_count,
                "written_candidate_allow_count": written_candidate_allow_count,
                "write_reduction_rate": write_reduction_rate,
                "reject_reason_distribution": reasons,
            },
        )

    def record_tri_retrieval_shadow(
        self,
        *,
        session_key: str,
        turn_id: str,
        baseline_result: dict[str, Any],
        experimental_result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> MemoryExperimentTrace | None:
        return self.record(
            feature_name="tri_retrieval",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline_result,
            experimental_result=experimental_result,
            metrics=metrics,
        )

    def record_graph_retrieval_shadow(
        self,
        *,
        session_key: str,
        turn_id: str,
        baseline_result: dict[str, Any],
        experimental_result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> MemoryExperimentTrace | None:
        return self.record(
            feature_name="graph_retrieval",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline_result,
            experimental_result=experimental_result,
            metrics=metrics,
        )

    def record_rerank_shadow(
        self,
        *,
        session_key: str,
        turn_id: str,
        baseline_result: dict[str, Any],
        experimental_result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> MemoryExperimentTrace | None:
        return self.record(
            feature_name="rerank_shadow",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline_result,
            experimental_result=experimental_result,
            metrics=metrics,
        )

    def record_injection_governance_shadow(
        self,
        *,
        session_key: str,
        turn_id: str,
        baseline_result: dict[str, Any],
        experimental_result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> MemoryExperimentTrace | None:
        return self.record(
            feature_name="injection_governance_shadow",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline_result,
            experimental_result=experimental_result,
            metrics=metrics,
        )

    def record_version_chain_shadow(
        self,
        *,
        session_key: str,
        turn_id: str,
        baseline_result: dict[str, Any],
        experimental_result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> MemoryExperimentTrace | None:
        return self.record(
            feature_name="version_chain_shadow",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline_result,
            experimental_result=experimental_result,
            metrics=metrics,
        )

    def record_provenance_shadow(
        self,
        *,
        session_key: str,
        turn_id: str,
        baseline_result: dict[str, Any],
        experimental_result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> MemoryExperimentTrace | None:
        return self.record(
            feature_name="provenance_shadow",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline_result,
            experimental_result=experimental_result,
            metrics=metrics,
        )

    def _existing_memory_snapshot(self) -> list[dict[str, object]]:
        if self._existing_memory_provider is None:
            return []
        try:
            return list(self._existing_memory_provider())
        except Exception:
            return []


def _diff_dicts(
    baseline: dict[str, Any],
    experimental: dict[str, Any],
) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for key in sorted(set(baseline) | set(experimental)):
        left = baseline.get(key)
        right = experimental.get(key)
        if left != right:
            changed[key] = {"baseline": left, "experimental": right}
    return changed


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered or marker in text for marker in markers)


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize_memory_text(text: str) -> set[str]:
    raw = str(text or "").lower()
    tokens = set(_WORD_RE.findall(raw))
    tokens.update(ch for ch in raw if _CJK_RE.match(ch))
    return {token for token in tokens if token.strip()}


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _score_existing_memory_overlap(
    summary: str,
    existing_memories: list[dict[str, object]] | None,
) -> dict[str, Any]:
    candidate_tokens = _tokenize_memory_text(summary)
    scored: list[tuple[str, float]] = []
    for item in existing_memories or []:
        item_id = str(item.get("id") or "").strip()
        item_summary = str(item.get("summary") or "").strip()
        if not item_id or not item_summary:
            continue
        similarity = _jaccard_similarity(
            candidate_tokens,
            _tokenize_memory_text(item_summary),
        )
        if similarity > 0:
            scored.append((item_id, similarity))
    scored.sort(key=lambda entry: (-entry[1], entry[0]))
    nearest = [item_id for item_id, score in scored if score >= 0.6][:3]
    max_similarity = scored[0][1] if scored else 0.0
    duplicate_risk = max_similarity
    novelty = 1.0 - max_similarity
    entropy = 1.0 - max_similarity
    return {
        "duplicate_risk_score": _clamp_score(duplicate_risk),
        "novelty_score": _clamp_score(novelty),
        "entropy_score": _clamp_score(entropy),
        "similar_memory_count": len(nearest),
        "nearest_memory_ids": nearest,
    }


def _average_signal(scored: list[dict[str, Any]], signal_name: str) -> float:
    if not scored:
        return 0.0
    return round(
        sum(float(item.get("signals", {}).get(signal_name) or 0.0) for item in scored)
        / len(scored),
        4,
    )


def score_write_candidate_shadow(
    summary: str,
    *,
    source_ref: str = "",
    existing_memories: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    text = str(summary or "").strip()
    explicit_markers = (
        "记住",
        "以后",
        "下次",
        "长期记忆",
        "用户明确要求",
        "remember",
        "always",
    )
    stable_markers = (
        "偏好",
        "习惯",
        "规则",
        "流程",
        "以后",
        "长期",
        "always",
        "prefer",
    )
    temporary_markers = (
        "临时",
        "测试",
        "今天这次",
        "本次",
        "不要写入长期记忆",
        "不要记",
        "temporary",
        "do not remember",
    )
    assistant_inference_markers = (
        "助手推断",
        "可能喜欢",
        "看起来",
        "应该是",
        "猜测",
        "seems",
        "probably",
        "maybe",
    )

    if not text:
        return {
            "decision": "reject",
            "reason": "empty",
            "score": 0.0,
            "final_score": 0.0,
            "reasons": ["empty"],
            "signals": {
                "explicit_user_intent_score": 0.0,
                "long_term_stability_score": 0.0,
                "novelty_score": 0.0,
                "entropy_score": 0.0,
                "temporary_risk_score": 0.0,
                "assistant_inference_risk_score": 0.0,
                "duplicate_risk_score": 0.0,
                "source_ref_confidence_score": 0.0,
            },
            "similar_memory_count": 0,
            "nearest_memory_ids": [],
        }

    explicit = _contains_any(text, explicit_markers)
    stable = explicit or _contains_any(text, stable_markers) or len(text) >= 16
    temporary = _contains_any(text, temporary_markers)
    assistant_inference = _contains_any(text, assistant_inference_markers)
    source_ref_confident = bool(str(source_ref or "").strip())
    overlap = _score_existing_memory_overlap(text, existing_memories)

    signals = {
        "explicit_user_intent_score": 1.0 if explicit else 0.2,
        "long_term_stability_score": 0.75 if stable else 0.35,
        "novelty_score": overlap["novelty_score"],
        "entropy_score": overlap["entropy_score"],
        "temporary_risk_score": 0.9 if temporary else 0.0,
        "assistant_inference_risk_score": 0.9 if assistant_inference else 0.0,
        "duplicate_risk_score": overlap["duplicate_risk_score"],
        "source_ref_confidence_score": 0.85 if source_ref_confident else 0.5,
    }

    final_score = (
        signals["explicit_user_intent_score"] * 0.40
        + signals["long_term_stability_score"] * 0.25
        + signals["novelty_score"] * 0.15
        + signals["source_ref_confidence_score"] * 0.15
        - signals["temporary_risk_score"] * 0.35
        - signals["assistant_inference_risk_score"] * 0.30
        - signals["duplicate_risk_score"] * 0.20
    )
    final_score = _clamp_score(final_score)

    reasons: list[str] = []
    if explicit:
        reasons.append("explicit_user_intent")
    if stable:
        reasons.append("long_term_stability")
    if temporary:
        reasons.append("temporary_state")
    if assistant_inference:
        reasons.append("assistant_inference")
    if source_ref_confident:
        reasons.append("source_ref_present")
    if float(overlap["duplicate_risk_score"]) >= 0.8:
        reasons.append("duplicate_existing_memory")
    elif float(overlap["novelty_score"]) >= 0.6:
        reasons.append("novel_information")
    if not reasons:
        reasons.append("low_information")

    duplicate_risk = float(overlap["duplicate_risk_score"])
    if temporary:
        decision = "reject"
        reason = "temporary_state"
    elif assistant_inference:
        decision = "reject"
        reason = "assistant_inference"
    elif duplicate_risk >= 0.8:
        decision = "reject"
        reason = "duplicate_existing_memory"
    elif final_score >= 0.7:
        decision = "allow"
        reason = "explicit_memory_signal" if explicit else "high_value_signal"
    elif final_score >= 0.45:
        decision = "review"
        reason = "moderate_value_signal"
        if "moderate_information_value" not in reasons:
            reasons.append("moderate_information_value")
    else:
        decision = "reject"
        reason = "low_information"

    return {
        "decision": decision,
        "reason": reason,
        "score": final_score,
        "final_score": final_score,
        "reasons": reasons,
        "signals": {key: _clamp_score(value) for key, value in signals.items()},
        "similar_memory_count": overlap["similar_memory_count"],
        "nearest_memory_ids": overlap["nearest_memory_ids"],
    }


def extract_explicit_memorize_baseline(
    calls: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    item_ids: list[str] = []
    for call in calls:
        result = str(call.get("result") or "")
        item_match = re.search(r"item_id=([A-Za-z0-9:_-]{1,128})", result)
        status_match = re.search(r"status=([A-Za-z0-9_-]{1,64})", result)
        if item_match:
            item_ids.append(item_match.group(1))
            status = status_match.group(1) if status_match else "written"
        else:
            status = "failed"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "attempted_count": len(calls),
        "baseline_written_count": len(item_ids),
        "written_item_ids": item_ids,
        "write_status_counts": status_counts,
    }


def _written_candidate_indexes(calls: list[dict[str, Any]]) -> set[int]:
    indexes: set[int] = set()
    for idx, call in enumerate(calls):
        result = str(call.get("result") or "")
        if re.search(r"item_id=([A-Za-z0-9:_-]{1,128})", result):
            indexes.add(idx)
    return indexes
