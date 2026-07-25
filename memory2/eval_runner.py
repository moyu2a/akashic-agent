from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from memory2.eval_cases import EvalCase, EVAL_CONFIG_MATRIX, load_eval_cases
from memory2.injection_governance_experiments import (
    build_injection_governance_shadow_result,
)
from memory2.provenance_experiments import build_provenance_shadow_result
from memory2.rerank_experiments import build_rerank_shadow_result
from memory2.retrieval_experiments import (
    build_provenance_lane,
    build_tri_retrieval_shadow_result,
)
from memory2.retrieval_graph_experiments import (
    build_graph_lane,
    build_graph_retrieval_shadow_result,
)
from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)
from memory2.version_chain_experiments import build_version_chain_shadow_result
from plugins.default_memory.experiments import (
    extract_explicit_memorize_baseline,
    score_write_candidate_shadow,
)


_FIXED_NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


@dataclass(frozen=True)
class EvalTrace:
    feature_name: str
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


@dataclass(frozen=True)
class EvalProfileResult:
    profile: str
    enabled: bool
    flags: dict[str, object]
    trace_features: tuple[str, ...]
    traces: dict[str, EvalTrace]
    recalled_ids: tuple[str, ...]
    injected_ids: tuple[str, ...]
    metrics: dict[str, Any]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    category: str
    phase_targets: tuple[str, ...]
    profiles: dict[str, EvalProfileResult]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures and all(result.passed for result in self.profiles.values())


@dataclass(frozen=True)
class EvalRunReport:
    cases: tuple[EvalCaseResult, ...]
    metrics: dict[str, Any]

    @property
    def passed(self) -> bool:
        return all(case.passed for case in self.cases)


def run_eval_case(case: EvalCase) -> EvalCaseResult:
    profiles = {profile: _run_profile(case, profile) for profile in case.config_profiles}
    failures = tuple(
        f"{profile}: {failure}"
        for profile, result in profiles.items()
        for failure in result.failures
    )
    return EvalCaseResult(
        case_id=case.id,
        category=case.category,
        phase_targets=case.phase_targets,
        profiles=profiles,
        failures=failures,
    )


def run_eval_cases(cases: Sequence[EvalCase]) -> EvalRunReport:
    case_results = tuple(run_eval_case(case) for case in cases)
    return EvalRunReport(cases=case_results, metrics=_report_metrics(case_results))


def run_eval_case_files(root: Path) -> EvalRunReport:
    return run_eval_cases(load_eval_cases(root))


