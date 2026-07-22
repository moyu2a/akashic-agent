from __future__ import annotations

import json
from pathlib import Path

from memory2.eval_sleep_hygiene_provenance import parse_source_ref_for_fetch
from memory2.source_ref_quality import (
    SourceRefQualityInput,
    message_list_source_ref,
    normalize_source_ref_shadow,
)


def test_message_list_source_ref_uses_json_array() -> None:
    source_ref = message_list_source_ref(["cli:local:0", "cli:local:1"])

    assert json.loads(source_ref) == ["cli:local:0", "cli:local:1"]
    parsed = parse_source_ref_for_fetch(source_ref)
    assert parsed.fetchable_by_id is True
    assert parsed.message_ids == ("cli:local:0", "cli:local:1")


def test_normalize_source_ref_upgrades_session_level_when_message_ids_exist() -> None:
    result = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="candidate-1",
            session_key="cli:local",
            baseline_source_ref="cli:local@post_response",
            candidate_message_ids=("cli:local:0", "cli:local:1"),
            expected_terms=("偏好",),
        )
    )

    assert result.normalized_source_ref == '["cli:local:0","cli:local:1"]'
    assert result.baseline_level == "session"
    assert result.normalized_level == "message"
    assert result.action == "upgraded_to_message_ids"


def test_normalize_source_ref_upgrades_missing_or_malformed_without_guessing() -> None:
    missing = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="missing",
            session_key="cli:local",
            baseline_source_ref="",
            candidate_message_ids=("cli:local:2",),
        )
    )
    malformed = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="malformed",
            session_key="cli:local",
            baseline_source_ref='["broken"',
            candidate_message_ids=("cli:local:3",),
        )
    )
    no_ids = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="no-ids",
            session_key="cli:local",
            baseline_source_ref="cli:local@post_response",
            candidate_message_ids=(),
        )
    )

    assert missing.action == "upgraded_to_message_ids"
    assert malformed.action == "upgraded_to_message_ids"
    assert no_ids.normalized_source_ref == "cli:local@post_response"
    assert no_ids.action == "kept_no_candidate_message_ids"


def test_normalize_source_ref_filters_duplicate_and_foreign_session_ids() -> None:
    result = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="candidate-1",
            session_key="cli:local",
            baseline_source_ref="cli:local@post_response",
            candidate_message_ids=(
                "cli:local:1",
                "qq:local:1",
                "cli:local:1",
                "not-a-message-id",
                "cli:local:2",
            ),
        )
    )

    assert result.candidate_message_ids == ("cli:local:1", "cli:local:2")
    assert result.normalized_source_ref == '["cli:local:1","cli:local:2"]'


def test_normalize_source_ref_replaces_foreign_baseline_message_ref() -> None:
    result = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="candidate-1",
            session_key="cli:local",
            baseline_source_ref="qq:local:1",
            candidate_message_ids=("cli:local:2",),
        )
    )

    assert result.baseline_level == "message"
    assert result.normalized_source_ref == '["cli:local:2"]'
    assert result.action == "upgraded_to_message_ids"


def test_normalize_source_ref_replaces_malformed_same_session_message_ref() -> None:
    result = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="candidate-1",
            session_key="cli:local",
            baseline_source_ref="cli:local:abc",
            candidate_message_ids=("cli:local:2",),
        )
    )

    assert result.baseline_level == "message"
    assert result.normalized_source_ref == '["cli:local:2"]'
    assert result.action == "upgraded_to_message_ids"


def test_normalize_source_ref_treats_string_expected_terms_as_one_term() -> None:
    result = normalize_source_ref_shadow(
        SourceRefQualityInput(
            candidate_id="candidate-1",
            session_key="cli:local",
            baseline_source_ref="cli:local:0",
            expected_terms="完整中文短语",  # type: ignore[arg-type]
        )
    )

    assert result.expected_terms == ("完整中文短语",)


