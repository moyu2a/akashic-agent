from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from memory2.eval_quantitative_cases import build_quantitative_eval_cases


def _walk_report_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for child in value.values():
            keys.update(_walk_report_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_walk_report_keys(child))
        return keys
    return set()


def _raw_fixture_strings(cases: list[object]) -> list[str]:
    values: list[str] = []
    for case in cases:
        setup = getattr(case, "setup")
        query = str(setup.get("query") or "").strip()
        if query:
            values.append(query)
        for item in setup.get("memory_items", []):
            if isinstance(item, dict):
                summary = str(item.get("summary") or "").strip()
                if summary:
                    values.append(summary)
        for replacement in setup.get("memory_replacements", []):
            if isinstance(replacement, dict):
                for key in ("old_summary", "new_summary"):
                    summary = str(replacement.get(key) or "").strip()
                    if summary:
                        values.append(summary)
    return values


def _assert_report_is_private(payload: dict[str, object], markdown: str) -> None:
    forbidden_keys = {
        "raw_prompt",
        "prompt",
        "full_answer",
        "raw_answer",
        "session_text",
        "memory_summary",
        "raw_memory_summary",
    }
    assert not (forbidden_keys & _walk_report_keys(payload))
    selected_cases = (
        build_quantitative_eval_cases("common", case_pack="standard", limit=2)
        + build_quantitative_eval_cases("hard", case_pack="standard", limit=2)
    )
    report_text = json.dumps(payload, ensure_ascii=False) + "\n" + markdown
    for raw_value in _raw_fixture_strings(selected_cases):
        assert raw_value not in report_text
    assert (
        "根据 system path safe version governed contract，应只使用 allowed_evidence 回答。"
        not in report_text
    )
    assert "根据系统路径注入记忆回答。" not in report_text
    assert "没有可用记忆，无法确认。" not in report_text


def _p6o19_gate_payload(
    *,
    replace_answer_rate: float,
    guided_answer_rate: float,
    retry_shadow_answer_rate: float,
) -> dict[str, object]:
    modes = (
        "safe_version_replace",
        "safe_version_replace_guided",
        "safe_version_replace_guided_with_retry_shadow",
    )
    rates = {
        "safe_version_replace": replace_answer_rate,
        "safe_version_replace_guided": guided_answer_rate,
        "safe_version_replace_guided_with_retry_shadow": retry_shadow_answer_rate,
    }
    cases = [
        {
            "case_id": f"case-{index}",
            "mode": mode,
            "answer_rule_passed": rates[mode] >= 100.0,
            "memory_grounding_passed": True,
            "forbidden_contains_violation_count": 0,
            "provider_error": False,
            "timeout": False,
            "safe_version_contract": {
                "answer_prompt_variant": "guided_retry_shadow"
                if mode == "safe_version_replace_guided_with_retry_shadow"
                else "guided"
                if mode == "safe_version_replace_guided"
                else "standard",
                "answer_candidate_contract": {
                    "enabled": mode
                    == "safe_version_replace_guided_with_retry_shadow",
                    "current_truth_count": 1
                    if mode == "safe_version_replace_guided_with_retry_shadow"
                    else 0,
                    "must_include_term_count": 1
                    if mode == "safe_version_replace_guided_with_retry_shadow"
                    else 0,
                    "forbidden_old_value_count": 1
                    if mode == "safe_version_replace_guided_with_retry_shadow"
                    else 0,
                    "language_requirement": "match_user_language"
                    if mode == "safe_version_replace_guided_with_retry_shadow"
                    else "",
                    "candidate_reason": "safe_version_guided_retry_shadow"
                    if mode == "safe_version_replace_guided_with_retry_shadow"
                    else "",
                },
            },
            "post_check_shadow": {
                "shadow_enabled": mode != "safe_version_replace",
                "needs_retry": mode == "safe_version_replace_guided_with_retry_shadow",
                "retry_reasons": ["required_terms_missing"]
                if mode == "safe_version_replace_guided_with_retry_shadow"
                else [],
                "answer_candidate_contract_enabled": mode
                == "safe_version_replace_guided_with_retry_shadow",
            },
        }
        for index, mode in enumerate(modes)
    ]
    mode_summaries = {
        mode: {
            "case_count": 1,
            "answer_success_count": 1 if rates[mode] >= 100.0 else 0,
            "grounding_success_count": 1,
            "forbidden_case_count": 0,
            "would_retry_count": 1
            if mode == "safe_version_replace_guided_with_retry_shadow"
            else 0,
            "retry_reason_counts": {"required_terms_missing": 1}
            if mode == "safe_version_replace_guided_with_retry_shadow"
            else {},
            "answer_rule_pass_rate": rates[mode],
            "memory_grounding_pass_rate": 100.0,
            "forbidden_violation_rate": 0.0,
            "contract_generation_success_rate": 100.0,
            "post_check_shadow_enabled_rate": 100.0
            if mode != "safe_version_replace"
            else 0.0,
            "answer_candidate_contract_enabled_rate": 100.0
            if mode == "safe_version_replace_guided_with_retry_shadow"
            else 0.0,
            "avg_total_token_count": 30.0,
            "avg_latency_ms": 10.0,
            "token_metrics_available": True,
        }
        for mode in modes
    }
    return {
        "cases": cases,
        "metrics": {
            "unique_case_count": 1,
            "mode_count": 3,
            "case_count": 3,
            "repeat_count": 1,
            "provider_error_count": 0,
            "timeout_count": 0,
            "checkpoint_input_count": 3,
            "malformed_checkpoint_line_count": 0,
            "real_llm_enabled": True,
            "fake_provider_enabled": False,
            "mode_summaries": mode_summaries,
        },
    }


