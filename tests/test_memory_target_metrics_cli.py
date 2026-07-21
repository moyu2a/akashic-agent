from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from memory2 import eval_target_metrics as target_metrics


def test_memory_target_metrics_cli_writes_reports(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_target_metrics_eval.json" in completed.stdout
    assert "memory_target_metrics_eval.md" in completed.stdout
    payload = json.loads(
        (tmp_path / "memory_target_metrics_eval.json").read_text(encoding="utf-8")
    )
    markdown = (tmp_path / "memory_target_metrics_eval.md").read_text(
        encoding="utf-8"
    )

    assert payload["metrics"]["measurement_mode"] == "offline_trace_real_baseline_target_metrics"
    assert payload["metrics"]["case_count"] == 80
    assert payload["metrics"]["online_row_count"] == 0
    assert "召回与回答增益表" in markdown
    assert "写入治理增益表" in markdown
    assert "记忆库卫生增益表" in markdown
    assert "离线真实 before/after" in markdown


def test_memory_target_metrics_cli_handles_common_subset(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path),
            "--case-set",
            "common",
            "--limit",
            "8",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "memory_target_metrics_eval.json").read_text(encoding="utf-8")
    )

    assert payload["metrics"]["common_case_count"] == 8
    assert payload["metrics"]["hard_case_count"] == 0


def test_memory_target_metrics_cli_handles_comprehensive_pack(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path),
            "--case-pack",
            "comprehensive",
            "--case-set",
            "common",
            "--limit",
            "12",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "memory_target_metrics_eval.json").read_text(encoding="utf-8")
    )

    assert payload["metrics"]["case_count"] == 12
    assert payload["metrics"]["common_case_count"] == 12
    assert payload["metrics"]["hard_case_count"] == 0


def test_memory_target_metrics_cli_reads_online_evidence_json(tmp_path: Path) -> None:
    write_path = tmp_path / "write_evidence.json"
    hygiene_path = tmp_path / "hygiene_evidence.json"
    write_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "w1",
                    "baseline_decision": "allow",
                    "after_decision": "reject",
                    "label": "pollution",
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    hygiene_path.write_text(
        json.dumps(
            [
                {
                    "item_id": "m1",
                    "baseline_state": "active",
                    "after_state": "merged",
                    "label": "duplicate",
                    "source_ref_available": True,
                    "source_fetch_success": True,
                    "baseline_token_estimate": 100,
                    "after_token_estimate": 50,
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path),
            "--limit",
            "4",
            "--online-checkpoint-source",
            "fake_provider",
            "--online-write-evidence-json",
            str(write_path),
            "--online-hygiene-evidence-json",
            str(hygiene_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "memory_target_metrics_eval.json").read_text(encoding="utf-8")
    )

    assert payload["metrics"]["online_row_count"] == 2
    assert any(
        row["measurement_source"] == "write_governance_evidence_json"
        for row in payload["write_governance_rows"]
    )
    assert any(
        row["measurement_source"] == "memory_hygiene_evidence_json"
        for row in payload["memory_hygiene_rows"]
    )
    assert any(
        row["measurement_layer"] == "online_evidence"
        for row in payload["write_governance_rows"]
    )
    assert any(
        row["measurement_layer"] == "online_evidence"
        for row in payload["memory_hygiene_rows"]
    )


def test_memory_target_metrics_cli_rebuilds_from_online_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint_rows = [
        {
            "spec_key": "case-1|chain_off|baseline|0",
            "result": {
                "answer_length": 20,
                "answer_rule_passed": False,
                "case_id": "case-1",
                "category": "common",
                "completion_token_count": 10,
                "evidence_source": "none",
                "expected_memory_used": False,
                "failures": [],
                "forbidden_contains_violation_count": 0,
                "latency_ms": 100,
                "memory_grounding_passed": False,
                "passed": False,
                "profile_name": "chain_off",
                "prompt_token_count": 20,
                "prompt_variant": "baseline",
                "provider_error": False,
                "repeat_index": 0,
                "timeout": False,
                "token_metrics_available": True,
                "total_token_count": 30,
                "used_memory_id_count": 0,
            },
        },
        {
            "spec_key": "case-1|chain_tri_retrieval|baseline|0",
            "result": {
                "answer_length": 24,
                "answer_rule_passed": True,
                "case_id": "case-1",
                "category": "common",
                "completion_token_count": 12,
                "evidence_source": "real_llm",
                "expected_memory_used": True,
                "failures": [],
                "forbidden_contains_violation_count": 0,
                "latency_ms": 90,
                "memory_grounding_passed": True,
                "passed": True,
                "profile_name": "chain_tri_retrieval",
                "prompt_token_count": 22,
                "prompt_variant": "baseline",
                "provider_error": False,
                "repeat_index": 0,
                "timeout": False,
                "token_metrics_available": True,
                "total_token_count": 34,
                "used_memory_id_count": 1,
            },
        },
    ]
    checkpoint.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in checkpoint_rows),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path / "reports"),
            "--case-pack",
            "comprehensive",
            "--online-checkpoint-jsonl",
            str(checkpoint),
            "--online-checkpoint-source",
            "real_llm",
            "--exclude-online-infra-failures",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "reports" / "memory_target_metrics_eval.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["metrics"]["online_row_count"] >= 1
    assert payload["metrics"]["online_status"] == "available"


