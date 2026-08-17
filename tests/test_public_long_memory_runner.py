from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_public_long_memory_runner_writes_fake_provider_smoke_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    checkpoint = tmp_path / "checkpoint.jsonl"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_public_long_memory_eval.py",
            "--dataset",
            "tests/fixtures/longmemeval_sample.jsonl",
            "--phase",
            "phase_a",
            "--sample-size",
            "5",
            "--seed",
            "42",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--checkpoint-jsonl",
            str(checkpoint),
            "--fresh-checkpoint",
            "--fake-provider",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "public_long_memory_eval.json" in completed.stdout
    report = json.loads((out_dir / "public_long_memory_eval.json").read_text())
    assert report["metrics"]["benchmark"] == "longmemeval"
    assert report["metrics"]["phase"] == "phase_a"
    assert report["metrics"]["profile"] == "chain_tri_governed_answer_contract"
    assert report["metrics"]["dataset_case_count"] == 6
    assert report["metrics"]["sampled_case_count"] == 5
    assert report["metrics"]["completed_call_count"] == 5
    assert report["metrics"]["provider_error_count"] == 0
    assert report["metrics"]["timeout_count"] == 0
    assert report["metrics"]["sampling"]["seed"] == 42
    assert set(report["metrics"]["sampled_category_distribution"]) == {
        "abstention",
        "single-session-user",
        "multi-session",
        "temporal-reasoning",
        "knowledge-update",
    }
    assert len(report["case_reviews"]) == 5
    assert (out_dir / "public_long_memory_eval.md").exists()
