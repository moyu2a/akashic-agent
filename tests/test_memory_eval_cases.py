from __future__ import annotations

from pathlib import Path

from memory2.eval_cases import (
    EVAL_CONFIG_MATRIX,
    EVAL_CONFIG_PROFILES,
    EVAL_PHASE_TARGETS,
    load_eval_case,
    load_eval_cases,
    validate_eval_case_payload,
)


FIXTURE_ROOT = Path("tests/fixtures/memory_eval_cases")


def test_eval_config_profiles_cover_phase_matrix() -> None:
    assert EVAL_CONFIG_PROFILES == (
        "off",
        "phase1",
        "phase2",
        "phase3",
        "phase4",
        "phase5",
        "all",
    )


def test_eval_phase_targets_are_distinct_from_config_profiles() -> None:
    assert EVAL_PHASE_TARGETS == (
        "phase1",
        "phase2a",
        "phase2b",
        "phase3a",
        "phase3b",
        "phase4a",
        "phase4b",
        "phase5",
    )
    assert "off" not in EVAL_PHASE_TARGETS
    assert "all" not in EVAL_PHASE_TARGETS


def test_eval_config_matrix_maps_profiles_to_real_flags() -> None:
    assert EVAL_CONFIG_MATRIX["off"] == {
        "enabled": False,
        "mode": "off",
        "flags": {},
    }
    assert EVAL_CONFIG_MATRIX["phase3"] == {
        "enabled": True,
        "mode": "shadow",
        "flags": {
            "rerank_shadow_enabled": True,
            "injection_governance_shadow_enabled": True,
        },
    }
    assert EVAL_CONFIG_MATRIX["phase5"]["flags"] == {
        "sleep_consolidation_shadow_enabled": True,
    }


def test_validate_eval_case_payload_reports_missing_required_fields() -> None:
    errors = validate_eval_case_payload({"id": "bad"}, source="inline")

    assert "inline: missing required field 'title'" in errors
    assert "inline: missing required field 'category'" in errors
    assert "inline: missing required field 'phase_targets'" in errors
    assert "inline: missing required field 'config_profiles'" in errors
    assert "inline: missing required field 'setup'" in errors
    assert "inline: missing required field 'expectations'" in errors


def test_validate_eval_case_payload_accepts_minimal_valid_case() -> None:
    errors = validate_eval_case_payload(
        {
            "id": "preference_recall",
            "title": "Preference recall",
            "category": "preference_recall",
            "phase_targets": ["phase2a", "phase3a"],
            "config_profiles": ["off", "phase2", "phase3", "all"],
            "setup": {
                "scope": {
                    "session_key": "cli:local",
                    "channel": "cli",
                    "chat_id": "local",
                },
                "memory_items": [
                    {
                        "id": "m_pref_cn",
                        "memory_type": "preference",
                        "summary": "用户偏好中文回答",
                        "status": "active",
                        "source_ref": "cli:local@post_response",
                        "scope_channel": "cli",
                        "scope_chat_id": "local",
                    }
                ],
                "query": "我希望你用什么语言回答？",
            },
            "expectations": {
                "should_recall_ids": ["m_pref_cn"],
                "should_not_recall_ids": [],
                "expected_trace_features": ["tri_retrieval", "rerank_shadow"],
                "expected_metric_keys": {
                    "tri_retrieval": ["semantic_hit_count"],
                    "rerank_shadow": ["rerank_changed_count"],
                },
                "profile_expectations": {
                    "off": {
                        "forbidden_trace_features": [
                            "tri_retrieval",
                            "rerank_shadow",
                        ]
                    },
                    "phase2": {
                        "required_trace_features": ["tri_retrieval"],
                        "metric_keys": {"tri_retrieval": ["semantic_hit_count"]},
                    },
                    "phase3": {
                        "required_trace_features": ["rerank_shadow"],
                        "metric_keys": {"rerank_shadow": ["rerank_changed_count"]},
                    },
                    "all": {
                        "required_trace_features": [
                            "tri_retrieval",
                            "rerank_shadow",
                        ]
                    },
                },
            },
        },
        source="inline",
    )

    assert errors == []