def test_source_ref_quality_eval_reports_before_after_uplift(tmp_path: Path) -> None:
    from memory2.eval_source_ref_quality import (
        build_source_ref_quality_fixture,
        open_marked_source_ref_quality_fixture_resolver,
        run_source_ref_quality_eval,
    )

    db_path = tmp_path / "sessions.db"
    candidates = build_source_ref_quality_fixture(db_path)

    handle = open_marked_source_ref_quality_fixture_resolver(db_path)
    try:
        report = run_source_ref_quality_eval(
            candidates=candidates,
            source_ref_resolver=handle.resolver,
        )
    finally:
        handle.close()

    metrics = report.metrics
    assert metrics["candidate_count"] == len(candidates)
    assert metrics["baseline_message_level_rate"] == 33.3333
    assert metrics["normalized_message_level_rate"] == 83.3333
    assert metrics["message_level_uplift_points"] == 50.0
    assert metrics["baseline_fetch_success_rate"] == 33.3333
    assert metrics["normalized_fetch_success_rate"] == 83.3333
    assert metrics["fetch_success_uplift_points"] == 50.0
    assert metrics["baseline_support_rate"] == 16.6667
    assert metrics["normalized_support_rate"] == 66.6667
    assert metrics["support_uplift_points"] == 50.0
    assert metrics["source_backed_eligible_count_before"] == 1
    assert metrics["source_backed_eligible_count_after"] == 4
    assert metrics["baseline_source_backed_eligible_rate"] == 16.6667
    assert metrics["normalized_source_backed_eligible_rate"] == 66.6667
    assert metrics["malformed_source_ref_count_after"] == 0
    assert report.metadata["evaluation_mode"] == "synthetic_fixture_shadow"
    assert report.metadata["production_uplift"] is False


