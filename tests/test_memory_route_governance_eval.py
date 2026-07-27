from __future__ import annotations

from types import SimpleNamespace

from memory2.eval_route_governance import (
    build_live_route_governance_rows,
    build_offline_route_governance_rows,
    live_route_governance_markdown_lines,
    route_governance_markdown_lines,
)


def test_offline_route_governance_rows_compare_baseline_tri_and_graph() -> None:
    report = SimpleNamespace(
        case_records=(
            {
                "case_id": "c1",
                "profile_name": "memory_base",
                "success_count": 0,
            },
            {
                "case_id": "c1",
                "profile_name": "tri_retrieval_only",
                "success_count": 1,
                "retrieval_scene": "fuzzy_reference",
                "candidate_drop_rate": 0.25,
                "expected_route_hit_rate": 1.0,
                "candidate_accept_rate": 0.75,
                "graph_lane_used": False,
                "route_decision": {"reason": "模糊指代"},
            },
            {
                "case_id": "c1",
                "profile_name": "graph_only",
                "success_count": 1,
                "graph_lane_used": True,
            },
        )
    )

    rows = build_offline_route_governance_rows(report)

    assert len(rows) == 1
    row = rows[0]
    assert row.scene == "fuzzy_reference"
    assert row.baseline_success == 0
    assert row.gated_success == 1
    assert row.graph_success == 1
    assert row.candidate_drop_rate == 25.0
    assert row.expected_route_hit_rate == 100.0
    assert row.candidate_accept_rate == 75.0
    assert row.graph_used_rate == 100.0
    assert "模糊指代" in row.note
    markdown = "\n".join(route_governance_markdown_lines(rows))
    assert "| scene | cases | baseline_success | gated_success | graph_success |" in markdown
    assert "expected_route_hit_rate" in markdown
    assert "candidate_accept_rate" in markdown


def test_live_route_governance_rows_summarize_engine_smoke() -> None:
    rows = build_live_route_governance_rows(
        (
            {
                "scene": "fuzzy_reference",
                "candidate_accept_rate": 0.75,
                "candidate_drop_rate": 0.25,
                "graph_used": True,
                "note": "ok",
            },
            {
                "scene": "fuzzy_reference",
                "candidate_accept_rate": 1.0,
                "candidate_drop_rate": 0.0,
                "graph_used": False,
                "note": "ok",
            },
        )
    )

    assert len(rows) == 1
    assert rows[0].candidate_accept_rate == 87.5
    assert rows[0].candidate_drop_rate == 12.5
    assert rows[0].graph_used_rate == 50.0
    assert "| scene | case_count | candidate_accept_rate | candidate_drop_rate |" in "\n".join(
        live_route_governance_markdown_lines(rows)
    )