def test_validate_eval_case_payload_rejects_config_profile_as_phase_target() -> None:
    errors = validate_eval_case_payload(
        {
            "id": "bad_phase",
            "title": "Bad phase",
            "category": "schema",
            "phase_targets": ["off"],
            "config_profiles": ["off", "all"],
            "setup": {
                "scope": {
                    "session_key": "cli:local",
                    "channel": "cli",
                    "chat_id": "local",
                },
                "memory_items": [],
                "query": "hello",
            },
            "expectations": {
                "should_recall_ids": [],
                "should_not_recall_ids": [],
                "expected_trace_features": [],
                "expected_metric_keys": {},
                "profile_expectations": {
                    "off": {"forbidden_trace_features": []},
                    "all": {"required_trace_features": []},
                },
            },
        },
        source="inline",
    )

    assert "inline: unknown phase target 'off' in 'phase_targets'" in errors


def test_memory_eval_fixture_pack_loads_all_cases() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)

    assert [case.id for case in cases] == [
        "conflict_memory",
        "cross_scope_isolation",
        "duplicate_memory",
        "injection_governance_budget",
        "preference_recall",
        "provenance_trace",
        "stale_memory_sleep",
        "temporary_memory_pollution",
        "vague_reference_graph",
    ]


def test_memory_eval_fixture_pack_covers_phase_targets() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)
    covered = {phase for case in cases for phase in case.phase_targets}

    assert {"phase1", "phase2a", "phase2b", "phase3a", "phase3b"}.issubset(covered)
    assert {"phase4a", "phase4b", "phase5"}.issubset(covered)


def test_memory_eval_fixture_pack_has_baseline_and_all_profiles() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)

    for case in cases:
        assert "off" in case.config_profiles
        assert "all" in case.config_profiles


def test_memory_eval_fixture_pack_declares_expected_metrics() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)

    by_id = {case.id: case for case in cases}
    assert by_id["temporary_memory_pollution"].expectations["expected_metric_keys"][
        "write_value_score"
    ] == ["temporary_risk_count", "policy_reject_count"]
    assert by_id["vague_reference_graph"].expectations["expected_metric_keys"][
        "graph_retrieval"
    ] == ["graph_hit_count", "graph_path_count", "baseline_graph_overlap_rate"]
    assert by_id["stale_memory_sleep"].expectations["expected_metric_keys"][
        "sleep_consolidation_shadow"
    ] == ["stale_candidate_count", "low_value_candidate_count"]
    assert by_id["injection_governance_budget"].expectations["expected_metric_keys"][
        "injection_governance_shadow"
    ] == ["prompt_token_delta", "dropped_by_reason"]


def test_memory_eval_fixture_ids_match_file_names() -> None:
    for path in sorted(FIXTURE_ROOT.glob("*.json")):
        case = load_eval_case(path)
        assert case.id == path.stem


def test_memory_eval_fixture_recall_ids_exist_in_setup() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)

    for case in cases:
        memory_ids = {str(item["id"]) for item in case.setup.get("memory_items", [])}
        expected = set(case.expectations["should_recall_ids"])
        forbidden = set(case.expectations["should_not_recall_ids"])
        assert expected.issubset(memory_ids)
        assert forbidden.issubset(memory_ids | _written_candidate_ids(case))


def test_memory_eval_fixture_metric_features_are_declared_traces() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)

    for case in cases:
        traces = set(case.expectations["expected_trace_features"])
        metric_features = set(case.expectations["expected_metric_keys"])
        assert metric_features.issubset(traces)


def test_memory_eval_fixture_profiles_match_phase_targets() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)
    phase_to_profile = {
        "phase1": "phase1",
        "phase2a": "phase2",
        "phase2b": "phase2",
        "phase3a": "phase3",
        "phase3b": "phase3",
        "phase4a": "phase4",
        "phase4b": "phase4",
        "phase5": "phase5",
    }

    for case in cases:
        profiles = set(case.config_profiles)
        for phase in case.phase_targets:
            assert phase_to_profile[phase] in profiles


def _written_candidate_ids(case) -> set[str]:
    result: set[str] = set()
    for call in case.setup.get("memorize_calls", []):
        text = str(call.get("result") or "")
        for token in text.split():
            if token.startswith("item_id="):
                result.add(token.removeprefix("item_id="))
    return result
