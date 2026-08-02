from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


EXPECTED_MODES = (
    "safe_version_replace",
    "safe_version_replace_guided",
    "safe_version_replace_guided_with_retry_shadow",
)

FORBIDDEN_KEYS = {
    "raw_prompt",
    "full_answer",
    "raw_answer",
    "session_text",
    "Authorization",
    "api_key",
    "current_truth_lines",
    "must_include_terms",
}

SCALAR_FIELDS = (
    "case_id",
    "case_index",
    "repeat_index",
    "category",
    "mode",
    "passed",
    "answer_rule_passed",
    "memory_grounding_passed",
    "expected_memory_used",
    "forbidden_contains_violation_count",
    "answer_length",
    "expected_contains_pass_count",
    "expected_contains_miss_count",
    "expected_any_pass_count",
    "expected_any_miss_count",
    "language_passed",
    "provider_error",
    "timeout",
    "latency_ms",
    "token_count",
    "prompt_token_count",
    "completion_token_count",
    "token_metrics_available",
    "replacement_seeded_count",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--anchor-mode", default="safe_version_replace_guided")
    parser.add_argument(
        "--comparison-mode",
        default="safe_version_replace_guided_with_retry_shadow",
    )
    args = parser.parse_args(argv)

    source = Path(args.report_json)
    payload = json.loads(source.read_text(encoding="utf-8"))
    export = build_answer_detail_exports(
        payload,
        source_report_json=str(source),
        anchor_mode=args.anchor_mode,
        comparison_mode=args.comparison_mode,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = list(export["per_case_rows"])
    movement = dict(export["movement"])
    summary = dict(export["summary"])

    (out_dir / "per_case_scoring_rows.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    _write_csv(rows, out_dir / "per_case_scoring_rows.csv")
    (out_dir / "case_movement_vs_guided.json").write_text(
        json.dumps(movement, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "case_movement_vs_guided.md").write_text(
        render_movement_markdown(movement),
        encoding="utf-8",
    )
    (out_dir / "export_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _validate_no_forbidden_keys({"rows": rows, "movement": movement, "summary": summary})
    print(out_dir / "per_case_scoring_rows.jsonl")
    print(out_dir / "per_case_scoring_rows.csv")
    print(out_dir / "case_movement_vs_guided.json")
    print(out_dir / "case_movement_vs_guided.md")
    print(out_dir / "export_summary.json")
    return 0


def build_answer_detail_exports(
    payload: dict[str, Any],
    *,
    source_report_json: str = "",
    anchor_mode: str,
    comparison_mode: str,
) -> dict[str, Any]:
    _validate_no_forbidden_keys(payload)
    raw_rows = [dict(row) for row in payload.get("cases", [])]
    if not raw_rows:
        raise ValueError("report must include case rows")
    _validate_modes(raw_rows)
    rows = [_flatten_row(row) for row in raw_rows]
    movement = _build_movement(
        rows,
        anchor_mode=anchor_mode,
        comparison_mode=comparison_mode,
    )
    if movement["unpaired_case_count"]:
        raise ValueError("guided/retry-shadow movement has unpaired rows")
    summary = {
        "source_report_json": source_report_json,
        "total_rows": len(rows),
        "expected_modes": list(EXPECTED_MODES),
        "mode_row_counts": _mode_row_counts(rows),
        "paired_case_count": movement["paired_case_count"],
        "unpaired_case_count": movement["unpaired_case_count"],
        "movement_counts": dict(movement["movement_counts"]),
        "forbidden_key_scan_passed": True,
    }
    return {"per_case_rows": rows, "movement": movement, "summary": summary}


def render_movement_markdown(movement: dict[str, Any]) -> str:
    lines = [
        "# P6o-20 Case Movement vs Guided",
        "",
        f"- anchor_mode: `{movement['anchor_mode']}`",
        f"- comparison_mode: `{movement['comparison_mode']}`",
        f"- paired_case_count: `{movement['paired_case_count']}`",
        f"- unpaired_case_count: `{movement['unpaired_case_count']}`",
        "- movement_counts: `"
        + json.dumps(
            movement["movement_counts"],
            ensure_ascii=False,
            sort_keys=True,
        )
        + "`",
        "",
        "| case_id | category | repeat | anchor_passed | comparison_passed | movement | anchor_failures | comparison_failures | comparison_retry_reasons |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in movement["rows"]:
        lines.append(
            f"| `{_md_cell(row['case_id'])}` | `{_md_cell(row['category'])}` | "
            f"{row['repeat_index']} | {str(row['anchor_passed']).lower()} | "
            f"{str(row['comparison_passed']).lower()} | `{row['movement']}` | "
            f"`{_md_cell(row['anchor_failures'])}` | "
            f"`{_md_cell(row['comparison_failures'])}` | "
            f"`{_md_cell(row['comparison_retry_reasons'])}` |"
        )
    return "\n".join(lines) + "\n"


def _flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = _dict(row.get("safe_version_metadata"))
    contract = _dict(row.get("safe_version_contract"))
    post = _dict(row.get("post_check_shadow"))
    candidate = _dict(contract.get("answer_candidate_contract"))
    version_boundary = _dict(contract.get("version_boundary"))

    flat: dict[str, Any] = {field: row.get(field) for field in SCALAR_FIELDS}
    flat["failures"] = _string_list(row.get("failures"))
    flat["post_check_shadow_enabled"] = bool(post.get("shadow_enabled"))
    flat["post_check_needs_retry"] = bool(post.get("needs_retry"))
    flat["post_check_retry_reasons"] = _string_list(post.get("retry_reasons"))
    flat["post_check_required_terms_missing"] = bool(
        post.get("required_terms_missing")
    )
    flat["post_check_answer_choice_group_missing"] = bool(
        post.get("answer_choice_group_missing")
    )
    flat["post_check_language_requirement_failed"] = bool(
        post.get("language_requirement_failed")
    )

    flat["safe_version_contract_generation_success"] = bool(
        metadata.get("contract_generation_success")
    )
    flat["safe_version_replace_applied"] = bool(metadata.get("replace_applied"))
    flat["answer_prompt_variant"] = str(contract.get("answer_prompt_variant") or "")
    flat["allowed_evidence_ids"] = _string_list(contract.get("allowed_evidence_ids"))
    flat["likely_relevant_evidence_ids"] = _string_list(
        contract.get("likely_relevant_evidence_ids")
    )
    flat["downgrade_ids"] = _string_list(contract.get("downgrade_ids"))
    flat["requires_review_ids"] = _string_list(contract.get("requires_review_ids"))
    flat["stale_warning_ids"] = _string_list(contract.get("stale_warning_ids"))
    flat["conflict_warning_ids"] = _string_list(contract.get("conflict_warning_ids"))
    flat["active_version_ids"] = _string_list(contract.get("active_version_ids"))
    flat["forbidden_boundary_ids"] = _string_list(
        contract.get("forbidden_boundary_ids")
    )
    flat["deleted_evidence_ids"] = _string_list(contract.get("deleted_evidence_ids"))
    flat["candidate_risk_tier_counts"] = _dict(
        contract.get("candidate_risk_tier_counts")
    )
    flat["accepted_candidate_risk_tier_counts"] = _dict(
        contract.get("accepted_candidate_risk_tier_counts")
    )
    flat["tiered_deleted_risks_by_reason"] = _dict(
        contract.get("tiered_deleted_risks_by_reason")
    )
    for key, value in version_boundary.items():
        flat[f"version_boundary_{key}"] = value
    flat["version_boundary_replacement_count"] = int(
        version_boundary.get("replacement_count") or 0
    )

    flat["answer_candidate_contract_enabled"] = bool(candidate.get("enabled"))
    flat["answer_candidate_current_truth_count"] = int(
        candidate.get("current_truth_count") or 0
    )
    flat["answer_candidate_must_include_term_count"] = int(
        candidate.get("must_include_term_count") or 0
    )
    flat["answer_candidate_forbidden_old_value_count"] = int(
        candidate.get("forbidden_old_value_count") or 0
    )
    flat["answer_candidate_language_requirement"] = str(
        candidate.get("language_requirement") or ""
    )
    flat["answer_candidate_reason"] = str(candidate.get("candidate_reason") or "")
    return flat


def _build_movement(
    rows: list[dict[str, Any]],
    *,
    anchor_mode: str,
    comparison_mode: str,
) -> dict[str, Any]:
    by_key: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("case_id") or ""), int(row.get("repeat_index") or 0))
        by_key.setdefault(key, {})[str(row.get("mode") or "")] = row

    movement_rows: list[dict[str, Any]] = []
    unpaired_rows: list[dict[str, Any]] = []
    counts = {
        "both_passed": 0,
        "anchor_passed_comparison_failed": 0,
        "anchor_failed_comparison_passed": 0,
        "both_failed": 0,
    }
    for (case_id, repeat_index), modes in sorted(by_key.items()):
        if anchor_mode not in modes or comparison_mode not in modes:
            unpaired_rows.append(
                {
                    "case_id": case_id,
                    "repeat_index": repeat_index,
                    "available_modes": sorted(modes),
                }
            )
            continue
        anchor = modes[anchor_mode]
        comparison = modes[comparison_mode]
        anchor_passed = bool(anchor.get("answer_rule_passed"))
        comparison_passed = bool(comparison.get("answer_rule_passed"))
        if anchor_passed and comparison_passed:
            movement = "both_passed"
        elif anchor_passed and not comparison_passed:
            movement = "anchor_passed_comparison_failed"
        elif not anchor_passed and comparison_passed:
            movement = "anchor_failed_comparison_passed"
        else:
            movement = "both_failed"
        counts[movement] += 1
        movement_rows.append(
            {
                "case_id": case_id,
                "category": comparison.get("category") or anchor.get("category") or "",
                "repeat_index": repeat_index,
                "anchor_mode": anchor_mode,
                "comparison_mode": comparison_mode,
                "anchor_passed": anchor_passed,
                "comparison_passed": comparison_passed,
                "movement": movement,
                "anchor_failures": list(anchor.get("failures") or []),
                "comparison_failures": list(comparison.get("failures") or []),
                "comparison_retry_reasons": list(
                    comparison.get("post_check_retry_reasons") or []
                ),
            }
        )
    return {
        "anchor_mode": anchor_mode,
        "comparison_mode": comparison_mode,
        "case_count": len(rows),
        "paired_case_count": len(movement_rows),
        "unpaired_case_count": len(unpaired_rows),
        "movement_counts": counts,
        "unpaired_rows": unpaired_rows,
        "rows": movement_rows,
    }


def _validate_modes(rows: list[dict[str, Any]]) -> None:
    mode_counts = _mode_row_counts(rows)
    if set(mode_counts) != set(EXPECTED_MODES):
        raise ValueError(f"unexpected modes: {sorted(mode_counts)}")
    if len(set(mode_counts.values())) != 1:
        raise ValueError(f"mode row counts differ: {mode_counts}")


def _mode_row_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        mode = str(row.get("mode") or "")
        counts[mode] = counts.get(mode, 0) + 1
    return dict(sorted(counts.items()))


def _validate_no_forbidden_keys(value: Any) -> None:
    keys = _walk_keys(value)
    blocked = FORBIDDEN_KEYS & keys
    if blocked:
        raise ValueError(f"forbidden keys present: {sorted(blocked)}")


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for child in value.values():
            keys.update(_walk_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_walk_keys(child))
        return keys
    return set()


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = list(rows[0]) if rows else list(SCALAR_FIELDS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _md_cell(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item)]


if __name__ == "__main__":
    raise SystemExit(main())
