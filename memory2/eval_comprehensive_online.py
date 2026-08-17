from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock

from agent.looping.core import AgentLoop
from agent.looping.ports import AgentLoopConfig, AgentLoopDeps, LLMConfig, MemoryServices
from agent.tools.registry import ToolRegistry
from bus.event_bus import EventBus
from core.memory.engine import (
    ExplicitRetrievalRequest,
    ExplicitRetrievalResult,
    ForgetRequest,
    ForgetResult,
    InterestRetrievalRequest,
    InterestRetrievalResult,
    MemoryEngineRetrieveRequest,
    MemoryEngineRetrieveResult,
    MemoryHit,
    MemoryIngestRequest,
    MemoryIngestResult,
    RememberRequest,
    RememberResult,
)
from memory2.eval_cases import EvalCase
from memory2.eval_llm_sample import (
    AnswerExpectation,
    LLMSampleAnswerDebugRecord,
    _extract_token_counts,
    _memory_summaries_by_id,
    _query,
    _RecordingProvider,
    _scope,
    answer_expectation_from_case,
    score_answer_text,
    write_llm_sample_answer_debug,
)
from memory2.eval_answer_contract import (
    build_production_governed_tri_evidence_contract,
    build_tri_answer_contract,
    build_version_boundary_info,
    render_answer_contract_block,
    render_production_evidence_contract_block,
    tri_answer_contract_evidence_ids,
)
from memory2.eval_answer_post_check import (
    answer_post_check_shadow_to_dict,
    build_answer_post_check_shadow,
)
from memory2.eval_memory_governance_profiles import (
    MEMORY_GOVERNANCE_PROFILE_ORDER,
    render_structured_evidence_only_block,
)
from memory2.eval_memory_governance_dataset import (
    memory_governance_case_to_eval_case,
)
from memory2.eval_runner import _baseline_recalled_items
from memory2.eval_quantitative_uplift import (
    BALANCED_SCORE_FORMULA,
    CHAIN_REPORT_PROFILES,
    CHAIN_PROFILES,
    QuantitativeProfileSummary,
    _family_trace_for_case,
    calculate_balanced_scores,
    calculate_main_score,
)
from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_retrieval_route,
    build_retrieval_routing_decision,
)
from session.manager import SessionManager


_FIXED_REPORT_TIME = datetime(2026, 7, 19, tzinfo=timezone.utc)

COMPREHENSIVE_CHAIN_PROFILES: tuple[str, ...] = CHAIN_REPORT_PROFILES
ANSWER_QUALITY_PROFILES: tuple[str, ...] = (
    "chain_memory_base",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_all_on",
)
TRI_CANDIDATE_GOVERNANCE_PROFILE = "chain_tri_candidate_governance"
TRI_EVIDENCE_ONLY_PROFILE = "chain_tri_evidence_only"
TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_answer_contract"
TRI_GOVERNED_ANSWER_CONTRACT_PROFILE = "chain_tri_governed_answer_contract"
TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE = (
    "chain_tri_rerank_governed_answer_contract"
)
TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE = (
    "chain_tri_version_governed_answer_contract"
)
TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE = (
    "chain_tri_rerank_version_governed_answer_contract"
)
PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES: tuple[str, ...] = (
    TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
)
OPTIONAL_ANSWER_QUALITY_PROFILES: tuple[str, ...] = (
    TRI_CANDIDATE_GOVERNANCE_PROFILE,
    TRI_EVIDENCE_ONLY_PROFILE,
    TRI_ANSWER_CONTRACT_PROFILE,
    TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
)
PROFILE_METADATA: dict[str, dict[str, object]] = {
    TRI_CANDIDATE_GOVERNANCE_PROFILE: {
        "eval_only": True,
        "oracle_protected": True,
        "uses_fixture_expected_ids": True,
        "candidate_governance_mode": "tiered",
        "description": (
            "Applies risk-tiered candidate governance to existing tri fused "
            "ids while protecting fixture should_recall_ids."
        ),
    },
    TRI_EVIDENCE_ONLY_PROFILE: {
        "eval_only": True,
        "oracle_protected": True,
        "uses_fixture_expected_ids": True,
        "candidate_governance_mode": "tiered",
        "combines_candidate_governance": True,
        "structured_evidence_only": True,
        "diagnostic_answer_contract": False,
        "production_safe_evidence_contract": False,
        "description": (
            "Applies candidate governance and renders structured evidence "
            "sections, without answer-contract instructions."
        ),
    },
    TRI_ANSWER_CONTRACT_PROFILE: {
        "eval_only": True,
        "diagnostic_answer_contract": True,
        "uses_fixture_answer_expectations": True,
        "description": (
            "Renders a structured answer contract over existing tri fused ids "
            "to test whether answer constraints improve grounded tri retrieval."
        ),
    },
    TRI_GOVERNED_ANSWER_CONTRACT_PROFILE: {
        "eval_only": True,
        "oracle_protected": True,
        "uses_fixture_expected_ids": True,
        "diagnostic_answer_contract": True,
        "uses_fixture_answer_expectations": False,
        "production_safe_evidence_contract": True,
        "combines_candidate_governance": True,
        "candidate_governance_mode": "tiered",
        "description": (
            "Combines candidate-governed tri ids with a production-safe "
            "evidence contract to test whether input filtering plus evidence "
            "boundaries can preserve answer quality while reducing forbidden risk."
        ),
    },
    TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE: {
        "eval_only": True,
        "oracle_protected": True,
        "uses_fixture_expected_ids": True,
        "diagnostic_answer_contract": True,
        "uses_fixture_answer_expectations": False,
        "production_safe_evidence_contract": True,
        "combines_candidate_governance": True,
        "combines_rerank_injection": True,
        "does_not_expand_recall": True,
        "candidate_governance_mode": "tiered",
        "description": (
            "Reorders candidate-governed tri ids with the existing "
            "rerank/injection signal, without adding ids outside governed tri "
            "evidence, then renders a production-safe evidence contract."
        ),
    },
    TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: {
        "eval_only": True,
        "oracle_protected": True,
        "uses_fixture_expected_ids": True,
        "diagnostic_answer_contract": True,
        "uses_fixture_answer_expectations": False,
        "production_safe_evidence_contract": True,
        "combines_candidate_governance": True,
        "combines_version_boundary": True,
        "does_not_expand_recall": True,
        "candidate_governance_mode": "tiered",
        "description": (
            "Keeps candidate-governed tri allowed ids unchanged and adds "
            "version-boundary fields for active versions, stale/superseded "
            "warnings, conflict warnings, and forbidden boundaries."
        ),
    },
    TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: {
        "eval_only": True,
        "oracle_protected": True,
        "uses_fixture_expected_ids": True,
        "diagnostic_answer_contract": True,
        "uses_fixture_answer_expectations": False,
        "production_safe_evidence_contract": True,
        "combines_candidate_governance": True,
        "combines_rerank_injection": True,
        "combines_version_boundary": True,
        "does_not_expand_recall": True,
        "candidate_governance_mode": "tiered",
        "description": (
            "Reorders candidate-governed tri evidence with rerank signal and "
            "adds safe version-boundary metadata without recall expansion."
        ),
    },
}
METRIC_SOURCES: dict[str, str] = {
    "online_answer_level": "real AgentLoop answer scoring",
    "online_balanced_proxy": "online answer-level fields converted into balanced proxy dimensions",
    "offline_retrieval_proxy": "existing offline trace retrieval metrics",
    "real_db_readonly_sampling_background": "aggregate-only real memory DB sampling status",
}


@dataclass(frozen=True)
class ComprehensiveRunSpec:
    case: EvalCase
    profile_name: str
    prompt_variant: str
    repeat_index: int


@dataclass(frozen=True)
class ComprehensiveCaseResult:
    case_id: str
    category: str
    profile_name: str
    prompt_variant: str
    repeat_index: int
    passed: bool
    answer_rule_passed: bool
    memory_grounding_passed: bool
    expected_memory_used: bool
    forbidden_contains_violation_count: int
    latency_ms: int
    prompt_token_count: int
    completion_token_count: int
    total_token_count: int
    token_metrics_available: bool
    provider_error: bool
    timeout: bool
    answer_length: int
    evidence_source: str
    used_memory_id_count: int
    failures: tuple[str, ...]
    answer_post_check_shadow: dict[str, object] | None = None
    evidence_render_metadata: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class ComprehensiveOnlineReport:
    run_id: str
    generated_at: str
    cases: tuple[ComprehensiveCaseResult, ...]
    case_records: tuple[dict[str, object], ...]
    failure_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def infra_passed(self) -> bool:
        return bool(self.cases) and all(
            not case.provider_error and not case.timeout for case in self.cases
        )


@dataclass(frozen=True)
class EvalRunProvenance:
    command_shape_hash: str
    dataset_path: str = ""
    profile_ladder: str = ""
    provider_name: str = ""
    model: str = ""
    config_hash: str = ""
    git_commit: str = ""
    real_llm_enabled: bool = False
    fake_provider_enabled: bool = False


@dataclass(frozen=True)
class _CheckpointLoadResult:
    rows: tuple[tuple[str, ComprehensiveCaseResult], ...]
    malformed_line_count: int
    provenance_mismatch_count: int


