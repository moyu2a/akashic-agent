from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memory2.eval_cases import EVAL_CONFIG_PROFILES, EVAL_PHASE_TARGETS, EvalCase


REQUIRED_PROFILE_EXPECTATIONS: tuple[str, ...] = (
    "chain_tri_retrieval",
    "chain_tri_candidate_governance",
    "chain_tri_evidence_only",
    "chain_tri_governed_answer_contract",
)


@dataclass(frozen=True)
class MemoryGovernanceEvalCase:
    case_id: str
    scenario: str
    user_question: str
    eval_base_time: str
    memories: tuple[dict[str, Any], ...]
    should_recall_ids: tuple[str, ...]
    should_not_recall_ids: tuple[str, ...]
    expected_answer_contains: tuple[str, ...]
    expected_answer_contains_any: tuple[tuple[str, ...], ...]
    forbidden_answer_contains: tuple[str, ...]
    evidence_graph: dict[str, Any]
    profile_expectations: dict[str, str]
    notes: str = ""


def load_memory_governance_cases(path: Path) -> tuple[MemoryGovernanceEvalCase, ...]:
    cases: list[MemoryGovernanceEvalCase] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
            cases.append(_case_from_payload(payload))
    return tuple(cases)


def validate_memory_governance_cases(
    cases: tuple[MemoryGovernanceEvalCase, ...],
) -> tuple[str, ...]:
    errors: list[str] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        label = case.case_id or "<missing case_id>"
        if not case.case_id:
            errors.append("missing case_id")
        if case.case_id in seen_case_ids:
            errors.append(f"{label}: duplicate case_id")
        seen_case_ids.add(case.case_id)
        if len(case.memories) < 2:
            errors.append(f"{label}: each case must include at least 2 memories")

        memory_ids: set[str] = set()
        superseded_ids: set[str] = set()
        for index, memory in enumerate(case.memories):
            memory_id = str(memory.get("id") or "")
            if not memory_id:
                errors.append(f"{label}: memories[{index}].id must be non-empty")
                continue
            if memory_id in memory_ids:
                errors.append(f"{label}: duplicate memory id {memory_id}")
            memory_ids.add(memory_id)
            if str(memory.get("status") or "") == "superseded":
                superseded_ids.add(memory_id)
            if "relative_timestamp_days" not in memory:
                errors.append(
                    f"{label}: memories[{index}].relative_timestamp_days is required"
                )

        should_recall = set(case.should_recall_ids)
        should_not = set(case.should_not_recall_ids)
        dangling_recall = sorted(should_recall - memory_ids)
        dangling_not = sorted(should_not - memory_ids)
        if dangling_recall:
            errors.append(
                f"{label}: dangling should_recall_ids {','.join(dangling_recall)}"
            )
        if dangling_not:
            errors.append(
                f"{label}: dangling should_not_recall_ids {','.join(dangling_not)}"
            )
        superseded_recall = sorted(should_recall & superseded_ids)
        if superseded_recall:
            errors.append(
                f"{label}: superseded should_recall_ids {','.join(superseded_recall)}"
            )

        expected_terms = set(case.expected_answer_contains)
        for group in case.expected_answer_contains_any:
            expected_terms.update(group)
        conflicts = sorted(expected_terms & set(case.forbidden_answer_contains))
        if conflicts:
            errors.append(
                f"{label}: expected/forbidden conflict {','.join(conflicts)}"
            )

        graph = case.evidence_graph
        graph_nodes = {str(item) for item in graph.get("nodes", ())}
        if graph_nodes - memory_ids:
            errors.append(
                f"{label}: evidence_graph dangling nodes "
                + ",".join(sorted(graph_nodes - memory_ids))
            )
        graph_edges = graph.get("edges", ())
        if not isinstance(graph_edges, list):
            errors.append(f"{label}: evidence_graph.edges must be a list")
            graph_edges = []
        adjacency: dict[str, list[str]] = {}
        for index, edge in enumerate(graph_edges):
            if not isinstance(edge, dict):
                errors.append(f"{label}: evidence_graph.edges[{index}] must be object")
                continue
            source = str(edge.get("from") or "")
            target = str(edge.get("to") or "")
            if source not in graph_nodes or source not in memory_ids:
                errors.append(f"{label}: evidence_graph edge from dangling {source}")
            if target not in graph_nodes or target not in memory_ids:
                errors.append(f"{label}: evidence_graph edge to dangling {target}")
            adjacency.setdefault(source, []).append(target)
        if _has_cycle(adjacency):
            errors.append(f"{label}: evidence_graph cycle detected")

        missing_profiles = [
            profile
            for profile in REQUIRED_PROFILE_EXPECTATIONS
            if profile not in case.profile_expectations
        ]
        if missing_profiles:
            errors.append(
                f"{label}: profile_expectations missing {','.join(missing_profiles)}"
            )
    return tuple(errors)


def memory_governance_case_to_json(case: MemoryGovernanceEvalCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "scenario": case.scenario,
        "user_question": case.user_question,
        "eval_base_time": case.eval_base_time,
        "memories": list(case.memories),
        "should_recall_ids": list(case.should_recall_ids),
        "should_not_recall_ids": list(case.should_not_recall_ids),
        "expected_answer_contains": list(case.expected_answer_contains),
        "expected_answer_contains_any": [
            list(group) for group in case.expected_answer_contains_any
        ],
        "forbidden_answer_contains": list(case.forbidden_answer_contains),
        "evidence_graph": dict(case.evidence_graph),
        "profile_expectations": dict(case.profile_expectations),
        "notes": case.notes,
    }


