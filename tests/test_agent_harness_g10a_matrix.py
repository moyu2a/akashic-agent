from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from eval.agent_harness.matrix import (
    DEFAULT_G10A_PROFILES,
    EXPECTED_G10A_CATEGORIES,
    load_task_dataset,
    run_g10a_matrix,
    validate_g10a_dataset,
)


def test_g10a_dataset_has_twenty_cases_across_four_scenarios() -> None:
    root = Path(__file__).resolve().parents[1]
    tasks = load_task_dataset(
        root / "my_md/test_docs/eval_suite/g10a-60turn-matrix.json"
    )

    counts = validate_g10a_dataset(tasks)

    assert len(tasks) == 20
    assert counts == {category: 5 for category in EXPECTED_G10A_CATEGORIES}


def test_g10a_matrix_runs_twenty_cases_across_three_profiles(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    tasks = load_task_dataset(
        root / "my_md/test_docs/eval_suite/g10a-60turn-matrix.json"
    )

    report = asyncio.run(
        run_g10a_matrix(
            tasks,
            output_dir=tmp_path,
            profiles=DEFAULT_G10A_PROFILES,
            git_sha="abc123",
            dataset_version="g10a-test",
            model="fake-model",
            provider="fake",
            environment_kind="fake",
            max_react_iterations=12,
            seed=11,
        )
    )

    payload = json.loads((tmp_path / "g10a-matrix-report.json").read_text())

    assert report.summary["expected_episode_count"] == 60
    assert report.summary["episode_count"] == 60
    assert report.summary["profile_names"] == list(DEFAULT_G10A_PROFILES)
    assert report.summary["security_hard_gate_passed"] is True
    assert report.summary["formal_g10a_ready"] is False
    assert "environment_kind=fake" in report.summary["blockers"][0]
    assert (
        payload["governance_profiles"]["budget_limited"]["call_budget_enabled"] is True
    )
    assert payload["governance_profiles"]["full_governance"][
        "requires_real_executor_fields"
    ] == [
        "tool_scope_enforced",
        "risk_preflight_enabled",
        "approval_required_for_high_risk",
        "path_check_enabled",
        "restricted_execution_enabled",
    ]
    assert payload["summary"]["episode_count"] == 60


def test_g10a_matrix_rejects_real_labels_until_real_executor_exists(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    tasks = load_task_dataset(
        root / "my_md/test_docs/eval_suite/g10a-60turn-matrix.json"
    )

    with pytest.raises(ValueError, match="fake structural"):
        asyncio.run(
            run_g10a_matrix(
                tasks,
                output_dir=tmp_path,
                profiles=DEFAULT_G10A_PROFILES,
                git_sha="abc123",
                dataset_version="g10a-test",
                model="real-model",
                provider="real-provider",
                environment_kind="sandbox_real",
                max_react_iterations=12,
                seed=11,
            )
        )
