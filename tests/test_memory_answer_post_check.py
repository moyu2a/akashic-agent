from __future__ import annotations

from memory2.eval_answer_post_check import (
    answer_post_check_shadow_to_dict,
    build_answer_post_check_shadow,
)


def _contract() -> dict[str, object]:
    return {
        "production_safe_evidence_contract": True,
        "allowed_evidence_ids": ["target", "weak", "conflict"],
        "likely_relevant_evidence_ids": ["target", "weak"],
        "stale_warning_ids": ["old"],
        "conflict_warning_ids": ["conflict"],
        "active_version_ids": ["target", "weak", "conflict"],
        "insufficient_evidence_ids": ["gap"],
        "insufficient_evidence_fallback": True,
        "forbidden_boundary_ids": ["blocked"],
        "deleted_evidence_ids": ["blocked", "old"],
    }


def test_post_check_records_allowed_missing_risky_and_fallback_signals() -> None:
    shadow = build_answer_post_check_shadow(
        "根据证据不足，无法确认。",
        _contract(),
        ["target", "conflict", "blocked"],
    )

    assert shadow.shadow_enabled is True
    assert shadow.production_safe_evidence_contract is True
    assert shadow.allowed_evidence_included is True
    assert shadow.included_allowed_evidence_ids == ("target", "conflict")
    assert shadow.missing_likely_relevant_context_ids == ("weak",)
    assert shadow.forbidden_boundary_included is True
    assert shadow.included_forbidden_boundary_ids == ("blocked",)
    assert shadow.conflict_evidence_included is True
    assert shadow.included_conflict_warning_ids == ("conflict",)
    assert shadow.stale_evidence_included is False
    assert shadow.insufficient_evidence_fallback_expected is True
    assert shadow.insufficient_evidence_fallback_observed is True
    assert shadow.needs_retry is True
    assert shadow.retry_reasons == (
        "forbidden_boundary_included",
        "missing_likely_relevant_context",
        "conflict_evidence_included",
    )
    assert shadow.raw_answer == ""
    assert shadow.raw_prompt == ""


def test_post_check_marks_missing_fallback_when_evidence_is_insufficient() -> None:
    shadow = build_answer_post_check_shadow(
        "可以继续执行。",
        _contract(),
        ["target", "weak"],
    )

    assert shadow.insufficient_evidence_fallback_expected is True
    assert shadow.insufficient_evidence_fallback_observed is False
    assert shadow.needs_retry is True
    assert "insufficient_evidence_fallback_missing" in shadow.retry_reasons


def test_post_check_is_disabled_for_non_production_safe_contract() -> None:
    shadow = build_answer_post_check_shadow(
        "根据 Answer Contract 回答。",
        {"required_terms": ["ORACLE_TERM"]},
        ["target"],
    )

    assert shadow.shadow_enabled is False
    assert shadow.production_safe_evidence_contract is False
    assert shadow.included_allowed_evidence_ids == ()
    assert shadow.retry_reasons == ()