def write_eval_report(report: EvalRunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _run_profile(case: EvalCase, profile: str) -> EvalProfileResult:
    config = EVAL_CONFIG_MATRIX[profile]
    enabled = bool(config.get("enabled")) and str(config.get("mode") or "") != "off"
    flags = dict(config.get("flags") or {})
    if not enabled:
        result = EvalProfileResult(
            profile=profile,
            enabled=False,
            flags=flags,
            trace_features=(),
            traces={},
            recalled_ids=(),
            injected_ids=(),
            metrics={"trace_count": 0},
            failures=(),
        )
        return result

    traces: dict[str, EvalTrace] = {}
    for feature_name in _enabled_features_for_case(case, profile, flags):
        trace = _build_trace(case, feature_name)
        if trace is not None:
            traces[feature_name] = trace
    recalled_ids = tuple(_ids(_baseline_recalled_items(case)))
    injected_ids = _injected_ids(traces)
    metrics = {
        "trace_count": len(traces),
        "recalled_count": len(recalled_ids),
        "injected_count": len(injected_ids),
    }
    result = EvalProfileResult(
        profile=profile,
        enabled=True,
        flags=flags,
        trace_features=tuple(traces),
        traces=traces,
        recalled_ids=recalled_ids,
        injected_ids=injected_ids,
        metrics=metrics,
        failures=(),
    )
    return _replace_profile_failures(
        result,
        _validate_profile_result(case, profile, result),
    )


def _replace_profile_failures(
    result: EvalProfileResult,
    failures: list[str],
) -> EvalProfileResult:
    return EvalProfileResult(
        profile=result.profile,
        enabled=result.enabled,
        flags=result.flags,
        trace_features=result.trace_features,
        traces=result.traces,
        recalled_ids=result.recalled_ids,
        injected_ids=result.injected_ids,
        metrics=result.metrics,
        failures=tuple(failures),
    )


def _enabled_features_for_case(
    case: EvalCase,
    profile: str,
    flags: dict[str, object],
) -> tuple[str, ...]:
    expected = set(_expectations(case).get("expected_trace_features", []))
    candidates: list[str] = []
    if profile in {"phase1", "all"}:
        candidates.append("write_value_score")
    if flags.get("graph_retrieval_enabled"):
        candidates.extend(["tri_retrieval", "graph_retrieval"])
    if flags.get("rerank_shadow_enabled"):
        candidates.append("rerank_shadow")
    if flags.get("injection_governance_shadow_enabled"):
        candidates.append("injection_governance_shadow")
    if flags.get("version_chain_shadow_enabled"):
        candidates.append("version_chain_shadow")
    if flags.get("provenance_shadow_enabled"):
        candidates.append("provenance_shadow")
    if flags.get("sleep_consolidation_shadow_enabled"):
        candidates.append("sleep_consolidation_shadow")
    return tuple(feature for feature in candidates if feature in expected)


def _build_trace(case: EvalCase, feature_name: str) -> EvalTrace | None:
    if feature_name == "write_value_score":
        return _build_write_value_trace(case)
    if feature_name == "tri_retrieval":
        semantic_items, keyword_items, provenance_items, _ = _candidate_lanes(case)
        result = build_tri_retrieval_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=semantic_items,
            keyword_items=keyword_items,
            provenance_items=provenance_items,
            latency_ms=0.0,
            top_n=max(8, len(_active_memory_items(case))),
        )
        metrics = dict(result.metrics)
        metrics.update(_copy_keys(result.experimental_result, (
            "semantic_hit_count",
            "keyword_hit_count",
            "provenance_hit_count",
            "fused_hit_count",
        )))
        return EvalTrace(feature_name, result.baseline_result, result.experimental_result, metrics)
    if feature_name == "graph_retrieval":
        semantic_items, keyword_items, provenance_items, graph_items = _candidate_lanes(case)
        baseline_miss = _baseline_miss_ids(case)
        result = build_graph_retrieval_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=_without_ids(semantic_items, baseline_miss),
            keyword_items=_without_ids(keyword_items, baseline_miss),
            provenance_items=_without_ids(provenance_items, baseline_miss),
            graph_items=graph_items,
            latency_ms=0.0,
            top_n=max(8, len(_active_memory_items(case))),
        )
        metrics = dict(result.metrics)
        metrics.update(_copy_keys(result.experimental_result, (
            "graph_hit_count",
            "graph_fused_hit_count",
        )))
        return EvalTrace(feature_name, result.baseline_result, result.experimental_result, metrics)
    if feature_name == "rerank_shadow":
        semantic_items, keyword_items, provenance_items, graph_items = _candidate_lanes(case)
        scope = _scope(case)
        result = build_rerank_shadow_result(
            query=_query(case),
            baseline_items=_baseline_recalled_items(case),
            semantic_items=semantic_items,
            keyword_items=keyword_items,
            provenance_items=provenance_items,
            graph_items=graph_items,
            scope_channel=scope["channel"],
            scope_chat_id=scope["chat_id"],
            top_n=max(8, len(_active_memory_items(case))),
        )
        return EvalTrace(feature_name, result.baseline_result, result.experimental_result, dict(result.metrics))
    if feature_name == "injection_governance_shadow":
        candidates = _injection_candidates(case)
        baseline_items = _baseline_recalled_items(case)
        result = build_injection_governance_shadow_result(
            baseline_items=baseline_items,
            baseline_injected_ids=_ids(baseline_items),
            baseline_text_block=_baseline_text_block(baseline_items),
            candidate_items=candidates,
            max_chars=180,
            max_items=4,
        )
        metrics = dict(result.metrics)
        metrics["dropped_by_reason"] = dict(result.experimental_result.get("drop_reasons", {}))
        return EvalTrace(feature_name, result.baseline_result, result.experimental_result, metrics)
    if feature_name == "version_chain_shadow":
        result = build_version_chain_shadow_result(
            memory_items=_memory_items(case),
            replacements=list(_setup(case).get("memory_replacements", [])),
            recalled_items=_baseline_recalled_items(case),
        )
        return EvalTrace(feature_name, result.baseline_result, result.experimental_result, dict(result.metrics))
    if feature_name == "provenance_shadow":
        scope = _scope(case)
        result = build_provenance_shadow_result(
            memory_items=_memory_items(case),
            recalled_items=_baseline_recalled_items(case),
            scope_channel=scope["channel"],
            scope_chat_id=scope["chat_id"],
        )
        return EvalTrace(feature_name, result.baseline_result, result.experimental_result, dict(result.metrics))
    if feature_name == "sleep_consolidation_shadow":
        result = build_sleep_consolidation_shadow_result(
            memory_items=_memory_items(case),
            now=_FIXED_NOW,
        )
        metrics = dict(result.metrics)
        metrics["job_latency_ms"] = 0.0
        return EvalTrace(feature_name, result.baseline_result, result.experimental_result, metrics)
    return None