def _p6o33_incremental_payload(
    *,
    replace_answer_rate: float,
    guided_answer_rate: float,
    retry_shadow_answer_rate: float,
) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    modes = (
        ("safe_version_replace", replace_answer_rate, "standard"),
        ("safe_version_replace_guided", guided_answer_rate, "guided"),
        (
            "safe_version_replace_guided_with_retry_shadow",
            retry_shadow_answer_rate,
            "guided_retry_shadow",
        ),
    )
    for mode, answer_rate, variant in modes:
        for index in range(4):
            passed = index < int(round(answer_rate / 25.0))
            cases.append(
                {
                    "case_id": f"case-{index}",
                    "case_index": index,
                    "repeat_index": 0,
                    "category": "common" if index < 2 else "hard",
                    "mode": mode,
                    "passed": passed,
                    "answer_rule_passed": passed,
                    "memory_grounding_passed": True,
                    "expected_memory_used": True,
                    "forbidden_contains_violation_count": 0,
                    "answer_length": 8,
                    "expected_contains_pass_count": 1 if passed else 0,
                    "expected_contains_miss_count": 0 if passed else 1,
                    "expected_any_pass_count": 1 if passed else 0,
                    "expected_any_miss_count": 0 if passed else 1,
                    "language_passed": True,
                    "failures": [] if passed else ["missing_expected_answer_term"],
                    "provider_error": False,
                    "timeout": False,
                    "latency_ms": 100,
                    "token_count": 200,
                    "prompt_token_count": 120,
                    "completion_token_count": 80,
                    "token_metrics_available": True,
                    "replacement_seeded_count": 1,
                    "safe_version_metadata": {
                        "contract_generation_success": True,
                        "answer_guidance_enabled": variant != "standard",
                        "answer_prompt_variant": variant,
                    },
                    "safe_version_contract": {
                        "profile_name": "system_path_safe_version_governed",
                        "production_safe": True,
                        "production_safe_evidence_contract": True,
                        "uses_fixture_answer_expectations": False,
                        "answer_guidance_enabled": variant != "standard",
                        "answer_prompt_variant": variant,
                        "candidate_governance_mode": "replace",
                        "allowed_evidence_ids": ["m1"],
                        "likely_relevant_evidence_ids": ["m1"],
                        "downgrade_ids": [],
                        "requires_review_ids": [],
                        "stale_warning_ids": [],
                        "conflict_warning_ids": [],
                        "active_version_ids": ["m1"],
                        "insufficient_evidence_ids": [],
                        "insufficient_evidence_fallback": False,
                        "forbidden_boundary_ids": [],
                        "deleted_evidence_ids": [],
                        "candidate_risk_tier_counts": {},
                        "accepted_candidate_risk_tier_counts": {},
                        "tiered_deleted_risks_by_reason": {},
                        "version_boundary": {"replacement_count": 1},
                        "answer_candidate_contract": {
                            "enabled": mode
                            == "safe_version_replace_guided_with_retry_shadow",
                            "current_truth_count": 1
                            if mode
                            == "safe_version_replace_guided_with_retry_shadow"
                            else 0,
                            "must_include_term_count": 1
                            if mode
                            == "safe_version_replace_guided_with_retry_shadow"
                            else 0,
                            "forbidden_old_value_count": 1
                            if mode
                            == "safe_version_replace_guided_with_retry_shadow"
                            else 0,
                        },
                    },
                    "post_check_shadow": {
                        "shadow_enabled": mode
                        == "safe_version_replace_guided_with_retry_shadow",
                        "needs_retry": False,
                        "retry_reasons": [],
                    },
                }
            )
    metrics = {
        "evaluation_level": "system_path_safe_version_governed",
        "unique_case_count": 4,
        "mode_count": 3,
        "case_count": 12,
        "repeat_count": 1,
        "provider_error_count": 0,
        "timeout_count": 0,
        "checkpoint_input_count": 0,
        "malformed_checkpoint_line_count": 0,
        "real_llm_enabled": True,
        "fake_provider_enabled": False,
        "answer_rule_pass_rate": 100.0,
        "memory_grounding_pass_rate": 100.0,
        "forbidden_violation_rate": 0.0,
        "mode_summaries": {
            "safe_version_replace": {
                "case_count": 4,
                "answer_success_count": 3,
                "grounding_success_count": 4,
                "forbidden_case_count": 0,
                "would_retry_count": 0,
                "retry_reason_counts": {},
                "answer_rule_pass_rate": replace_answer_rate,
                "memory_grounding_pass_rate": 100.0,
                "forbidden_violation_rate": 0.0,
                "contract_generation_success_rate": 100.0,
                "post_check_shadow_enabled_rate": 100.0,
                "answer_candidate_contract_enabled_rate": 0.0,
                "avg_total_token_count": 200.0,
                "avg_latency_ms": 100.0,
                "token_metrics_available": True,
            },
            "safe_version_replace_guided": {
                "case_count": 4,
                "answer_success_count": 3,
                "grounding_success_count": 4,
                "forbidden_case_count": 0,
                "would_retry_count": 0,
                "retry_reason_counts": {},
                "answer_rule_pass_rate": guided_answer_rate,
                "memory_grounding_pass_rate": 100.0,
                "forbidden_violation_rate": 0.0,
                "contract_generation_success_rate": 100.0,
                "post_check_shadow_enabled_rate": 100.0,
                "answer_candidate_contract_enabled_rate": 0.0,
                "avg_total_token_count": 200.0,
                "avg_latency_ms": 100.0,
                "token_metrics_available": True,
            },
            "safe_version_replace_guided_with_retry_shadow": {
                "case_count": 4,
                "answer_success_count": 4,
                "grounding_success_count": 4,
                "forbidden_case_count": 0,
                "would_retry_count": 1,
                "retry_reason_counts": {"answer_choice_group_missing": 1},
                "answer_rule_pass_rate": retry_shadow_answer_rate,
                "memory_grounding_pass_rate": 100.0,
                "forbidden_violation_rate": 0.0,
                "contract_generation_success_rate": 100.0,
                "post_check_shadow_enabled_rate": 100.0,
                "answer_candidate_contract_enabled_rate": 100.0,
                "avg_total_token_count": 200.0,
                "avg_latency_ms": 100.0,
                "token_metrics_available": True,
            },
        },
    }
    return {"cases": cases, "metrics": metrics}


