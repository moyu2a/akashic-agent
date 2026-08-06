from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_g10a_matrix_cli_writes_sixty_turn_report(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_agent_harness_g10a_matrix.py",
            "--dataset",
            "my_md/test_docs/eval_suite/g10a-60turn-matrix.json",
            "--out-dir",
            str(tmp_path),
            "--max-react-iterations",
            "12",
            "--seed",
            "17",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "episode_count=60" in result.stdout
    assert "security_hard_gate_passed=True" in result.stdout
    payload = json.loads((tmp_path / "g10a-matrix-report.json").read_text())
    assert payload["summary"]["episode_count"] == 60
    assert payload["summary"]["formal_g10a_ready"] is False
