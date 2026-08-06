from __future__ import annotations

import json
from pathlib import Path

from eval.agent_harness.protocol import EpisodeResult, RunManifest, TaskSpec
from eval.agent_harness.reports import write_run_report


def test_run_report_writes_json_and_markdown_without_raw_secret(
    tmp_path: Path,
) -> None:
    manifest = RunManifest(
        run_id="run-privacy",
        git_sha="abc123",
        dataset_version="v2",
        dataset_hash="hash",
        model="fake-model",
        provider="fake",
        config_hash="cfg",
        governance_profile="full_governance",
        environment_kind="fake",
        seed=1,
        repeat_index=0,
        runner_version="0.1",
    )
    task = TaskSpec(case_id="privacy-001", category="security")
    result = EpisodeResult(
        episode_id="privacy-001-r0",
        status="PASS",
        outcome_passed=True,
        events=(
            {
                "event_type": "tool_requested",
                "payload": {"api_key": "[REDACTED]", "text": "token=[REDACTED]"},
            },
        ),
    )

    paths = write_run_report(
        tmp_path,
        manifest=manifest,
        tasks=[task],
        results=[result],
    )

    payload = json.loads(paths.json_path.read_text(encoding="utf-8"))
    markdown = paths.markdown_path.read_text(encoding="utf-8")
    assert payload["manifest"]["run_id"] == "run-privacy"
    assert "[REDACTED]" in markdown
    assert "secret-value" not in json.dumps(payload)
