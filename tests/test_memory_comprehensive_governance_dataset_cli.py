from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from agent.provider import LLMResponse
from memory2.eval_comprehensive_online import (
    EvalRunProvenance,
    build_comprehensive_online_report_from_checkpoint,
    build_comprehensive_run_specs,
    memory_governance_case_to_eval_case,
    run_comprehensive_online_eval,
)
from memory2.eval_memory_governance_dataset import load_memory_governance_cases
from memory2.eval_memory_governance_profiles import MEMORY_GOVERNANCE_PROFILE_ORDER
from scripts.run_memory_comprehensive_online_eval import (
    EvalSamplingConfig,
    EvalSamplingProvider,
    build_command_shape_hash,
    resolve_profiles_from_args,
    validate_fresh_checkpoint_args,
)


class PassingProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            content="当前中文，无法确认时说明无法确认。",
            tool_calls=[],
            provider_fields={
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                }
            },
        )


class CapturingProvider:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.kwargs = kwargs
        return LLMResponse(content="ok", tool_calls=[], provider_fields={})


def test_cli_accepts_memory_governance_dataset(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--memory-governance-dataset",
            "my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl",
            "--profile-ladder",
            "memory_governance_p1_p4",
            "--prompt-variants",
            "baseline",
            "--repeats",
            "1",
            "--limit",
            "1",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (tmp_path / "reports" / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metrics"]["dataset_case_count"] == 1
    assert payload["metrics"]["profile_ladder"] == "memory_governance_p1_p4"
    assert payload["metrics"]["semantic_audit_release_decision"] == "pass"


def test_cli_profile_ladder_expands_to_expected_profiles() -> None:
    args = argparse.Namespace(
        profile_ladder="memory_governance_p1_p4",
        profiles="chain_off",
    )

    assert resolve_profiles_from_args(args) == MEMORY_GOVERNANCE_PROFILE_ORDER


def test_report_metadata_records_dataset_and_deterministic_config(tmp_path: Path) -> None:
    case = memory_governance_case_to_eval_case(
        load_memory_governance_cases(
            Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
        )[0]
    )
    specs = build_comprehensive_run_specs(
        [case],
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_tri_retrieval",),
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            PassingProvider(),
            "fake-model",
            real_llm_enabled=True,
            report_metadata={
                "result_type": "online_answer_level",
                "dataset_path": "my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl",
                "dataset_case_count": 80,
                "profile_ladder": "memory_governance_p1_p4",
                "deterministic": True,
                "temperature": 0,
                "top_p": 1,
                "seed_requested": 42,
                "seed_effective": False,
            },
        )
    )

    assert report.metrics["result_type"] == "online_answer_level"
    assert report.metrics["dataset_case_count"] == 80
    assert report.metrics["deterministic"] is True
    assert report.metrics["seed_effective"] is False


def test_report_metadata_keeps_98_75_out_of_causal_claim(tmp_path: Path) -> None:
    report = asyncio.run(
        run_comprehensive_online_eval(
            (),
            tmp_path / "workspace",
            PassingProvider(),
            "fake-model",
            real_llm_enabled=True,
            report_metadata={
                "causal_claim": "37.5_to_97.5_same_table_profile_ladder",
                "separate_safety_path_result": "98.75 belongs to system-path safe-version validation",
            },
        )
    )

    assert report.metrics["causal_claim"] == "37.5_to_97.5_same_table_profile_ladder"
    assert "98.75" not in report.metrics["causal_claim"]
    assert "98.75" in report.metrics["separate_safety_path_result"]


def test_report_records_actual_same_table_causal_chain_values(tmp_path: Path) -> None:
    report = asyncio.run(
        run_comprehensive_online_eval(
            (),
            tmp_path / "workspace",
            PassingProvider(),
            "fake-model",
            real_llm_enabled=True,
            report_metadata={
                "profile_ladder": "memory_governance_p1_p4",
                "causal_claim": "same_table_profile_ladder",
            },
        )
    )

    report.metrics["profile_summaries"] = {
        "chain_tri_retrieval": {"answer_rule_pass_rate": 41.25},
        "chain_tri_governed_answer_contract": {"answer_rule_pass_rate": 100.0},
    }
    from memory2.eval_comprehensive_online import annotate_memory_governance_causal_chain

    annotate_memory_governance_causal_chain(report.metrics)

    assert report.metrics["measured_causal_chain"] == "41.25_to_100.0_same_table_profile_ladder"
    assert (
        report.metrics["causal_claim_status"]
        == "new_measured_values_differ_from_historical_37.5_to_97.5"
    )


def test_cli_fresh_checkpoint_rejects_existing_nonempty_checkpoint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty"):
        validate_fresh_checkpoint_args(
            checkpoint_jsonl=checkpoint,
            fresh_checkpoint=True,
            resume=False,
        )


def test_cli_fresh_checkpoint_requires_checkpoint_jsonl() -> None:
    with pytest.raises(ValueError, match="requires --checkpoint-jsonl"):
        validate_fresh_checkpoint_args(
            checkpoint_jsonl=None,
            fresh_checkpoint=True,
            resume=False,
        )


def test_cli_fresh_checkpoint_rejects_resume(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot be used with --resume"):
        validate_fresh_checkpoint_args(
            checkpoint_jsonl=tmp_path / "checkpoint.jsonl",
            fresh_checkpoint=True,
            resume=True,
        )


def test_cli_fresh_checkpoint_rejects_nonzero_skipped_rows(tmp_path: Path) -> None:
    case = memory_governance_case_to_eval_case(
        load_memory_governance_cases(
            Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
        )[0]
    )
    specs = build_comprehensive_run_specs(
        [case],
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_tri_retrieval",),
    )
    checkpoint = tmp_path / "checkpoint.jsonl"
    provenance = EvalRunProvenance(command_shape_hash="same")
    asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            PassingProvider(),
            "fake-model",
            real_llm_enabled=True,
            checkpoint_jsonl=checkpoint,
            run_provenance=provenance,
        )
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace-2",
            PassingProvider(),
            "fake-model",
            real_llm_enabled=True,
            checkpoint_jsonl=checkpoint,
            resume=True,
            run_provenance=provenance,
        )
    )

    assert report.metrics["skipped_from_checkpoint_count"] == 1
    assert report.metrics["fresh_checkpoint_valid"] is False


