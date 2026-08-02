from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent.provider import LLMResponse
from core.memory.engine import MemoryEngineRetrieveRequest
from memory2.eval_comprehensive_online import (
    answer_expectation_for_profile,
    build_comprehensive_online_report_from_checkpoint,
    build_comprehensive_run_specs,
    ComprehensiveOnlineMemoryEngine,
    evidence_ids_for_profile,
    governed_tri_trace_for_case,
    profile_evidence_source,
    rerank_governed_evidence_order,
    run_comprehensive_online_eval,
    version_governed_tri_trace_for_case,
    write_comprehensive_online_markdown,
)
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_runner import _baseline_recalled_items


EXPECTED_ANSWER_QUALITY_PROFILES = [
    "chain_memory_base",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_all_on",
]


class ComprehensiveScriptedProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
        if "memory_id=" not in text:
            answer = "没有可用记忆，无法确认。"
        elif "Evidence Contract: chain_tri_" in text:
            answer = "根据 production-safe evidence contract，应使用 allowed_evidence，并在证据不足时说明无法确认。"
        elif "Answer Contract: chain_tri_governed_answer_contract" in text:
            answer = "根据 governed Answer Contract，应使用治理后的 allowed_evidence，并避免 forbidden_terms。"
        elif "Answer Contract: chain_tri_answer_contract" in text:
            answer = "根据 Answer Contract，应使用 must_use_memory_ids 中的证据回答，并避免 forbidden_terms。"
        elif "RRF" in text:
            answer = "三路召回使用 RRF 融合排序，并用中文回答。"
        elif "NetworkX" in text:
            answer = "NetworkX 图谱可以辅助第三路召回，并用中文回答。"
        elif "pytest" in text:
            answer = "Python 测试优先使用 pytest，并用中文回答。"
        else:
            answer = "应根据注入记忆回答，并用中文保留关键术语。"
        return LLMResponse(
            content=answer,
            tool_calls=[],
            provider_fields={
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                }
            },
        )


class SlowCountingProvider:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return LLMResponse(
                content="应根据注入记忆回答，并用中文保留关键术语。",
                tool_calls=[],
                provider_fields={
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 10,
                        "total_tokens": 30,
                    }
                },
            )
        finally:
            self.active -= 1


class CountingProvider:
    def __init__(self) -> None:
        self.call_count = 0

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            content="应根据注入记忆回答，并用中文保留关键术语。",
            tool_calls=[],
            provider_fields={
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                }
            },
        )


def _checkpoint_result(
    *,
    case_id: str = "case-1",
    profile_name: str = "chain_all_on",
    provider_error: bool = False,
    timeout: bool = False,
    passed: bool = True,
) -> dict[str, object]:
    return {
        "answer_length": 20,
        "answer_rule_passed": passed,
        "case_id": case_id,
        "category": "common",
        "completion_token_count": 10,
        "evidence_source": "none",
        "expected_memory_used": False,
        "failures": ["provider_error"] if provider_error else [],
        "forbidden_contains_violation_count": 0,
        "latency_ms": 100,
        "memory_grounding_passed": passed,
        "passed": passed,
        "profile_name": profile_name,
        "prompt_token_count": 20,
        "prompt_variant": "baseline",
        "provider_error": provider_error,
        "repeat_index": 0,
        "timeout": timeout,
        "token_metrics_available": True,
        "total_token_count": 30,
        "used_memory_id_count": 1,
    }


def test_evidence_ids_for_profile_models_chain_visibility() -> None:
    case = build_quantitative_eval_cases(limit=1)[0]

    assert evidence_ids_for_profile(case, "chain_memory_base") == tuple(
        item["id"] for item in _baseline_recalled_items(case)
    )
    assert evidence_ids_for_profile(case, "chain_off") == ()
    assert evidence_ids_for_profile(case, "chain_write_value") == ()
    assert evidence_ids_for_profile(case, "chain_tri_retrieval")
    assert profile_evidence_source("chain_tri_retrieval") == "tri_retrieval.fused_ids"
    assert (
        profile_evidence_source("chain_graph_retrieval")
        == "graph_retrieval.graph_fused_ids"
    )
    assert (
        profile_evidence_source("chain_rerank_injection")
        == "injection_governance.experimental_injected_ids"
    )
    assert (
        profile_evidence_source("chain_version_provenance")
        == "version_chain.active_leaf_ids"
    )
    assert (
        profile_evidence_source("chain_sleep_consolidation")
        == "sleep_consolidation.filtered_active_ids"
    )


def test_governed_tri_profile_preserves_targets_and_drops_should_not_candidates() -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    )
    cases_with_should_not_in_tri = 0

    for case in cases:
        tri_ids = list(evidence_ids_for_profile(case, "chain_tri_retrieval"))
        governed_ids = list(
            evidence_ids_for_profile(case, "chain_tri_candidate_governance")
        )
        expected_ids = {str(item) for item in case.expectations["should_recall_ids"]}
        should_not_ids = {
            str(item) for item in case.expectations["should_not_recall_ids"]
        }
        governed_set = set(governed_ids)

        assert expected_ids <= set(tri_ids)
        assert expected_ids <= governed_set
        assert not (governed_set & should_not_ids)
        assert len(governed_ids) == len(governed_set)
        assert governed_ids == [
            item_id for item_id in tri_ids if item_id in governed_set
        ]
        if set(tri_ids) & should_not_ids:
            cases_with_should_not_in_tri += 1

    assert len(cases) == 40
    assert cases_with_should_not_in_tri > 0