class ComprehensiveOnlineMemoryEngine:
    def __init__(
        self,
        case: EvalCase,
        *,
        profile_name: str,
        prompt_variant: str,
    ) -> None:
        if prompt_variant not in {"baseline", "coached"}:
            raise ValueError("prompt_variant must be 'baseline' or 'coached'")
        self.case = case
        self.profile_name = profile_name
        self.prompt_variant = prompt_variant
        self.retrieve_requests: list[MemoryEngineRetrieveRequest] = []
        self.used_memory_ids: list[str] = []
        self.last_text_block = ""
        self.last_raw: dict[str, object] = {}

    async def retrieve(
        self,
        request: MemoryEngineRetrieveRequest,
    ) -> MemoryEngineRetrieveResult:
        self.retrieve_requests.append(request)
        governed_trace: dict[str, object] | None = None
        if self.profile_name in {
            TRI_CANDIDATE_GOVERNANCE_PROFILE,
            TRI_EVIDENCE_ONLY_PROFILE,
            TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
            TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
            TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
            TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
        }:
            governed_trace = (
                rerank_version_governed_tri_trace_for_case(self.case)
                if self.profile_name
                == TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE
                else
                version_governed_tri_trace_for_case(self.case)
                if self.profile_name == TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE
                else rerank_governed_tri_trace_for_case(self.case)
                if self.profile_name == TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE
                else governed_tri_trace_for_case(self.case)
            )
            ids = list(tuple(governed_trace.get("ids", ())))
        if self.profile_name == TRI_EVIDENCE_ONLY_PROFILE:
            assert governed_trace is not None
            summaries = _memory_summaries_by_id(self.case)
            should_not_ids = {
                str(item) for item in self.case.expectations.get("should_not_recall_ids", ())
            }
            memory_items = [
                dict(item)
                for item in self.case.setup.get("memory_items", ())
                if isinstance(item, dict)
            ]
            by_id = {
                str(item.get("id") or item.get("memory_id") or ""): item
                for item in memory_items
            }
            allowed_evidence = [
                {
                    "id": item_id,
                    "summary": summaries.get(item_id, ""),
                    "status": by_id.get(item_id, {}).get("status", ""),
                    "confidence": by_id.get(item_id, {}).get("confidence", ""),
                }
                for item_id in ids
            ]
            forbidden_evidence = [
                {
                    "id": item_id,
                    "summary": summaries.get(item_id, ""),
                    "status": by_id.get(item_id, {}).get("status", ""),
                    "confidence": by_id.get(item_id, {}).get("confidence", ""),
                }
                for item_id in should_not_ids
                if item_id in by_id
            ]
            version_boundaries = [
                dict(item)
                for item in self.case.setup.get("memory_replacements", ())
                if isinstance(item, dict)
            ]
            self.used_memory_ids = ids
            hits = [
                MemoryHit(
                    id=item_id,
                    summary=summaries.get(item_id, ""),
                    content=summaries.get(item_id, ""),
                    score=1.0,
                    source_ref="",
                    engine_kind="comprehensive_online_eval",
                    injected=True,
                )
                for item_id in ids
            ]
            self.last_text_block = render_structured_evidence_only_block(
                allowed_evidence=allowed_evidence,
                forbidden_evidence=forbidden_evidence,
                conflict_evidence=[],
                version_boundaries=version_boundaries,
            )
            trace = dict(governed_trace.get("trace", {}))
            raw = {
                "ids": ids,
                "evidence_source": profile_evidence_source(self.profile_name),
                "candidate_governance_mode": trace.get("candidate_governance_mode"),
                "candidate_risk_tier_counts": trace.get(
                    "candidate_risk_tier_counts",
                    {},
                ),
                "accepted_candidate_risk_tier_counts": trace.get(
                    "accepted_candidate_risk_tier_counts",
                    {},
                ),
                "tiered_deleted_risks_by_reason": trace.get(
                    "tiered_deleted_risks_by_reason",
                    {},
                ),
                "structured_evidence_only": True,
                "answer_contract": None,
            }
            self.last_raw = dict(raw)
            return MemoryEngineRetrieveResult(
                text_block=self.last_text_block,
                hits=hits,
                raw=raw,
            )
        else:
            ids = list(evidence_ids_for_profile(self.case, self.profile_name))
        if (
            self.profile_name == TRI_ANSWER_CONTRACT_PROFILE
            or self.profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES
        ):
            if self.profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES:
                assert governed_trace is not None
                trace = dict(governed_trace.get("trace", {}))
                version_boundary_info = (
                    build_version_boundary_info(self.case, governed_trace)
                    if self.profile_name
                    in {
                        TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
                        TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
                    }
                    else None
                )
                contract = build_production_governed_tri_evidence_contract(
                    self.case,
                    governed_trace,
                    profile_name=self.profile_name,
                    version_boundary_info=version_boundary_info,
                )
                combines_candidate_governance = True
                combines_rerank_injection = (
                    self.profile_name
                    in {
                        TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
                        TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
                    }
                )
                combines_version_boundary = (
                    self.profile_name
                    in {
                        TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
                        TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
                    }
                )
                does_not_expand_recall = (
                    self.profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES
                )
                self.used_memory_ids = list(contract.allowed_evidence_ids)
                hits = [
                    MemoryHit(
                        id=item_id,
                        summary=summary,
                        content=summary,
                        score=1.0,
                        source_ref="",
                        engine_kind="comprehensive_online_eval",
                        injected=True,
                    )
                    for item_id, summary in contract.evidence_summaries
                ]
                self.last_text_block = render_production_evidence_contract_block(contract)
                raw = {
                    "ids": list(contract.allowed_evidence_ids),
                    "evidence_source": profile_evidence_source(self.profile_name),
                    "candidate_governance_mode": trace.get(
                        "candidate_governance_mode"
                    ),
                    "candidate_risk_tier_counts": trace.get(
                        "candidate_risk_tier_counts",
                        {},
                    ),
                    "accepted_candidate_risk_tier_counts": trace.get(
                        "accepted_candidate_risk_tier_counts",
                        {},
                    ),
                    "tiered_deleted_risks_by_reason": trace.get(
                        "tiered_deleted_risks_by_reason",
                        {},
                    ),
                    "candidate_risk_tiers": trace.get("candidate_risk_tiers", []),
                    "combines_rerank_injection": combines_rerank_injection,
                    "combines_version_boundary": combines_version_boundary,
                    "rerank_signal": trace.get("rerank_signal", {}),
                    "version_boundary": trace.get("version_boundary", {}),
                    "answer_contract": {
                        "diagnostic_eval_only": contract.diagnostic_eval_only,
                        "production_safe": contract.production_safe,
                        "production_safe_evidence_contract": True,
                        "uses_fixture_answer_expectations": (
                            contract.uses_fixture_answer_expectations
                        ),
                        "combines_candidate_governance": combines_candidate_governance,
                        "combines_rerank_injection": combines_rerank_injection,
                        "combines_version_boundary": combines_version_boundary,
                        "does_not_expand_recall": does_not_expand_recall,
                        "candidate_governance_mode": contract.candidate_governance_mode,
                        "allowed_evidence": list(contract.allowed_evidence),
                        "likely_relevant_evidence": list(
                            contract.likely_relevant_evidence
                        ),
                        "stale_warning": list(contract.stale_warning),
                        "conflict_warning": list(contract.conflict_warning),
                        "active_version": list(contract.active_version),
                        "forbidden_boundary": list(contract.forbidden_boundary),
                        "allowed_evidence_ids": list(contract.allowed_evidence_ids),
                        "likely_relevant_evidence_ids": list(
                            contract.likely_relevant_evidence_ids
                        ),
                        "downgrade_ids": list(contract.downgrade_ids),
                        "requires_review_ids": list(contract.requires_review_ids),
                        "stale_warning_ids": list(contract.stale_warning_ids),
                        "conflict_warning_ids": list(contract.conflict_warning_ids),
                        "active_version_ids": list(contract.active_version_ids),
                        "insufficient_evidence_ids": list(
                            contract.insufficient_evidence_ids
                        ),
                        "insufficient_evidence_fallback": (
                            contract.insufficient_evidence_fallback
                        ),
                        "forbidden_boundary_ids": list(contract.forbidden_boundary_ids),
                        "deleted_evidence_ids": list(contract.deleted_evidence_ids),
                        "evidence_render_metadata": list(
                            contract.evidence_render_metadata
                        ),
                        "public_long_memory_eval": contract.public_long_memory_eval,
                    },
                }
                self.last_raw = dict(raw)
                return MemoryEngineRetrieveResult(
                    text_block=self.last_text_block,
                    hits=hits,
                    raw=raw,
                )
            else:
                trace = {}
                contract = build_tri_answer_contract(self.case)
                combines_candidate_governance = False
            self.used_memory_ids = list(contract.allowed_evidence_ids)
            hits = [
                MemoryHit(
                    id=item_id,
                    summary=summary,
                    content=summary,
                    score=1.0,
                    source_ref="",
                    engine_kind="comprehensive_online_eval",
                    injected=True,
                )
                for item_id, summary in contract.evidence_summaries
            ]
            self.last_text_block = render_answer_contract_block(contract)
            raw: dict[str, object] = {
                "ids": list(contract.allowed_evidence_ids),
                "must_use_ids": list(contract.must_use_ids),
                "forbidden_ids": list(contract.forbidden_ids),
                "governance_dropped_ids": list(contract.governance_dropped_ids),
                "evidence_source": profile_evidence_source(self.profile_name),
                "answer_contract": {
                    "diagnostic_eval_only": contract.diagnostic_eval_only,
                    "combines_candidate_governance": combines_candidate_governance,
                    "candidate_governance_mode": (
                        "tiered" if combines_candidate_governance else "none"
                    ),
                    "required_terms": list(contract.required_terms),
                    "required_term_groups": [
                        list(group) for group in contract.required_term_groups
                    ],
                    "forbidden_terms": list(contract.forbidden_terms),
                },
            }
            if self.profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE:
                raw.update(
                    {
                        "candidate_governance_mode": trace.get(
                            "candidate_governance_mode"
                        ),
                        "candidate_risk_tier_counts": trace.get(
                            "candidate_risk_tier_counts",
                            {},
                        ),
                        "accepted_candidate_risk_tier_counts": trace.get(
                            "accepted_candidate_risk_tier_counts",
                            {},
                        ),
                        "tiered_deleted_risks_by_reason": trace.get(
                            "tiered_deleted_risks_by_reason",
                            {},
                        ),
                        "candidate_risk_tiers": trace.get("candidate_risk_tiers", []),
                    }
                )
            self.last_raw = dict(raw)
            return MemoryEngineRetrieveResult(
                text_block=self.last_text_block,
                hits=hits,
                raw=raw,
            )
        summaries = _memory_summaries_by_id(self.case)
        self.used_memory_ids = ids
        hits = [
            MemoryHit(
                id=item_id,
                summary=summaries.get(item_id, ""),
                content=summaries.get(item_id, ""),
                score=1.0,
                source_ref="",
                engine_kind="comprehensive_online_eval",
                injected=True,
            )
            for item_id in ids
        ]
        lines = [
            f"- memory_id={item_id}; summary={summaries.get(item_id, '')}"
            for item_id in ids
        ]
        if self.prompt_variant == "coached" and lines:
            lines.insert(
                0,
                "记忆评测说明：请优先使用下列记忆回答；"
                "如果记忆包含具体方案名、排序方式、工具名或关键术语，"
                "请在答案中保留这些关键术语。",
            )
        self.last_text_block = "\n".join(lines)
        raw: dict[str, object] = {
            "ids": ids,
            "evidence_source": profile_evidence_source(self.profile_name),
        }
        if self.profile_name == TRI_CANDIDATE_GOVERNANCE_PROFILE:
            assert governed_trace is not None
            trace = dict(governed_trace.get("trace", {}))
            raw.update(
                {
                    "candidate_governance_mode": trace.get(
                        "candidate_governance_mode"
                    ),
                    "candidate_risk_tier_counts": trace.get(
                        "candidate_risk_tier_counts",
                        {},
                    ),
                    "accepted_candidate_risk_tier_counts": trace.get(
                        "accepted_candidate_risk_tier_counts",
                        {},
                    ),
                    "tiered_deleted_risks_by_reason": trace.get(
                        "tiered_deleted_risks_by_reason",
                        {},
                    ),
                    "candidate_risk_tiers": trace.get("candidate_risk_tiers", []),
                }
            )
        self.last_raw = dict(raw)
        return MemoryEngineRetrieveResult(
            text_block=self.last_text_block,
            hits=hits,
            raw=raw,
        )

    async def retrieve_explicit(
        self,
        request: ExplicitRetrievalRequest,
    ) -> ExplicitRetrievalResult:
        return ExplicitRetrievalResult()

    async def retrieve_interest_block(
        self,
        request: InterestRetrievalRequest,
    ) -> InterestRetrievalResult:
        return InterestRetrievalResult()

    async def remember(self, request: RememberRequest) -> RememberResult:
        return RememberResult(item_id="comprehensive-online-memory", actual_type=request.memory_type)

    async def forget(self, request: ForgetRequest) -> ForgetResult:
        return ForgetResult(missing_ids=list(request.ids))

    async def ingest(self, request: MemoryIngestRequest) -> MemoryIngestResult:
        return MemoryIngestResult(accepted=True)

    async def refresh_recent_turns(self, request: object) -> None:
        return None

    async def consolidate(self, request: object) -> object:
        return None

    def read_self(self) -> str:
        return ""

    def read_recent_context(self) -> str:
        return ""

    def get_memory_context(self) -> str:
        return ""

    def has_long_term_memory(self) -> bool:
        return False