def _build_write_value_trace(case: EvalCase) -> EvalTrace | None:
    calls = _memorize_calls(case)
    candidates = _write_candidates(case)
    if not candidates:
        return None
    baseline = (
        extract_explicit_memorize_baseline(calls)
        if calls
        else {
            "attempted_count": len(candidates),
            "baseline_written_count": len(candidates),
            "written_item_ids": [str(item.get("id") or "") for item in candidates],
            "write_status_counts": {"fixture_candidate": len(candidates)},
        }
    )
    written_ids = {str(item_id) for item_id in baseline.get("written_item_ids", [])}
    existing_memories = [
        item for item in _active_memory_items(case) if str(item.get("id") or "") not in written_ids
    ]
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        summary = str(candidate.get("summary") or "")
        scored.append(
            {
                "summary": summary,
                **score_write_candidate_shadow(
                    summary,
                    source_ref=_source_ref_for_candidate(candidate, case),
                    existing_memories=[
                        item
                        for item in existing_memories
                        if str(item.get("id") or "") != str(candidate.get("id") or "")
                    ],
                ),
            }
        )
    allow_count = sum(1 for item in scored if item.get("decision") == "allow")
    reject_count = sum(1 for item in scored if item.get("decision") == "reject")
    review_count = sum(1 for item in scored if item.get("decision") == "review")
    reasons: dict[str, int] = {}
    for item in scored:
        reason = str(item.get("reason") or "unknown")
        reasons[reason] = reasons.get(reason, 0) + 1
    baseline_written_count = int(baseline.get("baseline_written_count") or 0)
    metrics = {
        "candidate_count": len(scored),
        "baseline_written_count": baseline_written_count,
        "policy_allow_count": allow_count,
        "policy_reject_count": reject_count,
        "policy_review_count": review_count,
        "temporary_risk_count": _risk_count(scored, "temporary_risk_score"),
        "assistant_inference_risk_count": _risk_count(
            scored,
            "assistant_inference_risk_score",
        ),
        "duplicate_risk_count": _risk_count(scored, "duplicate_risk_score"),
        "similar_memory_count": sum(int(item.get("similar_memory_count") or 0) for item in scored),
        "write_reduction_rate": (
            round(max(0, baseline_written_count - allow_count) / baseline_written_count, 4)
            if baseline_written_count
            else 0.0
        ),
        "reject_reason_distribution": reasons,
    }
    return EvalTrace(
        feature_name="write_value_score",
        baseline_result=baseline,
        experimental_result={
            "candidate_count": len(scored),
            "policy_allow_count": allow_count,
            "policy_reject_count": reject_count,
            "policy_review_count": review_count,
            "candidates": scored,
        },
        metrics=metrics,
    )


