"""Field contract tests for retrieval governance."""

from __future__ import annotations

from datetime import datetime

from memory2.eval_answer_contract import (
    ProductionEvidenceContract,
    build_production_governed_tri_evidence_contract,
    render_production_evidence_contract_block,
)
from memory2.eval_cases import EvalCase
from memory2.retrieval_experiments import (
    RetrievalLaneResult,
    build_provenance_lane,
    rrf_fuse_lanes,
)
from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_candidate_governance,
    apply_retrieval_route,
    build_retrieval_plan,
    build_retrieval_routing_decision,
)
from memory2.retriever import _rrf_merge_lanes


def _candidate(item_id: str, **extra: object) -> dict[str, object]:
    return {
        "id": item_id,
        "summary": f"memory {item_id}",
        "status": "active",
        "source_ref": f"telegram:1:{item_id}",
        "confidence": 0.9,
        **extra,
    }


def test_production_mode_ignores_protected_ids_for_strict_governance() -> None:
    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(
            enabled=True,
            protected_ids=("target",),
            eval_mode=False,
        )
    )

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate("target", source_ref="session:telegram:1", confidence=0.4),
            ],
        },
    )

    assert candidates == []
    assert trace["candidate_governance"]["protected_ids"] == []
    assert trace["protected_expected_ids"] == []
    assert trace["dropped_risks_by_reason"] == {
        "weak_source_ref": 1,
        "low_confidence": 1,
    }


def test_build_retrieval_plan_merges_request_and_route_fields() -> None:
    plan = build_retrieval_plan(
        "这条记忆的来源是什么？",
        scope_channel="telegram",
        scope_chat_id="room-1",
        memory_types=("event", "profile"),
        top_k=5,
        aux_queries=("来源",),
        score_threshold=0.55,
        time_start=datetime(2026, 8, 1),
        time_end=datetime(2026, 8, 18),
        keyword_enabled=True,
    )

    assert plan.query == "这条记忆的来源是什么？"
    assert plan.scope_channel == "telegram"
    assert plan.scope_chat_id == "room-1"
    assert plan.memory_types == ("event", "profile")
    assert plan.top_k == 5
    assert plan.score_threshold == 0.55
    assert plan.scene == "source_lookup"
    assert plan.allowed_lanes == ("provenance", "keyword", "semantic")
    assert plan.require_source_ref is True
    assert plan.require_scope_match is True
    assert plan.candidate_governance.enabled is False
    assert plan.to_routing_decision().scene == plan.scene


def test_eval_mode_allows_protected_ids_for_non_fatal_strict_governance() -> None:
    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(
            enabled=True,
            protected_ids=("target",),
            eval_mode=True,
        )
    )

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate("target", source_ref="session:telegram:1", confidence=0.4),
            ],
        },
    )

    assert [item["id"] for item in candidates] == ["target"]
    assert trace["candidate_governance"]["protected_ids"] == ["target"]
    assert trace["would_drop_protected_by_reason"] == {
        "weak_source_ref": 1,
        "low_confidence": 1,
    }


def test_candidate_governance_policy_serializes_decision_table_fields() -> None:
    policy = CandidateGovernancePolicy(
        enabled=True,
        mode="tiered",
        drop_rules=("scope_mismatch",),
        downgrade_rules=("low_confidence",),
        review_rules=("missing_source_ref",),
        allow_threshold=3,
        protected_ids=("eval-target",),
        eval_mode=True,
    )

    assert policy.to_dict() == {
        "enabled": True,
        "mode": "tiered",
        "drop_rules": ["scope_mismatch"],
        "downgrade_rules": ["low_confidence"],
        "review_rules": ["missing_source_ref"],
        "allow_threshold": 3,
        "protected_ids": ["eval-target"],
        "eval_mode": True,
        "protected_expected_ids": ["eval-target"],
        "drop_risks": ["scope_mismatch"],
        "fatal_risks": ["scope_mismatch"],
    }