def evidence_ids_for_profile(case: EvalCase, profile_name: str) -> tuple[str, ...]:
    if profile_name == "chain_off":
        return ()
    if profile_name == "chain_memory_base":
        return tuple(str(item.get("id") or "") for item in _baseline_recalled_items(case))
    if profile_name == "chain_write_value":
        return ()
    if profile_name == TRI_CANDIDATE_GOVERNANCE_PROFILE:
        return governed_tri_evidence_ids_for_case(case)
    if profile_name == TRI_EVIDENCE_ONLY_PROFILE:
        return governed_tri_evidence_ids_for_case(case)
    if profile_name == TRI_ANSWER_CONTRACT_PROFILE:
        return tri_answer_contract_evidence_ids(case)
    if profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE:
        return governed_tri_evidence_ids_for_case(case)
    if profile_name == TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE:
        return tuple(rerank_governed_tri_trace_for_case(case).get("ids", ()))
    if profile_name == TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE:
        return tuple(version_governed_tri_trace_for_case(case).get("ids", ()))
    if profile_name == TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE:
        return tuple(rerank_version_governed_tri_trace_for_case(case).get("ids", ()))
    if profile_name not in COMPREHENSIVE_CHAIN_PROFILES:
        raise ValueError(f"unknown profile_name: {profile_name}")
    if profile_name == "chain_tri_retrieval":
        return _ids_from_trace(case, "tri_retrieval", "fused_ids")
    if profile_name == "chain_graph_retrieval":
        return _ids_from_trace(case, "graph_retrieval", "graph_fused_ids")
    if profile_name == "chain_rerank_injection":
        return _ids_from_trace(
            case,
            "injection_governance_shadow",
            "experimental_injected_ids",
        )
    if profile_name == "chain_version_provenance":
        return _ids_from_trace(case, "version_chain_shadow", "active_leaf_ids")
    if profile_name in {"chain_sleep_consolidation", "chain_all_on"}:
        return _sleep_filtered_ids(case)
    return ()


def governed_tri_evidence_ids_for_case(case: EvalCase) -> tuple[str, ...]:
    return tuple(governed_tri_trace_for_case(case).get("ids", ()))


def governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    tri_ids = tuple(_ids_from_trace(case, "tri_retrieval", "fused_ids"))
    if not tri_ids:
        return {"ids": (), "trace": {}}
    expected_ids = tuple(
        str(item) for item in case.expectations.get("should_recall_ids", ())
    )
    should_not_ids = {
        str(item) for item in case.expectations.get("should_not_recall_ids", ())
    }
    candidates = _ordered_candidates_for_governed_tri(case, tri_ids, should_not_ids)
    decision = build_retrieval_routing_decision(str(case.setup.get("query") or ""))
    decision = replace(
        decision,
        allowed_lanes=("semantic",),
        max_per_lane={"semantic": max(len(candidates), 1)},
        require_source_ref=False,
        require_scope_match=False,
        graph_enabled=False,
    )
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(
            enabled=True,
            mode="tiered",
            protected_expected_ids=expected_ids,
        )
    )
    governed, trace = apply_retrieval_route(decision, {"semantic": candidates})
    ids = tuple(
        str(candidate.get("id") or candidate.get("memory_id") or "")
        for candidate in governed
        if candidate.get("id") or candidate.get("memory_id")
    )
    return {"ids": ids, "trace": trace}


def rerank_governed_evidence_order(
    governed_ids: Sequence[str],
    rerank_ids: Sequence[str],
) -> tuple[str, ...]:
    governed = tuple(str(item_id) for item_id in governed_ids if str(item_id))
    governed_set = set(governed)
    rerank = tuple(str(item_id) for item_id in rerank_ids if str(item_id))
    rerank_set = set(rerank)
    return tuple(
        [item_id for item_id in rerank if item_id in governed_set]
        + [item_id for item_id in governed if item_id not in rerank_set]
    )


def rerank_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    governed_trace = governed_tri_trace_for_case(case)
    governed_ids = tuple(str(item) for item in governed_trace.get("ids", ()))
    if not governed_ids:
        trace = dict(governed_trace.get("trace", {}))
        trace["rerank_signal"] = {
            "rerank_profile": "chain_rerank_injection",
            "rerank_ids": [],
            "reranked_governed_ids": [],
            "recall_expanded": False,
            "reordered_count": 0,
        }
        return {"ids": (), "trace": trace}
    rerank_ids = tuple(evidence_ids_for_profile(case, "chain_rerank_injection"))
    governed_set = set(governed_ids)
    ordered_ids = rerank_governed_evidence_order(governed_ids, rerank_ids)
    trace = dict(governed_trace.get("trace", {}))
    trace["rerank_signal"] = {
        "rerank_profile": "chain_rerank_injection",
        "rerank_ids": list(rerank_ids),
        "reranked_governed_ids": list(ordered_ids),
        "recall_expanded": bool(set(ordered_ids) - governed_set),
        "reordered_count": sum(
            1
            for index, item_id in enumerate(ordered_ids)
            if index >= len(governed_ids) or governed_ids[index] != item_id
        ),
    }
    return {"ids": ordered_ids, "trace": trace}


def version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    governed_trace = governed_tri_trace_for_case(case)
    governed_ids = tuple(str(item) for item in governed_trace.get("ids", ()))
    boundary = build_version_boundary_info(case, governed_trace)
    trace = dict(governed_trace.get("trace", {}))
    trace["version_boundary"] = {
        "active_version_ids": list(boundary.active_version_ids),
        "stale_warning_ids": list(boundary.stale_warning_ids),
        "conflict_warning_ids": list(boundary.conflict_warning_ids),
        "forbidden_boundary_ids": list(boundary.forbidden_boundary_ids),
        "rollback_candidate_ids": list(boundary.rollback_candidate_ids),
        "conflict_chain_count": boundary.conflict_chain_count,
        "stale_recalled_count": boundary.stale_recalled_count,
        "superseded_recalled_count": boundary.superseded_recalled_count,
        "recall_expanded": False,
    }
    return {"ids": governed_ids, "trace": trace}


def rerank_version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    trace_info = rerank_governed_tri_trace_for_case(case)
    ids = tuple(str(item) for item in trace_info.get("ids", ()))
    boundary = build_version_boundary_info(case, trace_info)
    trace = dict(trace_info.get("trace", {}))
    trace["version_boundary"] = {
        "active_version_ids": list(boundary.active_version_ids),
        "stale_warning_ids": list(boundary.stale_warning_ids),
        "conflict_warning_ids": list(boundary.conflict_warning_ids),
        "forbidden_boundary_ids": list(boundary.forbidden_boundary_ids),
        "rollback_candidate_ids": list(boundary.rollback_candidate_ids),
        "conflict_chain_count": boundary.conflict_chain_count,
        "stale_recalled_count": boundary.stale_recalled_count,
        "superseded_recalled_count": boundary.superseded_recalled_count,
        "recall_expanded": False,
    }
    return {"ids": ids, "trace": trace}


def _ordered_candidates_for_governed_tri(
    case: EvalCase,
    tri_ids: tuple[str, ...],
    should_not_ids: set[str],
) -> list[dict[str, object]]:
    scope = dict(case.setup.get("scope") or {})
    by_id = {
        str(item.get("id") or item.get("memory_id") or ""): item
        for item in case.setup.get("memory_items", [])
        if isinstance(item, dict)
    }
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for item_id in tri_ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        item = by_id.get(item_id)
        if item is None:
            continue
        candidate = dict(item)
        candidate["scope_match"] = (
            str(candidate.get("scope_channel") or "")
            == str(scope.get("channel") or "")
            and str(candidate.get("scope_chat_id") or "")
            == str(scope.get("chat_id") or "")
        )
        candidate["should_not_recall"] = item_id in should_not_ids
        candidates.append(candidate)
    return candidates


def profile_evidence_source(profile_name: str) -> str:
    sources = {
        "chain_off": "none",
        "chain_memory_base": "original_memory_baseline",
        "chain_write_value": "none_write_policy_only",
        "chain_tri_retrieval": "tri_retrieval.fused_ids",
        "chain_graph_retrieval": "graph_retrieval.graph_fused_ids",
        "chain_rerank_injection": "injection_governance.experimental_injected_ids",
        "chain_version_provenance": "version_chain.active_leaf_ids",
        "chain_sleep_consolidation": "sleep_consolidation.filtered_active_ids",
        "chain_all_on": "sleep_consolidation.filtered_active_ids",
        TRI_CANDIDATE_GOVERNANCE_PROFILE: (
            "tri_candidate_governance.risk_tiered_allowed_ids"
        ),
        TRI_EVIDENCE_ONLY_PROFILE: (
            "tri_evidence_only.structured_governed_allowed_evidence_ids"
        ),
        TRI_ANSWER_CONTRACT_PROFILE: "tri_answer_contract.allowed_evidence_ids",
        TRI_GOVERNED_ANSWER_CONTRACT_PROFILE: (
            "tri_governed_answer_contract.governed_allowed_evidence_ids"
        ),
        TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE: (
            "tri_rerank_governed_answer_contract."
            "reranked_governed_allowed_evidence_ids"
        ),
        TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: (
            "tri_version_governed_answer_contract."
            "version_boundaried_governed_allowed_evidence_ids"
        ),
        TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: (
            "tri_rerank_version_governed_answer_contract."
            "reranked_version_boundaried_governed_allowed_evidence_ids"
        ),
    }
    if profile_name not in sources:
        raise ValueError(f"unknown profile_name: {profile_name}")
    return sources[profile_name]


def answer_expectation_for_profile(
    case: EvalCase,
    profile_name: str,
) -> AnswerExpectation:
    expectation = answer_expectation_from_case(case)
    if profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES:
        governed_ids = evidence_ids_for_profile(case, profile_name)
        return AnswerExpectation(
            expected_memory_ids=governed_ids,
            expected_language=expectation.expected_language,
            grounding_required=bool(governed_ids),
        )
    if profile_name == "chain_version_provenance":
        active_ids = tuple(
            str(item_id)
            for item_id in case.expectations.get("expected_active_version_ids", ())
            if str(item_id)
        )
        if active_ids:
            return replace(expectation, expected_memory_ids=active_ids)
    return expectation


