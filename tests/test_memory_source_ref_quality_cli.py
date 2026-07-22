from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_source_ref_quality_cli_writes_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "report"
    fixture_db = tmp_path / "fixture" / "sessions.db"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_source_ref_quality_eval.py",
            "--output-dir",
            str(output_dir),
            "--fixture-db",
            str(fixture_db),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert fixture_db.exists()
    assert "source ref quality eval complete" in result.stdout
    payload = json.loads(
        (output_dir / "memory_source_ref_quality_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (output_dir / "memory_source_ref_quality_eval.md").read_text(
        encoding="utf-8"
    )

    assert payload["metadata"]["evaluation_mode"] == "synthetic_fixture_shadow"
    assert payload["metadata"]["production_uplift"] is False
    assert payload["metrics"]["normalized_fetch_success_rate"] > payload["metrics"]["baseline_fetch_success_rate"]
    assert payload["metrics"]["normalized_source_backed_eligible_rate"] > payload["metrics"]["baseline_source_backed_eligible_rate"]
    assert "shadow normalized_source_ref" in markdown
    assert "不是线上真实提升结论" in markdown