def test_allow_threshold_drops_candidate_with_low_fused_rank() -> None:
    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(
            enabled=True,
            mode="strict",
            drop_rules=("low_rrf_rank",),
            allow_threshold=3,
        )
    )

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate(
                    "late",
                    retrieval={"fused_rank": 4},
                ),
            ],
        },
    )

    assert candidates == []
    assert trace["dropped_risks_by_reason"] == {"low_rrf_rank": 1}


def test_post_rrf_candidate_governance_separates_allowed_uncertain_and_dropped() -> None:
    policy = CandidateGovernancePolicy(enabled=True, mode="tiered")
    allowed, trace = apply_candidate_governance(
        [
            _candidate(
                "active",
                retrieval={"fused_rank": 1, "lane_hits": ["semantic"]},
            ),
            _candidate(
                "conflict",
                conflict=True,
                retrieval={"fused_rank": 2, "lane_hits": ["semantic", "keyword"]},
            ),
            _candidate(
                "old",
                status="superseded",
                retrieval={"fused_rank": 3, "lane_hits": ["semantic"]},
            ),
        ],
        policy,
    )

    assert [item["id"] for item in allowed] == ["active"]
    assert [item["id"] for item in trace["uncertain_candidates"]] == ["conflict"]
    assert [item["candidate_id"] for item in trace["dropped_candidates"]] == ["old"]
    assert trace["candidate_risk_tiers"] == [
        {"candidate_id": "active", "tier": "allow", "action": "allow", "risks": ()},
        {
            "candidate_id": "conflict",
            "tier": "requires_review",
            "action": "requires_review",
            "risks": ("conflict_candidate",),
        },
        {
            "candidate_id": "old",
            "tier": "delete",
            "action": "delete",
            "risks": ("superseded_candidate",),
        },
    ]


def test_rrf_merge_lanes_attaches_retrieval_metadata() -> None:
    fused = _rrf_merge_lanes(
        {
            "semantic": [
                _candidate("a", score=0.91),
                _candidate("b", score=0.88),
            ],
            "keyword": [
                _candidate("b", keyword_score=1.0),
                _candidate("c", keyword_score=0.5),
            ],
            "provenance": [
                _candidate("b", provenance_score=0.7),
            ],
        },
        top_n=3,
    )

    by_id = {str(item["id"]): item for item in fused}
    retrieval = by_id["b"]["retrieval"]
    assert retrieval["fused_rank"] == 1
    assert retrieval["lane_hits"] == ["semantic", "keyword", "provenance"]
    assert retrieval["lane_ranks"] == {
        "semantic": 2,
        "keyword": 1,
        "provenance": 1,
    }
    assert retrieval["lane_scores"] == {
        "semantic": 0.88,
        "keyword": 1.0,
        "provenance": 0.7,
    }
    assert retrieval["lane_submitted_counts"] == {
        "semantic": 2,
        "keyword": 2,
        "provenance": 1,
    }


def test_experiment_rrf_fuse_lanes_attaches_retrieval_metadata() -> None:
    fused = rrf_fuse_lanes(
        [
            RetrievalLaneResult("semantic", [_candidate("a", score=0.9)]),
            RetrievalLaneResult("keyword", [_candidate("a", keyword_score=1.0)]),
        ],
        top_n=1,
    )

    assert fused[0]["retrieval"]["fused_rank"] == 1
    assert fused[0]["retrieval"]["lane_hits"] == ["semantic", "keyword"]
    assert fused[0]["retrieval"]["lane_submitted_counts"] == {
        "semantic": 1,
        "keyword": 1,
    }


def test_provenance_lane_requires_structured_source_and_scope_signal() -> None:
    lane = build_provenance_lane(
        "that previous plan",
        [
            _candidate(
                "same-scope",
                scope_channel="telegram",
                scope_chat_id="room-1",
                turn_index=3,
            ),
            _candidate("no-source", source_ref=""),
            _candidate("text-only", summary="that previous plan"),
        ],
        scope_channel="telegram",
        scope_chat_id="room-1",
        limit=10,
    )

    assert [item["id"] for item in lane.items] == ["same-scope"]
    assert "provenance_score" in lane.items[0]


