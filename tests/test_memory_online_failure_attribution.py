from __future__ import annotations

import json

from memory2.eval_online_failure_attribution import (
    build_online_failure_attribution_report,
    build_online_failure_attribution_report_from_checkpoint_rows,
    write_online_failure_attribution_json,
    write_online_failure_attribution_markdown,
)


def test_failure_attribution_groups_profile_failures() -> None:
    payload = {
        "case_records": [
            {
                "case_id": "base-ok",
                "profile_name": "chain_memory_base",
                "answer_rule_passed": True,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "used_memory_id_count": 2,
                "total_token_count": 100,
                "latency_ms": 1000,
                "provider_error": False,
                "timeout": False,
                "failures": [],
            },
            {
                "case_id": "tri-noisy",
                "profile_name": "chain_tri_retrieval",
                "answer_rule_passed": False,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 1,
                "used_memory_id_count": 4,
                "total_token_count": 130,
                "latency_ms": 1500,
                "provider_error": False,
                "timeout": False,
                "failures": ["found forbidden answer term: QQ"],
            },
            {
                "case_id": "version-grounding-miss",
                "profile_name": "chain_version_provenance",
                "answer_rule_passed": True,
                "memory_grounding_passed": False,
                "forbidden_contains_violation_count": 0,
                "used_memory_id_count": 1,
                "total_token_count": 90,
                "latency_ms": 900,
                "provider_error": False,
                "timeout": False,
                "failures": ["missing expected memory ids: case_graph"],
            },
        ],
        "metrics": {"real_llm_enabled": True, "case_count": 3},
    }

    report = build_online_failure_attribution_report(payload)

    tri = report.profile_rows["chain_tri_retrieval"]
    assert tri.case_count == 1
    assert tri.answer_failure_count == 1
    assert tri.forbidden_failure_count == 1
    assert tri.grounded_but_answer_failed_count == 1
    assert tri.primary_issue == "grounded_but_answer_failed"
    assert tri.failure_code_counts == {"found_forbidden_answer_term": 1}
    assert tri.top_failure_examples == ("found forbidden answer term: QQ",)

    version = report.profile_rows["chain_version_provenance"]
    assert version.grounding_failure_count == 1
    assert version.answer_failure_count == 0
    assert version.primary_issue == "grounding_only_failure"
    assert version.failure_code_counts == {"missing_expected_memory_ids": 1}


def test_failure_attribution_compares_profiles_to_memory_base() -> None:
    payload = {
        "case_records": [
            {
                "case_id": "same-case",
                "profile_name": "chain_memory_base",
                "prompt_variant": "baseline",
                "repeat_index": 0,
                "answer_rule_passed": True,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "used_memory_id_count": 2,
                "total_token_count": 100,
                "latency_ms": 1000,
                "provider_error": False,
                "timeout": False,
                "failures": [],
            },
            {
                "case_id": "same-case",
                "profile_name": "chain_tri_retrieval",
                "prompt_variant": "baseline",
                "repeat_index": 0,
                "answer_rule_passed": False,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 1,
                "used_memory_id_count": 5,
                "total_token_count": 130,
                "latency_ms": 1500,
                "provider_error": False,
                "timeout": False,
                "failures": ["found forbidden answer term: old"],
            },
        ],
        "metrics": {"real_llm_enabled": True, "case_count": 2},
    }

    report = build_online_failure_attribution_report(payload)

    tri = report.profile_rows["chain_tri_retrieval"]
    assert tri.baseline_answer_pass_profile_fail_count == 1
    assert tri.forbidden_introduced_vs_baseline_count == 1
    assert tri.avg_token_delta_vs_baseline == 30.0
    assert tri.avg_latency_delta_vs_baseline == 500.0


def test_failure_attribution_accepts_checkpoint_rows() -> None:
    rows = [
        {
            "spec_key": "case-a|chain_memory_base|baseline|0",
            "result": {
                "case_id": "case-a",
                "profile_name": "chain_memory_base",
                "prompt_variant": "baseline",
                "repeat_index": 0,
                "answer_rule_passed": True,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "used_memory_id_count": 1,
                "total_token_count": 100,
                "latency_ms": 1000,
                "provider_error": False,
                "timeout": False,
                "failures": [],
            },
        },
    ]

    report = build_online_failure_attribution_report_from_checkpoint_rows(rows)

    assert report.case_count == 1
    assert report.profile_rows["chain_memory_base"].case_count == 1


def test_failure_attribution_writes_json_and_markdown(tmp_path) -> None:
    payload = {
        "case_records": [
            {
                "case_id": "case-a",
                "profile_name": "chain_graph_retrieval",
                "answer_rule_passed": False,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 1,
                "used_memory_id_count": 3,
                "total_token_count": 120,
                "latency_ms": 1100,
                "provider_error": False,
                "timeout": False,
                "failures": ["missing expected answer term: NetworkX"],
            },
        ],
        "metrics": {"real_llm_enabled": True, "case_count": 1},
    }
    report = build_online_failure_attribution_report(payload)
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    write_online_failure_attribution_json(report, json_path)
    write_online_failure_attribution_markdown(report, md_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["case_count"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "Online Failure Attribution" in markdown
    assert "chain_graph_retrieval" in markdown
    assert "missing_expected_answer_term" in markdown