def memory_governance_case_to_eval_case(
    case: MemoryGovernanceEvalCase,
) -> EvalCase:
    scope = {
        "session_key": f"eval:{case.case_id}",
        "channel": "memory_governance_eval",
        "chat_id": case.case_id,
    }
    memory_items = [_memory_item_for_eval(case, memory, scope) for memory in case.memories]
    by_id = {str(item["id"]): item for item in memory_items}
    replacements: list[dict[str, object]] = []
    graph_edges = case.evidence_graph.get("edges", [])
    if isinstance(graph_edges, list):
        for edge in graph_edges:
            if not isinstance(edge, dict) or edge.get("type") != "supersedes":
                continue
            old_id = str(edge.get("from") or "")
            new_id = str(edge.get("to") or "")
            old = by_id.get(old_id, {})
            new = by_id.get(new_id, {})
            replacements.append(
                {
                    "old_item_id": old_id,
                    "new_item_id": new_id,
                    "old_memory_type": str(old.get("memory_type") or "preference"),
                    "new_memory_type": str(new.get("memory_type") or "preference"),
                    "old_summary": str(old.get("summary") or ""),
                    "new_summary": str(new.get("summary") or ""),
                    "old_source_ref": str(old.get("source_ref") or ""),
                    "new_source_ref": str(new.get("source_ref") or ""),
                }
            )
    return EvalCase(
        id=case.case_id,
        title=f"Memory Governance {case.case_id}",
        category=f"memory_governance_{case.scenario}",
        phase_targets=EVAL_PHASE_TARGETS,
        config_profiles=EVAL_CONFIG_PROFILES,
        setup={
            "scope": scope,
            "scenario_name": case.scenario,
            "measurement_family": "memory_governance",
            "target_profile": "memory_governance_p1_p4",
            "query": case.user_question,
            "memory_items": memory_items,
            "memory_replacements": replacements,
        },
        expectations={
            "should_recall_ids": list(case.should_recall_ids),
            "should_not_recall_ids": list(case.should_not_recall_ids),
            "expected_trace_features": [
                "tri_retrieval",
                "injection_governance_shadow",
                "version_chain_shadow",
            ],
            "expected_metric_keys": {
                "tri_retrieval": [
                    "semantic_hit_count",
                    "fused_hit_count",
                    "retrieval_latency_ms",
                ]
            },
            "expected_active_version_ids": list(case.should_recall_ids),
            "expected_stale_version_ids": list(case.should_not_recall_ids),
            "profile_expectations": dict(case.profile_expectations),
            "answer_expectations": {
                "expected_answer_contains": list(case.expected_answer_contains),
                "expected_answer_contains_any": [
                    list(group) for group in case.expected_answer_contains_any
                ],
                "forbidden_answer_contains": list(case.forbidden_answer_contains),
                "expected_memory_ids": list(case.should_recall_ids),
                "expected_language": "zh",
                "grounding_required": True,
            },
        },
        source_path="memory_governance_dataset",
    )


def _memory_item_for_eval(
    case: MemoryGovernanceEvalCase,
    memory: dict[str, Any],
    scope: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": str(memory.get("id") or ""),
        "memory_type": str(memory.get("memory_type") or "preference"),
        "summary": str(memory.get("summary") or memory.get("content") or ""),
        "content": str(memory.get("content") or memory.get("summary") or ""),
        "status": str(memory.get("status") or "active"),
        "source_ref": str(memory.get("source_ref") or f"eval://{case.case_id}"),
        "confidence": str(memory.get("confidence") or "medium"),
        "relative_timestamp_days": memory.get("relative_timestamp_days"),
        "scope_channel": scope["channel"],
        "scope_chat_id": scope["chat_id"],
        "extra_json": {
            "scenario": case.scenario,
            "relative_timestamp_days": memory.get("relative_timestamp_days"),
        },
    }


def _case_from_payload(payload: dict[str, Any]) -> MemoryGovernanceEvalCase:
    return MemoryGovernanceEvalCase(
        case_id=str(payload.get("case_id") or ""),
        scenario=str(payload.get("scenario") or ""),
        user_question=str(payload.get("user_question") or ""),
        eval_base_time=str(payload.get("eval_base_time") or ""),
        memories=tuple(dict(item) for item in payload.get("memories", ())),
        should_recall_ids=_string_tuple(payload.get("should_recall_ids")),
        should_not_recall_ids=_string_tuple(payload.get("should_not_recall_ids")),
        expected_answer_contains=_string_tuple(
            payload.get("expected_answer_contains")
        ),
        expected_answer_contains_any=tuple(
            _string_tuple(group)
            for group in payload.get("expected_answer_contains_any", ())
        ),
        forbidden_answer_contains=_string_tuple(
            payload.get("forbidden_answer_contains")
        ),
        evidence_graph=dict(payload.get("evidence_graph") or {}),
        profile_expectations={
            str(key): str(value)
            for key, value in dict(payload.get("profile_expectations") or {}).items()
        },
        notes=str(payload.get("notes") or ""),
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item))


def _has_cycle(adjacency: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in adjacency.get(node, ()):
            if visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in adjacency)
