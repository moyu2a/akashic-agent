from __future__ import annotations

from pathlib import Path

from memory2.eval_sleep_hygiene_evidence import run_sleep_hygiene_evidence_eval
from memory2.eval_sleep_hygiene_provenance import SessionStoreSourceRefResolver
from memory2.eval_sleep_hygiene_source_fixture import (
    build_sleep_hygiene_source_fixture,
)
from session.store import SessionStore


def test_source_fixture_builds_sessions_db_and_mixed_source_states(
    tmp_path: Path,
) -> None:
    fixture = build_sleep_hygiene_source_fixture(
        tmp_path / "sessions.db",
        duplicate_groups=3,
        stale_count=3,
        low_value_count=3,
        retained_count=3,
        hard_per_scenario=2,
    )

    assert fixture.session_db_path.exists()
    assert fixture.cases
    assert fixture.expected_status_counts["supported"] > 0
    assert fixture.expected_status_counts["missing"] > 0
    assert fixture.expected_status_counts["unsupported"] > 0
    assert fixture.expected_status_counts["session_ref_not_fetchable"] > 0
    assert fixture.expected_status_counts["parse_failed"] > 0
    assert fixture.expected_status_counts["missing_source_ref"] > 0


def test_source_fixture_can_rebuild_same_db_path(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"

    first = build_sleep_hygiene_source_fixture(db_path)
    second = build_sleep_hygiene_source_fixture(db_path)

    assert first.session_db_path == second.session_db_path
    assert second.session_db_path.exists()
    assert second.expected_status_counts == first.expected_status_counts


def test_source_fixture_runs_through_session_store_resolver(
    tmp_path: Path,
) -> None:
    fixture = build_sleep_hygiene_source_fixture(
        tmp_path / "sessions.db",
        duplicate_groups=3,
        stale_count=3,
        low_value_count=3,
        retained_count=3,
        hard_per_scenario=2,
    )
    store = SessionStore(fixture.session_db_path)
    try:
        resolver = SessionStoreSourceRefResolver(store)
        report = run_sleep_hygiene_evidence_eval(
            cases=fixture.cases,
            source_ref_resolver=resolver,
        )
    finally:
        store.close()
    source = report.metrics["source_evidence_metrics"]
    status_counts = source["source_support_status_counts"]

    assert source["source_fetch_mode"] == "session-store"
    assert source["source_fetch_success_rate"] < 100.0
    assert source["source_support_rate"] < 100.0
    assert source["missing_source_count"] > 0
    assert source["unsupported_source_count"] > 0
    assert source["session_ref_not_fetchable_count"] > 0
    assert source["malformed_source_ref_count"] > 0
    assert status_counts == fixture.expected_status_counts
    assert status_counts["missing_source_ref"] > 0