def test_memory_target_metrics_cli_reads_wrapped_online_evidence_json(tmp_path: Path) -> None:
    write_path = tmp_path / "write_evidence.json"
    hygiene_path = tmp_path / "hygiene_evidence.json"
    write_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "candidate_id": "w1",
                        "baseline_decision": "allow",
                        "after_decision": "review",
                        "label": "conflict",
                        "infra_error": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    hygiene_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "item_id": "m1",
                        "baseline_state": "active",
                        "after_state": "stale",
                        "label": "stale",
                        "source_ref_available": True,
                        "source_fetch_success": True,
                        "baseline_token_estimate": 100,
                        "after_token_estimate": 70,
                        "infra_error": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path),
            "--limit",
            "4",
            "--online-checkpoint-source",
            "fake_provider",
            "--online-write-evidence-json",
            str(write_path),
            "--online-hygiene-evidence-json",
            str(hygiene_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "memory_target_metrics_eval.json").read_text(encoding="utf-8")
    )

    assert payload["metrics"]["online_row_count"] == 2
    assert payload["metrics"]["online_status"] == "available"


def test_memory_target_metrics_cli_reads_online_evidence_jsonl(tmp_path: Path) -> None:
    write_path = tmp_path / "write_evidence.jsonl"
    hygiene_path = tmp_path / "hygiene_evidence.jsonl"
    write_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "candidate_id": "w1",
                        "baseline_decision": "allow",
                        "after_decision": "allow",
                        "label": "useful",
                        "infra_error": False,
                    }
                ),
                json.dumps(
                    {
                        "candidate_id": "w2",
                        "baseline_decision": "allow",
                        "after_decision": "reject",
                        "label": "pollution",
                        "infra_error": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    hygiene_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "item_id": "m1",
                        "baseline_state": "active",
                        "after_state": "merged",
                        "label": "duplicate",
                        "source_ref_available": True,
                        "source_fetch_success": True,
                        "baseline_token_estimate": 100,
                        "after_token_estimate": 50,
                        "infra_error": False,
                    }
                ),
                json.dumps(
                    {
                        "item_id": "m2",
                        "baseline_state": "active",
                        "after_state": "active",
                        "label": "retained",
                        "source_ref_available": True,
                        "source_fetch_success": True,
                        "baseline_token_estimate": 80,
                        "after_token_estimate": 80,
                        "infra_error": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path),
            "--limit",
            "4",
            "--online-checkpoint-source",
            "real_llm",
            "--online-write-evidence-json",
            str(write_path),
            "--online-hygiene-evidence-json",
            str(hygiene_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "memory_target_metrics_eval.json").read_text(encoding="utf-8")
    )

    assert payload["metrics"]["measurement_mode"] == (
        "offline_trace_real_baseline_plus_online_checkpoint_target_metrics"
    )
    assert payload["metrics"]["online_status"] == "available"
    assert payload["metrics"]["online_row_count"] == 2
    assert payload["metrics"]["online_write_record_count"] == 2
    assert payload["metrics"]["online_hygiene_record_count"] == 2