def test_middle_profiles_keep_version_and_injection_boundaries() -> None:
    cases = build_quantitative_eval_cases()
    tri_vs_version = 0
    graph_vs_rerank = 0
    graph_rerank_same_categories: set[str] = set()

    for case in cases:
        tri = evidence_ids_for_profile(case, "chain_tri_retrieval")
        graph = evidence_ids_for_profile(case, "chain_graph_retrieval")
        rerank = evidence_ids_for_profile(case, "chain_rerank_injection")
        version = evidence_ids_for_profile(case, "chain_version_provenance")
        if tri != version:
            tri_vs_version += 1
        if graph != rerank:
            graph_vs_rerank += 1
        else:
            graph_rerank_same_categories.add(case.category)

    assert tri_vs_version == len(cases)
    assert graph_vs_rerank >= len(cases) - 4
    assert graph_rerank_same_categories <= {"hard_version_chain"}


def test_version_provenance_grounding_uses_active_version_ids() -> None:
    case = next(
        item
        for item in build_quantitative_eval_cases(case_pack="comprehensive")
        if item.expectations.get("expected_active_version_ids")
    )

    expectation = answer_expectation_for_profile(case, "chain_version_provenance")

    assert expectation.expected_memory_ids == tuple(
        case.expectations["expected_active_version_ids"]
    )
    assert all(
        item_id in evidence_ids_for_profile(case, "chain_version_provenance")
        for item_id in expectation.expected_memory_ids
    )


def test_version_provenance_online_scoring_not_forced_to_graph_ids(
    tmp_path: Path,
) -> None:
    case = next(
        item
        for item in build_quantitative_eval_cases(case_pack="comprehensive")
        if item.expectations.get("expected_active_version_ids")
    )
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_version_provenance",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    record = report.case_records[0]
    assert record["memory_grounding_passed"] is True
    assert "missing expected memory ids" not in "\n".join(
        str(failure) for failure in record["failures"]
    )


def test_build_comprehensive_run_specs_can_create_320_answer_runs() -> None:
    cases = build_quantitative_eval_cases()
    specs = build_comprehensive_run_specs(
        cases,
        repeats=2,
        prompt_variants=("baseline", "coached"),
        profiles=("chain_all_on",),
    )

    assert len(cases) == 80
    assert len(specs) == 320
    assert {spec.profile_name for spec in specs} == {"chain_all_on"}
    assert {spec.prompt_variant for spec in specs} == {"baseline", "coached"}
    assert max(spec.repeat_index for spec in specs) == 1


def test_run_comprehensive_online_eval_reports_profile_metrics(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=4)
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_off", "chain_all_on"),
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    assert report.metrics["case_count"] == 8
    assert report.metrics["profile_count"] == 2
    assert report.metrics["real_llm_enabled"] is False
    assert report.metrics["raw_query_included"] is False
    assert "profile_summaries" in report.metrics
    off = report.metrics["profile_summaries"]["chain_off"]
    all_on = report.metrics["profile_summaries"]["chain_all_on"]
    assert off["memory_grounding_pass_rate"] == 0.0
    assert all_on["memory_grounding_pass_rate"] == 100.0
    assert all_on["avg_total_token_count"] == 30.0


def test_online_report_uses_chain_memory_base_for_profile_comparison(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=4)
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_memory_base", "chain_off", "chain_all_on"),
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    assert report.metrics["baseline_profile"] == "chain_memory_base"
    assert report.metrics["control_profile"] == "chain_off"
    uplift = report.metrics["profile_uplift_vs_memory_base"]
    assert uplift["chain_memory_base"] == 0.0
    assert uplift["chain_all_on"] == round(
        float(report.metrics["profile_summaries"]["chain_all_on"]["main_score"])
        - float(report.metrics["profile_summaries"]["chain_memory_base"]["main_score"]),
        4,
    )


def test_online_report_exposes_answer_quality_uplift_vs_memory_base(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=4, case_pack="comprehensive")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=tuple(EXPECTED_ANSWER_QUALITY_PROFILES),
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    rows = report.metrics["profile_answer_quality_uplift_vs_memory_base"]
    base = rows["chain_memory_base"]
    tri = rows["chain_tri_retrieval"]

    assert base["baseline_profile"] == "chain_memory_base"
    assert base["is_combo_check_row"] is False
    assert base["answer_pass_relative_lift_percent"] == 0.0
    assert base["grounding_pass_relative_lift_percent"] == 0.0
    assert tri["case_count"] == 4
    assert tri["is_combo_check_row"] is False
    assert "answer_pass_delta_points" in tri
    assert "grounding_pass_delta_points" in tri
    assert "forbidden_violation_reduction_percent" in tri
    assert "avg_total_token_overhead" in tri
    assert "avg_latency_overhead_ms" in tri
    assert report.metrics["answer_quality_required_profiles"] == list(
        EXPECTED_ANSWER_QUALITY_PROFILES
    )
    assert report.metrics["answer_quality_missing_profiles"] == []
    assert report.metrics["answer_quality_partial_matrix"] is False


def test_optional_tri_candidate_governance_profile_does_not_make_old_reports_partial(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="standard")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_memory_base", "chain_tri_retrieval"),
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    assert "chain_tri_candidate_governance" not in report.metrics[
        "answer_quality_missing_profiles"
    ]
    assert "chain_tri_candidate_governance" not in report.metrics["profile_metadata"]


