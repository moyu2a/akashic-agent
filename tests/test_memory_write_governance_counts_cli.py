from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_memory_write_governance_counts_cli_writes_offline_report(
    tmp_path: Path,
) -> None:
    env = {
        **os.environ,
        "OPENAI_API_KEY": "offline-eval-must-not-use",
        "AKASHIC_OBSERVE_DB": str(tmp_path / "observe-must-not-exist.db"),
        "AKASHIC_MEMORY_DB": str(tmp_path / "memory-must-not-exist.db"),
    }
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_write_governance_counts_eval.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )

    assert "memory_write_governance_counts_eval.json" in completed.stdout
    payload = json.loads(
        (tmp_path / "memory_write_governance_counts_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (tmp_path / "memory_write_governance_counts_eval.md").read_text(
        encoding="utf-8"
    )
    assert payload["metrics"]["measurement_mode"] == "offline_write_governance_count_eval"
    assert payload["metrics"]["candidate_count"] == 1200
    assert payload["metrics"]["offline_only"] is True
    assert payload["metrics"]["llm_calls_enabled"] is False
    assert payload["metrics"]["db_access_enabled"] is False
    assert payload["metrics"]["production_state_access_enabled"] is False
    assert len(payload["main_rows"]) == 6
    assert len(payload["case_set_rows"]) == 12
    assert len(payload["subtype_rows"]) == 60
    assert "## 写入治理主表" in markdown
    assert "## Common/Hard 分组表" in markdown
    assert "## 误伤表" in markdown
    assert "## 漏拦表" in markdown
    assert "## 复核缺口表" in markdown
    assert not (tmp_path / "observe-must-not-exist.db").exists()
    assert not (tmp_path / "memory-must-not-exist.db").exists()