def _validate_profile_result(
    case: EvalCase,
    profile: str,
    result: EvalProfileResult,
) -> list[str]:
    expectations = _expectations(case)
    profile_expectations = expectations.get("profile_expectations", {})
    profile_payload = (
        profile_expectations.get(profile, {})
        if isinstance(profile_expectations, dict)
        else {}
    )
    failures: list[str] = []
    for feature in profile_payload.get("required_trace_features", []):
        if str(feature) not in result.traces:
            failures.append(f"missing required trace feature '{feature}'")
    for feature in profile_payload.get("forbidden_trace_features", []):
        if str(feature) in result.traces:
            failures.append(f"forbidden trace feature '{feature}' was present")

    expected_metric_keys = dict(expectations.get("expected_metric_keys", {}))
    profile_metric_keys = dict(profile_payload.get("metric_keys", {}))
    for feature_name, keys in {**expected_metric_keys, **profile_metric_keys}.items():
        if feature_name not in result.traces:
            continue
        metrics = result.traces[str(feature_name)].metrics
        for key in keys:
            if str(key) not in metrics:
                failures.append(
                    f"trace '{feature_name}' missing metric key '{key}'"
                )

    if result.enabled:
        recalled = set(result.recalled_ids)
        injected = set(result.injected_ids)
        baseline_miss = {
            str(item)
            for item in expectations.get("baseline_miss_recall_ids", [])
            if str(item)
        }
        for item_id in expectations.get("should_recall_ids", []):
            if str(item_id) in baseline_miss:
                continue
            if str(item_id) not in recalled:
                failures.append(f"should recall id '{item_id}' was not recalled")
        for item_id in expectations.get("should_not_recall_ids", []):
            item = str(item_id)
            if item in recalled:
                failures.append(f"should not recall id '{item}' was recalled")
            if item in injected:
                failures.append(f"should not recall id '{item}' was injected")
    return failures


def _report_metrics(cases: Sequence[EvalCaseResult]) -> dict[str, Any]:
    profiles = [profile for case in cases for profile in case.profiles.values()]
    trace_count_by_feature: dict[str, int] = {}
    for profile in profiles:
        for feature in profile.trace_features:
            trace_count_by_feature[feature] = trace_count_by_feature.get(feature, 0) + 1
    failed_profile_count = sum(1 for profile in profiles if not profile.passed)
    profile_count = len(profiles)
    return {
        "case_count": len(cases),
        "profile_count": profile_count,
        "passed_case_count": sum(1 for case in cases if case.passed),
        "failed_case_count": sum(1 for case in cases if not case.passed),
        "failed_profile_count": failed_profile_count,
        "trace_count": sum(len(profile.trace_features) for profile in profiles),
        "trace_count_by_feature": trace_count_by_feature,
        "profile_pass_rate": (
            round((profile_count - failed_profile_count) / profile_count, 4)
            if profile_count
            else 0.0
        ),
    }


def _report_to_dict(report: EvalRunReport) -> dict[str, Any]:
    return {
        "passed": report.passed,
        "metrics": report.metrics,
        "cases": [_case_to_dict(case) for case in report.cases],
    }


def _case_to_dict(case: EvalCaseResult) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "category": case.category,
        "phase_targets": list(case.phase_targets),
        "passed": case.passed,
        "failures": list(case.failures),
        "profiles": {
            name: _profile_to_dict(profile)
            for name, profile in case.profiles.items()
        },
    }


def _profile_to_dict(profile: EvalProfileResult) -> dict[str, Any]:
    return {
        "profile": profile.profile,
        "enabled": profile.enabled,
        "flags": profile.flags,
        "trace_features": list(profile.trace_features),
        "traces": {
            name: _trace_to_dict(trace)
            for name, trace in profile.traces.items()
        },
        "recalled_ids": list(profile.recalled_ids),
        "injected_ids": list(profile.injected_ids),
        "metrics": profile.metrics,
        "passed": profile.passed,
        "failures": list(profile.failures),
    }