def test_post_check_dict_is_private_and_structured() -> None:
    shadow = build_answer_post_check_shadow(
        "这是一段完整回答，证据不足，无法确认。",
        _contract(),
        ["target", "weak"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)

    assert payload["shadow_enabled"] is True
    assert payload["production_safe_evidence_contract"] is True
    assert payload["allowed_evidence_included"] is True
    assert payload["included_allowed_evidence_ids"] == ["target", "weak"]
    assert "raw_answer" not in payload
    assert "raw_prompt" not in payload
    assert "full_answer" not in payload
    assert "这是一段完整回答" not in str(payload)


def test_post_check_retry_shadow_flags_required_term_score_miss() -> None:
    shadow = build_answer_post_check_shadow(
        "我建议继续使用 unittest。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 1,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 1,
                "expected_any_miss_count": 0,
                "language_passed": True,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["answer_candidate_contract_enabled"] is True
    assert payload["required_terms_missing"] is True
    assert payload["needs_retry"] is True
    assert "required_terms_missing" in payload["retry_reasons"]
    assert "pytest" not in str(payload)


def test_post_check_retry_shadow_flags_language_failure() -> None:
    shadow = build_answer_post_check_shadow(
        "Use pytest.",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 0,
                "expected_any_miss_count": 0,
                "language_passed": False,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["language_requirement_failed"] is True
    assert payload["needs_retry"] is True
    assert "language_requirement_failed" in payload["retry_reasons"]


def test_post_check_retry_shadow_flags_dsml_tool_markup_and_meta_action() -> None:
    shadow = build_answer_post_check_shadow(
        "我先查一下。<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name=\"read_file\">",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 1,
                "expected_any_miss_count": 0,
                "language_passed": True,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["dsml_tool_markup_in_final_answer"] is True
    assert payload["tool_markup_in_final_answer"] is True
    assert payload["meta_action_final_answer"] is True
    assert payload["answerable_evidence_contract_ignored"] is True
    assert "dsml_tool_markup_in_final_answer" in payload["retry_reasons"]
    assert "tool_markup_in_final_answer" in payload["retry_reasons"]
    assert "meta_action_final_answer" in payload["retry_reasons"]
    assert "answerable_evidence_contract_ignored" in payload["retry_reasons"]


def test_post_check_retry_shadow_flags_plain_meta_action_without_scorer_dependence() -> None:
    shadow = build_answer_post_check_shadow(
        "先翻一下记忆文件核实“上次的回答方式”具体指什么。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 0,
                "expected_any_miss_count": 0,
                "language_passed": True,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["meta_action_final_answer"] is True
    assert payload["answerable_evidence_contract_ignored"] is True
    assert "meta_action_final_answer" in payload["retry_reasons"]
    assert "answerable_evidence_contract_ignored" in payload["retry_reasons"]


def test_post_check_retry_if_needed_marks_actionable_answer_misses() -> None:
    shadow = build_answer_post_check_shadow(
        "我先查一下。<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name=\"read_file\">",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 1,
                "expected_any_miss_count": 1,
                "language_passed": True,
                "forbidden_contains_violation_count": 0,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["retry_if_needed_shadow_enabled"] is True
    assert payload["retry_if_needed_eligible"] is True
    assert payload["retry_if_needed_reasons"] == [
        "required_terms_missing",
        "answer_choice_group_missing",
        "dsml_tool_markup_in_final_answer",
        "tool_markup_in_final_answer",
        "meta_action_final_answer",
        "answerable_evidence_contract_ignored",
    ]
    assert payload["retry_if_needed_blocked_reasons"] == []


def test_post_check_retry_if_needed_blocks_forbidden_answer_term() -> None:
    shadow = build_answer_post_check_shadow(
        "用户旧偏好 unittest。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 1,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 0,
                "expected_any_miss_count": 0,
                "language_passed": True,
                "forbidden_contains_violation_count": 1,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["retry_if_needed_shadow_enabled"] is True
    assert payload["retry_if_needed_eligible"] is False
    assert payload["retry_if_needed_reasons"] == []
    assert payload["retry_if_needed_blocked_reasons"] == [
        "forbidden_answer_term_found"
    ]


def test_post_check_does_not_mark_contract_ignored_without_current_truth() -> None:
    shadow = build_answer_post_check_shadow(
        "先查一下记忆文件。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 0,
                "must_include_term_count": 0,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 0,
                "expected_any_miss_count": 0,
                "language_passed": True,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["meta_action_final_answer"] is True
    assert payload["answerable_evidence_contract_ignored"] is False
    assert "meta_action_final_answer" in payload["retry_reasons"]
    assert "answerable_evidence_contract_ignored" not in payload["retry_reasons"]


def test_post_check_low_risk_meta_phrase_is_telemetry_only_when_answer_passed() -> None:
    shadow = build_answer_post_check_shadow(
        "当前偏好是短句和要点；以后回答前我会先核实是否有更新。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 0,
                "expected_any_miss_count": 0,
                "language_passed": True,
                "forbidden_contains_violation_count": 0,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["meta_action_final_answer"] is True
    assert payload["answerable_evidence_contract_ignored"] is False
    assert payload["retry_if_needed_eligible"] is False
    assert "meta_action_final_answer" in payload["retry_reasons"]
    assert "meta_action_final_answer" not in payload["retry_if_needed_reasons"]


def test_post_check_action_only_meta_answer_stays_retry_eligible() -> None:
    shadow = build_answer_post_check_shadow(
        "先翻一下记忆文件核实。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 1,
                "expected_any_miss_count": 0,
                "language_passed": True,
                "forbidden_contains_violation_count": 0,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["meta_action_final_answer"] is True
    assert payload["answerable_evidence_contract_ignored"] is True
    assert payload["retry_if_needed_eligible"] is True
    assert "meta_action_final_answer" in payload["retry_if_needed_reasons"]
