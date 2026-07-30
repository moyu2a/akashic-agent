from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_MODES = (
    "safe_version_replace",
    "safe_version_replace_guided",
    "safe_version_replace_guided_with_retry_shadow",
)

EXPECTED_VARIANTS = {
    "safe_version_replace": "standard",
    "safe_version_replace_guided": "guided",
    "safe_version_replace_guided_with_retry_shadow": "guided_retry_shadow",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    payload = _load_payload(Path(args.report_json))
    decision = _build_gate_decision(payload)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "p6o19_answer_candidate_retry_shadow_report.md").write_text(
        _render_report(decision),
        encoding="utf-8",
    )
    print(out_dir / "gate_decision.json")
    print(out_dir / "p6o19_answer_candidate_retry_shadow_report.md")
    return 0


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_gate_decision(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(payload["metrics"])
    rows = list(payload["cases"])
    summaries = {
        str(mode): dict(summary)
        for mode, summary in dict(metrics.get("mode_summaries") or {}).items()
    }

    _require(int(metrics.get("provider_error_count", 0) or 0) == 0, "provider_error_count must be 0")
    _require(int(metrics.get("timeout_count", 0) or 0) == 0, "timeout_count must be 0")
    _require(
        int(metrics.get("malformed_checkpoint_line_count", 0) or 0) == 0,
        "malformed_checkpoint_line_count must be 0",
    )
    _require(rows, "report must include case rows")
    _require(
        set(summaries) == set(EXPECTED_MODES),
        "mode set must match P6o-19 expected modes",
    )
    _require(
        int(metrics.get("mode_count", 0) or 0) == len(EXPECTED_MODES),
        "mode_count must be 3",
    )

    case_counts = {
        mode: int(summaries[mode].get("case_count", 0) or 0)
        for mode in EXPECTED_MODES
    }
    _require(all(count > 0 for count in case_counts.values()), "each mode must have rows")
    _require(
        len(set(case_counts.values())) == 1,
        "each mode must have the same number of rows",
    )
    _require(
        sum(case_counts.values()) == int(metrics.get("case_count", len(rows)) or 0),
        "summary case_count must match report case_count",
    )

    row_mode_counts = {mode: 0 for mode in EXPECTED_MODES}
    variant_mismatches: list[str] = []
    unsafe_candidate_rows: list[str] = []
    for row in rows:
        mode = str(row.get("mode") or "")
        if mode not in row_mode_counts:
            continue
        row_mode_counts[mode] += 1
        contract = dict(row.get("safe_version_contract") or {})
        actual_variant = contract.get("answer_prompt_variant")
        if actual_variant != EXPECTED_VARIANTS[mode]:
            variant_mismatches.append(mode)
        candidate = dict(contract.get("answer_candidate_contract") or {})
        if mode == "safe_version_replace_guided_with_retry_shadow":
            if candidate.get("enabled") is not True:
                variant_mismatches.append(mode)
            if "current_truth_lines" in candidate or "must_include_terms" in candidate:
                unsafe_candidate_rows.append(str(row.get("case_id") or "unknown"))
    _require(row_mode_counts == case_counts, "case rows must match mode summary counts")
    _require(not variant_mismatches, "every row must carry expected prompt variant metadata")
    _require(
        not unsafe_candidate_rows,
        "answer_candidate_contract report fields must be sanitized",
    )

    _require(
        all(
            float(summary.get("memory_grounding_pass_rate", 0.0) or 0.0) >= 100.0
            for summary in summaries.values()
        ),
        "grounding must remain 100%",
    )
    _require(
        all(
            float(summary.get("forbidden_violation_rate", 0.0) or 0.0) == 0.0
            for summary in summaries.values()
        ),
        "forbidden violation must remain 0%",
    )
    retry_summary = summaries["safe_version_replace_guided_with_retry_shadow"]
    _require(
        float(retry_summary.get("answer_candidate_contract_enabled_rate", 0.0) or 0.0)
        == 100.0,
        "retry-shadow answer candidate contract must be enabled for every row",
    )

    guided = summaries["safe_version_replace_guided"]
    retry_answer_rate = float(retry_summary.get("answer_rule_pass_rate", 0.0) or 0.0)
    guided_answer_rate = float(guided.get("answer_rule_pass_rate", 0.0) or 0.0)
    answer_delta = round(retry_answer_rate - guided_answer_rate, 4)
    gate_passed = answer_delta > 0.0

    return {
        "gate_passed": gate_passed,
        "case_count": metrics.get("case_count"),
        "unique_case_count": metrics.get("unique_case_count"),
        "mode_count": metrics.get("mode_count"),
        "repeat_count": metrics.get("repeat_count"),
        "provider_error_count": metrics.get("provider_error_count"),
        "timeout_count": metrics.get("timeout_count"),
        "checkpoint_input_count": metrics.get("checkpoint_input_count"),
        "malformed_checkpoint_line_count": metrics.get(
            "malformed_checkpoint_line_count"
        ),
        "real_llm_enabled": bool(metrics.get("real_llm_enabled")),
        "fake_provider_enabled": bool(metrics.get("fake_provider_enabled")),
        "guided_answer_rate": guided_answer_rate,
        "retry_shadow_answer_rate": retry_answer_rate,
        "answer_delta_vs_guided": answer_delta,
        "retry_shadow_would_retry_count": int(
            retry_summary.get("would_retry_count", 0) or 0
        ),
        "retry_shadow_reason_counts": dict(
            retry_summary.get("retry_reason_counts") or {}
        ),
        "mode_summaries": summaries,
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _render_report(decision: dict[str, Any]) -> str:
    summaries = dict(decision["mode_summaries"])
    lines = [
        "# P6o-19 Answer Candidate Retry Shadow",
        "",
        "## Method",
        "",
        "- Modes: `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_guided_with_retry_shadow`.",
        "- P6o-19 is eval-only shadow telemetry: it does not execute a real retry and does not change production defaults.",
        "- Reported answer-candidate fields are sanitized counts and reason labels only.",
        "",
        "## Infra",
        "",
        f"- case_count: `{decision['case_count']}`.",
        f"- unique_case_count: `{decision['unique_case_count']}`.",
        f"- mode_count: `{decision['mode_count']}`.",
        f"- repeat_count: `{decision['repeat_count']}`.",
        f"- provider_error_count: `{decision['provider_error_count']}`.",
        f"- timeout_count: `{decision['timeout_count']}`.",
        f"- checkpoint_input_count: `{decision['checkpoint_input_count']}`.",
        f"- malformed_checkpoint_line_count: `{decision['malformed_checkpoint_line_count']}`.",
        f"- real_llm_enabled: `{str(decision['real_llm_enabled']).lower()}`.",
        f"- fake_provider_enabled: `{str(decision['fake_provider_enabled']).lower()}`.",
        "",
        "## Results",
        "",
        "| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | candidate_contract | would_retry | retry_reasons | avg_tokens | avg_latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for mode in EXPECTED_MODES:
        summary = summaries[mode]
        lines.append(
            f"| `{mode}` | {summary['case_count']} | {summary['answer_success_count']} | "
            f"{summary['answer_rule_pass_rate']} | {summary['memory_grounding_pass_rate']} | "
            f"{summary['forbidden_violation_rate']} | "
            f"{summary.get('answer_candidate_contract_enabled_rate', 0.0)} | "
            f"{summary.get('would_retry_count', 0)} | "
            f"`{json.dumps(summary.get('retry_reason_counts') or {}, ensure_ascii=False, sort_keys=True)}` | "
            f"{summary.get('avg_total_token_count', 0.0)} | {summary.get('avg_latency_ms', 0.0)} |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            f"- guided_answer_rate: `{decision['guided_answer_rate']}`.",
            f"- retry_shadow_answer_rate: `{decision['retry_shadow_answer_rate']}`.",
            f"- answer_delta_vs_guided: `{decision['answer_delta_vs_guided']}`.",
            f"- retry_shadow_would_retry_count: `{decision['retry_shadow_would_retry_count']}`.",
            f"- retry_shadow_reason_counts: `{json.dumps(decision['retry_shadow_reason_counts'], ensure_ascii=False, sort_keys=True)}`.",
            f"- gate_passed: `{str(decision['gate_passed']).lower()}`.",
            "",
            "## Conclusion",
            "",
            (
                "P6o-19 passed: retry-shadow produced a same-run answer-rate lift over guided while preserving grounding and forbidden safety."
                if decision["gate_passed"]
                else "P6o-19 did not pass the quality gate: retry-shadow did not exceed guided in this report. Fake-provider runs should be interpreted as wiring and privacy checks only."
            ),
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
