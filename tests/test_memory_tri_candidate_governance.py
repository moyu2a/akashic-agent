from __future__ import annotations

import json
import os
import subprocess
import sys

from memory2.eval_tri_candidate_governance import (
    build_tri_candidate_governance_report,
    write_tri_candidate_governance_report,
)


def test_tri_candidate_governance_report_has_counts_and_preserves_targets() -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")

    metrics = report["metrics"]
    assert metrics["case_count"] > 0
    assert (
        metrics["protected_expected_hit_count"]
        == metrics["baseline_expected_hit_count"]
    )
    assert metrics["protected_expected_hit_loss_count"] == 0
    assert metrics["unprotected_expected_hit_loss_count"] >= 0
    assert "dropped_risks_by_reason" in metrics
    assert "unprotected_dropped_risks_by_reason" in metrics
    assert "would_drop_protected_by_reason" in metrics
    assert "failure_bucket_counts" in metrics
    assert isinstance(metrics["dropped_risks_by_reason"], dict)
    assert "case_rows" in report


def test_tri_candidate_governance_report_uses_fixture_should_not_ids() -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")

    metrics = report["metrics"]
    assert metrics["should_not_candidate_count"] > 0
    assert metrics["strict_should_not_drop_count"] > 0
    assert metrics["strict_should_not_kept_count"] == 0


def test_tri_candidate_governance_report_writes_private_artifacts(tmp_path) -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")
    json_path, md_path = write_tri_candidate_governance_report(report, tmp_path)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["metrics"]["case_count"] == report["metrics"]["case_count"]
    markdown = md_path.read_text(encoding="utf-8")
    assert "Tri Candidate Governance" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown


def test_tri_candidate_governance_report_records_tiered_metrics() -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")

    metrics = report["metrics"]
    assert metrics["tiered_candidate_risk_tier_counts"]
    assert "delete" in metrics["tiered_candidate_risk_tier_counts"]
    assert "accepted_candidate_risk_tier_counts" not in metrics
    assert metrics["tiered_accepted_candidate_risk_tier_counts"]
    assert metrics["tiered_deleted_risks_by_reason"]
    rows = report["case_rows"]
    assert rows
    assert all("tiered_classified_candidate_count" in row for row in rows)
    assert all("tiered_accepted_candidate_count" in row for row in rows)
    assert any(row["tiered_downgrade_count"] > 0 for row in rows)


def test_tri_candidate_governance_markdown_mentions_risk_tiers(tmp_path) -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")
    _json_path, md_path = write_tri_candidate_governance_report(report, tmp_path)

    markdown = md_path.read_text(encoding="utf-8")
    assert "Risk Tier Metrics" in markdown
    assert "tiered_candidate_risk_tier_counts" in markdown
    assert "tiered_accepted_candidate_count" in markdown
    assert "tiered_downgrade_count" in markdown


def test_tri_candidate_governance_cli_writes_offline_report(tmp_path) -> None:
    env = {
        **os.environ,
        "OPENAI_API_KEY": "offline-eval-must-not-use",
        "AKASHIC_OBSERVE_DB": str(tmp_path / "observe-must-not-exist.db"),
        "AKASHIC_MEMORY_DB": str(tmp_path / "memory-must-not-exist.db"),
    }

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_tri_candidate_governance_eval.py",
            "--out-dir",
            str(tmp_path),
            "--case-pack",
            "standard",
        ],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    assert "tri_candidate_governance.json" in completed.stdout
    payload = json.loads(
        (tmp_path / "tri_candidate_governance.json").read_text(encoding="utf-8")
    )
    markdown = (tmp_path / "tri_candidate_governance.md").read_text(
        encoding="utf-8"
    )
    assert payload["metrics"]["case_pack"] == "standard"
    assert payload["metrics"]["protected_expected_hit_loss_count"] == 0
    assert "Tri Candidate Governance" in markdown
    assert not (tmp_path / "observe-must-not-exist.db").exists()
    assert not (tmp_path / "memory-must-not-exist.db").exists()