def build_comprehensive_run_specs(
    cases: Sequence[EvalCase],
    *,
    repeats: int,
    prompt_variants: Sequence[str],
    profiles: Sequence[str],
) -> tuple[ComprehensiveRunSpec, ...]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    valid_variants = {"baseline", "coached"}
    invalid_variants = [
        variant for variant in prompt_variants if variant not in valid_variants
    ]
    if invalid_variants:
        raise ValueError("unknown prompt_variant(s): " + ", ".join(invalid_variants))
    allowed_profiles = set(COMPREHENSIVE_CHAIN_PROFILES) | set(
        OPTIONAL_ANSWER_QUALITY_PROFILES
    )
    invalid_profiles = [profile for profile in profiles if profile not in allowed_profiles]
    if invalid_profiles:
        raise ValueError("unknown profile_name(s): " + ", ".join(invalid_profiles))
    answer_cases = [
        case
        for case in cases
        if isinstance(case.expectations.get("answer_expectations"), dict)
    ]
    specs: list[ComprehensiveRunSpec] = []
    for case in answer_cases:
        for repeat_index in range(repeats):
            for prompt_variant in prompt_variants:
                for profile_name in profiles:
                    specs.append(
                        ComprehensiveRunSpec(
                            case=case,
                            profile_name=profile_name,
                            prompt_variant=prompt_variant,
                            repeat_index=repeat_index,
                        )
                    )
    return tuple(specs)


async def run_comprehensive_online_eval(
    specs: Sequence[ComprehensiveRunSpec],
    workspace: Path,
    provider: object,
    model: str,
    *,
    timeout_s: float = 60.0,
    real_llm_enabled: bool = False,
    answer_debug_dir: Path | None = None,
    real_memory_sample_metrics: dict[str, object] | None = None,
    checkpoint_jsonl: Path | None = None,
    resume: bool = False,
    concurrency: int = 1,
    report_metadata: dict[str, object] | None = None,
    run_provenance: EvalRunProvenance | None = None,
    provider_request_debug_dir: Path | None = None,
) -> ComprehensiveOnlineReport:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    workspace.mkdir(parents=True, exist_ok=True)
    checkpoint_state = _load_checkpoint_rows(
        checkpoint_jsonl,
        command_shape_hash=run_provenance.command_shape_hash
        if resume and run_provenance is not None
        else None,
    )
    existing = (
        _checkpoint_results_from_rows(
            checkpoint_state.rows,
            include_infra_failures=False,
        )
        if resume
        else {}
    )
    results: list[ComprehensiveCaseResult] = list(existing.values())
    skipped = 0
    pending: list[tuple[int, ComprehensiveRunSpec, str]] = []
    for index, spec in enumerate(specs):
        key = _spec_key(spec)
        if key in existing:
            skipped += 1
            continue
        pending.append((index, spec, key))

    if concurrency == 1:
        for index, spec, key in pending:
            result = await _run_comprehensive_case(
                spec,
                workspace
                / f"case-{index:04d}-{_safe_name(spec.profile_name)}-{_safe_name(spec.prompt_variant)}-{_safe_name(spec.case.id)}",
                provider,
                model,
                timeout_s=timeout_s,
                case_index=index,
                answer_debug_dir=answer_debug_dir,
                provider_request_debug_dir=provider_request_debug_dir,
            )
            results.append(result)
            _append_checkpoint_result(checkpoint_jsonl, key, result, run_provenance)
    else:
        semaphore = asyncio.Semaphore(concurrency)

        async def run_pending(
            index: int,
            pending_spec: ComprehensiveRunSpec,
            pending_key: str,
        ) -> tuple[str, ComprehensiveCaseResult]:
            async with semaphore:
                return (
                    pending_key,
                    await _run_comprehensive_case(
                        pending_spec,
                        workspace
                        / f"case-{index:04d}-{_safe_name(pending_spec.profile_name)}-{_safe_name(pending_spec.prompt_variant)}-{_safe_name(pending_spec.case.id)}",
                        provider,
                        model,
                        timeout_s=timeout_s,
                        case_index=index,
                        answer_debug_dir=answer_debug_dir,
                        provider_request_debug_dir=provider_request_debug_dir,
                    ),
                )

        tasks = [
            asyncio.create_task(run_pending(index, spec, key))
            for index, spec, key in pending
        ]
        for task in asyncio.as_completed(tasks):
            key, result = await task
            results.append(result)
            _append_checkpoint_result(checkpoint_jsonl, key, result, run_provenance)
    return _build_comprehensive_report(
        tuple(results),
        real_llm_enabled=real_llm_enabled,
        completed_call_count=len(results),
        skipped_from_checkpoint_count=skipped,
        real_memory_sample_metrics=real_memory_sample_metrics or {},
        concurrency=concurrency,
        report_metadata=report_metadata or {},
        malformed_checkpoint_line_count=checkpoint_state.malformed_line_count,
        checkpoint_provenance_mismatch_count=(
            checkpoint_state.provenance_mismatch_count if resume else 0
        ),
    )


def build_gated_comprehensive_online_report(
    reason: str,
    *,
    real_memory_sample_metrics: dict[str, object] | None = None,
) -> ComprehensiveOnlineReport:
    metrics = _empty_metrics(real_memory_sample_metrics or {})
    metrics["gate_reason"] = reason
    return ComprehensiveOnlineReport(
        run_id=_deterministic_run_id(()),
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        cases=(),
        case_records=(),
        failure_records=({"case_id": "", "failure": reason},),
        metrics=metrics,
    )


def build_comprehensive_online_report_from_checkpoint(
    checkpoint_jsonl: Path,
    *,
    real_llm_enabled: bool,
    exclude_infra_failures: bool = False,
    real_memory_sample_metrics: dict[str, object] | None = None,
    command_shape_hash: str | None = None,
) -> ComprehensiveOnlineReport:
    checkpoint_state = _load_checkpoint_rows(
        checkpoint_jsonl,
        command_shape_hash=command_shape_hash,
    )
    rows = checkpoint_state.rows
    input_count = len(rows)
    loaded = _checkpoint_results_from_rows(rows, include_infra_failures=True)
    results = tuple(loaded.values())
    excluded = 0
    if exclude_infra_failures:
        excluded = sum(
            1 for _key, result in rows if result.timeout or result.provider_error
        )
        kept: dict[str, ComprehensiveCaseResult] = {}
        for key, result in rows:
            if result.timeout or result.provider_error:
                continue
            kept[key] = result
        results = tuple(kept.values())
    report = _build_comprehensive_report(
        results,
        real_llm_enabled=real_llm_enabled,
        completed_call_count=len(results),
        skipped_from_checkpoint_count=0,
        real_memory_sample_metrics=real_memory_sample_metrics or {},
        malformed_checkpoint_line_count=checkpoint_state.malformed_line_count,
        checkpoint_provenance_mismatch_count=(
            checkpoint_state.provenance_mismatch_count
        ),
    )
    report.metrics["checkpoint_input_count"] = input_count
    report.metrics["excluded_infra_failure_count"] = excluded
    report.metrics["partial_due_to_infra_failure"] = bool(excluded)
    report.metrics["checkpoint_report_only"] = True
    report.metrics["concurrency"] = "checkpoint_report_only"
    return report


