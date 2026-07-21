from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_comprehensive_online_cli_gates_real_llm_by_default(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--limit",
            "4",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    payload = json.loads(
        (tmp_path / "reports" / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metrics"]["real_llm_enabled"] is False
    assert payload["metrics"]["gate_reason"] == "real_llm_disabled"


def test_comprehensive_online_cli_fake_provider_writes_report(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--limit",
            "4",
            "--profiles",
            "chain_off,chain_all_on",
            "--repeats",
            "1",
            "--prompt-variants",
            "baseline",
            "--concurrency",
            "2",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_comprehensive_online_eval.json" in completed.stdout
    payload = json.loads(
        (tmp_path / "reports" / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (
        tmp_path / "reports" / "memory_comprehensive_online_eval.md"
    ).read_text(encoding="utf-8")
    assert payload["metrics"]["evaluation_level"] == "comprehensive_online_agentloop"
    assert payload["metrics"]["case_count"] == 8
    assert payload["metrics"]["real_llm_enabled"] is False
    assert payload["metrics"]["concurrency"] == 2
    assert payload["passed"] is False
    assert payload["metrics"]["infra_passed"] is True
    assert payload["metrics"]["answer_quality_passed"] is False
    assert (
        payload["metrics"]["metric_sources"]["online_answer_level"]
        == "real AgentLoop answer scoring"
    )
    assert "综合线上评测" in markdown
    assert "不是生产回答准确率" in markdown


def test_comprehensive_online_cli_accepts_comprehensive_case_pack_core_matrix(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--case-pack",
            "comprehensive",
            "--case-set",
            "common",
            "--limit",
            "2",
            "--profiles",
            "chain_off,chain_tri_retrieval,chain_rerank_injection,chain_all_on",
            "--repeats",
            "1",
            "--prompt-variants",
            "baseline",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(
        (tmp_path / "reports" / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )

    assert "memory_comprehensive_online_eval.json" in completed.stdout
    assert payload["metrics"]["case_count"] == 8
    assert payload["metrics"]["real_llm_enabled"] is False
    assert payload["metrics"]["profile_count"] == 4
    assert payload["metrics"]["prompt_variant_count"] == 1


def test_comprehensive_online_cli_fake_provider_report_is_sanitized(
    tmp_path: Path,
) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--limit",
            "1",
            "--profiles",
            "chain_off,chain_all_on",
            "--repeats",
            "1",
            "--prompt-variants",
            "baseline",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    report_text = (
        tmp_path / "reports" / "memory_comprehensive_online_eval.json"
    ).read_text(encoding="utf-8")
    markdown_text = (
        tmp_path / "reports" / "memory_comprehensive_online_eval.md"
    ).read_text(encoding="utf-8")
    assert "请继续用中文回答，并保持 pytest 风格。" not in report_text
    assert "用户偏好中文回答" not in report_text
    assert "没有可用记忆，无法确认。" not in report_text
    assert "请继续用中文回答，并保持 pytest 风格。" not in markdown_text
    assert "用户偏好中文回答" not in markdown_text
    assert "没有可用记忆，无法确认。" not in markdown_text


def test_comprehensive_online_cli_can_write_checkpoint_only_partial_report(
    tmp_path: Path,
) -> None:
    valid_result = {
        "answer_length": 20,
        "answer_rule_passed": True,
        "case_id": "case-1",
        "category": "common",
        "completion_token_count": 10,
        "evidence_source": "none",
        "expected_memory_used": False,
        "failures": [],
        "forbidden_contains_violation_count": 0,
        "latency_ms": 100,
        "memory_grounding_passed": True,
        "passed": True,
        "profile_name": "chain_all_on",
        "prompt_token_count": 20,
        "prompt_variant": "baseline",
        "provider_error": False,
        "repeat_index": 0,
        "timeout": False,
        "token_metrics_available": True,
        "total_token_count": 30,
        "used_memory_id_count": 1,
    }
    failed_result = {
        **valid_result,
        "case_id": "case-2",
        "provider_error": True,
        "passed": False,
        "failures": ["provider_error"],
    }
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(
        "\n".join(
            [
                json.dumps({"spec_key": "ok", "result": valid_result}),
                json.dumps({"spec_key": "bad", "result": failed_result}),
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--checkpoint-jsonl",
            str(checkpoint),
            "--checkpoint-report-only",
            "--exclude-infra-failures",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_comprehensive_online_eval.json" in completed.stdout
    payload = json.loads(
        (tmp_path / "reports" / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metrics"]["case_count"] == 1
    assert payload["metrics"]["checkpoint_input_count"] == 2
    assert payload["metrics"]["excluded_infra_failure_count"] == 1


def test_comprehensive_online_cli_rejects_fake_provider_with_real_llm_flag(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--enable-real-llm",
            "--limit",
            "1",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "cannot be used together" in completed.stderr


def test_comprehensive_online_provider_gate_does_not_construct_real_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.run_memory_comprehensive_online_eval as cli

    def fail_provider(**_kwargs: object) -> object:
        raise AssertionError("LLMProvider must not be constructed")

    monkeypatch.setattr(cli.agent_provider, "LLMProvider", fail_provider)
    args = argparse.Namespace(
        enable_real_llm=False,
        fake_provider=False,
        config="config.toml",
        timeout_s=60.0,
    )

    provider, model = cli.build_provider_for_comprehensive_online(args)

    assert provider is None
    assert model is None


def test_comprehensive_online_debug_dir_must_stay_under_workspace(
    tmp_path: Path,
) -> None:
    import scripts.run_memory_comprehensive_online_eval as cli

    with pytest.raises(ValueError, match="answer debug"):
        cli.resolve_answer_debug_dir(
            workspace=tmp_path / "workspace",
            out_dir=tmp_path / "reports",
            include_answer_debug=True,
            answer_debug_dir=tmp_path / "reports" / "answer_debug",
        )