def test_optional_tri_candidate_governance_profile_gets_answer_quality_row(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="standard")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=(
            "chain_memory_base",
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
        ),
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    rows = report.metrics["profile_answer_quality_uplift_vs_memory_base"]
    assert "chain_tri_candidate_governance" in rows
    assert rows["chain_tri_candidate_governance"]["case_count"] == 2
    metadata = report.metrics["profile_metadata"]["chain_tri_candidate_governance"]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["uses_fixture_expected_ids"] is True


def test_tri_answer_contract_profile_is_optional_eval_only() -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]

    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    assert len(specs) == 1
    assert evidence_ids_for_profile(case, "chain_tri_answer_contract")
    assert (
        profile_evidence_source("chain_tri_answer_contract")
        == "tri_answer_contract.allowed_evidence_ids"
    )


def test_tri_answer_contract_profile_injects_contract_block(tmp_path: Path) -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert "Answer Contract: chain_tri_answer_contract" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "forbidden_memory_ids:" in result.text_block
    assert result.raw["evidence_source"] == "tri_answer_contract.allowed_evidence_ids"


def _case_with_tiered_tri_candidate():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        trace_info = governed_tri_trace_for_case(case)
        trace = trace_info["trace"]
        records = trace.get("candidate_risk_tiers", [])
        accepted_ids = set(trace_info["ids"])
        accepted_soft_ids = {
            str(record["candidate_id"])
            for record in records
            if record.get("tier") in {"downgrade", "requires_review"}
            and str(record.get("candidate_id") or "") in accepted_ids
        }
        deleted_ids = {
            str(record["candidate_id"])
            for record in records
            if record.get("tier") == "delete"
        }
        if accepted_soft_ids and deleted_ids.isdisjoint(accepted_ids):
            return case
    raise AssertionError("fixture must include a tiered governed tri case")


def test_tri_candidate_governance_uses_tiered_evidence_source() -> None:
    case = _case_with_tiered_tri_candidate()

    governed_ids = evidence_ids_for_profile(case, "chain_tri_candidate_governance")

    assert governed_ids
    assert (
        profile_evidence_source("chain_tri_candidate_governance")
        == "tri_candidate_governance.risk_tiered_allowed_ids"
    )
    assert set(governed_ids) <= set(evidence_ids_for_profile(case, "chain_tri_retrieval"))
    assert set(governed_ids).isdisjoint(
        set(str(item) for item in case.expectations["should_not_recall_ids"])
    )
    trace_info = governed_tri_trace_for_case(case)
    trace = trace_info["trace"]
    accepted_ids = set(trace_info["ids"])
    assert any(
        record.get("tier") in {"downgrade", "requires_review"}
        and str(record.get("candidate_id") or "") in accepted_ids
        for record in trace["candidate_risk_tiers"]
    )
    assert all(
        record.get("tier") != "delete"
        or str(record.get("candidate_id") or "") not in accepted_ids
        for record in trace["candidate_risk_tiers"]
    )


def test_tri_candidate_governance_raw_exposes_tiered_trace(tmp_path: Path) -> None:
    case = _case_with_tiered_tri_candidate()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_candidate_governance",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert result.raw["candidate_governance_mode"] == "tiered"
    assert isinstance(result.raw["candidate_risk_tier_counts"], dict)
    assert isinstance(result.raw["accepted_candidate_risk_tier_counts"], dict)
    assert isinstance(result.raw["candidate_risk_tiers"], list)


def test_governed_answer_contract_raw_exposes_tiered_candidate_trace(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert result.raw["candidate_governance_mode"] == "tiered"
    assert isinstance(result.raw["candidate_risk_tier_counts"], dict)
    assert isinstance(result.raw["candidate_risk_tiers"], list)
    assert result.raw["answer_contract"]["candidate_governance_mode"] == "tiered"


def _case_with_tri_governance_drop():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        tri_ids = set(evidence_ids_for_profile(case, "chain_tri_retrieval"))
        governed_ids = set(
            evidence_ids_for_profile(case, "chain_tri_candidate_governance")
        )
        if tri_ids - governed_ids:
            return case
    raise AssertionError("fixture must include at least one governed tri drop")


def test_tri_governed_answer_contract_profile_is_optional_eval_only() -> None:
    case = _case_with_tri_governance_drop()

    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    assert len(specs) == 1
    assert evidence_ids_for_profile(case, "chain_tri_governed_answer_contract")
    assert evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    ) == evidence_ids_for_profile(case, "chain_tri_candidate_governance")
    assert set(evidence_ids_for_profile(case, "chain_tri_retrieval")) > set(
        evidence_ids_for_profile(case, "chain_tri_governed_answer_contract")
    )
    assert (
        profile_evidence_source("chain_tri_governed_answer_contract")
        == "tri_governed_answer_contract.governed_allowed_evidence_ids"
    )


def test_tri_governed_answer_contract_profile_injects_governed_contract_block(
    tmp_path: Path,
) -> None:
    case = _case_with_tri_governance_drop()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert "Evidence Contract: chain_tri_governed_answer_contract" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "forbidden_boundary_count:" in result.text_block
    assert "deleted_evidence_count:" in result.text_block
    assert "forbidden_boundary_ids:" not in result.text_block
    assert "deleted_evidence_ids:" not in result.text_block
    assert result.raw["candidate_risk_tier_counts"]["delete"] > 0
    assert result.raw["tiered_deleted_risks_by_reason"]
    assert result.raw["evidence_source"] == (
        "tri_governed_answer_contract.governed_allowed_evidence_ids"
    )
    assert result.raw["answer_contract"]["diagnostic_eval_only"] is True
    assert result.raw["answer_contract"]["production_safe"] is True
    assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
    assert result.raw["answer_contract"]["uses_fixture_answer_expectations"] is False
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True


