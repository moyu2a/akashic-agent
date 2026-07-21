from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_write_governance_online_cli_gates_real_llm_by_default(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_write_governance_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--limit",
            "2",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    payload = json.loads(
        (
            tmp_path / "reports" / "memory_write_governance_online_eval.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["metrics"]["real_llm_enabled"] is False
    assert payload["metrics"]["gate_reason"] == "real_llm_disabled"


def test_write_governance_online_cli_fake_provider_writes_target_metric_evidence(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_write_governance_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--case-set",
            "common",
            "--limit",
            "6",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_write_governance_online_evidence.jsonl" in completed.stdout
    evidence = tmp_path / "reports" / "memory_write_governance_online_evidence.jsonl"
    assert evidence.exists()
    rows = [
        json.loads(line)
        for line in evidence.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 6
    assert {row["label"] for row in rows} == {
        "useful",
        "pollution",
        "duplicate",
        "conflict",
    }

    target = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path / "target"),
            "--online-checkpoint-source",
            "fake_provider",
            "--online-write-evidence-json",
            str(evidence),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "memory_target_metrics_eval.json" in target.stdout
    payload = json.loads(
        (tmp_path / "target" / "memory_target_metrics_eval.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metrics"]["online_write_record_count"] == 6
    assert payload["metrics"]["online_status"] == "available"
