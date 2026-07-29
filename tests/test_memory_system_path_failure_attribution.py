from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from memory2.eval_system_path_failure_attribution import (
    build_system_path_failure_attribution,
)


def _row(
    case_id: str,
    mode: str,
    repeat_index: int,
    *,
    answer: bool,
    grounding: bool = True,
    forbidden_count: int = 0,
    failures: list[str] | None = None,
    answer_length: int = 24,
    expected_miss: int = 0,
    any_miss: int = 0,
    language_passed: bool = True,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "category": "hard",
        "mode": mode,
        "repeat_index": repeat_index,
        "answer_rule_passed": answer,
        "memory_grounding_passed": grounding,
        "forbidden_contains_violation_count": forbidden_count,
        "failures": failures or [],
        "answer_length": answer_length,
        "expected_contains_miss_count": expected_miss,
        "expected_any_miss_count": any_miss,
        "language_passed": language_passed,
        "provider_error": False,
        "timeout": False,
    }


def test_failure_attribution_pairs_modes_and_counts_movements() -> None:
    payload = {
        "metrics": {"unique_case_count": 2, "repeat_count": 2},
        "cases": [
            _row("case-a", "current", 0, answer=False, forbidden_count=1),
            _row("case-a", "safe_version_replace", 0, answer=True),
            _row("case-a", "current", 1, answer=False, forbidden_count=1),
            _row("case-a", "safe_version_replace", 1, answer=True),
            _row("case-b", "current", 0, answer=True),
            _row(
                "case-b",
                "safe_version_replace",
                0,
                answer=False,
                failures=["missing_expected_answer_term"],
                expected_miss=1,
            ),
            _row("case-b", "current", 1, answer=True),
            _row(
                "case-b",
                "safe_version_replace",
                1,
                answer=False,
                failures=["missing_expected_answer_term_group"],
                any_miss=1,
            ),
        ],
    }

    report = build_system_path_failure_attribution(payload)

    assert report["metrics"]["paired_run_count"] == 4
    assert report["metrics"]["baseline_failed_candidate_passed_count"] == 2
    assert report["metrics"]["baseline_passed_candidate_failed_count"] == 2
    assert report["metrics"]["candidate_failure_bucket_counts"][
        "answer_rule_miss_required_terms"
    ] == 1
    assert report["metrics"]["candidate_failure_bucket_counts"][
        "answer_rule_miss_any_group"
    ] == 1
    assert len(report["case_repeat_matrix"]) == 4


def test_failure_attribution_cli_writes_private_reports(tmp_path: Path) -> None:
    payload = {
        "metrics": {"unique_case_count": 1, "repeat_count": 1},
        "cases": [
            _row("case-a", "current", 0, answer=False, forbidden_count=1),
            _row("case-a", "safe_version_replace", 0, answer=True),
        ],
    }
    input_path = tmp_path / "system_path_safe_version_eval.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_failure_attribution.py",
            "--input-json",
            str(input_path),
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    json_payload = json.loads(
        (out_dir / "system_path_failure_attribution.json").read_text(encoding="utf-8")
    )
    markdown = (out_dir / "system_path_failure_attribution.md").read_text(
        encoding="utf-8"
    )
    text = json.dumps(json_payload, ensure_ascii=False) + markdown
    assert "raw_prompt" not in text
    assert "full_answer" not in text
    assert "session_text" not in text
    assert "memory_summary" not in text
    assert json_payload["metrics"]["paired_run_count"] == 1