def test_governed_answer_contract_profile_uses_production_safe_contract(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert "Evidence Contract: chain_tri_governed_answer_contract" in result.text_block
    assert "production_safe=true" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "likely_relevant_evidence_ids:" in result.text_block
    assert "forbidden_boundary_count:" in result.text_block
    assert "forbidden_boundary_ids:" not in result.text_block
    assert "required_terms:" not in result.text_block
    assert "required_term_groups:" not in result.text_block
    assert "forbidden_terms:" not in result.text_block
    assert result.raw["answer_contract"]["production_safe"] is True
    assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
    assert result.raw["answer_contract"]["uses_fixture_answer_expectations"] is False
    assert "allowed_evidence" in result.raw["answer_contract"]
    assert "likely_relevant_evidence" in result.raw["answer_contract"]
    assert "stale_warning" in result.raw["answer_contract"]
    assert "conflict_warning" in result.raw["answer_contract"]
    assert "active_version" in result.raw["answer_contract"]
    assert "forbidden_boundary" in result.raw["answer_contract"]
    assert "required_terms" not in result.raw["answer_contract"]
    assert "required_term_groups" not in result.raw["answer_contract"]
    assert "forbidden_terms" not in result.raw["answer_contract"]


def test_governed_answer_contract_scoring_expectation_is_not_oracle_terms() -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    oracle = answer_expectation_for_profile(case, "chain_tri_answer_contract")

    expectation = answer_expectation_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )

    assert oracle.expected_answer_contains or oracle.expected_answer_contains_any
    assert expectation.expected_answer_contains == ()
    assert expectation.expected_answer_contains_any == ()
    assert expectation.forbidden_answer_contains == ()
    assert expectation.expected_memory_ids == evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    assert expectation.grounding_required is True


def _case_with_version_boundary_signal():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        if case.setup.get("memory_replacements"):
            return case
    raise AssertionError("fixture must include memory replacements")


def test_version_governed_profile_does_not_expand_governed_ids() -> None:
    case = _case_with_version_boundary_signal()

    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    version_governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_version_governed_answer_contract",
    )

    assert version_governed_ids == governed_ids
    assert set(version_governed_ids) == set(governed_ids)
    assert profile_evidence_source(
        "chain_tri_version_governed_answer_contract"
    ) == (
        "tri_version_governed_answer_contract."
        "version_boundaried_governed_allowed_evidence_ids"
    )


def test_version_governed_trace_exposes_boundary_without_recall_expansion() -> None:
    case = _case_with_version_boundary_signal()

    trace_info = version_governed_tri_trace_for_case(case)
    version_boundary = trace_info["trace"]["version_boundary"]
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )

    assert trace_info["ids"] == governed_ids
    assert version_boundary["recall_expanded"] is False
    assert isinstance(version_boundary["active_version_ids"], list)
    assert isinstance(version_boundary["stale_warning_ids"], list)
    assert isinstance(version_boundary["forbidden_boundary_ids"], list)
    assert set(version_boundary["active_version_ids"]) <= set(governed_ids)
    assert set(version_boundary["stale_warning_ids"]) <= set(governed_ids)
    assert set(version_boundary["forbidden_boundary_ids"]).isdisjoint(governed_ids)


def test_version_governed_profile_injects_production_safe_contract_block(
    tmp_path: Path,
) -> None:
    case = _case_with_version_boundary_signal()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_version_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )

    assert (
        "Evidence Contract: chain_tri_version_governed_answer_contract"
        in result.text_block
    )
    assert "active_version_ids:" in result.text_block
    assert "stale_warning_ids:" in result.text_block
    assert "forbidden_boundary_count:" in result.text_block
    assert "forbidden_boundary_ids:" not in result.text_block
    assert result.raw["evidence_source"] == (
        "tri_version_governed_answer_contract."
        "version_boundaried_governed_allowed_evidence_ids"
    )
    assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True
    assert result.raw["answer_contract"]["combines_version_boundary"] is True
    assert result.raw["version_boundary"]["recall_expanded"] is False
    assert tuple(result.raw["ids"]) == governed_ids
    assert tuple(engine.used_memory_ids) == governed_ids
    assert tuple(hit.id for hit in result.hits) == governed_ids
    assert set(result.raw["answer_contract"]["forbidden_boundary_ids"]).isdisjoint(
        result.raw["answer_contract"]["allowed_evidence_ids"]
    )


def test_version_governed_engine_hides_forbidden_ids_but_keeps_raw_post_check() -> None:
    case = _case_with_version_boundary_signal()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_version_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )
    forbidden_ids = tuple(result.raw["answer_contract"]["forbidden_boundary_ids"])
    deleted_ids = tuple(result.raw["answer_contract"]["deleted_evidence_ids"])

    assert forbidden_ids
    assert "forbidden_boundary_ids:" not in result.text_block
    assert "deleted_evidence_ids:" not in result.text_block
    for item_id in forbidden_ids + deleted_ids:
        assert item_id not in result.text_block
    assert "forbidden_boundary_count:" in result.text_block
    assert "deleted_evidence_count:" in result.text_block


