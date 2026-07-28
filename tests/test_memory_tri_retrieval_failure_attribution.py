from __future__ import annotations

import json

from memory2.eval_tri_retrieval_failure_attribution import (
    build_tri_retrieval_failure_attribution_report,
    write_tri_retrieval_failure_attribution_json,
    write_tri_retrieval_failure_attribution_markdown,
)


def _record(
    case_id: str,
    profile: str,
    *,
    answer: bool,
    grounding: bool,
    forbidden: int = 0,
    failures: list[str] | None = None,
    tokens: int = 100,
    latency: int = 1000,
) -> dict[str, object]:
    category = (
        case_id.removesuffix("_01")
        if case_id.startswith(("common_", "hard_"))
        else "common_tool_preference"
    )
    return {
        "case_id": case_id,
        "category": category,
        "profile_name": profile,
        "prompt_variant": "baseline",
        "repeat_index": 0,
        "answer_rule_passed": answer,
        "memory_grounding_passed": grounding,
        "forbidden_contains_violation_count": forbidden,
        "used_memory_id_count": 3,
        "total_token_count": tokens,
        "latency_ms": latency,
        "provider_error": False,
        "timeout": False,
        "failures": failures or [],
    }


def test_tri_failure_report_classifies_grounded_answer_failures() -> None:
    payload = {
        "case_records": [
            _record("case-a", "chain_memory_base", answer=True, grounding=True),
            _record(
                "case-a",
                "chain_tri_retrieval",
                answer=False,
                grounding=True,
                failures=["missing expected answer term: 使用 telegram"],
            ),
            _record("case-a", "chain_rerank_injection", answer=True, grounding=True),
        ],
        "metrics": {
            "real_llm_enabled": True,
            "case_count": 3,
            "unique_case_count": 1,
        },
    }

    report = build_tri_retrieval_failure_attribution_report(payload)

    assert report.metrics["tri_case_count"] == 1
    assert report.metrics["tri_answer_fail_count"] == 1
    assert report.metrics["tri_grounded_answer_fail_count_any"] == 1
    assert report.metrics["tri_grounded_non_forbidden_answer_fail_count"] == 1
    assert report.metrics["tri_grounding_fail_count"] == 0
    assert report.metrics["tri_forbidden_fail_count"] == 0
    assert report.metrics["failure_bucket_counts"] == {
        "grounded_answer_rule_miss": 1
    }
    assert report.case_rows[0].failure_bucket == "grounded_answer_rule_miss"
    assert report.case_rows[0].pass_pattern == "base_pass_tri_fail_rerank_pass"
    assert report.case_rows[0].tri_failed_but_rerank_passed is True


def test_tri_failure_report_adds_fixture_proxy_and_pairwise_counts() -> None:
    payload = {
        "case_records": [
            _record(
                "common_tool_preference_01",
                "chain_memory_base",
                answer=True,
                grounding=True,
            ),
            _record(
                "common_tool_preference_01",
                "chain_tri_retrieval",
                answer=False,
                grounding=True,
                tokens=130,
            ),
            _record(
                "common_tool_preference_01",
                "chain_rerank_injection",
                answer=True,
                grounding=True,
                tokens=120,
            ),
            _record(
                "common_tri_rrf_01",
                "chain_memory_base",
                answer=False,
                grounding=True,
            ),
            _record(
                "common_tri_rrf_01",
                "chain_tri_retrieval",
                answer=True,
                grounding=True,
            ),
            _record(
                "common_tri_rrf_01",
                "chain_rerank_injection",
                answer=True,
                grounding=True,
            ),
        ],
        "metrics": {"real_llm_enabled": True, "case_count": 6, "unique_case_count": 2},
    }

    report = build_tri_retrieval_failure_attribution_report(payload)

    assert report.metrics["baseline_passed_but_tri_failed_count"] == 1
    assert report.metrics["baseline_failed_but_tri_passed_count"] == 1
    assert report.metrics["tri_failed_but_rerank_passed_count"] == 1
    row = next(
        item for item in report.case_rows if item.case_id == "common_tool_preference_01"
    )
    assert row.fixture_tri_evidence_id_count > 0
    assert row.fixture_baseline_evidence_id_count > 0
    assert row.fixture_evidence_count_delta_vs_base >= 0
    assert isinstance(row.fixture_rerank_reduced_evidence_count, bool)
    assert row.used_memory_id_count == 3


def test_tri_failure_report_handles_forbidden_and_missing_pairs() -> None:
    payload = {
        "case_records": [
            _record(
                "case-without-pairs",
                "chain_tri_retrieval",
                answer=False,
                grounding=True,
                forbidden=1,
                failures=["found_forbidden_answer_term"],
            ),
        ],
        "metrics": {"real_llm_enabled": True, "case_count": 1, "unique_case_count": 1},
    }

    report = build_tri_retrieval_failure_attribution_report(payload)

    row = report.case_rows[0]
    assert row.failure_bucket == "forbidden_answer_failure"
    assert row.baseline_answer_passed is None
    assert row.rerank_answer_passed is None
    assert row.pass_pattern == "base_missing_tri_fail_rerank_missing"
    assert report.metrics["tri_grounded_answer_fail_count_any"] == 1
    assert report.metrics["tri_grounded_non_forbidden_answer_fail_count"] == 0
    assert report.metrics["failure_bucket_counts"] == {"forbidden_answer_failure": 1}
    assert report.metrics["failure_bucket_code_counts"] == {
        "forbidden_answer_failure": {"found_forbidden_answer_term": 1}
    }


def test_tri_failure_report_writes_json_and_markdown(tmp_path) -> None:
    payload = {
        "case_records": [
            _record("case-a", "chain_memory_base", answer=True, grounding=True),
            _record("case-a", "chain_tri_retrieval", answer=False, grounding=True),
            _record("case-a", "chain_rerank_injection", answer=True, grounding=True),
        ],
        "metrics": {"real_llm_enabled": True, "case_count": 3, "unique_case_count": 1},
    }
    report = build_tri_retrieval_failure_attribution_report(payload)
    json_path = tmp_path / "tri.json"
    md_path = tmp_path / "tri.md"

    write_tri_retrieval_failure_attribution_json(report, json_path)
    write_tri_retrieval_failure_attribution_markdown(report, md_path)

    written = json.loads(json_path.read_text(encoding="utf-8"))
    assert written["metrics"]["tri_case_count"] == 1
    markdown = md_path.read_text(encoding="utf-8")
    assert "Tri Retrieval Failure Attribution" in markdown
    assert "grounded_answer_rule_miss" in markdown
    assert "fixture proxy" in markdown
    assert "Pass Pattern" in markdown
    assert "下一步建议" in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
    assert "raw_memory_summary" not in markdown