def test_production_evidence_contract_keeps_uncertain_out_of_summaries() -> None:
    contract = ProductionEvidenceContract(
        profile_name="test",
        diagnostic_eval_only=True,
        production_safe=True,
        uses_fixture_answer_expectations=False,
        candidate_governance_mode="tiered",
        allowed_evidence=("allowed",),
        likely_relevant_evidence=("allowed",),
        stale_warning=(),
        conflict_warning=(),
        active_version=("allowed",),
        forbidden_boundary=(),
        allowed_evidence_ids=("allowed",),
        likely_relevant_evidence_ids=("allowed",),
        downgrade_ids=(),
        requires_review_ids=("uncertain",),
        uncertain_evidence_ids=("uncertain",),
        stale_warning_ids=(),
        conflict_warning_ids=(),
        active_version_ids=("allowed",),
        insufficient_evidence_ids=(),
        insufficient_evidence_fallback=False,
        forbidden_boundary_ids=(),
        deleted_evidence_ids=(),
        evidence_summaries=(("allowed", "allowed content"),),
    )

    rendered = render_production_evidence_contract_block(contract)

    assert "uncertain_evidence_ids: uncertain" in rendered
    assert "allowed content" in rendered
    assert "uncertain content" not in rendered


def test_build_production_contract_excludes_requires_review_from_summaries() -> None:
    case = EvalCase(
        id="case-uncertain",
        title="Uncertain evidence contract",
        category="contract",
        phase_targets=(),
        config_profiles=(),
        setup={
            "query": "What is the current preference?",
            "memory_items": [
                {
                    "id": "allowed",
                    "summary": "allowed content",
                    "source_ref": "telegram:1:1",
                },
                {
                    "id": "uncertain",
                    "summary": "uncertain content",
                    "source_ref": "telegram:1:2",
                    "conflict": True,
                },
            ],
        },
        expectations={},
        source_path="",
    )

    contract = build_production_governed_tri_evidence_contract(
        case,
        {
            "ids": ["allowed", "uncertain"],
            "trace": {
                "candidate_risk_tiers": [
                    {
                        "candidate_id": "allowed",
                        "tier": "allow",
                        "risks": (),
                    },
                    {
                        "candidate_id": "uncertain",
                        "tier": "requires_review",
                        "risks": ("conflict_candidate",),
                    },
                ]
            },
        },
    )

    assert contract.allowed_evidence_ids == ("allowed",)
    assert contract.uncertain_evidence_ids == ("uncertain",)
    assert contract.evidence_summaries == (("allowed", "allowed content"),)


def test_empty_allowed_contract_instructs_model_not_to_use_uncertain() -> None:
    contract = ProductionEvidenceContract(
        profile_name="test",
        diagnostic_eval_only=True,
        production_safe=True,
        uses_fixture_answer_expectations=False,
        candidate_governance_mode="tiered",
        allowed_evidence=(),
        likely_relevant_evidence=(),
        stale_warning=(),
        conflict_warning=(),
        active_version=(),
        forbidden_boundary=(),
        allowed_evidence_ids=(),
        likely_relevant_evidence_ids=(),
        downgrade_ids=(),
        requires_review_ids=("uncertain",),
        uncertain_evidence_ids=("uncertain",),
        stale_warning_ids=(),
        conflict_warning_ids=(),
        active_version_ids=(),
        insufficient_evidence_ids=("uncertain",),
        insufficient_evidence_fallback=True,
        forbidden_boundary_ids=(),
        deleted_evidence_ids=(),
        evidence_summaries=(),
    )

    rendered = render_production_evidence_contract_block(contract)

    assert "uncertain_evidence_ids: uncertain" in rendered
    assert "Do not use uncertain_evidence as an answer source" in rendered
    assert "say the available memory cannot confirm the answer" in rendered
