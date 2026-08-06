from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_compatibility_cli_runs_from_repository_root() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/run_agent_harness_compatibility.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "entries=10" in result.stdout
    assert "adapter_ready=0" in result.stdout
    assert "main_gate_ready_count=0" in result.stdout
    assert "main_gate_allowed=0" in result.stdout