def _trace_to_dict(trace: EvalTrace) -> dict[str, Any]:
    return {
        "feature_name": trace.feature_name,
        "baseline_result": trace.baseline_result,
        "experimental_result": trace.experimental_result,
        "metrics": trace.metrics,
    }


def _memory_items(case: EvalCase) -> list[dict[str, object]]:
    return [dict(item) for item in _setup(case).get("memory_items", [])]


def _active_memory_items(case: EvalCase) -> list[dict[str, object]]:
    return [
        item
        for item in _memory_items(case)
        if str(item.get("status") or "active") == "active"
        and str(item.get("id") or "").strip()
    ]


def _scope(case: EvalCase) -> dict[str, str]:
    scope = _setup(case).get("scope", {})
    if not isinstance(scope, dict):
        return {"session_key": "", "channel": "", "chat_id": ""}
    return {
        "session_key": str(scope.get("session_key") or ""),
        "channel": str(scope.get("channel") or ""),
        "chat_id": str(scope.get("chat_id") or ""),
    }


def _query(case: EvalCase) -> str:
    setup = _setup(case)
    query = str(setup.get("query") or "").strip()
    if query:
        return query
    conversation = setup.get("conversation", [])
    if not isinstance(conversation, list):
        return ""
    return "\n".join(
        str(message.get("content") or "")
        for message in conversation
        if isinstance(message, dict)
    ).strip()


def _baseline_recalled_items(case: EvalCase) -> list[dict[str, object]]:
    expectations = _expectations(case)
    should_recall = {str(item) for item in expectations.get("should_recall_ids", [])}
    should_not = {str(item) for item in expectations.get("should_not_recall_ids", [])}
    baseline_miss = _baseline_miss_ids(case)
    query_terms = _terms(_query(case))
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    scope = _scope(case)
    for item in _active_memory_items(case):
        item_id = str(item.get("id") or "").strip()
        if not item_id or item_id in should_not:
            continue
        if item_id in baseline_miss:
            continue
        if item_id in should_recall:
            result.append(_with_default_score(item, 0.82))
            seen.add(item_id)
            continue
        if not _same_scope(item, scope):
            continue
        if query_terms & _terms(str(item.get("summary") or "")):
            result.append(_with_default_score(item, 0.62))
            seen.add(item_id)
    return [item for item in result if str(item.get("id") or "") in seen]


def _baseline_miss_ids(case: EvalCase) -> set[str]:
    return {
        str(item)
        for item in _expectations(case).get("baseline_miss_recall_ids", [])
        if str(item)
    }


def _without_ids(
    items: list[dict[str, object]],
    excluded_ids: set[str],
) -> list[dict[str, object]]:
    if not excluded_ids:
        return items
    return [
        item
        for item in items
        if str(item.get("id") or "").strip() not in excluded_ids
    ]