def test_memory_target_metrics_cli_rejects_invalid_write_evidence(tmp_path: Path) -> None:
    write_path = tmp_path / "bad_write_evidence.json"
    write_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "w1",
                    "baseline_decision": "allow",
                    "label": "pollution",
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path / "out"),
            "--limit",
            "4",
            "--online-write-evidence-json",
            str(write_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "write evidence row 0 missing required fields: after_decision" in completed.stderr


def test_memory_target_metrics_cli_rejects_invalid_hygiene_evidence(tmp_path: Path) -> None:
    hygiene_path = tmp_path / "bad_hygiene_evidence.json"
    hygiene_path.write_text(
        json.dumps(
            [
                {
                    "item_id": "m1",
                    "baseline_state": "active",
                    "after_state": "merged",
                    "label": "duplicate",
                    "source_ref_available": True,
                    "source_fetch_success": True,
                    "baseline_token_estimate": "many",
                    "after_token_estimate": 50,
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path / "out"),
            "--limit",
            "4",
            "--online-hygiene-evidence-json",
            str(hygiene_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "hygiene evidence row 0 field baseline_token_estimate must be a nonnegative number" in completed.stderr


def test_memory_target_metrics_cli_rejects_invalid_evidence_domains(tmp_path: Path) -> None:
    write_path = tmp_path / "bad_write_domain.json"
    hygiene_path = tmp_path / "bad_hygiene_domain.json"
    write_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "w1",
                    "baseline_decision": "allow",
                    "after_decision": "defer",
                    "label": "pollution",
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    hygiene_path.write_text(
        json.dumps(
            [
                {
                    "item_id": "m1",
                    "baseline_state": "active",
                    "after_state": "archived",
                    "label": "retained",
                    "source_ref_available": True,
                    "source_fetch_success": True,
                    "baseline_token_estimate": 100,
                    "after_token_estimate": 100,
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path / "out"),
            "--limit",
            "4",
            "--online-write-evidence-json",
            str(write_path),
            "--online-hygiene-evidence-json",
            str(hygiene_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "write evidence row 0 field after_decision has invalid decision: defer" in completed.stderr


def test_memory_target_metrics_cli_rejects_nonboolean_evidence_fields(tmp_path: Path) -> None:
    write_path = tmp_path / "bad_write_bool.json"
    hygiene_path = tmp_path / "bad_hygiene_bool.json"
    write_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "w1",
                    "baseline_decision": "allow",
                    "after_decision": "reject",
                    "label": "pollution",
                    "infra_error": "false",
                }
            ]
        ),
        encoding="utf-8",
    )
    hygiene_path.write_text(
        json.dumps(
            [
                {
                    "item_id": "m1",
                    "baseline_state": "active",
                    "after_state": "merged",
                    "label": "duplicate",
                    "source_ref_available": "true",
                    "source_fetch_success": True,
                    "baseline_token_estimate": 100,
                    "after_token_estimate": 50,
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path / "out"),
            "--limit",
            "4",
            "--online-write-evidence-json",
            str(write_path),
            "--online-hygiene-evidence-json",
            str(hygiene_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "write evidence row 0 field infra_error must be boolean" in completed.stderr


def test_memory_target_metrics_cli_renders_online_evidence_rows(tmp_path: Path) -> None:
    write_path = tmp_path / "write_evidence.json"
    hygiene_path = tmp_path / "hygiene_evidence.json"
    write_path.write_text(
        json.dumps(
            [
                {
                    "candidate_id": "w1",
                    "baseline_decision": "allow",
                    "after_decision": "reject",
                    "label": "pollution",
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    hygiene_path.write_text(
        json.dumps(
            [
                {
                    "item_id": "m1",
                    "baseline_state": "active",
                    "after_state": "merged",
                    "label": "duplicate",
                    "source_ref_available": True,
                    "source_fetch_success": True,
                    "baseline_token_estimate": 100,
                    "after_token_estimate": 50,
                    "infra_error": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_target_metrics_eval.py",
            "--out-dir",
            str(tmp_path),
            "--limit",
            "4",
            "--online-checkpoint-source",
            "fake_provider",
            "--online-write-evidence-json",
            str(write_path),
            "--online-hygiene-evidence-json",
            str(hygiene_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    markdown = (tmp_path / "memory_target_metrics_eval.md").read_text(encoding="utf-8")

    assert "## 在线证据行" in markdown
    assert "write_governance_evidence_json" in markdown
    assert "memory_hygiene_evidence_json" in markdown


def test_memory_target_metrics_cli_cleans_up_on_failure(tmp_path: Path) -> None:
    out_dir = tmp_path / "failed_reports"
    original = target_metrics.build_target_metric_report

    def boom(cases):  # type: ignore[no-untyped-def]
        raise RuntimeError("target metric eval failed")

    target_metrics.build_target_metric_report = boom  # type: ignore[assignment]
    try:
        exit_code = target_metrics.main(["--out-dir", str(out_dir)])
    finally:
        target_metrics.build_target_metric_report = original  # type: ignore[assignment]

    assert exit_code != 0
    assert not out_dir.exists() or not any(out_dir.iterdir())
