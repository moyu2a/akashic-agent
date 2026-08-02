from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_VARIANTS = {
    "safe_version_replace": "standard",
    "safe_version_replace_guided": "guided",
    "safe_version_replace_structured_guided": "structured_guided",
    "safe_version_replace_near_query_block": "near_query_block",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-json", required=True)
    parser.add_argument("--rebuilt-json", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    primary = _load_payload(Path(args.primary_json))
    rebuilt = _load_payload(Path(args.rebuilt_json))
    decision = _build_gate_decision(primary, rebuilt)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "evidence_prompt_ab_report.md").write_text(
        _render_report(decision),
        encoding="utf-8",
    )
    print(out_dir / "gate_decision.json")
    print(out_dir / "evidence_prompt_ab_report.md")
    return 0


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_gate_decision(
    primary_payload: dict[str, Any],
    rebuilt_payload: dict[str, Any],
) -> dict[str, Any]:
    primary = primary_payload["metrics"]
    rebuilt = rebuilt_payload["metrics"]
    rows = list(primary_payload["cases"])
    _require(int(primary["case_count"]) == 160, "primary case_count must be 160")
    _require(int(primary["unique_case_count"]) == 40, "primary unique_case_count must be 40")
    _require(int(primary["mode_count"]) == 4, "primary mode_count must be 4")
    _require(int(primary["repeat_count"]) == 1, "primary repeat_count must be 1")
    _require(int(primary["provider_error_count"]) == 0, "primary provider_error_count must be 0")
    _require(int(primary["timeout_count"]) == 0, "primary timeout_count must be 0")
    _require(int(rebuilt["checkpoint_input_count"]) == 160, "rebuilt checkpoint_input_count must be 160")
    _require(
        int(rebuilt["malformed_checkpoint_line_count"]) == 0,
        "rebuilt malformed_checkpoint_line_count must be 0",
    )
    _require(int(rebuilt["case_count"]) == 160, "rebuilt case_count must be 160")
    _require(
        primary["mode_summaries"] == rebuilt["mode_summaries"],
        "primary and rebuilt mode_summaries must match",
    )
    _require(
        all(bool(row.get("token_metrics_available")) for row in rows),
        "every row must have token metrics",
    )
    summaries = dict(primary["mode_summaries"])
    _require(
        set(summaries) == set(EXPECTED_VARIANTS),
        "mode set must match P6o-18 expected variants",
    )
    _require(
        all(bool(summary.get("token_metrics_available")) for summary in summaries.values()),
        "every mode must have token metrics",
    )
    variant_mismatches = []
    for row in rows:
        mode = str(row.get("mode") or "")
        expected = EXPECTED_VARIANTS.get(mode)
        contract = dict(row.get("safe_version_contract") or {})
        metadata = dict(row.get("safe_version_metadata") or {})
        actual_contract = contract.get("answer_prompt_variant")
        actual_metadata = metadata.get("answer_prompt_variant")
        if actual_contract != expected or actual_metadata != expected:
            variant_mismatches.append(mode)
        expected_guidance = expected != "standard"
        if bool(contract.get("answer_guidance_enabled")) != expected_guidance:
            variant_mismatches.append(mode)
    _require(not variant_mismatches, "every row must carry expected variant metadata")

    replace = dict(summaries["safe_version_replace"])
    guided = dict(summaries["safe_version_replace_guided"])
    structured = dict(summaries["safe_version_replace_structured_guided"])
    near_query = dict(summaries["safe_version_replace_near_query_block"])
    _require(
        all(float(summary["memory_grounding_pass_rate"]) >= 100.0 for summary in summaries.values()),
        "grounding must remain 100%",
    )
    _require(
        all(float(summary["forbidden_violation_rate"]) == 0.0 for summary in summaries.values()),
        "forbidden violation must remain 0%",
    )

    new_variants = {
        "safe_version_replace_structured_guided": structured,
        "safe_version_replace_near_query_block": near_query,
    }
    best_new_mode = max(
        new_variants,
        key=lambda mode: float(new_variants[mode]["answer_rule_pass_rate"]),
    )
    best_new = new_variants[best_new_mode]
    token_limit = round(float(replace["avg_total_token_count"]) * 1.08, 4)
    gate_passed = (
        float(best_new["answer_rule_pass_rate"])
        > float(guided["answer_rule_pass_rate"])
        and float(best_new["avg_total_token_count"]) <= token_limit
    )
    return {
        "gate_passed": gate_passed,
        "case_count": primary["case_count"],
        "unique_case_count": primary["unique_case_count"],
        "mode_count": primary["mode_count"],
        "repeat_count": primary["repeat_count"],
        "provider_error_count": primary["provider_error_count"],
        "timeout_count": primary["timeout_count"],
        "checkpoint_input_count": rebuilt["checkpoint_input_count"],
        "malformed_checkpoint_line_count": rebuilt["malformed_checkpoint_line_count"],
        "best_new_mode": best_new_mode,
        "token_limit": token_limit,
        "mode_summaries": summaries,
        "answer_deltas_vs_guided": {
            mode: round(
                float(summary["answer_rule_pass_rate"])
                - float(guided["answer_rule_pass_rate"]),
                4,
            )
            for mode, summary in summaries.items()
            if mode != "safe_version_replace_guided"
        },
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _render_report(decision: dict[str, Any]) -> str:
    summaries = dict(decision["mode_summaries"])
    lines = [
        "# P6o-18 Evidence Prompt A/B",
        "",
        "## Method",
        "",
        "- Case pack: standard balanced small, common `20` + hard `20`.",
        "- Modes: `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_structured_guided`, `safe_version_replace_near_query_block`.",
        "- Repeats: `1`.",
        "- Real calls: `40` unique cases * `4` modes = `160`.",
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
        "",
        "## Results",
        "",
        "| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens | avg_latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in summaries.items():
        lines.append(
            f"| `{mode}` | {summary['case_count']} | {summary['answer_success_count']} | "
            f"{summary['answer_rule_pass_rate']} | {summary['memory_grounding_pass_rate']} | "
            f"{summary['forbidden_violation_rate']} | {summary['avg_total_token_count']} | "
            f"{summary['avg_latency_ms']} |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            f"- best_new_mode: `{decision['best_new_mode']}`.",
            f"- token_limit: `{decision['token_limit']}`.",
            f"- gate_passed: `{str(decision['gate_passed']).lower()}`.",
            "",
            "## Conclusion",
            "",
            (
                "P6o-18 passed: at least one new prompt variant exceeded `safe_version_replace_guided` while keeping grounding, forbidden, and token gates."
                if decision["gate_passed"]
                else "P6o-18 did not pass: neither new prompt variant produced a sufficient same-run lift over `safe_version_replace_guided` under the exploratory gate."
            ),
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