def _candidate_lanes(
    case: EvalCase,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    scope = _scope(case)
    active = [item for item in _active_memory_items(case) if _same_scope(item, scope)]
    should_recall = {str(item) for item in _expectations(case).get("should_recall_ids", [])}
    query_terms = _terms(_query(case))
    semantic_items = [
        _with_default_score(item, 0.8 if str(item.get("id") or "") in should_recall else 0.6)
        for item in active
        if str(item.get("id") or "") in should_recall
        or query_terms & _terms(str(item.get("summary") or ""))
    ]
    keyword_items = [
        {**dict(item), "keyword_score": float(item.get("keyword_score") or 0.55)}
        for item in active
        if query_terms & _terms(str(item.get("summary") or ""))
    ]
    provenance_items = build_provenance_lane(
        _query(case),
        active,
        scope_channel=scope["channel"],
        scope_chat_id=scope["chat_id"],
        limit=max(20, len(active)),
    ).items
    graph_items = build_graph_lane(
        _query(case),
        active,
        scope_channel=scope["channel"],
        scope_chat_id=scope["chat_id"],
        limit=max(20, len(active)),
    ).items
    return semantic_items, keyword_items, provenance_items, graph_items


def _injection_candidates(case: EvalCase) -> list[dict[str, object]]:
    semantic_items, keyword_items, provenance_items, graph_items = _candidate_lanes(case)
    scope = _scope(case)
    result = build_rerank_shadow_result(
        query=_query(case),
        baseline_items=_baseline_recalled_items(case),
        semantic_items=semantic_items,
        keyword_items=keyword_items,
        provenance_items=provenance_items,
        graph_items=graph_items,
        scope_channel=scope["channel"],
        scope_chat_id=scope["chat_id"],
        top_n=max(8, len(_active_memory_items(case))),
    )
    ranked = list(result.experimental_result.get("ranked_items", []))
    by_id = {str(item.get("id") or ""): dict(item) for item in ranked if str(item.get("id") or "")}
    for item in _active_memory_items(case):
        item_id = str(item.get("id") or "").strip()
        if item_id and item_id not in by_id and _same_scope(item, scope):
            by_id[item_id] = _with_default_score(item, float(item.get("score") or 0.5))
    return list(by_id.values())


def _memorize_calls(case: EvalCase) -> list[dict[str, Any]]:
    calls = _setup(case).get("memorize_calls", [])
    if not isinstance(calls, list):
        return []
    return [dict(call) for call in calls if isinstance(call, dict)]


def _write_candidates(case: EvalCase) -> list[dict[str, object]]:
    calls = _memorize_calls(case)
    if calls:
        return [
            {
                "summary": str(call.get("summary") or ""),
                "source_ref": _scope(case)["session_key"] + "@post_response",
            }
            for call in calls
            if str(call.get("summary") or "").strip()
        ]
    return _active_memory_items(case)


def _source_ref_for_candidate(candidate: dict[str, object], case: EvalCase) -> str:
    source_ref = str(candidate.get("source_ref") or "").strip()
    if source_ref:
        return source_ref
    session_key = _scope(case)["session_key"]
    return f"{session_key}@post_response" if session_key else ""


def _risk_count(scored: list[dict[str, Any]], signal_name: str) -> int:
    return sum(
        1
        for item in scored
        if float(item.get("signals", {}).get(signal_name) or 0.0) >= 0.5
    )


def _setup(case: EvalCase) -> dict[str, Any]:
    return dict(case.setup)


def _expectations(case: EvalCase) -> dict[str, Any]:
    return dict(case.expectations)


def _same_scope(item: dict[str, object], scope: dict[str, str]) -> bool:
    return (
        str(item.get("scope_channel") or "") == scope["channel"]
        and str(item.get("scope_chat_id") or "") == scope["chat_id"]
    )


def _with_default_score(item: dict[str, object], score: float) -> dict[str, object]:
    copy = dict(item)
    copy.setdefault("score", round(score, 4))
    return copy


def _terms(text: str) -> set[str]:
    raw = str(text or "").lower()
    words = set(re.findall(r"[a-z0-9_]+", raw))
    cjk = {raw[idx : idx + 2] for idx in range(max(0, len(raw) - 1))}
    return {term for term in words | cjk if term.strip()}


def _ids(items: list[dict[str, object]]) -> list[str]:
    return [
        str(item.get("id") or "").strip()
        for item in items
        if str(item.get("id") or "").strip()
    ]


def _injected_ids(traces: dict[str, EvalTrace]) -> tuple[str, ...]:
    injection = traces.get("injection_governance_shadow")
    if injection is None:
        return ()
    ids = injection.experimental_result.get("experimental_injected_ids", [])
    if not isinstance(ids, list):
        return ()
    return tuple(str(item_id) for item_id in ids if str(item_id).strip())


def _baseline_text_block(items: list[dict[str, object]]) -> str:
    return "\n".join(str(item.get("summary") or "") for item in items)


def _copy_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}
