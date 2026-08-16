from __future__ import annotations

import asyncio

from core.memory.engine import MemoryEngineRetrieveRequest
from memory2.eval_comprehensive_online import (
    ComprehensiveOnlineMemoryEngine,
    MEMORY_GOVERNANCE_PROFILE_ORDER,
    evidence_ids_for_profile,
    profile_evidence_source,
)
from memory2.eval_memory_governance_profiles import (
    get_memory_governance_profile,
    render_structured_evidence_only_block,
)
from memory2.eval_quantitative_cases import build_quantitative_eval_cases


def test_chain_tri_evidence_only_profile_exists() -> None:
    spec = get_memory_governance_profile("chain_tri_evidence_only")

    assert spec.name == "chain_tri_evidence_only"


def test_chain_tri_evidence_only_has_governance_and_structure_without_contract() -> None:
    spec = get_memory_governance_profile("chain_tri_evidence_only")

    assert spec.candidate_governance is True
    assert spec.structured_evidence is True
    assert spec.answer_contract is False
    assert spec.production_safe_contract is False
    assert spec.answer_guidance is False


def test_structured_evidence_only_block_has_sections() -> None:
    block = render_structured_evidence_only_block(
        allowed_evidence=[{"id": "m1", "summary": "允许证据"}],
        forbidden_evidence=[{"id": "m2", "summary": "禁用证据"}],
        conflict_evidence=[{"id": "m3", "summary": "冲突证据"}],
        version_boundaries=[{"from": "m2", "to": "m1", "type": "supersedes"}],
    )

    assert "Allowed Evidence" in block
    assert "Forbidden Evidence" in block
    assert "Conflict Evidence" in block
    assert "Version Boundaries" in block


def test_structured_evidence_only_block_does_not_include_answer_contract_language() -> None:
    block = render_structured_evidence_only_block(
        allowed_evidence=[{"id": "m1", "summary": "允许证据"}],
        forbidden_evidence=[],
        conflict_evidence=[],
        version_boundaries=[],
    )

    forbidden_phrases = (
        "必须根据证据回答",
        "只能使用允许证据回答",
        "不允许使用其他信息回答",
        "must answer",
        "only use allowed evidence",
    )
    assert not any(phrase in block for phrase in forbidden_phrases)


def test_profile_order_keeps_p3_between_p2_and_p4() -> None:
    assert MEMORY_GOVERNANCE_PROFILE_ORDER == (
        "chain_tri_retrieval",
        "chain_tri_candidate_governance",
        "chain_tri_evidence_only",
        "chain_tri_answer_contract",
        "chain_tri_governed_answer_contract",
    )


def test_evidence_only_profile_retrieves_governed_ids_with_structured_block() -> None:
    async def run() -> None:
        case = build_quantitative_eval_cases(case_set="common", limit=1)[0]
        engine = ComprehensiveOnlineMemoryEngine(
            case,
            profile_name="chain_tri_evidence_only",
            prompt_variant="baseline",
        )

        result = await engine.retrieve(MemoryEngineRetrieveRequest(query="test"))

        assert tuple(engine.used_memory_ids) == evidence_ids_for_profile(
            case,
            "chain_tri_evidence_only",
        )
        assert result.raw["evidence_source"] == profile_evidence_source(
            "chain_tri_evidence_only"
        )
        assert "Allowed Evidence" in result.text_block
        assert "Answer Contract" not in result.text_block

    asyncio.run(run())