def test_cli_real_run_requires_enable_real_llm_for_memory_governance_ladder(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--memory-governance-dataset",
            "my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl",
            "--profile-ladder",
            "memory_governance_p1_p4",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--enable-real-llm" in completed.stderr


def test_memory_governance_case_adapter_outputs_valid_eval_case() -> None:
    case = memory_governance_case_to_eval_case(
        load_memory_governance_cases(
            Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
        )[0]
    )

    assert case.id == "mgov_001"
    assert case.setup["scope"] == {
        "session_key": "eval:mgov_001",
        "channel": "memory_governance_eval",
        "chat_id": "mgov_001",
    }
    assert case.setup["query"] == "我现在在回答语言上的有效偏好是什么？"
    assert case.expectations["answer_expectations"]["expected_language"] == "zh"
    assert case.expectations["answer_expectations"]["grounding_required"] is True


def test_memory_governance_case_adapter_maps_supersedes_edges_to_replacements() -> None:
    case = memory_governance_case_to_eval_case(
        load_memory_governance_cases(
            Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
        )[0]
    )

    assert case.setup["memory_replacements"] == [
        {
            "old_item_id": "mgov_001_old",
            "new_item_id": "mgov_001_new",
            "old_memory_type": "preference",
            "new_memory_type": "preference",
            "old_summary": "用户过去在回答语言上的偏好是英文",
            "new_summary": "用户现在在回答语言上的偏好是中文",
            "old_source_ref": "eval://mgov_001/old",
            "new_source_ref": "eval://mgov_001/new",
        }
    ]


def test_eval_sampling_provider_passes_temperature_top_p_and_seed_to_extra_body() -> None:
    provider = CapturingProvider()
    wrapped = EvalSamplingProvider(
        provider,
        EvalSamplingConfig(
            deterministic=True,
            temperature=0,
            top_p=1,
            seed=42,
        ),
    )

    asyncio.run(wrapped.chat(messages=[], extra_body={"provider_flag": True}))

    assert provider.kwargs is not None
    assert provider.kwargs["extra_body"] == {
        "provider_flag": True,
        "temperature": 0,
        "top_p": 1,
        "seed": 42,
    }


def test_report_marks_seed_effective_false_when_provider_seed_support_unknown() -> None:
    assert EvalSamplingConfig(
        deterministic=True,
        temperature=0,
        top_p=1,
        seed=42,
    ).seed_effective is False


def test_resume_ignores_checkpoint_rows_with_mismatched_config_hash(tmp_path: Path) -> None:
    case = memory_governance_case_to_eval_case(
        load_memory_governance_cases(
            Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
        )[0]
    )
    specs = build_comprehensive_run_specs(
        [case],
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_tri_retrieval",),
    )
    checkpoint = tmp_path / "checkpoint.jsonl"
    asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            PassingProvider(),
            "fake-model",
            real_llm_enabled=True,
            checkpoint_jsonl=checkpoint,
            run_provenance=EvalRunProvenance(command_shape_hash="old"),
        )
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace-2",
            PassingProvider(),
            "fake-model",
            real_llm_enabled=True,
            checkpoint_jsonl=checkpoint,
            resume=True,
            run_provenance=EvalRunProvenance(command_shape_hash="new"),
        )
    )

    assert report.metrics["checkpoint_provenance_mismatch_count"] == 1
    assert report.metrics["skipped_from_checkpoint_count"] == 0


