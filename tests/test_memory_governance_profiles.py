from __future__ import annotations

import asyncio

from core.memory.engine import MemoryEngineRetrieveRequest
from memory2.eval_comprehensive_online import (
    ComprehensiveOnlineMemoryEngine,
    FACTORIAL_GOVERNANCE_PROFILE_ORDER,
    MEMORY_GOVERNANCE_PROFILE_ORDER,
    evidence_ids_for_profile,
    profile_evidence_source,
)
from memory2.eval_memory_governance_profiles import (
    FACTORIAL_PROFILE_ALIASES,
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


def test_factorial_profile_order_covers_all_csa_combinations() -> None:
    assert FACTORIAL_GOVERNANCE_PROFILE_ORDER == (
        "tri_rrf",
        "tri_rrf_candidate",
        "tri_rrf_structured",
        "tri_rrf_answer",
        "tri_rrf_candidate_structured",
        "tri_rrf_candidate_answer",
        "tri_rrf_structured_answer",
        "tri_rrf_candidate_structured_answer",
    )

    combinations = {
        (
            get_memory_governance_profile(profile).candidate_governance,
            get_memory_governance_profile(profile).structured_evidence,
            get_memory_governance_profile(profile).answer_guidance,
        )
        for profile in FACTORIAL_GOVERNANCE_PROFILE_ORDER
    }
    assert combinations == {
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    }


def test_factorial_profiles_preserve_legacy_equivalents() -> None:
    assert FACTORIAL_PROFILE_ALIASES["chain_tri_retrieval"] == "tri_rrf"
    assert (
        FACTORIAL_PROFILE_ALIASES["chain_tri_governed_answer_contract"]
        == "tri_rrf_candidate_structured_answer"
    )
    assert get_memory_governance_profile("chain_tri_retrieval").name == "chain_tri_retrieval"
    assert get_memory_governance_profile("tri_rrf").name == "tri_rrf"


def test_factorial_profile_evidence_sources_are_named() -> None:
    assert profile_evidence_source("tri_rrf") == "tri_rrf.fused_ids"
    assert (
        profile_evidence_source("tri_rrf_candidate_structured_answer")
        == "tri_rrf_candidate_structured_answer.governed_structured_answer_ids"
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


def test_factorial_answer_only_profile_adds_guidance_without_structure() -> None:
    async def run() -> None:
        case = build_quantitative_eval_cases(case_set="common", limit=1)[0]
        engine = ComprehensiveOnlineMemoryEngine(
            case,
            profile_name="tri_rrf_answer",
            prompt_variant="baseline",
        )

        result = await engine.retrieve(MemoryEngineRetrieveRequest(query="test"))

        assert tuple(engine.used_memory_ids) == evidence_ids_for_profile(case, "tri_rrf")
        assert result.raw["factorial_profile"]["answer_guidance"] is True
        assert result.raw["factorial_profile"]["structured_evidence"] is False
        assert "Answer Guidance" in result.text_block
        assert "Allowed Evidence" not in result.text_block

    asyncio.run(run())


def test_factorial_structured_only_profile_uses_tri_ids_without_candidate_governance() -> None:
    async def run() -> None:
        case = build_quantitative_eval_cases(case_set="common", limit=1)[0]
        engine = ComprehensiveOnlineMemoryEngine(
            case,
            profile_name="tri_rrf_structured",
            prompt_variant="baseline",
        )

        result = await engine.retrieve(MemoryEngineRetrieveRequest(query="test"))

        assert tuple(engine.used_memory_ids) == evidence_ids_for_profile(case, "tri_rrf")
        assert result.raw["factorial_profile"]["candidate_governance"] is False
        assert result.raw["factorial_profile"]["structured_evidence"] is True
        assert "Allowed Evidence" in result.text_block
        assert "Answer Guidance" not in result.text_block

    asyncio.run(run())