def test_version_governed_profile_report_metadata_and_post_check_shadow(
    tmp_path: Path,
) -> None:
    case = _case_with_version_boundary_signal()
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_version_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    metadata = report.metrics["profile_metadata"][
        "chain_tri_version_governed_answer_contract"
    ]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["combines_candidate_governance"] is True
    assert metadata["combines_version_boundary"] is True
    assert metadata["does_not_expand_recall"] is True
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 1
    assert report.case_records[0]["answer_post_check_shadow"]["shadow_enabled"] is True


def test_version_governed_answer_expectation_is_grounding_only_not_oracle_terms() -> None:
    case = _case_with_version_boundary_signal()

    expectation = answer_expectation_for_profile(
        case,
        "chain_tri_version_governed_answer_contract",
    )

    assert expectation.expected_answer_contains == ()
    assert expectation.expected_answer_contains_any == ()
    assert expectation.forbidden_answer_contains == ()
    assert expectation.expected_memory_ids == evidence_ids_for_profile(
        case,
        "chain_tri_version_governed_answer_contract",
    )
    assert expectation.grounding_required is True


def test_version_governed_boundary_ignores_unrelated_superseded_fixture_rows() -> None:
    case = _case_with_version_boundary_signal()
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                *case.setup.get("memory_items", ()),
                {
                    "id": "unrelated_old",
                    "summary": "unrelated superseded fixture evidence",
                    "status": "superseded",
                    "source_ref": "telegram:unrelated:0",
                },
                {
                    "id": "unrelated_new",
                    "summary": "unrelated active fixture evidence",
                    "status": "active",
                    "source_ref": "telegram:unrelated:1",
                },
            ],
            "memory_replacements": [
                *case.setup.get("memory_replacements", ()),
                {
                    "old_item_id": "unrelated_old",
                    "new_item_id": "unrelated_new",
                    "old_summary": "unrelated superseded fixture evidence",
                    "new_summary": "unrelated active fixture evidence",
                    "old_source_ref": "telegram:unrelated:0",
                    "new_source_ref": "telegram:unrelated:1",
                },
            ],
        },
    )

    trace_info = version_governed_tri_trace_for_case(case)
    boundary = trace_info["trace"]["version_boundary"]

    assert trace_info["ids"] == governed_ids
    assert "unrelated_old" not in boundary["stale_warning_ids"]
    assert "unrelated_old" not in boundary["forbidden_boundary_ids"]
    assert "unrelated_new" not in boundary["active_version_ids"]


def test_tri_answer_contract_profile_report_records_eval_only_metadata(
    tmp_path: Path,
) -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    metadata = report.metrics["profile_metadata"]["chain_tri_answer_contract"]
    assert metadata["eval_only"] is True
    assert metadata["diagnostic_answer_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is True
    assert report.metrics["profile_summaries"]["chain_tri_answer_contract"][
        "case_count"
    ] == 1

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")
    assert "diagnostic_answer_contract" in markdown
    assert "uses_fixture_answer_expectations" in markdown


def test_tri_governed_answer_contract_report_records_combined_eval_metadata(
    tmp_path: Path,
) -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    metadata = report.metrics["profile_metadata"][
        "chain_tri_governed_answer_contract"
    ]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["uses_fixture_expected_ids"] is True
    assert metadata["diagnostic_answer_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is False
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["combines_candidate_governance"] is True

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")
    assert "chain_tri_governed_answer_contract" in markdown
    assert "combines_candidate_governance" in markdown


def test_governed_answer_contract_report_metadata_marks_no_fixture_answer_expectations(
    tmp_path: Path,
) -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    metadata = report.metrics["profile_metadata"][
        "chain_tri_governed_answer_contract"
    ]
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is False

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")
    assert "production_safe_evidence_contract" in markdown


def test_rerank_governed_evidence_order_reorders_only_within_governed_set() -> None:
    ordered = rerank_governed_evidence_order(
        governed_ids=("target", "weak", "tail", "stale"),
        rerank_ids=("outside", "tail", "target", "outside_2"),
    )

    assert ordered == ("tail", "target", "weak", "stale")


def _case_with_rerank_governed_order_delta():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_governed_answer_contract",
        )
        rerank_ids = evidence_ids_for_profile(case, "chain_rerank_injection")
        rerank_set = set(rerank_ids)
        expected_order = tuple(
            [item_id for item_id in rerank_ids if item_id in set(governed_ids)]
            + [item_id for item_id in governed_ids if item_id not in rerank_set]
        )
        if governed_ids and expected_order != governed_ids:
            return case, governed_ids, rerank_ids, expected_order
    raise AssertionError("fixture must include a rerank/governed ordering delta")


def test_rerank_governed_profile_reorders_without_expanding_governed_ids() -> None:
    case, governed_ids, rerank_ids, expected_order = (
        _case_with_rerank_governed_order_delta()
    )

    rerank_governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )

    assert rerank_governed_ids == expected_order
    assert set(rerank_governed_ids) == set(governed_ids)
    assert set(rerank_governed_ids).isdisjoint(
        set(evidence_ids_for_profile(case, "chain_tri_retrieval")) - set(governed_ids)
    )
    assert any(item_id in rerank_ids for item_id in rerank_governed_ids)
    assert profile_evidence_source(
        "chain_tri_rerank_governed_answer_contract"
    ) == "tri_rerank_governed_answer_contract.reranked_governed_allowed_evidence_ids"


