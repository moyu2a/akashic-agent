from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent.provider import LLMResponse
from memory2.eval_comprehensive_online import (
    build_comprehensive_online_report_from_checkpoint,
    build_comprehensive_run_specs,
    evidence_ids_for_profile,
    profile_evidence_source,
    run_comprehensive_online_eval,
    write_comprehensive_online_markdown,
)
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_runner import _baseline_recalled_items


class ComprehensiveScriptedProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
        if "memory_id=" not in text:
            answer = "没有可用记忆，无法确认。"
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


def test_middle_profiles_use_distinct_shadow_evidence_sets() -> None:
    cases = build_quantitative_eval_cases()
    tri_vs_version = 0
    graph_vs_rerank = 0
    graph_vs_tri = 0

    for case in cases:
        tri = evidence_ids_for_profile(case, "chain_tri_retrieval")
        graph = evidence_ids_for_profile(case, "chain_graph_retrieval")
        rerank = evidence_ids_for_profile(case, "chain_rerank_injection")
        version = evidence_ids_for_profile(case, "chain_version_provenance")
        if tri != version:
            tri_vs_version += 1
        if graph != rerank:
            graph_vs_rerank += 1
        if graph != tri:
            graph_vs_tri += 1

    assert tri_vs_version == len(cases)
    assert graph_vs_rerank == len(cases)
    assert graph_vs_tri >= len(cases) // 2


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