def write_comprehensive_online_json(
    report: ComprehensiveOnlineReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _report_to_dict(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def write_comprehensive_online_markdown(
    report: ComprehensiveOnlineReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = report.metrics
    lines = [
        "# Memory 综合线上评测报告",
        "",
        "本报告使用真实 AgentLoop 的 answer-level 评测链路；如开启真实 LLM，则会记录真实模型回答的规则命中、记忆 grounding、token 和延迟。它不是生产回答准确率。",
        "",
        "## 边界",
        "",
        "- 常规报告不包含原始 query、memory summary、prompt、session 原文或完整回答。",
        "- 真实 memory DB 只读采样只进入聚合指标，不写样本正文。",
        "- 主表使用 answer、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。",
        "",
        "## 总览",
        "",
    ]
    for key in (
        "evaluation_level",
        "real_llm_enabled",
        "case_count",
        "unique_case_count",
        "completed_call_count",
        "skipped_from_checkpoint_count",
        "checkpoint_input_count",
        "excluded_infra_failure_count",
        "partial_due_to_infra_failure",
        "checkpoint_report_only",
        "concurrency",
        "profile_count",
        "prompt_variant_count",
        "repeat_count",
        "answer_rule_pass_rate",
        "memory_grounding_pass_rate",
        "forbidden_violation_rate",
        "avg_latency_ms",
        "total_token_count",
        "avg_total_token_count",
    ):
        lines.append(f"- `{key}`: `{metrics.get(key, 'unavailable')}`")
    if metrics.get("checkpoint_report_only"):
        lines.extend(
            [
                "",
                "## Checkpoint Report Notes",
                "",
                "- 本报告由 checkpoint 重建，没有继续发起新的 LLM 调用。",
                "- `case_count` 只统计进入最终评分的有效样本。",
                "- `checkpoint_input_count` 是 checkpoint 原始条数，`excluded_infra_failure_count` 是被排除的 timeout / provider error 条数。",
                "- 如果 `partial_due_to_infra_failure = True`，只能视为部分真实线上评测，不能视为完整 2560-run 结论。",
            ]
        )
    lines.extend(["", "## Profile Summary", ""])
    profile_summaries = metrics.get("profile_summaries", {})
    if isinstance(profile_summaries, dict):
        lines.extend(
            [
                "| profile | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for profile in _profiles_for_markdown(metrics):
            summary = profile_summaries.get(profile)
            if not isinstance(summary, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        profile,
                        _fmt(summary.get("case_count")),
                        _fmt(summary.get("answer_success_count")),
                        _fmt(summary.get("grounding_success_count")),
                        _fmt(summary.get("forbidden_case_count")),
                        _fmt(summary.get("answer_rule_pass_rate")),
                        _fmt(summary.get("memory_grounding_pass_rate")),
                        _fmt(summary.get("forbidden_violation_rate")),
                        _fmt(summary.get("avg_total_token_count")),
                    ]
                )
                + " |"
            )
        control = profile_summaries.get("chain_off")
        if isinstance(control, dict):
            lines.extend(
                [
                    "",
                    "## Disabled Enhancement Control",
                    "",
                    "| control | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                    "| "
                    + " | ".join(
                        [
                            "chain_off",
                            _fmt(control.get("case_count")),
                            _fmt(control.get("answer_success_count")),
                            _fmt(control.get("grounding_success_count")),
                            _fmt(control.get("forbidden_case_count")),
                            _fmt(control.get("answer_rule_pass_rate")),
                            _fmt(control.get("memory_grounding_pass_rate")),
                            _fmt(control.get("forbidden_violation_rate")),
                            _fmt(control.get("avg_total_token_count")),
                        ]
                    )
                    + " |",
                ]
            )
    lines.extend(
        _answer_quality_markdown_sections(metrics)
    )
    lines.extend(_profile_metadata_markdown_section(metrics))
    lines.extend(_answer_post_check_shadow_markdown_section(metrics))
    lines.extend(
        [
            "",
            "## 原始评分字段",
            "",
            "- `main_score`、profile uplift 和 online balanced proxy 保留在 JSON 输出中以兼容既有消费者，不作为本报告主表的解释口径。",
        ]
    )
    lines.extend(["", "## Metric Sources", ""])
    for key, value in METRIC_SOURCES.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Real Memory Readonly Sampling", ""])
    real_memory = metrics.get("real_memory_sample_metrics", {})
    if isinstance(real_memory, dict):
        for key in sorted(real_memory):
            lines.append(f"- `{key}`: `{real_memory[key]}`")
    lines.extend(["", "## 结论", ""])
    lines.append(
        "- 如果某个中后段 profile 的 answer-level 增益不明显，需要结合 offline retrieval proxy 和 online balanced proxy 看治理、证据和效率价值。"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run_comprehensive_case(
    spec: ComprehensiveRunSpec,
    workspace: Path,
    provider: object,
    model: str,
    *,
    timeout_s: float,
    case_index: int,
    answer_debug_dir: Path | None,
    provider_request_debug_dir: Path | None = None,
) -> ComprehensiveCaseResult:
    workspace.mkdir(parents=True, exist_ok=True)
    memory = ComprehensiveOnlineMemoryEngine(
        spec.case,
        profile_name=spec.profile_name,
        prompt_variant=spec.prompt_variant,
    )
    recording_provider = _RecordingProvider(provider)
    event_bus = EventBus()
    session_manager = SessionManager(workspace)
    tools = ToolRegistry()
    loop = AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=recording_provider,  # type: ignore[arg-type]
            light_provider=recording_provider,  # type: ignore[arg-type]
            tools=tools,
            session_manager=session_manager,
            workspace=workspace,
            event_bus=event_bus,
            memory_services=MemoryServices(engine=memory),  # type: ignore[arg-type]
        ),
        AgentLoopConfig(llm=LLMConfig(model=model, max_iterations=2)),
    )
    scope = _scope(spec.case)
    query = _query(spec.case)
    started = time.perf_counter()
    answer = ""
    provider_error = False
    timeout = False
    failures: list[str] = []
    try:
        answer = await asyncio.wait_for(
            loop.process_direct(
                query,
                session_key=scope["session_key"],
                channel=scope["channel"],
                chat_id=scope["chat_id"],
                skip_post_memory=True,
                message_timestamp=_message_timestamp_for_case(spec.case),
            ),
            timeout=max(0.001, float(timeout_s)),
        )
        await event_bus.drain()
    except TimeoutError:
        timeout = True
        failures.append("timeout")
    except Exception:
        provider_error = True
        failures.append("provider_error")
    finally:
        await event_bus.aclose()
    latency_ms = int((time.perf_counter() - started) * 1000)
    if recording_provider.errors and not provider_error:
        provider_error = True
        failures.append("provider_error")

    score = score_answer_text(
        answer,
        answer_expectation_for_profile(spec.case, spec.profile_name),
        memory.used_memory_ids,
    )
    answer_post_check_shadow: dict[str, object] | None = None
    answer_contract = memory.last_raw.get("answer_contract")
    if (
        spec.profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES
        and isinstance(answer_contract, dict)
    ):
        answer_post_check_shadow = answer_post_check_shadow_to_dict(
            build_answer_post_check_shadow(
                answer,
                answer_contract,
                memory.used_memory_ids,
            )
        )
    evidence_render_metadata = ()
    raw_answer_contract = memory.last_raw.get("answer_contract")
    if isinstance(raw_answer_contract, dict):
        raw_metadata = raw_answer_contract.get("evidence_render_metadata")
        if isinstance(raw_metadata, list):
            evidence_render_metadata = tuple(
                dict(item) for item in raw_metadata if isinstance(item, dict)
            )
    failures.extend(score.failures)
    token_counts = _extract_token_counts(
        recording_provider.responses[-1] if recording_provider.responses else None
    )
    result = ComprehensiveCaseResult(
        case_id=spec.case.id,
        category=spec.case.category,
        profile_name=spec.profile_name,
        prompt_variant=spec.prompt_variant,
        repeat_index=spec.repeat_index,
        passed=not failures,
        answer_rule_passed=score.answer_rule_passed,
        memory_grounding_passed=score.memory_grounding_passed,
        expected_memory_used=score.expected_memory_used,
        forbidden_contains_violation_count=score.forbidden_contains_violation_count,
        latency_ms=latency_ms,
        prompt_token_count=int(token_counts["prompt_token_count"]),
        completion_token_count=int(token_counts["completion_token_count"]),
        total_token_count=int(token_counts["total_token_count"]),
        token_metrics_available=bool(token_counts["token_metrics_available"]),
        provider_error=provider_error,
        timeout=timeout,
        answer_length=len(answer),
        evidence_source=profile_evidence_source(spec.profile_name),
        used_memory_id_count=len(memory.used_memory_ids),
        failures=tuple(failures),
        answer_post_check_shadow=answer_post_check_shadow,
        evidence_render_metadata=evidence_render_metadata,
    )
    if answer_debug_dir is not None:
        write_llm_sample_answer_debug(
            LLMSampleAnswerDebugRecord(
                case_id=spec.case.id,
                case_index=case_index,
                prompt_variant=f"{spec.profile_name}-{spec.prompt_variant}",
                session_key=scope["session_key"],
                evidence_block_text=memory.last_text_block,
                answer_text=answer,
                answer_length=len(answer),
                used_memory_ids=tuple(memory.used_memory_ids),
                matched_expected_terms=score.matched_expected_terms,
                missing_expected_terms=score.missing_expected_terms,
                matched_any_groups=score.matched_any_groups,
                missing_any_groups=score.missing_any_groups,
                failures=tuple(failures),
                answer_rule_passed=score.answer_rule_passed,
                memory_grounding_passed=score.memory_grounding_passed,
            ),
            answer_debug_dir
            / f"{case_index:04d}-{_safe_name(spec.profile_name)}-{_safe_name(spec.prompt_variant)}-{_safe_name(spec.case.id)}.json",
        )
    if provider_request_debug_dir is not None:
        _write_provider_request_debug(
            provider_request_debug_dir
            / f"{case_index:04d}-{_safe_name(spec.profile_name)}-{_safe_name(spec.prompt_variant)}-{_safe_name(spec.case.id)}.json",
            case_id=spec.case.id,
            case_index=case_index,
            profile_name=spec.profile_name,
            prompt_variant=spec.prompt_variant,
            repeat_index=spec.repeat_index,
            user_question=query,
            evidence_block_text=memory.last_text_block,
            provider_request=(
                recording_provider.requests[-1] if recording_provider.requests else {}
            ),
        )
    return result


def _message_timestamp_for_case(case: EvalCase) -> datetime | None:
    public_meta = case.setup.get("public_long_memory")
    if not isinstance(public_meta, dict):
        return None
    raw = str(public_meta.get("question_date") or "").strip()
    if not raw:
        return None
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        raw = f"{raw}T00:00:00+00:00"
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_comprehensive_report(
    results: tuple[ComprehensiveCaseResult, ...],
    *,
    real_llm_enabled: bool,
    completed_call_count: int,
    skipped_from_checkpoint_count: int,
    real_memory_sample_metrics: dict[str, object],
    concurrency: int = 1,
    report_metadata: dict[str, object] | None = None,
    malformed_checkpoint_line_count: int = 0,
    checkpoint_provenance_mismatch_count: int = 0,
) -> ComprehensiveOnlineReport:
    metrics = _metrics_from_results(
        results,
        real_llm_enabled=real_llm_enabled,
        completed_call_count=completed_call_count,
        skipped_from_checkpoint_count=skipped_from_checkpoint_count,
        real_memory_sample_metrics=real_memory_sample_metrics,
        concurrency=concurrency,
    )
    metrics.update(report_metadata or {})
    metrics["malformed_checkpoint_line_count"] = malformed_checkpoint_line_count
    metrics["checkpoint_provenance_mismatch_count"] = (
        checkpoint_provenance_mismatch_count
    )
    metrics["fresh_checkpoint_valid"] = (
        int(metrics.get("skipped_from_checkpoint_count") or 0) == 0
        and malformed_checkpoint_line_count == 0
        and checkpoint_provenance_mismatch_count == 0
    )
    annotate_memory_governance_causal_chain(metrics)
    return ComprehensiveOnlineReport(
        run_id=_deterministic_run_id(results),
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        cases=results,
        case_records=tuple(_case_record(result) for result in results),
        failure_records=_failure_records(results),
        metrics=metrics,
    )


def _metrics_from_results(
    results: tuple[ComprehensiveCaseResult, ...],
    *,
    real_llm_enabled: bool,
    completed_call_count: int,
    skipped_from_checkpoint_count: int,
    real_memory_sample_metrics: dict[str, object],
    concurrency: int = 1,
) -> dict[str, object]:
    count = len(results)
    profiles = _profiles_in_order(results)
    variants = sorted({result.prompt_variant for result in results})
    profile_summaries = _profile_summaries(results, profiles)
    uplift = _profile_uplift_vs_memory_base(profile_summaries)
    adjacent = _chain_adjacent_uplift(profile_summaries)
    answer_quality_profiles = _answer_quality_profiles_for_report(profile_summaries)
    answer_quality_rows = _build_profile_answer_quality_uplift_rows(
        profile_summaries,
        profiles=answer_quality_profiles,
    )
    answer_quality_chain_rows = _build_chain_answer_quality_rows(
        profile_summaries,
        ordered_profiles=answer_quality_profiles,
    )
    answer_quality_missing_profiles = [
        profile for profile in ANSWER_QUALITY_PROFILES if profile not in profile_summaries
    ]
    profile_metadata = {
        profile: dict(PROFILE_METADATA[profile])
        for profile in profiles
        if profile in PROFILE_METADATA
    }
    return {
        "evaluation_level": "comprehensive_online_agentloop",
        "real_llm_enabled": real_llm_enabled,
        "case_count": count,
        "unique_case_count": len({result.case_id for result in results}),
        "completed_call_count": completed_call_count,
        "skipped_from_checkpoint_count": skipped_from_checkpoint_count,
        "concurrency": concurrency,
        "infra_passed": bool(results)
        and all(not result.provider_error and not result.timeout for result in results),
        "answer_quality_passed": bool(results) and all(result.passed for result in results),
        "profile_count": len(profiles),
        "prompt_variant_count": len(variants),
        "repeat_count": max((result.repeat_index for result in results), default=-1) + 1,
        "passed_case_count": sum(1 for result in results if result.passed),
        "failed_answer_case_count": sum(
            1
            for result in results
            if not result.answer_rule_passed and not result.provider_error and not result.timeout
        ),
        "provider_error_count": sum(1 for result in results if result.provider_error),
        "timeout_count": sum(1 for result in results if result.timeout),
        "answer_rule_pass_rate": _rate(
            sum(1 for result in results if result.answer_rule_passed),
            count,
        ),
        "memory_grounding_pass_rate": _rate(
            sum(1 for result in results if result.memory_grounding_passed),
            count,
        ),
        "forbidden_violation_rate": _rate(
            sum(1 for result in results if result.forbidden_contains_violation_count > 0),
            count,
        ),
        "avg_latency_ms": _avg(result.latency_ms for result in results),
        "total_token_count": sum(result.total_token_count for result in results),
        "avg_total_token_count": _avg(result.total_token_count for result in results),
        "token_metrics_available": any(result.token_metrics_available for result in results),
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "session_text_included": False,
        "full_answer_included": False,
        "profile_summaries": profile_summaries,
        "baseline_profile": "chain_memory_base",
        "control_profile": "chain_off",
        "answer_quality_required_profiles": list(ANSWER_QUALITY_PROFILES),
        "answer_quality_missing_profiles": answer_quality_missing_profiles,
        "answer_quality_partial_matrix": bool(answer_quality_missing_profiles),
        "profile_metadata": profile_metadata,
        "answer_post_check_shadow": _answer_post_check_shadow_metrics(results),
        "profile_answer_quality_uplift_vs_memory_base": answer_quality_rows,
        "chain_answer_quality_uplift_rows": answer_quality_chain_rows,
        "profile_uplift_vs_memory_base": uplift,
        "profile_uplift_vs_off": _profile_uplift_vs_off(profile_summaries),
        "chain_adjacent_uplift": adjacent,
        "online_balanced_proxy_summaries": _online_balanced_proxy_summaries(
            profile_summaries,
        ),
        "metric_sources": dict(METRIC_SOURCES),
        "real_memory_sample_metrics": real_memory_sample_metrics,
    }


def _empty_metrics(real_memory_sample_metrics: dict[str, object]) -> dict[str, object]:
    return {
        "evaluation_level": "comprehensive_online_agentloop",
        "real_llm_enabled": False,
        "case_count": 0,
        "unique_case_count": 0,
        "completed_call_count": 0,
        "skipped_from_checkpoint_count": 0,
        "concurrency": 1,
        "infra_passed": False,
        "answer_quality_passed": False,
        "profile_count": 0,
        "prompt_variant_count": 0,
        "repeat_count": 0,
        "passed_case_count": 0,
        "failed_answer_case_count": 0,
        "provider_error_count": 0,
        "timeout_count": 0,
        "answer_rule_pass_rate": 0.0,
        "memory_grounding_pass_rate": 0.0,
        "forbidden_violation_rate": 0.0,
        "avg_latency_ms": 0.0,
        "total_token_count": 0,
        "avg_total_token_count": 0.0,
        "token_metrics_available": False,
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "session_text_included": False,
        "full_answer_included": False,
        "profile_summaries": {},
        "baseline_profile": "chain_memory_base",
        "control_profile": "chain_off",
        "answer_quality_required_profiles": list(ANSWER_QUALITY_PROFILES),
        "answer_quality_missing_profiles": list(ANSWER_QUALITY_PROFILES),
        "answer_quality_partial_matrix": True,
        "profile_metadata": {},
        "answer_post_check_shadow": _answer_post_check_shadow_metrics(()),
        "profile_answer_quality_uplift_vs_memory_base": {},
        "chain_answer_quality_uplift_rows": (),
        "profile_uplift_vs_memory_base": {},
        "profile_uplift_vs_off": {},
        "chain_adjacent_uplift": {},
        "online_balanced_proxy_summaries": {},
        "metric_sources": dict(METRIC_SOURCES),
        "real_memory_sample_metrics": real_memory_sample_metrics,
    }


def annotate_memory_governance_causal_chain(metrics: dict[str, object]) -> None:
    summaries = metrics.get("profile_summaries")
    if not isinstance(summaries, dict):
        return
    p1 = summaries.get("chain_tri_retrieval")
    p4 = summaries.get("chain_tri_governed_answer_contract")
    if not isinstance(p1, dict) or not isinstance(p4, dict):
        return
    p1_rate = float(p1.get("answer_rule_pass_rate") or 0.0)
    p4_rate = float(p4.get("answer_rule_pass_rate") or 0.0)
    metrics["measured_causal_chain"] = (
        f"{p1_rate}_to_{p4_rate}_same_table_profile_ladder"
    )
    if round(p1_rate, 4) == 37.5 and round(p4_rate, 4) == 97.5:
        metrics["causal_claim_status"] = "reproduced_historical_37.5_to_97.5"
    else:
        metrics["causal_claim_status"] = (
            "new_measured_values_differ_from_historical_37.5_to_97.5"
        )


def _profile_summaries(
    results: tuple[ComprehensiveCaseResult, ...],
    profiles: tuple[str, ...],
) -> dict[str, dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    for profile in profiles:
        rows = [result for result in results if result.profile_name == profile]
        count = len(rows)
        answer = _rate(sum(1 for row in rows if row.answer_rule_passed), count)
        grounding = _rate(sum(1 for row in rows if row.memory_grounding_passed), count)
        forbidden = _rate(
            sum(1 for row in rows if row.forbidden_contains_violation_count > 0),
            count,
        )
        summaries[profile] = {
            "case_count": count,
            "answer_success_count": sum(
                1 for row in rows if row.answer_rule_passed
            ),
            "grounding_success_count": sum(
                1 for row in rows if row.memory_grounding_passed
            ),
            "forbidden_case_count": sum(
                1
                for row in rows
                if row.forbidden_contains_violation_count > 0
            ),
            "answer_rule_pass_rate": answer,
            "memory_grounding_pass_rate": grounding,
            "forbidden_violation_rate": forbidden,
            "main_score": calculate_main_score(
                answer_rule_pass_rate=answer,
                memory_grounding_pass_rate=grounding,
                forbidden_violation_rate=forbidden,
            ),
            "avg_latency_ms": _avg(row.latency_ms for row in rows),
            "avg_total_token_count": _avg(row.total_token_count for row in rows),
            "token_metrics_available": any(row.token_metrics_available for row in rows),
            "evidence_source": profile_evidence_source(profile),
        }
    return summaries


def _answer_post_check_shadow_metrics(
    results: tuple[ComprehensiveCaseResult, ...],
) -> dict[str, object]:
    shadows = [
        result.answer_post_check_shadow
        for result in results
        if isinstance(result.answer_post_check_shadow, dict)
    ]
    enabled = [shadow for shadow in shadows if shadow.get("shadow_enabled") is True]
    return {
        "case_count": len(shadows),
        "enabled_case_count": len(enabled),
        "needs_retry_count": sum(
            1 for shadow in enabled if shadow.get("needs_retry") is True
        ),
        "forbidden_boundary_included_count": sum(
            1
            for shadow in enabled
            if shadow.get("forbidden_boundary_included") is True
        ),
        "stale_evidence_included_count": sum(
            1 for shadow in enabled if shadow.get("stale_evidence_included") is True
        ),
        "conflict_evidence_included_count": sum(
            1 for shadow in enabled if shadow.get("conflict_evidence_included") is True
        ),
        "missing_likely_relevant_context_count": sum(
            1
            for shadow in enabled
            if shadow.get("missing_likely_relevant_context_ids")
        ),
        "insufficient_fallback_missing_count": sum(
            1
            for shadow in enabled
            if shadow.get("insufficient_evidence_fallback_expected") is True
            and shadow.get("insufficient_evidence_fallback_observed") is False
        ),
    }


def _profile_uplift_vs_off(
    summaries: dict[str, dict[str, object]],
) -> dict[str, float | str]:
    off = summaries.get("chain_off")
    if not off:
        return {profile: "unavailable" for profile in summaries}
    baseline = float(off["main_score"])
    return {
        profile: round(float(summary["main_score"]) - baseline, 4)
        for profile, summary in summaries.items()
    }


def _profile_uplift_vs_memory_base(
    summaries: dict[str, dict[str, object]],
) -> dict[str, float | str]:
    baseline_row = summaries.get("chain_memory_base")
    if not baseline_row:
        return {profile: "unavailable" for profile in summaries}
    baseline = float(baseline_row["main_score"])
    return {
        profile: round(float(summary["main_score"]) - baseline, 4)
        for profile, summary in summaries.items()
    }


def _relative_rate_lift(after: float, baseline: float) -> float | None:
    if float(baseline) == 0.0:
        return None
    return round(((float(after) - float(baseline)) / float(baseline)) * 100.0, 4)


def _relative_reduction(before: float, after: float) -> float | None:
    if float(before) == 0.0:
        return None
    return round(((float(before) - float(after)) / float(before)) * 100.0, 4)


def _build_profile_answer_quality_uplift_rows(
    profile_summaries: dict[str, dict[str, object]],
    *,
    baseline_profile: str = "chain_memory_base",
    profiles: Sequence[str] = ANSWER_QUALITY_PROFILES,
) -> dict[str, dict[str, object]]:
    baseline = profile_summaries.get(baseline_profile)
    if not isinstance(baseline, dict):
        return {}
    rows: dict[str, dict[str, object]] = {}
    base_answer = float(baseline.get("answer_rule_pass_rate") or 0.0)
    base_grounding = float(baseline.get("memory_grounding_pass_rate") or 0.0)
    base_forbidden = float(baseline.get("forbidden_violation_rate") or 0.0)
    base_tokens = float(baseline.get("avg_total_token_count") or 0.0)
    base_latency = float(baseline.get("avg_latency_ms") or 0.0)
    for profile in profiles:
        summary = profile_summaries.get(profile)
        if not isinstance(summary, dict):
            continue
        answer = float(summary.get("answer_rule_pass_rate") or 0.0)
        grounding = float(summary.get("memory_grounding_pass_rate") or 0.0)
        forbidden = float(summary.get("forbidden_violation_rate") or 0.0)
        tokens = float(summary.get("avg_total_token_count") or 0.0)
        latency = float(summary.get("avg_latency_ms") or 0.0)
        rows[profile] = {
            "baseline_profile": baseline_profile,
            "is_combo_check_row": profile == "chain_all_on",
            "case_count": summary.get("case_count", 0),
            "answer_success_count": summary.get("answer_success_count", 0),
            "grounding_success_count": summary.get("grounding_success_count", 0),
            "forbidden_case_count": summary.get("forbidden_case_count", 0),
            "answer_rule_pass_rate": answer,
            "answer_pass_delta_points": round(answer - base_answer, 4),
            "answer_pass_relative_lift_percent": _relative_rate_lift(
                answer,
                base_answer,
            ),
            "memory_grounding_pass_rate": grounding,
            "grounding_pass_delta_points": round(grounding - base_grounding, 4),
            "grounding_pass_relative_lift_percent": _relative_rate_lift(
                grounding,
                base_grounding,
            ),
            "forbidden_violation_rate": forbidden,
            "forbidden_violation_delta_points": round(forbidden - base_forbidden, 4),
            "forbidden_violation_reduction_percent": _relative_reduction(
                base_forbidden,
                forbidden,
            ),
            "avg_total_token_count": tokens,
            "avg_total_token_overhead": round(tokens - base_tokens, 4),
            "avg_total_token_reduction_percent": _relative_reduction(
                base_tokens,
                tokens,
            ),
            "avg_latency_ms": latency,
            "avg_latency_overhead_ms": round(latency - base_latency, 4),
            "avg_latency_reduction_percent": _relative_reduction(
                base_latency,
                latency,
            ),
        }
    return rows


def _build_chain_answer_quality_rows(
    profile_summaries: dict[str, dict[str, object]],
    *,
    ordered_profiles: Sequence[str] = ANSWER_QUALITY_PROFILES,
    baseline_profile: str = "chain_memory_base",
) -> tuple[dict[str, object], ...]:
    baseline = profile_summaries.get(baseline_profile)
    if not isinstance(baseline, dict):
        return ()
    rows: list[dict[str, object]] = []
    previous: dict[str, object] | None = None
    previous_profile: str | None = None
    base_answer = float(baseline.get("answer_rule_pass_rate") or 0.0)
    base_grounding = float(baseline.get("memory_grounding_pass_rate") or 0.0)
    for profile in ordered_profiles:
        current = profile_summaries.get(profile)
        if not isinstance(current, dict):
            continue
        current_answer = float(current.get("answer_rule_pass_rate") or 0.0)
        current_grounding = float(current.get("memory_grounding_pass_rate") or 0.0)
        prev_answer = (
            float(previous.get("answer_rule_pass_rate") or 0.0)
            if isinstance(previous, dict)
            else current_answer
        )
        prev_grounding = (
            float(previous.get("memory_grounding_pass_rate") or 0.0)
            if isinstance(previous, dict)
            else current_grounding
        )
        rows.append(
            {
                "profile_name": profile,
                "previous_profile": previous_profile,
                "is_combo_check_row": profile == "chain_all_on",
                "case_count": current.get("case_count", 0),
                "answer_rule_pass_rate": current_answer,
                "adjacent_answer_pass_delta_points": round(
                    current_answer - prev_answer,
                    4,
                ),
                "cumulative_answer_pass_delta_points": round(
                    current_answer - base_answer,
                    4,
                ),
                "cumulative_answer_pass_relative_lift_percent": _relative_rate_lift(
                    current_answer,
                    base_answer,
                ),
                "memory_grounding_pass_rate": current_grounding,
                "adjacent_grounding_pass_delta_points": round(
                    current_grounding - prev_grounding,
                    4,
                ),
                "cumulative_grounding_pass_delta_points": round(
                    current_grounding - base_grounding,
                    4,
                ),
                "cumulative_grounding_pass_relative_lift_percent": _relative_rate_lift(
                    current_grounding,
                    base_grounding,
                ),
            }
        )
        previous = current
        previous_profile = profile
    return tuple(rows)


def _chain_adjacent_uplift(
    summaries: dict[str, dict[str, object]],
) -> dict[str, float | str]:
    result: dict[str, float | str] = {}
    previous_score: float | None = None
    for profile in COMPREHENSIVE_CHAIN_PROFILES:
        summary = summaries.get(profile)
        if summary is None:
            continue
        current_score = float(summary["main_score"])
        result[profile] = (
            0.0 if previous_score is None else round(current_score - previous_score, 4)
        )
        previous_score = current_score
    return result


def _online_balanced_proxy_summaries(
    summaries: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    off_tokens = _first_summary_value(summaries, "chain_off", "avg_total_token_count")
    result: dict[str, dict[str, object]] = {}
    previous_score: float | None = None
    for profile in COMPREHENSIVE_CHAIN_PROFILES:
        summary = summaries.get(profile)
        if summary is None:
            continue
        current_tokens = summary.get("avg_total_token_count")
        token_signal_value: float | str = "unavailable"
        token_signal_kind = "unavailable"
        if isinstance(current_tokens, (int, float)) and isinstance(off_tokens, (int, float)):
            token_signal_kind = "prompt_token_delta"
            token_signal_value = round(float(current_tokens) - float(off_tokens), 4)
        row = QuantitativeProfileSummary(
            profile_name=profile,
            feature_name=profile,
            case_set="overall",
            case_count=int(summary["case_count"]),
            target_count=int(summary["case_count"]),
            success_count=int(
                round(
                    float(summary["answer_rule_pass_rate"])
                    / 100.0
                    * int(summary["case_count"])
                )
            ),
            miss_count=max(
                0,
                int(summary["case_count"])
                - int(
                    round(
                        float(summary["answer_rule_pass_rate"])
                        / 100.0
                        * int(summary["case_count"])
                    )
                ),
            ),
            recall_rate=float(summary["answer_rule_pass_rate"]),
            grounding_count=int(
                round(
                    float(summary["memory_grounding_pass_rate"])
                    / 100.0
                    * int(summary["case_count"])
                )
            ),
            forbidden_count=int(
                round(
                    float(summary["forbidden_violation_rate"])
                    / 100.0
                    * int(summary["case_count"])
                )
            ),
            repeat_count=1,
            answer_rule_pass_rate=float(summary["answer_rule_pass_rate"]),
            memory_grounding_pass_rate=float(summary["memory_grounding_pass_rate"]),
            forbidden_violation_rate=float(summary["forbidden_violation_rate"]),
            main_score=float(summary["main_score"]),
            baseline_score=0.0,
            uplift_points=0.0,
            uplift_pct=None,
            token_signal_kind=token_signal_kind,
            token_signal_value=token_signal_value,
            token_signal_delta="unavailable",
            latency_ms=summary.get("avg_latency_ms", "unavailable"),
            latency_delta_ms="unavailable",
            unavailable=(),
        )
        scores = calculate_balanced_scores(row)
        balanced = float(scores["balanced_score"])
        result[profile] = {
            "metric_source": "online_balanced_proxy",
            "answer_derived_retrieval_proxy_score": scores["retrieval_proxy_score"],
            "answer_score": scores["answer_score"],
            "grounding_score": scores["grounding_score"],
            "governance_score": scores["governance_score"],
            "efficiency_score": scores["efficiency_score"],
            "online_balanced_proxy_score": balanced,
            "online_balanced_proxy_delta": (
                0.0
                if previous_score is None
                else round(balanced - previous_score, 4)
            ),
            "available_dimensions": scores["balanced_score_available_dimensions"],
            "unavailable_dimensions": scores["unavailable_dimensions"],
            "formula": BALANCED_SCORE_FORMULA,
        }
        previous_score = balanced
    return result


def _ids_from_trace(case: EvalCase, family_name: str, key: str) -> tuple[str, ...]:
    trace = _family_trace_for_case(case, family_name)
    if trace is None:
        return ()
    raw_ids = trace.experimental_result.get(key, [])
    if not isinstance(raw_ids, (list, tuple)):
        return ()
    return _dedupe_ids(str(item) for item in raw_ids if str(item))


def _sleep_filtered_ids(case: EvalCase) -> tuple[str, ...]:
    base_ids = list(_ids_from_trace(case, "graph_retrieval", "graph_fused_ids"))
    if not base_ids:
        base_ids = list(_ids_from_trace(case, "version_chain_shadow", "active_leaf_ids"))
    sleep = _family_trace_for_case(case, "sleep_consolidation_shadow")
    if sleep is None:
        return tuple(base_ids)
    experimental = sleep.experimental_result
    stale = set(str(item) for item in experimental.get("stale_candidate_ids", []))
    low_value = set(
        str(item) for item in experimental.get("low_value_candidate_ids", [])
    )
    duplicate_ids = {
        str(item_id)
        for group in experimental.get("duplicate_groups", [])
        if isinstance(group, dict)
        for item_id in group.get("item_ids", [])
    }
    protected = {str(item) for item in case.expectations.get("should_recall_ids", [])}
    drop_ids = stale | low_value | duplicate_ids
    return tuple(
        item_id
        for item_id in base_ids
        if item_id not in drop_ids or item_id in protected
    )


def _dedupe_ids(ids: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    for item_id in ids:
        if item_id and item_id not in result:
            result.append(item_id)
    return tuple(result)


def _case_record(result: ComprehensiveCaseResult) -> dict[str, object]:
    return {
        "case_id": result.case_id,
        "category": result.category,
        "profile_name": result.profile_name,
        "prompt_variant": result.prompt_variant,
        "repeat_index": result.repeat_index,
        "passed": result.passed,
        "answer_rule_passed": result.answer_rule_passed,
        "memory_grounding_passed": result.memory_grounding_passed,
        "expected_memory_used": result.expected_memory_used,
        "forbidden_contains_violation_count": result.forbidden_contains_violation_count,
        "latency_ms": result.latency_ms,
        "prompt_token_count": result.prompt_token_count,
        "completion_token_count": result.completion_token_count,
        "total_token_count": result.total_token_count,
        "token_metrics_available": result.token_metrics_available,
        "provider_error": result.provider_error,
        "timeout": result.timeout,
        "answer_length": result.answer_length,
        "evidence_source": result.evidence_source,
        "used_memory_id_count": result.used_memory_id_count,
        "failures": [_sanitize_failure(failure) for failure in result.failures],
        "answer_post_check_shadow": result.answer_post_check_shadow,
        "evidence_render_metadata": list(result.evidence_render_metadata),
    }


def _write_provider_request_debug(
    path: Path,
    *,
    case_id: str,
    case_index: int,
    profile_name: str,
    prompt_variant: str,
    repeat_index: int,
    user_question: str,
    evidence_block_text: str,
    provider_request: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case_id,
        "case_index": case_index,
        "profile_name": profile_name,
        "prompt_variant": prompt_variant,
        "repeat_index": repeat_index,
        "user_question": user_question,
        "evidence_block_text": evidence_block_text,
        "provider_request": _sanitize_provider_request(provider_request),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _sanitize_provider_request(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(secret in lowered for secret in ("api_key", "authorization", "token")):
                continue
            if callable(item):
                continue
            sanitized[key_text] = _sanitize_provider_request(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_provider_request(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_provider_request(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _failure_records(
    results: tuple[ComprehensiveCaseResult, ...],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for result in results:
        for failure in result.failures:
            records.append(
                {
                    "case_id": result.case_id,
                    "profile_name": result.profile_name,
                    "prompt_variant": result.prompt_variant,
                    "repeat_index": result.repeat_index,
                    "failure": _sanitize_failure(failure),
                }
            )
    return tuple(records)


def _report_to_dict(report: ComprehensiveOnlineReport) -> dict[str, object]:
    return {
        "passed": report.passed,
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "metrics": report.metrics,
        "case_records": list(report.case_records),
        "failure_records": list(report.failure_records),
    }


def _load_checkpoint_rows(
    path: Path | None,
    *,
    command_shape_hash: str | None = None,
) -> _CheckpointLoadResult:
    if path is None or not path.exists():
        return _CheckpointLoadResult((), 0, 0)
    rows: list[tuple[str, ComprehensiveCaseResult]] = []
    malformed = 0
    mismatches = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if command_shape_hash is not None:
            provenance = payload.get("run_provenance")
            row_hash = (
                str(provenance.get("command_shape_hash") or "")
                if isinstance(provenance, dict)
                else ""
            )
            if row_hash != command_shape_hash:
                mismatches += 1
                continue
        key = str(payload.get("spec_key") or "")
        result_payload = payload.get("result")
        if key and isinstance(result_payload, dict):
            rows.append(
                (
                    key,
                    ComprehensiveCaseResult(
                        **{
                            **result_payload,
                            "failures": tuple(result_payload.get("failures", [])),
                            "answer_post_check_shadow": result_payload.get(
                                "answer_post_check_shadow"
                            ),
                            "evidence_render_metadata": tuple(
                                dict(item)
                                for item in result_payload.get(
                                    "evidence_render_metadata",
                                    [],
                                )
                                if isinstance(item, dict)
                            ),
                        }
                    ),
                )
            )
    return _CheckpointLoadResult(tuple(rows), malformed, mismatches)


def _checkpoint_results_from_rows(
    rows: Sequence[tuple[str, ComprehensiveCaseResult]],
    *,
    include_infra_failures: bool,
) -> dict[str, ComprehensiveCaseResult]:
    results: dict[str, ComprehensiveCaseResult] = {}
    for key, result in rows:
        if not include_infra_failures and (result.provider_error or result.timeout):
            continue
        results[key] = result
    return results


def _load_checkpoint_results(
    path: Path | None,
    *,
    include_infra_failures: bool = True,
) -> dict[str, ComprehensiveCaseResult]:
    return _checkpoint_results_from_rows(
        _load_checkpoint_rows(path).rows,
        include_infra_failures=include_infra_failures,
    )


def _append_checkpoint_result(
    path: Path | None,
    spec_key: str,
    result: ComprehensiveCaseResult,
    run_provenance: EvalRunProvenance | None = None,
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "spec_key": spec_key,
                    "run_provenance": asdict(run_provenance)
                    if run_provenance is not None
                    else {},
                    "result": _case_record(result),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


def _spec_key(spec: ComprehensiveRunSpec) -> str:
    return "|".join(
        [
            spec.case.id,
            spec.profile_name,
            spec.prompt_variant,
            str(spec.repeat_index),
        ]
    )


def _deterministic_run_id(results: Sequence[ComprehensiveCaseResult]) -> str:
    seed = "|".join(
        f"{result.case_id}:{result.profile_name}:{result.prompt_variant}:{result.repeat_index}"
        for result in results
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _profiles_in_order(results: tuple[ComprehensiveCaseResult, ...]) -> tuple[str, ...]:
    seen = {result.profile_name for result in results}
    ordered = tuple(profile for profile in COMPREHENSIVE_CHAIN_PROFILES if profile in seen)
    optional = tuple(
        profile for profile in OPTIONAL_ANSWER_QUALITY_PROFILES if profile in seen
    )
    known = set(ordered) | set(optional)
    unknown = tuple(profile for profile in sorted(seen) if profile not in known)
    return (*ordered, *optional, *unknown)


def _answer_quality_profiles_for_report(
    profile_summaries: dict[str, dict[str, object]],
) -> tuple[str, ...]:
    optional = tuple(
        profile
        for profile in OPTIONAL_ANSWER_QUALITY_PROFILES
        if profile in profile_summaries
    )
    return (*ANSWER_QUALITY_PROFILES, *optional)


def _profiles_for_markdown(metrics: dict[str, object]) -> tuple[str, ...]:
    summaries = metrics.get("profile_summaries", {})
    if not isinstance(summaries, dict):
        return ()
    ordered = tuple(
        profile for profile in COMPREHENSIVE_CHAIN_PROFILES if profile in summaries
    )
    optional = tuple(
        profile for profile in OPTIONAL_ANSWER_QUALITY_PROFILES if profile in summaries
    )
    known = set(ordered) | set(optional)
    unknown = tuple(profile for profile in sorted(summaries) if profile not in known)
    return (*ordered, *optional, *unknown)


def _answer_quality_profiles_for_markdown(
    metrics: dict[str, object],
) -> tuple[str, ...]:
    summaries = metrics.get("profile_summaries", {})
    if not isinstance(summaries, dict):
        return ANSWER_QUALITY_PROFILES
    return _answer_quality_profiles_for_report(summaries)


def _first_summary_value(
    summaries: dict[str, dict[str, object]],
    profile: str,
    key: str,
) -> object:
    summary = summaries.get(profile)
    return summary.get(key) if summary else "unavailable"


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100.0, 4)


def _avg(values: Any) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value) or "unknown"


def _sanitize_failure(failure: str) -> str:
    if failure.startswith("missing expected answer term group:"):
        return "missing_expected_answer_term_group"
    if failure.startswith("missing expected answer term:"):
        return "missing_expected_answer_term"
    if failure.startswith("found forbidden answer term:"):
        return "found_forbidden_answer_term"
    if failure.startswith("missing expected memory ids:"):
        return "missing_expected_memory_ids"
    return failure


def _answer_quality_markdown_sections(metrics: dict[str, object]) -> list[str]:
    lines: list[str] = [
        "",
        "## Answer Quality Uplift Vs Original Memory",
        "",
        "`combo/check` marks `chain_all_on`; it is a combined verification row, not a pure single-module answer/retrieval gain.",
    ]
    rows = metrics.get("profile_answer_quality_uplift_vs_memory_base", {})
    answer_quality_profiles = _answer_quality_profiles_for_markdown(metrics)
    if isinstance(rows, dict) and rows:
        lines.extend(
            [
                "| profile | cases | answer_pass | answer_rate | answer_lift | grounding_pass | grounding_rate | grounding_lift | forbidden_rate | forbidden_reduction |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for profile in answer_quality_profiles:
            row = rows.get(profile)
            if not isinstance(row, dict):
                continue
            label = f"{profile} (combo/check)" if row.get("is_combo_check_row") else profile
            lines.append(
                "| "
                + " | ".join(
                    [
                        label,
                        _fmt(row.get("case_count")),
                        _fmt(row.get("answer_success_count")),
                        _fmt(row.get("answer_rule_pass_rate")),
                        _fmt_percent(row.get("answer_pass_relative_lift_percent")),
                        _fmt(row.get("grounding_success_count")),
                        _fmt(row.get("memory_grounding_pass_rate")),
                        _fmt_percent(row.get("grounding_pass_relative_lift_percent")),
                        _fmt(row.get("forbidden_violation_rate")),
                        _fmt_percent(row.get("forbidden_violation_reduction_percent")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- No answer-quality uplift rows available.")

    lines.extend(
        [
            "",
            "## Chain Answer Quality Uplift",
            "",
        ]
    )
    chain_rows = metrics.get("chain_answer_quality_uplift_rows", ())
    if isinstance(chain_rows, (list, tuple)) and chain_rows:
        lines.extend(
            [
                "| profile | previous | answer_rate | adjacent_answer_delta | cumulative_answer_lift | grounding_rate | adjacent_grounding_delta | cumulative_grounding_lift |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for raw_row in chain_rows:
            if not isinstance(raw_row, dict):
                continue
            label = (
                f"{raw_row.get('profile_name')} (combo/check)"
                if raw_row.get("is_combo_check_row")
                else str(raw_row.get("profile_name"))
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        label,
                        _fmt(raw_row.get("previous_profile")),
                        _fmt(raw_row.get("answer_rule_pass_rate")),
                        _fmt(raw_row.get("adjacent_answer_pass_delta_points")),
                        _fmt_percent(
                            raw_row.get("cumulative_answer_pass_relative_lift_percent")
                        ),
                        _fmt(raw_row.get("memory_grounding_pass_rate")),
                        _fmt(raw_row.get("adjacent_grounding_pass_delta_points")),
                        _fmt_percent(
                            raw_row.get("cumulative_grounding_pass_relative_lift_percent")
                        ),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- No chain answer-quality uplift rows available.")

    lines.extend(
        [
            "",
            "## Cost And Latency Observation",
            "",
            "| profile | avg_tokens | token_overhead_vs_memory_base | token_reduction | avg_latency_ms | latency_overhead_ms | latency_reduction |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if isinstance(rows, dict) and rows:
        for profile in answer_quality_profiles:
            row = rows.get(profile)
            if not isinstance(row, dict):
                continue
            label = f"{profile} (combo/check)" if row.get("is_combo_check_row") else profile
            lines.append(
                "| "
                + " | ".join(
                    [
                        label,
                        _fmt(row.get("avg_total_token_count")),
                        _fmt(row.get("avg_total_token_overhead")),
                        _fmt_percent(row.get("avg_total_token_reduction_percent")),
                        _fmt(row.get("avg_latency_ms")),
                        _fmt(row.get("avg_latency_overhead_ms")),
                        _fmt_percent(row.get("avg_latency_reduction_percent")),
                    ]
                )
                + " |"
            )
    return lines


def _profile_metadata_markdown_section(metrics: dict[str, object]) -> list[str]:
    metadata = metrics.get("profile_metadata", {})
    if not isinstance(metadata, dict) or not metadata:
        return []
    lines = [
        "",
        "## Eval-Only Profile Metadata",
        "",
        (
            "| profile | eval_only | oracle_protected | uses_fixture_expected_ids | "
            "diagnostic_answer_contract | uses_fixture_answer_expectations | "
            "production_safe_evidence_contract | combines_candidate_governance | "
            "combines_rerank_injection | combines_version_boundary | "
            "does_not_expand_recall |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for profile in sorted(metadata):
        row = metadata.get(profile)
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    profile,
                    _fmt(row.get("eval_only")),
                    _fmt(row.get("oracle_protected")),
                    _fmt(row.get("uses_fixture_expected_ids")),
                    _fmt(row.get("diagnostic_answer_contract")),
                    _fmt(row.get("uses_fixture_answer_expectations")),
                    _fmt(row.get("production_safe_evidence_contract")),
                    _fmt(row.get("combines_candidate_governance")),
                    _fmt(row.get("combines_rerank_injection")),
                    _fmt(row.get("combines_version_boundary")),
                    _fmt(row.get("does_not_expand_recall")),
                ]
            )
            + " |"
        )
    return lines


def _answer_post_check_shadow_markdown_section(metrics: dict[str, object]) -> list[str]:
    shadow = metrics.get("answer_post_check_shadow", {})
    if not isinstance(shadow, dict) or not shadow:
        return []
    return [
        "",
        "## Answer Post-Check Shadow",
        "",
        "- `case_count`: `" + _fmt(shadow.get("case_count")) + "`",
        "- `enabled_case_count`: `" + _fmt(shadow.get("enabled_case_count")) + "`",
        "- `needs_retry_count`: `" + _fmt(shadow.get("needs_retry_count")) + "`",
        "- `forbidden_boundary_included_count`: `"
        + _fmt(shadow.get("forbidden_boundary_included_count"))
        + "`",
        "- `stale_evidence_included_count`: `"
        + _fmt(shadow.get("stale_evidence_included_count"))
        + "`",
        "- `conflict_evidence_included_count`: `"
        + _fmt(shadow.get("conflict_evidence_included_count"))
        + "`",
        "- `missing_likely_relevant_context_count`: `"
        + _fmt(shadow.get("missing_likely_relevant_context_count"))
        + "`",
        "- `insufficient_fallback_missing_count`: `"
        + _fmt(shadow.get("insufficient_fallback_missing_count"))
        + "`",
    ]


def _fmt_percent(value: object) -> str:
    if value is None:
        return "N/A"
    return _fmt(value)


def _fmt(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)