def test_rerank_governed_profile_never_expands_recall_on_p6o6_slice() -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    )

    for case in cases:
        governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_governed_answer_contract",
        )
        rerank_governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_rerank_governed_answer_contract",
        )

        assert set(rerank_governed_ids) == set(governed_ids)
        assert len(rerank_governed_ids) == len(governed_ids)


def test_rerank_governed_profile_injects_production_safe_contract_block(
    tmp_path: Path,
) -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_rerank_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert (
        "Evidence Contract: chain_tri_rerank_governed_answer_contract"
        in result.text_block
    )
    assert "production_safe=true" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "forbidden_boundary_count:" in result.text_block
    assert "forbidden_boundary_ids:" not in result.text_block
    assert result.raw["evidence_source"] == (
        "tri_rerank_governed_answer_contract.reranked_governed_allowed_evidence_ids"
    )
    assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True
    assert result.raw["answer_contract"]["combines_rerank_injection"] is True
    assert result.raw["rerank_signal"]["recall_expanded"] is False


def test_rerank_governed_profile_report_metadata_and_post_check_shadow(
    tmp_path: Path,
) -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_rerank_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    metadata = report.metrics["profile_metadata"][
        "chain_tri_rerank_governed_answer_contract"
    ]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["combines_candidate_governance"] is True
    assert metadata["combines_rerank_injection"] is True
    assert metadata["does_not_expand_recall"] is True
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 1
    assert report.case_records[0]["answer_post_check_shadow"]["shadow_enabled"] is True


def test_rerank_governed_profile_metadata_markdown_exposes_rerank_columns(
    tmp_path: Path,
) -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_rerank_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert "combines_rerank_injection" in markdown
    assert "does_not_expand_recall" in markdown
    assert "chain_tri_rerank_governed_answer_contract" in markdown


def test_rerank_governed_answer_expectation_is_grounding_only_not_oracle_terms() -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )

    expectation = answer_expectation_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )

    assert expectation.expected_answer_contains == ()
    assert expectation.expected_answer_contains_any == ()
    assert expectation.forbidden_answer_contains == ()
    assert expectation.expected_memory_ids == evidence_ids_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )
    assert expectation.grounding_required is True


def _case_with_version_boundary_and_rerank_delta():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        if not case.setup.get("memory_replacements"):
            continue
        governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_governed_answer_contract",
        )
        rerank_ids = evidence_ids_for_profile(
            case,
            "chain_tri_rerank_governed_answer_contract",
        )
        if rerank_ids != governed_ids and set(rerank_ids) == set(governed_ids):
            return case
    raise AssertionError("fixture must include version boundary case with rerank delta")


def test_rerank_version_governed_profile_reorders_without_recall_expansion() -> None:
    case = _case_with_version_boundary_and_rerank_delta()

    combo_ids = evidence_ids_for_profile(
        case,
        "chain_tri_rerank_version_governed_answer_contract",
    )
    rerank_ids = evidence_ids_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )

    assert combo_ids == rerank_ids
    assert combo_ids != governed_ids
    assert set(combo_ids) == set(governed_ids)
    assert profile_evidence_source(
        "chain_tri_rerank_version_governed_answer_contract"
    ) == (
        "tri_rerank_version_governed_answer_contract."
        "reranked_version_boundaried_governed_allowed_evidence_ids"
    )


def test_rerank_version_governed_profile_injects_safe_combined_contract() -> None:
    case = _case_with_version_boundary_and_rerank_delta()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_rerank_version_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert (
        "Evidence Contract: chain_tri_rerank_version_governed_answer_contract"
        in result.text_block
    )
    assert "forbidden_boundary_ids:" not in result.text_block
    assert "deleted_evidence_ids:" not in result.text_block
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True
    assert result.raw["answer_contract"]["combines_rerank_injection"] is True
    assert result.raw["answer_contract"]["combines_version_boundary"] is True
    assert result.raw["answer_contract"]["does_not_expand_recall"] is True
    assert result.raw["rerank_signal"]["recall_expanded"] is False
    assert result.raw["version_boundary"]["recall_expanded"] is False


def test_p6o3_governed_contract_fake_provider_smoke_is_private(
    tmp_path: Path,
) -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=2, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=2, case_pack="standard")
    )
    specs = build_comprehensive_run_specs(
        cases,
        profiles=(
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
            "chain_tri_governed_answer_contract",
        ),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )
    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert report.metrics["case_count"] == 12
    assert report.metrics["real_llm_enabled"] is False
    assert report.metrics["provider_error_count"] == 0
    assert report.metrics["timeout_count"] == 0
    metadata = report.metrics["profile_metadata"][
        "chain_tri_governed_answer_contract"
    ]
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is False
    governed_rows = [
        row
        for row in report.case_records
        if row["profile_name"] == "chain_tri_governed_answer_contract"
    ]
    assert governed_rows
    assert all(row["passed"] is True for row in governed_rows)
    assert all(row["failures"] == [] for row in governed_rows)
    assert "production_safe_evidence_contract" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown


def test_p6o4_governed_contract_records_answer_post_check_shadow(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    assert report.metrics["answer_post_check_shadow"]["case_count"] == 1
    assert report.metrics["answer_post_check_shadow"]["enabled_case_count"] == 1
    assert report.metrics["answer_post_check_shadow"]["needs_retry_count"] == 0
    record = report.case_records[0]
    shadow = record["answer_post_check_shadow"]
    assert shadow["shadow_enabled"] is True
    assert shadow["production_safe_evidence_contract"] is True
    assert shadow["allowed_evidence_included"] is True
    assert shadow["forbidden_boundary_included"] is False
    assert shadow["needs_retry"] is False
    assert "raw_answer" not in shadow
    assert "full_answer" not in shadow


def test_p6o4_answer_post_check_shadow_markdown_is_private(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )
    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert "## Answer Post-Check Shadow" in markdown
    assert "needs_retry_count" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
    assert "根据 production-safe evidence contract" not in markdown


def test_p6o4_post_check_shadow_does_not_change_scoring_or_provider_calls(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    target_id = governed_ids[0]
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                {
                    **item,
                    "insufficient_evidence": (
                        True
                        if str(item.get("id") or item.get("memory_id") or "")
                        == target_id
                        else item.get("insufficient_evidence", False)
                    ),
                }
                for item in case.setup["memory_items"]
            ],
        },
    )
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )
    provider = CountingProvider()

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            provider,
            model="scripted",
            real_llm_enabled=False,
        )
    )

    record = report.case_records[0]
    shadow = record["answer_post_check_shadow"]
    assert provider.call_count == 1
    assert record["passed"] is True
    assert record["answer_rule_passed"] is True
    assert record["memory_grounding_passed"] is True
    assert record["failures"] == []
    assert shadow["needs_retry"] is True
    assert "insufficient_evidence_fallback_missing" in shadow["retry_reasons"]
    assert report.metrics["answer_post_check_shadow"]["needs_retry_count"] == 1


def test_p6o4_non_governed_rows_have_no_post_check_shadow(
    tmp_path: Path,
) -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_retrieval",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    assert report.case_records[0]["answer_post_check_shadow"] is None
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 0


def test_p6o4_answer_post_check_shadow_fake_provider_smoke(
    tmp_path: Path,
) -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=2, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=2, case_pack="standard")
    )
    specs = build_comprehensive_run_specs(
        cases,
        profiles=(
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
            "chain_tri_governed_answer_contract",
        ),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )
    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert report.metrics["case_count"] == 12
    assert report.metrics["real_llm_enabled"] is False
    assert report.metrics["provider_error_count"] == 0
    assert report.metrics["timeout_count"] == 0
    shadow_metrics = report.metrics["answer_post_check_shadow"]
    assert shadow_metrics["case_count"] == 4
    assert shadow_metrics["enabled_case_count"] == 4
    assert shadow_metrics["forbidden_boundary_included_count"] == 0
    assert shadow_metrics["insufficient_fallback_missing_count"] == 0
    governed_rows = [
        row
        for row in report.case_records
        if row["profile_name"] == "chain_tri_governed_answer_contract"
    ]
    assert len(governed_rows) == 4
    assert all(isinstance(row["answer_post_check_shadow"], dict) for row in governed_rows)
    assert all(
        row["answer_post_check_shadow"]["shadow_enabled"] is True
        for row in governed_rows
    )
    assert all(
        row["answer_post_check_shadow"]["forbidden_boundary_included"] is False
        for row in governed_rows
    )
    assert "## Answer Post-Check Shadow" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown


def test_optional_tri_candidate_governance_profile_is_visible_in_markdown(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="standard")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=(
            "chain_memory_base",
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
        ),
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )
    markdown_path = tmp_path / "report.md"

    write_comprehensive_online_markdown(report, markdown_path)

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "chain_tri_candidate_governance" in markdown
    assert "eval_only" in markdown
    assert "oracle_protected" in markdown


def test_online_report_exposes_chain_answer_quality_rows(tmp_path: Path) -> None:
    cases = build_quantitative_eval_cases(limit=4, case_pack="comprehensive")
    profiles = tuple(EXPECTED_ANSWER_QUALITY_PROFILES)
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=profiles,
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    rows = report.metrics["chain_answer_quality_uplift_rows"]
    assert [row["profile_name"] for row in rows] == list(profiles)
    assert rows[0]["previous_profile"] is None
    assert rows[1]["previous_profile"] == "chain_memory_base"
    assert "adjacent_answer_pass_delta_points" in rows[1]
    assert "cumulative_answer_pass_relative_lift_percent" in rows[-1]
    assert "cumulative_grounding_pass_relative_lift_percent" in rows[-1]
    assert rows[-1]["is_combo_check_row"] is True


def test_online_primary_table_uses_counts_and_rates(tmp_path: Path) -> None:
    cases = build_quantitative_eval_cases(limit=2)
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_memory_base", "chain_off"),
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )
    path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, path)

    markdown = path.read_text(encoding="utf-8")
    base = report.metrics["profile_summaries"]["chain_memory_base"]
    assert base["answer_success_count"] <= base["case_count"]
    assert "| profile | cases | answer_success | grounding_success | forbidden_cases |" in markdown
    assert "| profile | main_score |" not in markdown
    assert "## Disabled Enhancement Control" in markdown


