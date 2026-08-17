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
            "--profile",
            "chain_tri_governed_answer_contract",
            "--prompt-variants",
            "baseline",
            "--repeats",
            "1",
            "--evidence-render-mode",
            "answer_window",
            "--long-evidence-token-limit",
            "3000",
            "--reserved-prompt-token-budget",
            "2000",
            "--answer-window-turns",
            "2",
            "--model-context-window",
            "8192",
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
    assert report["metrics"]["actual_call_shape"] == "5 * 1 * 1 * 1 = 5"
    assert report["metrics"]["provider_error_count"] == 0
    assert report["metrics"]["timeout_count"] == 0
    assert report["metrics"]["prompt_variants"] == ["baseline"]
    assert report["metrics"]["repeats"] == 1
    assert report["metrics"]["evidence_render_mode"] == "answer_window"
    assert report["metrics"]["long_evidence_token_limit"] == 3000
    assert report["metrics"]["reserved_prompt_token_budget"] == 2000
    assert report["metrics"]["model_context_window"] == 8192
    assert report["metrics"]["effective_evidence_token_budget"] == 3000
    assert report["metrics"]["tool_call_only_count"] == 0
    assert report["metrics"]["tool_call_style_output_count"] == 0
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


def test_public_long_memory_runner_captures_sanitized_provider_requests(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    checkpoint = tmp_path / "checkpoint.jsonl"
    workspace = tmp_path / "workspace"
    request_dir = tmp_path / "requests"
    dataset = tmp_path / "single_category.jsonl"
    dataset.write_text(
        '{"id":"capture_001","category":"single-session-user",'
        '"question":"What drink does Alice prefer?","answer":"green tea",'
        '"question_date":"2024/02/03 (Sat) 13:45",'
        '"history":[{"role":"user","content":"Alice says she prefers green tea.","has_answer":true}]}\n',
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_public_long_memory_eval.py",
            "--dataset",
            str(dataset),
            "--phase",
            "phase_a",
            "--sample-size",
            "1",
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
            "--profile",
            "chain_tri_governed_answer_contract",
            "--prompt-variants",
            "baseline",
            "--repeats",
            "1",
            "--evidence-render-mode",
            "answer_window",
            "--capture-provider-request",
            "--provider-request-debug-dir",
            str(request_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    request_files = sorted(request_dir.glob("*.json"))
    structured_files = sorted(
        (workspace / "public_long_memory_structured_evidence").glob("*.json")
    )
    assert len(request_files) == 1
    assert len(structured_files) == 1
    report = json.loads((out_dir / "public_long_memory_eval.json").read_text())
    assert report["metrics"]["provider_request_capture_file_count"] == 1
    assert report["metrics"]["provider_request_snapshot_clean_count"] == 1
    assert report["metrics"]["provider_request_snapshot_mutation_count"] == 0
    assert report["metrics"]["structured_evidence_snapshot_file_count"] == 1
    payload = json.loads(request_files[0].read_text(encoding="utf-8"))
    assert payload["case_id"]
    assert payload["provider_request"]["model"] == "fake-model"
    assert "messages" in payload["provider_request"]
    assert "api_key" not in json.dumps(payload, ensure_ascii=False).lower()
    assert payload["user_question"]
    assert payload["evidence_block_text"]
    assert payload["structured_evidence_snapshot_path"]
    assert Path(payload["structured_evidence_snapshot_path"]).exists()
    request_text = json.dumps(payload["provider_request"], ensure_ascii=False)
    assert "request_time=2024-02-03T13:45:00+00:00" in request_text
    assert "green tea" not in [
        message.get("content")
        for message in payload["provider_request"]["messages"]
        if message.get("role") == "assistant"
    ]

    answer_debug_files = sorted(
        (workspace / "public_long_memory_answer_debug").glob("*.json")
    )
    answer_debug = json.loads(answer_debug_files[0].read_text(encoding="utf-8"))
    assert answer_debug["structured_evidence_snapshot_path"] == payload[
        "structured_evidence_snapshot_path"
    ]

    structured = json.loads(structured_files[0].read_text(encoding="utf-8"))
    assert structured["case_id"] == "capture_001"
    assert structured["profile_name"] == "chain_tri_governed_answer_contract"
    assert structured["rendered_evidence_block_text"] == payload["evidence_block_text"]
    assert structured["raw_retrieved_items"][0]["id"] == "capture_001_history_0001"
    assert structured["governed_structured_evidence"]["allowed_evidence_ids"] == [
        "capture_001_history_0001"
    ]
    assert structured["truncation_applied"] is False
    assert structured["answer_session_covered"] is True
    assert structured["gold_supporting_fact_hit"] is True