def test_checkpoint_report_only_exposes_provenance_mismatches(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(
        json.dumps(
            {
                "spec_key": "case|profile|baseline|0",
                "run_provenance": {"command_shape_hash": "old"},
                "result": {
                    "answer_length": 20,
                    "answer_rule_passed": True,
                    "case_id": "case",
                    "category": "memory_governance",
                    "completion_token_count": 10,
                    "evidence_source": "tri",
                    "expected_memory_used": True,
                    "failures": [],
                    "forbidden_contains_violation_count": 0,
                    "latency_ms": 1,
                    "memory_grounding_passed": True,
                    "passed": True,
                    "profile_name": "chain_tri_retrieval",
                    "prompt_token_count": 10,
                    "prompt_variant": "baseline",
                    "provider_error": False,
                    "repeat_index": 0,
                    "timeout": False,
                    "token_metrics_available": True,
                    "total_token_count": 20,
                    "used_memory_id_count": 1,
                    "answer_post_check_shadow": None,
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=True,
        command_shape_hash="new",
    )

    assert report.metrics["checkpoint_provenance_mismatch_count"] == 1
    assert report.metrics["checkpoint_report_only"] is True


def test_comprehensive_checkpoint_loader_tolerates_malformed_tail(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text("{not-json", encoding="utf-8")

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=True,
    )

    assert report.metrics["malformed_checkpoint_line_count"] == 1


def test_command_shape_hash_changes_with_config_hash() -> None:
    first = build_command_shape_hash(
        dataset_path="dataset",
        profile_ladder="memory_governance_p1_p4",
        profiles=("chain_tri_retrieval",),
        prompt_variants=("baseline",),
        repeats=1,
        deterministic=True,
        temperature=0,
        top_p=1,
        seed=42,
        provider_name="deepseek",
        model="model",
        config_hash="a",
        git_commit="commit",
    )
    second = build_command_shape_hash(
        dataset_path="dataset",
        profile_ladder="memory_governance_p1_p4",
        profiles=("chain_tri_retrieval",),
        prompt_variants=("baseline",),
        repeats=1,
        deterministic=True,
        temperature=0,
        top_p=1,
        seed=42,
        provider_name="deepseek",
        model="model",
        config_hash="b",
        git_commit="commit",
    )

    assert first != second