def test_online_markdown_renders_answer_quality_uplift_tables(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="comprehensive")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=tuple(EXPECTED_ANSWER_QUALITY_PROFILES),
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )
    path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, path)
    markdown = path.read_text(encoding="utf-8")

    assert "## Answer Quality Uplift Vs Original Memory" in markdown
    assert (
        "| profile | cases | answer_pass | answer_rate | answer_lift | "
        "grounding_pass | grounding_rate | grounding_lift | forbidden_rate | "
        "forbidden_reduction |"
    ) in markdown
    assert "## Chain Answer Quality Uplift" in markdown
    assert (
        "| profile | previous | answer_rate | adjacent_answer_delta | "
        "cumulative_answer_lift | grounding_rate | adjacent_grounding_delta | "
        "cumulative_grounding_lift |"
    ) in markdown
    assert "## Cost And Latency Observation" in markdown
    answer_section = markdown.split(
        "## Answer Quality Uplift Vs Original Memory",
        1,
    )[1].split("## Chain Answer Quality Uplift", 1)[0]
    assert "chain_write_value" not in answer_section
    assert "chain_sleep_consolidation" not in answer_section
    assert "combo/check" in markdown


def test_run_comprehensive_online_eval_supports_bounded_concurrency(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=4)
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_all_on",),
    )
    provider = SlowCountingProvider()

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            provider,
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
            concurrency=2,
        )
    )

    assert report.metrics["concurrency"] == 2
    assert provider.max_active == 2


def test_resume_retries_checkpointed_infra_failures(tmp_path: Path) -> None:
    cases = build_quantitative_eval_cases(limit=1)
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_all_on",),
    )
    checkpoint = tmp_path / "checkpoint.jsonl"
    spec = specs[0]
    key = f"{spec.case.id}|chain_all_on|baseline|0"
    checkpoint.write_text(
        json.dumps(
            {
                "spec_key": key,
                "result": _checkpoint_result(
                    case_id=spec.case.id,
                    provider_error=True,
                    passed=False,
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    provider = CountingProvider()

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            provider,
            model="scripted",
            timeout_s=5.0,
            checkpoint_jsonl=checkpoint,
            resume=True,
        )
    )

    assert provider.call_count == 1
    assert report.metrics["skipped_from_checkpoint_count"] == 0
    assert report.metrics["provider_error_count"] == 0
    assert len(checkpoint.read_text(encoding="utf-8").splitlines()) == 2


def test_build_report_from_checkpoint_can_exclude_infra_failures(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    valid_result = _checkpoint_result(case_id="case-1")
    failed_result = _checkpoint_result(
        case_id="case-2",
        provider_error=True,
        passed=False,
    )
    checkpoint.write_text(
        "\n".join(
            [
                json.dumps({"spec_key": "same", "result": failed_result}),
                json.dumps({"spec_key": "same", "result": valid_result}),
                json.dumps({"spec_key": "bad", "result": failed_result}),
            ]
        ),
        encoding="utf-8",
    )

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=True,
        exclude_infra_failures=True,
    )

    assert report.metrics["case_count"] == 1
    assert report.metrics["checkpoint_input_count"] == 3
    assert report.metrics["excluded_infra_failure_count"] == 2
    assert report.metrics["partial_due_to_infra_failure"] is True


def test_p6o4_checkpoint_loader_accepts_rows_without_post_check_shadow(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(
        json.dumps(
            {
                "spec_key": "old",
                "result": _checkpoint_result(
                    case_id="case-old",
                    profile_name="chain_tri_governed_answer_contract",
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=False,
    )

    assert report.case_records[0]["answer_post_check_shadow"] is None
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 0


def test_answer_quality_uplift_handles_zero_denominators_and_filters_profiles(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    rows = [
        (
            "base",
            {
                **_checkpoint_result(
                    case_id="case-base",
                    profile_name="chain_memory_base",
                    passed=False,
                ),
                "answer_rule_passed": False,
                "memory_grounding_passed": False,
                "forbidden_contains_violation_count": 1,
                "total_token_count": 100,
                "latency_ms": 1000,
            },
        ),
        (
            "tri",
            {
                **_checkpoint_result(
                    case_id="case-tri",
                    profile_name="chain_tri_retrieval",
                    passed=True,
                ),
                "answer_rule_passed": True,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "total_token_count": 120,
                "latency_ms": 900,
            },
        ),
        (
            "write",
            _checkpoint_result(
                case_id="case-write",
                profile_name="chain_write_value",
                passed=True,
            ),
        ),
    ]
    checkpoint.write_text(
        "\n".join(
            json.dumps({"spec_key": key, "result": result})
            for key, result in rows
        ),
        encoding="utf-8",
    )

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=True,
    )

    uplift = report.metrics["profile_answer_quality_uplift_vs_memory_base"]
    tri = uplift["chain_tri_retrieval"]
    assert "chain_write_value" not in uplift
    assert tri["answer_pass_relative_lift_percent"] is None
    assert tri["grounding_pass_relative_lift_percent"] is None
    assert tri["answer_pass_delta_points"] == 100.0
    assert tri["grounding_pass_delta_points"] == 100.0
    assert tri["forbidden_violation_reduction_percent"] == 100.0
    assert tri["avg_total_token_overhead"] == 20.0
    assert tri["avg_latency_overhead_ms"] == -100.0
    assert report.metrics["answer_quality_partial_matrix"] is True
    assert "chain_graph_retrieval" in report.metrics["answer_quality_missing_profiles"]


def test_report_passed_tracks_answer_quality_separately_from_infra(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(
        json.dumps(
            {
                "spec_key": "bad-answer",
                "result": _checkpoint_result(passed=False),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=True,
    )

    assert report.passed is False
    assert report.metrics["infra_passed"] is True
    assert report.metrics["answer_quality_passed"] is False
