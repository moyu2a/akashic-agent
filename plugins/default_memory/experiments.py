from __future__ import annotations

import json
import re
import uuid
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
    def __init__(self, *, workspace: Path, config: MemoryExperimentsConfig) -> None:
        self._workspace = workspace
        self._config = config
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
        scored = [score_write_candidate_shadow(summary) for summary in summaries]
        allow_count = sum(1 for item in scored if item.get("decision") == "allow")
        reject_count = sum(1 for item in scored if item.get("decision") == "reject")
        reasons: dict[str, int] = {}
        for item in scored:
            reason = str(item.get("reason") or "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1

        return self.record(
            feature_name="write_value_score",
            session_key=session_key,
            turn_id=turn_id,
            baseline_result=baseline,
            experimental_result={
                "candidate_count": len(summaries),
                "policy_allow_count": allow_count,
                "policy_reject_count": reject_count,
                "candidates": scored,
            },
            metrics={
                "candidate_count": len(summaries),
                "baseline_written_count": baseline["baseline_written_count"],
                "policy_allow_count": allow_count,
                "policy_reject_count": reject_count,
                "reject_reason_distribution": reasons,
            },
        )


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


def score_write_candidate_shadow(summary: str) -> dict[str, Any]:
    text = str(summary or "").strip()
    lowered = text.lower()
    temporary_markers = (
        "临时",
        "测试",
        "不要写入长期记忆",
        "不要记",
        "temporary",
        "do not remember",
    )
    explicit_markers = (
        "记住",
        "长期记忆",
        "用户明确要求",
        "remember",
    )
    if not text:
        return {"decision": "reject", "reason": "empty", "score": 0.0}
    if any(marker in lowered or marker in text for marker in temporary_markers):
        return {"decision": "reject", "reason": "temporary_state", "score": 0.2}
    if any(marker in lowered or marker in text for marker in explicit_markers):
        return {"decision": "allow", "reason": "explicit_memory_signal", "score": 0.8}

    score = 0.55 if len(text) >= 12 else 0.35
    decision = "allow" if score >= 0.5 else "reject"
    reason = "basic_value_signal" if decision == "allow" else "low_information"
    return {"decision": decision, "reason": reason, "score": score}


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
