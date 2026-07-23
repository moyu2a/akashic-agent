from __future__ import annotations

from pathlib import Path

from memory2.eval_source_ref_quality import (
    open_marked_source_ref_quality_fixture_resolver,
    run_source_ref_quality_eval,
)
from memory2.eval_source_ref_quality_cases import (
    SOURCE_REF_QUALITY_EXPANDED_SCENARIOS,
    build_source_ref_quality_case_pack,
)


def test_expanded_source_ref_case_pack_has_expected_distribution(
    tmp_path: Path,
) -> None:
    pack = build_source_ref_quality_case_pack(tmp_path / "sessions.db")

    assert len(pack.candidates) == 200
    assert pack.metadata["case_pack"] == "expanded"
    assert pack.metadata["synthetic_fixture"] is True
    assert pack.metadata["common_per_scenario"] == 20
    assert pack.metadata["hard_per_scenario"] == 20
    assert set(pack.scenario_counts) == set(SOURCE_REF_QUALITY_EXPANDED_SCENARIOS)
    assert all(count == 20 for count in pack.scenario_counts.values())
    assert pack.case_set_counts == {"common": 100, "hard": 100}


def test_expanded_source_ref_case_pack_expected_metrics(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    pack = build_source_ref_quality_case_pack(db_path)
    handle = open_marked_source_ref_quality_fixture_resolver(db_path)
    try:
        report = run_source_ref_quality_eval(
            candidates=pack.candidates,
            source_ref_resolver=handle.resolver,
        )
    finally:
        handle.close()

    metrics = report.metrics
    assert metrics["candidate_count"] == 200
    assert metrics["baseline_message_level_rate"] == 40.0
    assert metrics["normalized_message_level_rate"] == 90.0
    assert metrics["message_level_uplift_points"] == 50.0
    assert metrics["baseline_parse_success_rate"] == 80.0
    assert metrics["normalized_parse_success_rate"] == 100.0
    assert metrics["parse_success_uplift_points"] == 20.0
    assert metrics["baseline_fetch_success_rate"] == 20.0
    assert metrics["normalized_fetch_success_rate"] == 80.0
    assert metrics["fetch_success_uplift_points"] == 60.0
    assert metrics["baseline_support_rate"] == 10.0
    assert metrics["normalized_support_rate"] == 70.0
    assert metrics["support_uplift_points"] == 60.0
    assert metrics["source_backed_eligible_count_before"] == 20
    assert metrics["source_backed_eligible_count_after"] == 140
    assert metrics["baseline_source_backed_eligible_rate"] == 10.0
    assert metrics["normalized_source_backed_eligible_rate"] == 70.0
    assert metrics["source_backed_eligible_uplift_points"] == 60.0
    assert metrics["malformed_source_ref_count_before"] == 20
    assert metrics["malformed_source_ref_count_after"] == 0


def test_expanded_source_ref_case_pack_refuses_unmarked_session_db(
    tmp_path: Path,
) -> None:
    from session.store import SessionStore

    db_path = tmp_path / "sessions.db"
    store = SessionStore(db_path)
    try:
        store.create_session(key="telegram:123")
        store.insert_message(
            "telegram:123",
            role="user",
            content="真实会话内容不能被 expanded source_ref fixture 覆盖",
            ts="2026-07-22T00:00:00+08:00",
            seq=0,
        )
    finally:
        store.close()

    try:
        build_source_ref_quality_case_pack(db_path)
    except ValueError as exc:
        assert "refusing to overwrite existing non-fixture session db" in str(exc)
    else:
        raise AssertionError("expected expanded fixture builder to reject existing db")

    store = SessionStore(db_path)
    try:
        messages = store.fetch_session_messages("telegram:123")
    finally:
        store.close()
    assert [message["content"] for message in messages] == [
        "真实会话内容不能被 expanded source_ref fixture 覆盖"
    ]
