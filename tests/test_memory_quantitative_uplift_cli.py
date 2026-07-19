from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_memory_quantitative_uplift_cli_writes_reports(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_quantitative_uplift_eval.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_quantitative_uplift_eval.json" in completed.stdout
    json_path = tmp_path / "memory_quantitative_uplift_eval.json"
    md_path = tmp_path / "memory_quantitative_uplift_eval.md"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["case_count"] == 80
    assert payload["metrics"]["common_case_count"] == 40
    assert payload["metrics"]["hard_case_count"] == 40
    assert payload["metrics"]["repeat_count"] == 1
    assert md_path.exists()


def test_memory_quantitative_uplift_cli_is_deterministic(tmp_path: Path) -> None:
    def run_cli(out_dir: Path) -> dict[str, object]:
        subprocess.run(
            [
                sys.executable,
                "scripts/run_memory_quantitative_uplift_eval.py",
                "--out-dir",
                str(out_dir),
                "--case-set",
                "common",
                "--limit",
                "8",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        return json.loads(
            (out_dir / "memory_quantitative_uplift_eval.json").read_text(
                encoding="utf-8"
            )
        )

    payload_a = run_cli(tmp_path / "reports_a")
    payload_b = run_cli(tmp_path / "reports_b")

    assert payload_a["metrics"] == payload_b["metrics"]
    assert payload_a["profile_summaries"] == payload_b["profile_summaries"]
    assert payload_a["generated_at"] == payload_b["generated_at"]


def test_memory_quantitative_uplift_cli_fails_when_report_builder_fails(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "failed_reports"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import runpy; "
                "import memory2.eval_quantitative_uplift as uplift; "
                "uplift.build_quantitative_uplift_report = "
                "lambda cases: (_ for _ in ()).throw(RuntimeError('eval runner failed')); "
                "runpy.run_path('scripts/run_memory_quantitative_uplift_eval.py', "
                "run_name='__main__')"
            ),
            "--out-dir",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "eval runner failed" in completed.stderr
    assert not (out_dir / "memory_quantitative_uplift_eval.json").exists()
    assert not (out_dir / "memory_quantitative_uplift_eval.md").exists()