def test_system_path_safe_version_cli_fake_provider_writes_sanitized_report(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--modes",
            "current,safe_version_shadow,safe_version_replace",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (out_dir / "system_path_safe_version_eval.md").read_text(
        encoding="utf-8"
    )
    assert markdown.startswith("# System Path Safe Version Governed")
    assert payload["metrics"]["evaluation_level"] == "system_path_safe_version_governed"
    assert payload["metrics"]["unique_case_count"] == 4
    assert payload["metrics"]["mode_count"] == 3
    assert payload["metrics"]["case_count"] == 12
    assert payload["metrics"]["fake_provider_enabled"] is True
    assert payload["metrics"]["real_llm_enabled"] is False
    assert "answer_rule_pass_rate" in payload["metrics"]
    assert "memory_grounding_pass_rate" in payload["metrics"]
    assert "forbidden_violation_rate" in payload["metrics"]
    assert "token_metrics_available" in payload["metrics"]
    assert payload["metrics"]["raw_query_included"] is False
    assert payload["metrics"]["raw_memory_summary_included"] is False
    assert payload["metrics"]["prompt_included"] is False
    assert payload["metrics"]["complete_response_included"] is False
    assert payload["metrics"]["conversation_log_included"] is False
    assert "safe_version_replace" in payload["metrics"]["mode_summaries"]
    assert (
        payload["metrics"]["mode_summaries"]["safe_version_shadow"][
            "contract_generation_success_rate"
        ]
        == 100.0
    )
    assert (
        payload["metrics"]["mode_summaries"]["safe_version_shadow"][
            "post_check_shadow_enabled_rate"
        ]
        == 100.0
    )
    assert (
        payload["metrics"]["mode_summaries"]["safe_version_replace"][
            "post_check_shadow_enabled_rate"
        ]
        == 100.0
    )
    assert (
        payload["metrics"]["mode_summaries"]["current"][
            "post_check_shadow_enabled_rate"
        ]
        == 0.0
    )
    current = payload["metrics"]["mode_summaries"]["current"]
    replace = payload["metrics"]["mode_summaries"]["safe_version_replace"]
    assert "answer_success_count" in current
    assert "answer_rule_pass_rate" in current
    assert "memory_grounding_pass_rate" in current
    assert "forbidden_violation_rate" in current
    assert "avg_total_token_count" in current
    assert "avg_latency_ms" in current
    assert replace["contract_generation_success_rate"] == 100.0
    assert replace["post_check_shadow_enabled_rate"] == 100.0
    assert (
        "| mode | cases | answer_success | answer_rate | grounding_rate | "
        "forbidden_rate | contract_success | post_check_shadow | avg_tokens | "
        "avg_latency_ms |"
    ) in markdown
    assert all("post_check_shadow" in row for row in payload["cases"])
    for row in payload["cases"]:
        assert "answer_rule_passed" in row
        assert "memory_grounding_passed" in row
        assert "expected_memory_used" in row
        assert "forbidden_contains_violation_count" in row
        assert "failures" in row
        assert "answer_passed" not in row
    assert payload["metrics"]["replacement_seeded_count"] > 0
    version_rows = [
        row
        for row in payload["cases"]
        if row["mode"] in {"safe_version_shadow", "safe_version_replace"}
        and row.get("replacement_seeded_count", 0) > 0
    ]
    assert version_rows
    assert all(
        row["safe_version_contract"]["version_boundary"]["replacement_count"] > 0
        for row in version_rows
    )
    _assert_report_is_private(payload, markdown)


def test_system_path_safe_version_cli_supports_replace_guided_mode(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--balanced-small",
            "--common-limit",
            "1",
            "--hard-limit",
            "1",
            "--modes",
            "safe_version_replace,safe_version_replace_guided",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    summaries = payload["metrics"]["mode_summaries"]
    assert summaries["safe_version_replace"]["case_count"] == 2
    assert summaries["safe_version_replace_guided"]["case_count"] == 2
    guided_rows = [
        row for row in payload["cases"] if row["mode"] == "safe_version_replace_guided"
    ]
    assert guided_rows
    assert all(
        row["safe_version_metadata"]["answer_guidance_enabled"] is True
        for row in guided_rows
    )
    assert all(
        row["safe_version_contract"]["answer_guidance_enabled"] is True
        for row in guided_rows
    )
    assert all(
        row["post_check_shadow"]["shadow_enabled"] is True
        for row in guided_rows
    )


def test_system_path_safe_version_cli_supports_p6o18_prompt_variants(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--balanced-small",
            "--common-limit",
            "1",
            "--hard-limit",
            "1",
            "--modes",
            (
                "safe_version_replace,safe_version_replace_guided,"
                "safe_version_replace_structured_guided,"
                "safe_version_replace_near_query_block"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    assert payload["metrics"]["mode_count"] == 4
    assert payload["metrics"]["case_count"] == 8
    expected = {
        "safe_version_replace": "standard",
        "safe_version_replace_guided": "guided",
        "safe_version_replace_structured_guided": "structured_guided",
        "safe_version_replace_near_query_block": "near_query_block",
    }
    for row in payload["cases"]:
        assert (
            row["safe_version_contract"]["answer_prompt_variant"]
            == expected[row["mode"]]
        )
        assert (
            row["safe_version_metadata"]["answer_prompt_variant"]
            == expected[row["mode"]]
        )


def test_system_path_safe_version_cli_supports_guided_retry_shadow_mode(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--balanced-small",
            "--common-limit",
            "1",
            "--hard-limit",
            "1",
            "--modes",
            "safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    summaries = payload["metrics"]["mode_summaries"]
    shadow = summaries["safe_version_replace_guided_with_retry_shadow"]
    assert shadow["case_count"] == 2
    assert shadow["answer_candidate_contract_enabled_rate"] == 100.0
    assert "would_retry_count" in shadow
    assert "retry_reason_counts" in shadow
    rows = [
        row
        for row in payload["cases"]
        if row["mode"] == "safe_version_replace_guided_with_retry_shadow"
    ]
    assert rows
    assert all(
        row["safe_version_contract"]["answer_prompt_variant"] == "guided_retry_shadow"
        for row in rows
    )
    assert all(
        row["safe_version_contract"]["answer_candidate_contract"]["enabled"] is True
        for row in rows
    )
    for row in rows:
        post = row["post_check_shadow"]
        assert "retry_if_needed_shadow_enabled" in post
        assert "retry_if_needed_eligible" in post
        assert "retry_if_needed_reasons" in post
        assert "retry_if_needed_blocked_reasons" in post
        assert "raw_answer" not in str(post)
        assert "raw_prompt" not in str(post)


def test_system_path_safe_version_guided_retry_shadow_stays_single_call(
    tmp_path: Path,
) -> None:
    from memory2.eval_quantitative_cases import build_quantitative_eval_cases
    from memory2.eval_system_path_safe_version import run_system_path_safe_version_cases
    from scripts.run_memory_system_path_safe_version_eval import (
        ScriptedSystemPathProvider,
    )

    cases = build_quantitative_eval_cases("common", case_pack="standard", limit=1)
    provider = ScriptedSystemPathProvider()

    report = asyncio.run(
        run_system_path_safe_version_cases(
            cases,
            tmp_path / "workspace",
            provider,
            modes=("safe_version_replace_guided_with_retry_shadow",),
            model="fake-model",
            repeats=1,
        )
    )

    assert report.metrics["case_count"] == 1
    assert len(provider.calls) == 1
    assert report.cases[0]["post_check_shadow"]["retry_if_needed_shadow_enabled"] is True
    assert report.cases[0]["post_check_shadow"]["retry_if_needed_eligible"] in {True, False}


def test_system_path_safe_version_cli_writes_answer_debug_only_when_requested(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    debug_dir = out_dir / "answer_debug"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--balanced-small",
            "--common-limit",
            "1",
            "--hard-limit",
            "0",
            "--modes",
            "safe_version_replace_guided_with_retry_shadow",
            "--answer-debug-dir",
            str(debug_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    markdown = (out_dir / "system_path_safe_version_eval.md").read_text(
        encoding="utf-8"
    )
    _assert_report_is_private(payload, markdown)
    debug_files = sorted(debug_dir.glob("*.json"))
    assert len(debug_files) == len(payload["cases"])
    debug_payload = json.loads(debug_files[0].read_text(encoding="utf-8"))
    assert debug_payload["case_id"] == payload["cases"][0]["case_id"]
    assert debug_payload["mode"] == "safe_version_replace_guided_with_retry_shadow"
    assert debug_payload["repeat_index"] == 0
    assert debug_payload["query"]
    assert debug_payload["answer_text"]
    assert debug_payload["safe_version_contract"]["answer_prompt_variant"] == "guided_retry_shadow"
    assert debug_payload["post_check_shadow"]["shadow_enabled"] is True
    assert "raw_answer" not in _walk_report_keys(payload)
    debug_rows = [
        json.loads(path.read_text(encoding="utf-8")) for path in debug_files
    ]
    assert all(
        "current_truth_lines"
        not in row["safe_version_contract"]["answer_candidate_contract"]
        for row in debug_rows
    )
    assert all(
        "must_include_terms"
        not in row["safe_version_contract"]["answer_candidate_contract"]
        for row in debug_rows
    )


def test_system_path_safe_version_cli_supports_schema_first_shadow_mode(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--balanced-small",
            "--common-limit",
            "1",
            "--hard-limit",
            "1",
            "--modes",
            "safe_version_replace,safe_version_replace_guided,safe_version_replace_schema_first_shadow",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    schema = payload["metrics"]["mode_summaries"][
        "safe_version_replace_schema_first_shadow"
    ]
    assert schema["case_count"] == 2
    assert schema["answer_candidate_contract_enabled_rate"] == 100.0
    assert schema["would_retry_count"] == 2
    assert schema["retry_reason_counts"]["required_terms_missing"] == 2
    assert schema["retry_reason_counts"]["answer_choice_group_missing"] == 2
    rows = [
        row
        for row in payload["cases"]
        if row["mode"] == "safe_version_replace_schema_first_shadow"
    ]
    assert rows
    assert all(
        row["safe_version_contract"]["answer_prompt_variant"] == "schema_first_shadow"
        for row in rows
    )
    assert all(
        row["safe_version_contract"]["answer_candidate_contract"]["enabled"] is True
        for row in rows
    )
    assert all(
        "current_truth_lines"
        not in row["safe_version_contract"]["answer_candidate_contract"]
        for row in rows
    )
    assert all(
        row["post_check_shadow"]["required_terms_missing"] is True for row in rows
    )
    assert all(
        row["post_check_shadow"]["answer_choice_group_missing"] is True for row in rows
    )
    _assert_report_is_private(
        payload,
        (out_dir / "system_path_safe_version_eval.md").read_text(encoding="utf-8"),
    )


def test_p6o19_gate_writes_retry_shadow_decision(tmp_path: Path) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    out_dir = tmp_path / "gate"
    report_json.write_text(
        json.dumps(
            _p6o19_gate_payload(
                replace_answer_rate=50.0,
                guided_answer_rate=75.0,
                retry_shadow_answer_rate=100.0,
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_memory_p6o19_gate.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    decision = json.loads((out_dir / "gate_decision.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "p6o19_answer_candidate_retry_shadow_report.md").read_text(
        encoding="utf-8"
    )
    assert decision["gate_passed"] is True
    assert decision["answer_delta_vs_guided"] == 25.0
    assert decision["retry_shadow_would_retry_count"] == 1
    assert decision["retry_shadow_reason_counts"] == {"required_terms_missing": 1}
    assert "# P6o-19 Answer Candidate Retry Shadow" in markdown


def test_p6o33_incremental_analysis_writes_uplift_and_failure_tables(
    tmp_path: Path,
) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    out_dir = tmp_path / "analysis"
    report_json.write_text(
        json.dumps(
            _p6o33_incremental_payload(
                replace_answer_rate=50.0,
                guided_answer_rate=75.0,
                retry_shadow_answer_rate=100.0,
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_memory_p6o33_incremental_eval.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(
        (out_dir / "p6o33_incremental_analysis.json").read_text(encoding="utf-8")
    )
    markdown = (out_dir / "p6o33_incremental_analysis.md").read_text(
        encoding="utf-8"
    )
    assert analysis["gate_passed"] is True
    assert analysis["target_reached"] is True
    assert analysis["answer_delta_a_to_b_pp"] == 25.0
    assert analysis["answer_delta_b_to_c_pp"] == 25.0
    assert analysis["paired_comparison"]["b_to_c"]["wins"] == 1
    assert analysis["paired_comparison"]["b_to_c"]["losses"] == 0
    assert analysis["category_summaries"]["common"]["safe_version_replace"]["case_count"] == 2
    assert analysis["failure_reason_counts"]["safe_version_replace"] == {
        "missing_expected_answer_term": 2
    }
    assert "retry shadow 不是真实 retry" in markdown
    assert "| safe_version_replace_guided_with_retry_shadow |" in markdown


def test_p6o33_incremental_analysis_rejects_wrong_mode_set(tmp_path: Path) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    payload = _p6o33_incremental_payload(
        replace_answer_rate=50.0,
        guided_answer_rate=75.0,
        retry_shadow_answer_rate=100.0,
    )
    payload["metrics"]["mode_summaries"].pop("safe_version_replace")
    report_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_memory_p6o33_incremental_eval.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(tmp_path / "analysis"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "mode set must match P6o33 expected modes" in completed.stderr


def test_p6o33_incremental_analysis_rejects_truncated_case_rows(
    tmp_path: Path,
) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    payload = _p6o33_incremental_payload(
        replace_answer_rate=50.0,
        guided_answer_rate=75.0,
        retry_shadow_answer_rate=100.0,
    )
    payload["cases"] = payload["cases"][:-1]
    report_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_memory_p6o33_incremental_eval.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(tmp_path / "analysis"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "report case rows must match metrics case_count" in completed.stderr


def test_p6o33_incremental_analysis_rejects_unpaired_case_sets(
    tmp_path: Path,
) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    payload = _p6o33_incremental_payload(
        replace_answer_rate=50.0,
        guided_answer_rate=75.0,
        retry_shadow_answer_rate=100.0,
    )
    for row in payload["cases"]:
        if row["mode"] == "safe_version_replace_guided_with_retry_shadow":
            row["case_id"] = f"other-{row['case_index']}"
            break
    report_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/analyze_memory_p6o33_incremental_eval.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(tmp_path / "analysis"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "paired mode case sets must match" in completed.stderr


def test_system_path_safe_version_run_metadata_records_git_and_config_hash(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[agent]\nsystem_prompt = 'x'\n", encoding="utf-8")

    import scripts.run_memory_system_path_safe_version_eval as cli

    args = SimpleNamespace(
        config=str(config),
        enable_real_llm=True,
        fake_provider=False,
        persona_mode="work",
        modes="safe_version_replace",
        repeats=1,
        case_pack="standard",
        balanced_small=True,
        common_limit=40,
        hard_limit=40,
        timeout_s=60.0,
    )

    metadata = cli._build_run_metadata(args, model="test-model")

    assert metadata["git_commit"]
    assert len(str(metadata["git_commit"])) == 40
    assert metadata["config_hash"]
    assert len(str(metadata["config_hash"])) == 64


def test_p6o19_gate_rejects_infra_and_checkpoint_abnormalities(
    tmp_path: Path,
) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    payload = _p6o19_gate_payload(
        replace_answer_rate=50.0,
        guided_answer_rate=75.0,
        retry_shadow_answer_rate=100.0,
    )
    payload["metrics"]["provider_error_count"] = 1
    payload["metrics"]["malformed_checkpoint_line_count"] = 1
    report_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_memory_p6o19_gate.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(tmp_path / "gate"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "provider_error_count must be 0" in completed.stderr


def test_p6o20_detail_export_writes_per_case_scoring_and_movement(
    tmp_path: Path,
) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    out_dir = tmp_path / "details"
    payload = _p6o19_gate_payload(
        replace_answer_rate=50.0,
        guided_answer_rate=0.0,
        retry_shadow_answer_rate=100.0,
    )
    for row in payload["cases"]:
        row["case_id"] = "case-shared"
        row["category"] = "hard"
        row["repeat_index"] = 0
        row["expected_contains_pass_count"] = 1 if row["answer_rule_passed"] else 0
        row["expected_contains_miss_count"] = 0 if row["answer_rule_passed"] else 1
        row["expected_any_pass_count"] = 1 if row["answer_rule_passed"] else 0
        row["expected_any_miss_count"] = 0 if row["answer_rule_passed"] else 1
        row["language_passed"] = True
        row["failures"] = (
            [] if row["answer_rule_passed"] else ["missing_expected_answer_term"]
        )
        row["latency_ms"] = 10
        row["token_count"] = 30

    report_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/export_memory_p6o20_answer_details.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(out_dir),
            "--anchor-mode",
            "safe_version_replace_guided",
            "--comparison-mode",
            "safe_version_replace_guided_with_retry_shadow",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    rows = [
        json.loads(line)
        for line in (out_dir / "per_case_scoring_rows.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    movement = json.loads(
        (out_dir / "case_movement_vs_guided.json").read_text(encoding="utf-8")
    )
    summary = json.loads((out_dir / "export_summary.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "case_movement_vs_guided.md").read_text(encoding="utf-8")

    assert rows
    assert {
        "case_id",
        "mode",
        "answer_rule_passed",
        "expected_contains_miss_count",
        "expected_any_miss_count",
        "language_passed",
        "failures",
        "post_check_needs_retry",
        "post_check_retry_reasons",
    } <= set(rows[0])
    assert "raw_prompt" not in str(rows)
    assert "raw_answer" not in str(rows)
    assert isinstance(rows[0]["failures"], list)
    assert isinstance(rows[0]["post_check_retry_reasons"], list)
    assert "allowed_evidence_ids" in rows[0]
    assert "version_boundary_replacement_count" in rows[0]
    assert movement["movement_counts"]["anchor_failed_comparison_passed"] == 1
    assert summary["forbidden_key_scan_passed"] is True
    assert summary["paired_case_count"] == 1
    assert (
        "| case_id | category | repeat | anchor_passed | comparison_passed | "
        "movement |"
    ) in markdown


def test_system_path_safe_version_cli_rejects_fake_and_real_flags(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--enable-real-llm",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert (
        "--fake-provider and --enable-real-llm cannot be used together"
        in completed.stderr
    )


def test_system_path_safe_version_cli_repeats_shape_and_indices(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--modes",
            "current,safe_version_replace",
            "--repeats",
            "3",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    metrics = payload["metrics"]
    assert metrics["unique_case_count"] == 4
    assert metrics["mode_count"] == 2
    assert metrics["repeat_count"] == 3
    assert metrics["case_count"] == 24
    assert sorted({row["repeat_index"] for row in payload["cases"]}) == [0, 1, 2]
    assert sorted(metrics["repeat_summaries"]) == ["0", "1", "2"]
    for summary in metrics["repeat_summaries"].values():
        assert summary["case_count"] == 8
        assert "mode_summaries" in summary
        assert summary["mode_summaries"]["current"]["case_count"] == 4
        assert summary["mode_summaries"]["safe_version_replace"]["case_count"] == 4


def test_system_path_safe_version_cli_rejects_invalid_repeats(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--repeats",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "repeats must be at least 1" in completed.stderr


def test_system_path_safe_version_cli_rejects_invalid_infra_abort_args(
    tmp_path: Path,
) -> None:
    bad_count = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace-count"),
            "--out-dir",
            str(tmp_path / "reports-count"),
            "--fake-provider",
            "--early-infra-abort-count",
            "-1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    bad_rate = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace-rate"),
            "--out-dir",
            str(tmp_path / "reports-rate"),
            "--fake-provider",
            "--early-infra-abort-rate",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert bad_count.returncode != 0
    assert "--early-infra-abort-count must be >= 0" in bad_count.stderr
    assert bad_rate.returncode != 0
    assert "--early-infra-abort-rate must be > 0.0 and <= 1.0" in bad_rate.stderr


def test_system_path_blocked_status_marks_quality_interpretation_disallowed() -> None:
    from memory2.eval_system_path_safe_version import (
        SystemPathSafeVersionReport,
        build_system_path_blocked_status,
        system_path_report_infra_failure_rate,
    )

    report = SystemPathSafeVersionReport(
        cases=(
            {
                "case_id": "case-a",
                "mode": "safe_version_replace",
                "timeout": True,
                "provider_error": False,
                "answer_rule_passed": False,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "latency_ms": 1000,
                "token_count": 0,
                "replacement_seeded_count": 1,
                "safe_version_contract": {},
            },
        ),
        metrics={
            "evaluation_level": "system_path_safe_version_governed",
            "unique_case_count": 1,
            "mode_count": 1,
            "case_count": 1,
            "repeat_count": 1,
            "provider_error_count": 0,
            "timeout_count": 1,
            "malformed_checkpoint_line_count": 0,
            "checkpoint_input_count": 0,
            "real_llm_enabled": True,
            "fake_provider_enabled": False,
            "raw_query_included": False,
            "raw_memory_summary_included": False,
            "prompt_included": False,
            "conversation_log_included": False,
            "complete_response_included": False,
        },
    )

    status = build_system_path_blocked_status(
        report,
        reason="early infra failure rate 100.0% met or exceeded 50.0%",
        checkpoint_jsonl=Path("checkpoint.jsonl"),
    )

    assert status["status"] == "infra_blocked"
    assert status["quality_interpretation_allowed"] is False
    assert status["reason"] == "early infra failure rate 100.0% met or exceeded 50.0%"
    assert status["case_count"] == 1
    assert status["timeout_count"] == 1
    assert status["provider_error_count"] == 0
    assert status["checkpoint_jsonl"] == "checkpoint.jsonl"
    assert system_path_report_infra_failure_rate(report) == 1.0


def test_system_path_eval_aborts_when_early_fresh_rows_are_all_timeouts(
    tmp_path: Path,
) -> None:
    from agent.provider import LLMResponse
    from memory2.eval_system_path_safe_version import (
        SystemPathInfraAbort,
        run_system_path_safe_version_cases,
    )

    class SlowProvider:
        async def chat(self, **kwargs: object) -> LLMResponse:
            await asyncio.sleep(1)
            return LLMResponse(content="too late", tool_calls=[])

    cases = build_quantitative_eval_cases("all", case_pack="standard", limit=2)
    checkpoint_jsonl = tmp_path / "checkpoint.jsonl"

    try:
        asyncio.run(
            run_system_path_safe_version_cases(
                cases,
                tmp_path / "workspace",
                SlowProvider(),
                modes=("safe_version_replace",),
                model="slow-model",
                timeout_s=0.001,
                real_llm_enabled=True,
                checkpoint_jsonl=checkpoint_jsonl,
                early_infra_abort_count=2,
                early_infra_abort_rate=0.5,
            )
        )
    except SystemPathInfraAbort as exc:
        assert exc.fresh_case_count == 2
        assert exc.fresh_timeout_count == 2
        assert exc.fresh_provider_error_count == 0
        assert exc.report.metrics["case_count"] == 2
        assert exc.report.metrics["timeout_count"] == 2
        assert "early infra failure rate 100.0% met or exceeded 50.0%" in exc.reason
    else:
        raise AssertionError("expected SystemPathInfraAbort")

    assert checkpoint_jsonl.exists()
    assert len(checkpoint_jsonl.read_text(encoding="utf-8").splitlines()) == 2


def test_system_path_eval_can_render_work_persona(
    tmp_path: Path,
) -> None:
    from agent.provider import LLMResponse
    from memory2.eval_system_path_safe_version import (
        run_system_path_safe_version_cases,
    )

    class CapturingProvider:
        def __init__(self) -> None:
            self.messages: list[list[dict[str, object]]] = []

        async def chat(self, **kwargs: object) -> LLMResponse:
            self.messages.append(list(kwargs["messages"]))  # type: ignore[index]
            return LLMResponse(
                content="旧方案回滚要沿版本链使用当前叶子和回滚候选。",
                tool_calls=[],
            )

    provider = CapturingProvider()
    cases = build_quantitative_eval_cases("all", case_pack="standard", limit=1)

    asyncio.run(
        run_system_path_safe_version_cases(
            cases,
            tmp_path / "workspace",
            provider,
            modes=("safe_version_replace_guided_with_retry_shadow",),
            model="capture-model",
            persona_mode="work",
        )
    )

    rendered = "\n".join(
        str(message.get("content") or "")
        for message in provider.messages[0]
        if message.get("role") == "system"
    )
    assert "## 工作模式" in rendered
    assert "任务正确性优先" in rendered
    assert "先接住，再展开" not in rendered


def test_system_path_eval_aborts_when_two_of_three_early_rows_are_infra_failures(
    tmp_path: Path,
) -> None:
    from agent.provider import LLMResponse
    from memory2.eval_system_path_safe_version import (
        SystemPathInfraAbort,
        run_system_path_safe_version_cases,
    )

    class MostlySlowProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def chat(self, **kwargs: object) -> LLMResponse:
            self.calls += 1
            if self.calls <= 2:
                await asyncio.sleep(1)
            return LLMResponse(content="根据系统路径注入记忆回答。", tool_calls=[])

    cases = build_quantitative_eval_cases("all", case_pack="standard", limit=3)

    try:
        asyncio.run(
            run_system_path_safe_version_cases(
                cases,
                tmp_path / "workspace",
                MostlySlowProvider(),
                modes=("safe_version_replace",),
                model="mostly-slow-model",
                timeout_s=0.001,
                real_llm_enabled=True,
                early_infra_abort_count=3,
                early_infra_abort_rate=0.5,
            )
        )
    except SystemPathInfraAbort as exc:
        assert exc.fresh_case_count == 3
        assert exc.fresh_timeout_count == 2
        assert exc.report.metrics["case_count"] == 3
        assert exc.report.metrics["timeout_count"] == 2
        assert "66.6667% met or exceeded 50.0%" in exc.reason
    else:
        raise AssertionError("expected SystemPathInfraAbort")


def test_system_path_safe_version_cli_writes_blocked_status_on_early_abort(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    checkpoint_jsonl = tmp_path / "checkpoint.jsonl"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--limit",
            "2",
            "--modes",
            "safe_version_replace",
            "--timeout-s",
            "0.001",
            "--fake-provider-delay-s",
            "0.05",
            "--checkpoint-jsonl",
            str(checkpoint_jsonl),
            "--early-infra-abort-count",
            "1",
            "--early-infra-abort-rate",
            "1.0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    blocked = json.loads((out_dir / "blocked_status.json").read_text(encoding="utf-8"))
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    markdown = (out_dir / "system_path_safe_version_eval.md").read_text(
        encoding="utf-8"
    )
    assert blocked["status"] == "infra_blocked"
    assert blocked["quality_interpretation_allowed"] is False
    assert blocked["timeout_count"] == 1
    assert blocked["case_count"] == payload["metrics"]["case_count"]
    assert blocked["fresh_case_count"] == 1
    assert blocked["fresh_timeout_count"] == 1
    assert "early infra failure rate" in blocked["reason"]
    assert "raw_prompt" not in markdown


def test_system_path_safe_version_checkpoint_resume_skips_successes(
    tmp_path: Path,
) -> None:
    from memory2.eval_system_path_safe_version import (
        build_system_path_safe_version_report_from_checkpoint,
        run_system_path_safe_version_cases,
    )
    from scripts.run_memory_system_path_safe_version_eval import (
        ScriptedSystemPathProvider,
    )

    cases = build_quantitative_eval_cases(
        "common",
        case_pack="standard",
        limit=1,
    )
    checkpoint = tmp_path / "checkpoint.jsonl"
    provider = ScriptedSystemPathProvider()

    first = asyncio.run(
        run_system_path_safe_version_cases(
            cases,
            tmp_path / "workspace-first",
            provider,
            modes=("current", "safe_version_replace"),
            checkpoint_jsonl=checkpoint,
            repeats=1,
        )
    )
    assert first.metrics["case_count"] == 2
    assert first.metrics["skipped_from_checkpoint_count"] == 0

    original_call_count = len(provider.calls)
    resumed = asyncio.run(
        run_system_path_safe_version_cases(
            cases,
            tmp_path / "workspace-resume",
            provider,
            modes=("current", "safe_version_replace"),
            checkpoint_jsonl=checkpoint,
            resume=True,
            repeats=1,
        )
    )
    assert resumed.metrics["case_count"] == 2
    assert resumed.metrics["skipped_from_checkpoint_count"] == 2
    assert len(provider.calls) == original_call_count

    rebuilt = build_system_path_safe_version_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=False,
    )
    assert rebuilt.metrics["checkpoint_input_count"] == 2
    assert rebuilt.metrics["case_count"] == 2


def _checkpoint_record(
    *,
    case_id: str,
    mode: str,
    repeat_index: int = 0,
    answer: bool = True,
    grounding: bool = True,
    forbidden_count: int = 0,
    provider_error: bool = False,
    timeout: bool = False,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "case_index": 0,
        "repeat_index": repeat_index,
        "category": "common",
        "mode": mode,
        "passed": answer and not provider_error and not timeout,
        "answer_rule_passed": answer,
        "memory_grounding_passed": grounding,
        "expected_memory_used": grounding,
        "forbidden_contains_violation_count": forbidden_count,
        "answer_length": 24,
        "expected_contains_pass_count": 1 if answer else 0,
        "expected_contains_miss_count": 0 if answer else 1,
        "expected_any_pass_count": 0,
        "expected_any_miss_count": 0,
        "language_passed": True,
        "failures": ["provider_error"] if provider_error else [],
        "provider_error": provider_error,
        "timeout": timeout,
        "latency_ms": 10,
        "token_count": 30,
        "prompt_token_count": 20,
        "completion_token_count": 10,
        "token_metrics_available": True,
        "replacement_seeded_count": 0,
        "safe_version_metadata": {},
        "safe_version_contract": {},
        "post_check_shadow": {"shadow_enabled": False},
    }


def test_system_path_safe_version_checkpoint_report_only_includes_infra_rows(
    tmp_path: Path,
) -> None:
    from memory2.eval_system_path_safe_version import (
        build_system_path_safe_version_report_from_checkpoint,
    )

    checkpoint = tmp_path / "checkpoint.jsonl"
    rows = [
        {
            "spec_key": "case-a|current|0",
            "result": _checkpoint_record(case_id="case-a", mode="current"),
        },
        {
            "spec_key": "case-b|current|0",
            "result": _checkpoint_record(
                case_id="case-b",
                mode="current",
                answer=False,
                provider_error=True,
            ),
        },
        {
            "spec_key": "case-c|safe_version_replace|0",
            "result": _checkpoint_record(
                case_id="case-c",
                mode="safe_version_replace",
                answer=False,
                timeout=True,
            ),
        },
    ]
    checkpoint.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = build_system_path_safe_version_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=True,
    )

    assert report.metrics["checkpoint_input_count"] == 3
    assert report.metrics["malformed_checkpoint_line_count"] == 0
    assert report.metrics["case_count"] == 3
    assert report.metrics["provider_error_count"] == 1
    assert report.metrics["timeout_count"] == 1


def test_system_path_safe_version_cli_report_only_marks_timeout_checkpoint_blocked(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    checkpoint_jsonl = tmp_path / "checkpoint.jsonl"
    record = _checkpoint_record(
        case_id="case-timeout",
        mode="safe_version_replace",
        answer=False,
        timeout=True,
    )
    checkpoint_jsonl.write_text(
        json.dumps(
            {
                "spec_key": "case-timeout|safe_version_replace|0",
                "result": record,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--out-dir",
            str(out_dir),
            "--enable-real-llm",
            "--checkpoint-jsonl",
            str(checkpoint_jsonl),
            "--checkpoint-report-only",
            "--early-infra-abort-count",
            "1",
            "--early-infra-abort-rate",
            "1.0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    blocked = json.loads((out_dir / "blocked_status.json").read_text(encoding="utf-8"))
    assert blocked["status"] == "infra_blocked"
    assert blocked["quality_interpretation_allowed"] is False
    assert blocked["case_count"] == 1
    assert blocked["timeout_count"] == 1
    assert (
        "checkpoint infra failure rate 100.0% met or exceeded 100.0%"
        in blocked["reason"]
    )


def test_system_path_safe_version_checkpoint_loader_tolerates_malformed_tail(
    tmp_path: Path,
) -> None:
    from memory2.eval_system_path_safe_version import (
        build_system_path_safe_version_report_from_checkpoint,
        run_system_path_safe_version_cases,
    )
    from scripts.run_memory_system_path_safe_version_eval import (
        ScriptedSystemPathProvider,
    )

    cases = build_quantitative_eval_cases(
        "common",
        case_pack="standard",
        limit=1,
    )
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "spec_key": f"{cases[0].id}|current|0",
                        "result": _checkpoint_record(
                            case_id=cases[0].id,
                            mode="current",
                            answer=False,
                            provider_error=True,
                        ),
                    },
                    ensure_ascii=False,
                ),
                '{"spec_key": "partial"',
            ]
        ),
        encoding="utf-8",
    )

    provider = ScriptedSystemPathProvider()
    report = asyncio.run(
        run_system_path_safe_version_cases(
            cases,
            tmp_path / "workspace",
            provider,
            modes=("current", "safe_version_replace"),
            checkpoint_jsonl=checkpoint,
            resume=True,
            repeats=1,
        )
    )

    assert report.metrics["malformed_checkpoint_line_count"] == 1
    assert report.metrics["skipped_from_checkpoint_count"] == 0
    assert len(provider.calls) == 2

    rebuilt = build_system_path_safe_version_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=False,
    )
    assert rebuilt.metrics["checkpoint_input_count"] == 4
    assert rebuilt.metrics["malformed_checkpoint_line_count"] == 1
    assert rebuilt.metrics["case_count"] == 2


def test_system_path_safe_version_fake_provider_rows_are_answer_scored(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--modes",
            "current,safe_version_replace",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(
            encoding="utf-8"
        )
    )
    metrics = payload["metrics"]
    assert metrics["fake_provider_enabled"] is True
    assert metrics["real_llm_enabled"] is False
    assert "answer_rule_pass_rate" in metrics
    assert "memory_grounding_pass_rate" in metrics
    assert "forbidden_violation_rate" in metrics
    assert "token_metrics_available" in metrics
    for row in payload["cases"]:
        assert "answer_rule_passed" in row
        assert "memory_grounding_passed" in row
        assert "expected_memory_used" in row
        assert "forbidden_contains_violation_count" in row
        assert "failures" in row
        assert "answer_passed" not in row


def test_system_path_safe_version_rows_include_sanitized_scoring_counts(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "1",
            "--hard-limit",
            "1",
            "--modes",
            "current,safe_version_replace",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    for row in payload["cases"]:
        assert "answer_length" in row
        assert "expected_contains_pass_count" in row
        assert "expected_contains_miss_count" in row
        assert "expected_any_pass_count" in row
        assert "expected_any_miss_count" in row
        assert "language_passed" in row
        assert not isinstance(row.get("matched_expected_terms"), list)
        assert not isinstance(row.get("missing_expected_terms"), list)


def test_system_path_safe_version_real_provider_builder_requires_api_key(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    import scripts.run_memory_system_path_safe_version_eval as cli

    args = SimpleNamespace(
        fake_provider=False,
        enable_real_llm=True,
        config=str(tmp_path / "config.toml"),
        timeout_s=60.0,
    )
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: SimpleNamespace(
            api_key="",
            model="real-model",
            base_url="https://example.invalid",
            system_prompt="",
            extra_body={},
            provider="test-provider",
        ),
    )

    provider, model = cli.build_provider_for_system_path_safe_version(args)

    assert provider is None
    assert model == "real-model"


def test_system_path_safe_version_real_provider_builder_uses_config(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    import scripts.run_memory_system_path_safe_version_eval as cli

    created: dict[str, object] = {}

    class FakeRealProvider:
        def __init__(self, **kwargs: object) -> None:
            created.update(kwargs)

    args = SimpleNamespace(
        fake_provider=False,
        enable_real_llm=True,
        config=str(tmp_path / "config.toml"),
        timeout_s=12.5,
    )
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: SimpleNamespace(
            api_key="secret-key",
            model="real-model",
            base_url="https://example.invalid",
            system_prompt="system",
            extra_body={"x": 1},
            provider="test-provider",
        ),
    )
    monkeypatch.setattr(cli.agent_provider, "LLMProvider", FakeRealProvider)

    provider, model = cli.build_provider_for_system_path_safe_version(args)

    assert isinstance(provider, FakeRealProvider)
    assert model == "real-model"
    assert created["api_key"] == "secret-key"
    assert created["request_timeout_s"] == 12.5
    assert created["provider_name"] == "test-provider"
