from __future__ import annotations

from memory2.eval_answer_retrieval_counts import build_answer_retrieval_count_report
from memory2.eval_quantitative_cases import build_quantitative_eval_cases


def test_answer_retrieval_report_excludes_write_and_sleep_profiles() -> None:
    report = build_answer_retrieval_count_report(
        build_quantitative_eval_cases(case_pack="answer_comprehensive_v2")
    )

    single_profiles = [row["profile_name"] for row in report.single_module_rows]
    chain_profiles = [row["profile_name"] for row in report.chain_rows]

    assert single_profiles == [
        "memory_base",
        "tri_retrieval_only",
        "graph_only",
        "rerank_only",
        "version_provenance_only",
        "all_on",
    ]
    assert chain_profiles == [
        "chain_memory_base",
        "chain_tri_retrieval",
        "chain_graph_retrieval",
        "chain_rerank_injection",
        "chain_version_provenance",
        "chain_all_on",
    ]
    assert "write_value_only" not in single_profiles
    assert "sleep_only" not in single_profiles
    assert "chain_write_value" not in chain_profiles
    assert "chain_sleep_consolidation" not in chain_profiles
    for row in report.single_module_rows + report.chain_rows:
        assert "write_value_score" not in row["feature_names"]
        assert "sleep_consolidation_shadow" not in row["feature_names"]


def test_answer_retrieval_report_uses_count_and_percentage_deltas() -> None:
    report = build_answer_retrieval_count_report(
        build_quantitative_eval_cases(case_pack="answer_comprehensive_v2")
    )

    assert report.metrics["case_count"] == 1000
    assert report.metrics["target_count"] == 2000
    assert report.metrics["sleep_consolidation_excluded"] is True
    baseline = report.single_module_rows[0]
    tri = next(
        row
        for row in report.single_module_rows
        if row["profile_name"] == "tri_retrieval_only"
    )

    assert baseline["profile_name"] == "memory_base"
    assert baseline["success_delta_vs_baseline"] == 0
    assert baseline["recall_delta_points_vs_baseline"] == 0.0
    assert tri["target_count"] == baseline["target_count"]
    assert tri["miss_count"] == tri["target_count"] - tri["success_count"]
    assert isinstance(tri["success_delta_vs_baseline"], int)
    assert isinstance(tri["recall_delta_points_vs_baseline"], float)
    assert tri["recall_delta_points_vs_baseline"] == round(
        tri["recall_rate"] - baseline["recall_rate"],
        4,
    )


def test_answer_retrieval_all_on_is_answer_only_not_full_quantitative_all() -> None:
    report = build_answer_retrieval_count_report(
        build_quantitative_eval_cases(case_pack="answer_comprehensive_v2")
    )

    single_all_on = next(
        row for row in report.single_module_rows if row["profile_name"] == "all_on"
    )
    chain_all_on = next(
        row for row in report.chain_rows if row["profile_name"] == "chain_all_on"
    )
    assert single_all_on["feature_names"] == [
        "tri_retrieval",
        "graph_retrieval",
        "rerank_shadow",
        "injection_governance_shadow",
        "version_chain_shadow",
        "provenance_shadow",
    ]
    assert chain_all_on["feature_names"] == single_all_on["feature_names"]


def test_answer_retrieval_chain_rows_include_adjacent_and_cumulative_deltas() -> None:
    report = build_answer_retrieval_count_report(
        build_quantitative_eval_cases(case_pack="answer_comprehensive_v2")
    )

    base = report.chain_rows[0]
    tri = next(
        row for row in report.chain_rows if row["profile_name"] == "chain_tri_retrieval"
    )
    assert base["adjacent_success_delta"] == 0
    assert base["adjacent_miss_reduction"] == 0
    assert base["adjacent_recall_delta_points"] == 0.0
    assert tri["adjacent_recall_delta_points"] == round(
        tri["recall_rate"] - base["recall_rate"],
        4,
    )
    assert tri["cumulative_recall_delta_points"] == round(
        tri["recall_rate"] - base["recall_rate"],
        4,
    )
