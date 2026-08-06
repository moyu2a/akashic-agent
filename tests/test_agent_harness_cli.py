from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_script_runs_from_repository_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_agent_harness.py",
            "run",
            "--dataset",
            "my_md/test_docs/eval_suite/agent-harness-v2.yaml",
            "--repeat",
            "1",
            "--out-dir",
            str(tmp_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "run-report.json").exists()
