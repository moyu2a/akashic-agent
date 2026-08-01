from __future__ import annotations

import argparse
import json
from collections import Counter
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
    parser.add_argument("--target-answer-rate", type=float, default=80.0)
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    analysis = build_p6o33_analysis(
        payload,
        target_answer_rate=float(args.target_answer_rate),
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "p6o33_incremental_analysis.json"
    md_path = out_dir / "p6o33_incremental_analysis.md"
    json_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_p6o33_markdown(analysis), encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0


def build_p6o33_analysis(
    payload: dict[str, Any],
    *,
    target_answer_rate: float = 80.0,
) -> dict[str, Any]:
    metrics = dict(payload.get("metrics") or {})
    rows = [dict(row) for row in list(payload.get("cases") or [])]
    summaries = {
        str(mode): dict(summary)
        for mode, summary in dict(metrics.get("mode_summaries") or {}).items()
    }

    _require(rows, "report must include case rows")
    _require(
        len(rows) == int(metrics.get("case_count", 0) or 0),
        "report case rows must match metrics case_count",
    )
    _require(
        set(summaries) == set(EXPECTED_MODES),
        "mode set must match P6o33 expected modes",
    )
    _require(
        int(metrics.get("mode_count", 0) or 0) == len(EXPECTED_MODES),
        "mode_count must be 3",
    )
    _require(
        bool(metrics.get("real_llm_enabled")) is True,
        "real_llm_enabled must be true",
    )
    _require(
        bool(metrics.get("fake_provider_enabled")) is False,
        "fake_provider_enabled must be false",
    )
    _require(
        int(metrics.get("provider_error_count", 0) or 0) == 0,
        "provider_error_count must be 0",
    )
    _require(int(metrics.get("timeout_count", 0) or 0) == 0, "timeout_count must be 0")
    _require(
        int(metrics.get("malformed_checkpoint_line_count", 0) or 0) == 0,
        "malformed_checkpoint_line_count must be 0",
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
    _require(
        int(metrics.get("unique_case_count", 0) or 0) == next(iter(case_counts.values())),
        "unique_case_count must match per-mode row count",
    )

    _validate_rows(rows, case_counts)
    _validate_pairable_case_sets(rows, int(metrics.get("unique_case_count", 0) or 0))
    _require(
        all(
            float(summaries[mode].get("memory_grounding_pass_rate", 0.0) or 0.0)
            == 100.0
            for mode in EXPECTED_MODES
        ),
        "grounding must remain 100%",
    )
    _require(
        all(
            float(summaries[mode].get("forbidden_violation_rate", 0.0) or 0.0)
            == 0.0
            for mode in EXPECTED_MODES
        ),
        "forbidden violation must remain 0%",
    )
    _require(
        float(
            summaries["safe_version_replace_guided_with_retry_shadow"].get(
                "answer_candidate_contract_enabled_rate",
                0.0,
            )
            or 0.0
        )
        == 100.0,
        "retry-shadow answer candidate contract must be enabled for every row",
    )

    replace_rate = _answer_rate(summaries, "safe_version_replace")
    guided_rate = _answer_rate(summaries, "safe_version_replace_guided")
    retry_shadow_rate = _answer_rate(
        summaries,
        "safe_version_replace_guided_with_retry_shadow",
    )
    delta_a_to_b = round(guided_rate - replace_rate, 4)
    delta_b_to_c = round(retry_shadow_rate - guided_rate, 4)
    target_reached = retry_shadow_rate >= float(target_answer_rate)
    paired = {
        "a_to_b": _paired_comparison(
            rows,
            "safe_version_replace",
            "safe_version_replace_guided",
        ),
        "b_to_c": _paired_comparison(
            rows,
            "safe_version_replace_guided",
            "safe_version_replace_guided_with_retry_shadow",
        ),
    }
    gate_passed = (
        target_reached
        and (delta_b_to_c >= 5.0 or paired["b_to_c"]["wins"] > paired["b_to_c"]["losses"])
    )

    analysis = {
        "gate_passed": gate_passed,
        "target_reached": target_reached,
        "target_answer_rate": float(target_answer_rate),
        "case_count": metrics.get("case_count"),
        "unique_case_count": metrics.get("unique_case_count"),
        "mode_count": metrics.get("mode_count"),
        "repeat_count": metrics.get("repeat_count"),
        "real_llm_enabled": bool(metrics.get("real_llm_enabled")),
        "fake_provider_enabled": bool(metrics.get("fake_provider_enabled")),
        "provider_error_count": int(metrics.get("provider_error_count", 0) or 0),
        "timeout_count": int(metrics.get("timeout_count", 0) or 0),
        "checkpoint_input_count": int(metrics.get("checkpoint_input_count", 0) or 0),
        "malformed_checkpoint_line_count": int(
            metrics.get("malformed_checkpoint_line_count", 0) or 0
        ),
        "answer_delta_a_to_b_pp": delta_a_to_b,
        "answer_delta_b_to_c_pp": delta_b_to_c,
        "paired_comparison": paired,
        "mode_summaries": summaries,
        "category_summaries": _category_summaries(rows),
        "failure_reason_counts": _failure_reason_counts(rows),
        "failed_cases": _failed_cases(rows),
        "retry_shadow_reason_counts": dict(
            summaries["safe_version_replace_guided_with_retry_shadow"].get(
                "retry_reason_counts"
            )
            or {}
        ),
    }
    return analysis


def _validate_rows(rows: list[dict[str, Any]], case_counts: dict[str, int]) -> None:
    row_mode_counts = {mode: 0 for mode in EXPECTED_MODES}
    variant_mismatches: list[str] = []
    unsafe_candidate_rows: list[str] = []
    for row in rows:
        mode = str(row.get("mode") or "")
        _require(mode in row_mode_counts, f"unexpected row mode: {mode}")
        row_mode_counts[mode] += 1
        contract = dict(row.get("safe_version_contract") or {})
        actual_variant = contract.get("answer_prompt_variant")
        if actual_variant != EXPECTED_VARIANTS[mode]:
            variant_mismatches.append(f"{row.get('case_id')}:{mode}:{actual_variant}")
        candidate = dict(contract.get("answer_candidate_contract") or {})
        if mode == "safe_version_replace_guided_with_retry_shadow":
            if candidate.get("enabled") is not True:
                variant_mismatches.append(f"{row.get('case_id')}:{mode}:candidate_off")
            if "current_truth_lines" in candidate or "must_include_terms" in candidate:
                unsafe_candidate_rows.append(str(row.get("case_id") or "unknown"))
    _require(row_mode_counts == case_counts, "case rows must match mode summary counts")
    _require(
        not variant_mismatches,
        "every row must carry expected prompt variant metadata",
    )
    _require(
        not unsafe_candidate_rows,
        "answer_candidate_contract report fields must be sanitized",
    )


def _validate_pairable_case_sets(
    rows: list[dict[str, Any]],
    expected_unique_case_count: int,
) -> None:
    keys_by_mode = {
        mode: {
            _case_key(row)
            for row in rows
            if row.get("mode") == mode
        }
        for mode in EXPECTED_MODES
    }
    for mode, keys in keys_by_mode.items():
        _require(
            len(keys) == expected_unique_case_count,
            f"{mode} unique paired case count must match unique_case_count",
        )
    first_keys = keys_by_mode[EXPECTED_MODES[0]]
    _require(
        all(keys == first_keys for keys in keys_by_mode.values()),
        "paired mode case sets must match",
    )


def _answer_rate(summaries: dict[str, dict[str, Any]], mode: str) -> float:
    return float(summaries[mode].get("answer_rule_pass_rate", 0.0) or 0.0)


def _paired_comparison(
    rows: list[dict[str, Any]],
    left_mode: str,
    right_mode: str,
) -> dict[str, int]:
    left = {
        _case_key(row): bool(row.get("answer_rule_passed"))
        for row in rows
        if row.get("mode") == left_mode
    }
    right = {
        _case_key(row): bool(row.get("answer_rule_passed"))
        for row in rows
        if row.get("mode") == right_mode
    }
    keys = sorted(set(left) & set(right))
    wins = sum(1 for key in keys if not left[key] and right[key])
    losses = sum(1 for key in keys if left[key] and not right[key])
    ties = sum(1 for key in keys if left[key] == right[key])
    return {"wins": wins, "losses": losses, "ties": ties, "paired_cases": len(keys)}


def _case_key(row: dict[str, Any]) -> tuple[int, str]:
    return (
        int(row.get("repeat_index", 0) or 0),
        str(row.get("case_id") or row.get("case_index") or ""),
    )


def _category_summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    categories = sorted({str(row.get("category") or "unknown") for row in rows})
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for category in categories:
        result[category] = {}
        for mode in EXPECTED_MODES:
            selected = [
                row
                for row in rows
                if row.get("mode") == mode and str(row.get("category") or "unknown") == category
            ]
            result[category][mode] = {
                "case_count": len(selected),
                "answer_success_count": sum(
                    1 for row in selected if bool(row.get("answer_rule_passed"))
                ),
                "answer_rule_pass_rate": _pct(
                    sum(1 for row in selected if bool(row.get("answer_rule_passed"))),
                    len(selected),
                ),
                "failure_count": sum(
                    1 for row in selected if not bool(row.get("answer_rule_passed"))
                ),
            }
    return result


def _failure_reason_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for mode in EXPECTED_MODES:
        counter: Counter[str] = Counter()
        for row in rows:
            if row.get("mode") != mode:
                continue
            for failure in list(row.get("failures") or []):
                counter[str(failure)] += 1
        result[mode] = dict(sorted(counter.items()))
    return result


def _failed_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        if bool(row.get("answer_rule_passed")) and not row.get("failures"):
            continue
        failures.append(
            {
                "case_id": row.get("case_id"),
                "case_index": row.get("case_index"),
                "repeat_index": row.get("repeat_index"),
                "category": row.get("category"),
                "mode": row.get("mode"),
                "failures": list(row.get("failures") or []),
                "post_check_shadow": dict(row.get("post_check_shadow") or {}),
            }
        )
    return failures


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator * 100.0 / denominator, 4)


def render_p6o33_markdown(analysis: dict[str, Any]) -> str:
    summaries = dict(analysis["mode_summaries"])
    lines = [
        "# P6o33 Contract Incremental Medium Real Eval",
        "",
        "## Method",
        "",
        "- A: `safe_version_replace` = Evidence Contract.",
        "- B: `safe_version_replace_guided` = A + Answer Guidance.",
        "- C: `safe_version_replace_guided_with_retry_shadow` = B + Answer Candidate Contract.",
        "- retry shadow 不是真实 retry；本实验不执行第二次 LLM 调用。",
        "",
        "## Results",
        "",
        "| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | candidate_contract | would_retry | retry_reasons | avg_tokens | avg_latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for mode in EXPECTED_MODES:
        summary = summaries[mode]
        lines.append(
            f"| {mode} | {summary['case_count']} | {summary['answer_success_count']} | "
            f"{summary['answer_rule_pass_rate']} | {summary['memory_grounding_pass_rate']} | "
            f"{summary['forbidden_violation_rate']} | "
            f"{summary.get('answer_candidate_contract_enabled_rate', 0.0)} | "
            f"{summary.get('would_retry_count', 0)} | "
            f"`{json.dumps(summary.get('retry_reason_counts') or {}, ensure_ascii=False, sort_keys=True)}` | "
            f"{summary.get('avg_total_token_count', 0.0)} | {summary.get('avg_latency_ms', 0.0)} |"
        )
    paired = dict(analysis["paired_comparison"])
    lines.extend(
        [
            "",
            "## Incremental Effect",
            "",
            f"- A -> B answer delta: `{analysis['answer_delta_a_to_b_pp']}` pp.",
            f"- B -> C answer delta: `{analysis['answer_delta_b_to_c_pp']}` pp.",
            f"- B -> C paired: `{json.dumps(paired['b_to_c'], ensure_ascii=False, sort_keys=True)}`.",
            f"- target_reached: `{str(analysis['target_reached']).lower()}`.",
            f"- gate_passed: `{str(analysis['gate_passed']).lower()}`.",
            "",
            "## Failure Reasons",
            "",
            "```json",
            json.dumps(analysis["failure_reason_counts"], ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


if __name__ == "__main__":
    raise SystemExit(main())