def test_source_ref_quality_fixture_refuses_to_overwrite_unmarked_session_db(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import build_source_ref_quality_fixture
    from session.store import SessionStore

    db_path = tmp_path / "sessions.db"
    store = SessionStore(db_path)
    try:
        store.create_session(key="telegram:123")
        store.insert_message(
            "telegram:123",
            role="user",
            content="真实会话内容不能被 source_ref quality fixture 覆盖",
            ts="2026-07-22T00:00:00+08:00",
            seq=0,
        )
    finally:
        store.close()

    try:
        build_source_ref_quality_fixture(db_path)
    except ValueError as exc:
        assert "refusing to overwrite existing non-fixture session db" in str(exc)
    else:
        raise AssertionError("expected fixture builder to reject existing db")

    store = SessionStore(db_path)
    try:
        messages = store.fetch_session_messages("telegram:123")
    finally:
        store.close()
    assert [message["content"] for message in messages] == [
        "真实会话内容不能被 source_ref quality fixture 覆盖"
    ]


def test_source_ref_quality_eval_does_not_upgrade_foreign_session_ids(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import (
        build_source_ref_quality_fixture,
        open_marked_source_ref_quality_fixture_resolver,
        run_source_ref_quality_eval,
    )

    db_path = tmp_path / "sessions.db"
    build_source_ref_quality_fixture(db_path)
    handle = open_marked_source_ref_quality_fixture_resolver(db_path)
    try:
        report = run_source_ref_quality_eval(
            candidates=(
                SourceRefQualityInput(
                    candidate_id="foreign",
                    session_key="cli:local",
                    baseline_source_ref="cli:local@post_response",
                    candidate_message_ids=("qq:local:0",),
                    expected_terms=("偏好",),
                ),
            ),
            source_ref_resolver=handle.resolver,
        )
    finally:
        handle.close()

    record = report.records[0]
    assert record["candidate_message_ids"] == ()
    assert record["normalized_source_ref"] == "cli:local@post_response"
    assert record["normalized_source_backed_eligible"] is False


def test_source_ref_quality_eval_rejects_foreign_baseline_message_ref(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import (
        build_source_ref_quality_fixture,
        open_marked_source_ref_quality_fixture_resolver,
        run_source_ref_quality_eval,
    )

    db_path = tmp_path / "sessions.db"
    build_source_ref_quality_fixture(db_path)
    handle = open_marked_source_ref_quality_fixture_resolver(db_path)
    try:
        report = run_source_ref_quality_eval(
            candidates=(
                SourceRefQualityInput(
                    candidate_id="foreign-baseline",
                    session_key="cli:local",
                    baseline_source_ref="qq:local:0",
                    candidate_message_ids=("cli:local:1",),
                    expected_terms=("source_ref",),
                ),
            ),
            source_ref_resolver=handle.resolver,
        )
    finally:
        handle.close()

    record = report.records[0]
    assert record["baseline_fetch_success"] is False
    assert record["baseline_support_status"] == "foreign_session_source"
    assert record["baseline_source_backed_eligible"] is False
    assert record["normalized_fetch_success"] is True
    assert record["normalized_source_backed_eligible"] is True


def test_source_ref_quality_eval_rejects_malformed_same_session_baseline_ref(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import run_source_ref_quality_eval
    from memory2.eval_sleep_hygiene_provenance import MappingSourceRefResolver

    resolver = MappingSourceRefResolver({"cli:local:abc": "source_ref"})
    report = run_source_ref_quality_eval(
        candidates=(
            SourceRefQualityInput(
                candidate_id="malformed-baseline",
                session_key="cli:local",
                baseline_source_ref="cli:local:abc",
                candidate_message_ids=(),
                expected_terms=("source_ref",),
            ),
        ),
        source_ref_resolver=resolver,
    )

    record = report.records[0]
    assert record["baseline_fetch_success"] is False
    assert record["baseline_support_status"] == "invalid_message_id"
    assert record["baseline_source_backed_eligible"] is False


def test_source_ref_quality_fixture_resolver_refuses_unmarked_db(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import (
        open_marked_source_ref_quality_fixture_resolver,
    )
    from session.store import SessionStore

    db_path = tmp_path / "sessions.db"
    store = SessionStore(db_path)
    try:
        store.create_session(key="cli:local")
    finally:
        store.close()

    try:
        open_marked_source_ref_quality_fixture_resolver(db_path)
    except ValueError as exc:
        assert "refusing to open unmarked source_ref quality fixture db" in str(exc)
    else:
        raise AssertionError("expected resolver opener to reject unmarked db")


def test_source_ref_quality_fixture_resolver_missing_path_does_not_create_db(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import (
        open_marked_source_ref_quality_fixture_resolver,
    )

    db_path = tmp_path / "missing" / "sessions.db"

    try:
        open_marked_source_ref_quality_fixture_resolver(db_path)
    except ValueError as exc:
        assert "refusing to open unmarked source_ref quality fixture db" in str(exc)
    else:
        raise AssertionError("expected resolver opener to reject missing db")

    assert not db_path.exists()


def test_source_ref_quality_eval_missing_candidate_id_is_not_eligible(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import (
        build_source_ref_quality_fixture,
        open_marked_source_ref_quality_fixture_resolver,
        run_source_ref_quality_eval,
    )

    db_path = tmp_path / "sessions.db"
    build_source_ref_quality_fixture(db_path)
    handle = open_marked_source_ref_quality_fixture_resolver(db_path)
    try:
        report = run_source_ref_quality_eval(
            candidates=(
                SourceRefQualityInput(
                    candidate_id="missing-candidate-id",
                    session_key="cli:local",
                    baseline_source_ref="cli:local@post_response",
                    candidate_message_ids=("cli:local:999",),
                    expected_terms=("source_ref",),
                ),
            ),
            source_ref_resolver=handle.resolver,
        )
    finally:
        handle.close()

    record = report.records[0]
    assert record["normalized_source_ref"] == '["cli:local:999"]'
    assert record["normalized_fetch_success"] is False
    assert record["normalized_support_status"] == "missing"
    assert record["normalized_source_backed_eligible"] is False


def test_source_ref_quality_eligible_requires_fetch_success_and_supported(
    tmp_path: Path,
) -> None:
    from memory2.eval_source_ref_quality import (
        build_source_ref_quality_fixture,
        open_marked_source_ref_quality_fixture_resolver,
        run_source_ref_quality_eval,
    )

    db_path = tmp_path / "sessions.db"
    candidates = build_source_ref_quality_fixture(db_path)
    handle = open_marked_source_ref_quality_fixture_resolver(db_path)
    try:
        report = run_source_ref_quality_eval(
            candidates=candidates,
            source_ref_resolver=handle.resolver,
        )
    finally:
        handle.close()

    by_id = {str(record["candidate_id"]): record for record in report.records}
    assert by_id["already-message-supported"]["baseline_source_backed_eligible"] is True
    assert by_id["session-level-upgradable"]["baseline_source_backed_eligible"] is False
    assert by_id["session-level-upgradable"]["normalized_source_backed_eligible"] is True
    assert by_id["missing-upgradable"]["baseline_source_backed_eligible"] is False
    assert by_id["missing-upgradable"]["normalized_source_backed_eligible"] is True
    assert by_id["malformed-upgradable"]["baseline_source_backed_eligible"] is False
    assert by_id["malformed-upgradable"]["normalized_source_backed_eligible"] is True
    assert by_id["unsupported-message-kept"]["normalized_source_backed_eligible"] is False
    assert by_id["session-level-no-ids"]["normalized_source_backed_eligible"] is False


def test_source_ref_quality_eval_empty_candidates_returns_unavailable_rates() -> None:
    from memory2.eval_sleep_hygiene_provenance import MappingSourceRefResolver
    from memory2.eval_source_ref_quality import run_source_ref_quality_eval

    report = run_source_ref_quality_eval(
        candidates=(),
        source_ref_resolver=MappingSourceRefResolver({}),
    )

    assert report.metrics["candidate_count"] == 0
    assert report.metrics["baseline_message_level_rate"] == "unavailable"
    assert report.metrics["normalized_message_level_rate"] == "unavailable"
    assert report.metrics["message_level_uplift_points"] == "unavailable"
    assert report.metrics["baseline_fetch_success_rate"] == "unavailable"
    assert report.metrics["normalized_source_backed_eligible_rate"] == "unavailable"
    assert report.metadata["evaluation_mode"] == "synthetic_fixture_shadow"
