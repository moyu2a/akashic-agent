from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.run_memory_llm_sample_eval as cli


def test_select_llm_sample_runs_preserves_case_order() -> None:
    cases = [
        cli.load_eval_case(
            Path("tests/fixtures/memory_eval_cases/preference_recall.json")
        ),
        cli.load_eval_case(
            Path("tests/fixtures/memory_eval_cases/vague_reference_graph.json")
        ),
    ]

    selected = cli.select_llm_sample_runs(
        cases,
        case_ids=["vague_reference_graph", "preference_recall"],
        repeat_count=3,
        evidence_prompt_mode="baseline",
    )

    assert [(run.case.id, run.prompt_variant) for run in selected] == [
        ("vague_reference_graph", "baseline"),
        ("vague_reference_graph", "baseline"),
        ("vague_reference_graph", "baseline"),
        ("preference_recall", "baseline"),
        ("preference_recall", "baseline"),
        ("preference_recall", "baseline"),
    ]


def test_select_llm_sample_runs_expands_both_variants() -> None:
    cases = [
        cli.load_eval_case(
            Path("tests/fixtures/memory_eval_cases/vague_reference_graph.json")
        ),
    ]

    selected = cli.select_llm_sample_runs(
        cases,
        case_ids=["vague_reference_graph"],
        repeat_count=2,
        evidence_prompt_mode="both",
    )

    assert [(run.case.id, run.prompt_variant, run.repeat_index) for run in selected] == [
        ("vague_reference_graph", "baseline", 0),
        ("vague_reference_graph", "coached", 0),
        ("vague_reference_graph", "baseline", 1),
        ("vague_reference_graph", "coached", 1),
    ]


def test_select_llm_sample_runs_rejects_repeat_count_below_one() -> None:
    cases = [
        cli.load_eval_case(
            Path("tests/fixtures/memory_eval_cases/vague_reference_graph.json")
        ),
    ]

    with pytest.raises(ValueError):
        cli.select_llm_sample_runs(
            cases,
            case_ids=["vague_reference_graph"],
            repeat_count=0,
            evidence_prompt_mode="baseline",
        )


def test_select_llm_sample_runs_rejects_unknown_case_id() -> None:
    cases = [
        cli.load_eval_case(
            Path("tests/fixtures/memory_eval_cases/vague_reference_graph.json")
        ),
    ]

    with pytest.raises(ValueError, match="unknown case_id"):
        cli.select_llm_sample_runs(
            cases,
            case_ids=["missing_case"],
            repeat_count=1,
            evidence_prompt_mode="baseline",
        )


def test_provider_gate_without_real_llm_does_not_construct_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_provider(**_kwargs: Any) -> object:
        raise AssertionError("LLMProvider must not be constructed")

    monkeypatch.setattr(cli.agent_provider, "LLMProvider", fail_provider)
    args = argparse.Namespace(
        enable_real_llm=False,
        fake_provider=False,
        config="config.toml",
        timeout_s=60.0,
    )

    provider, model = cli.build_provider_for_llm_sample(args)

    assert provider is None
    assert model is None


def test_provider_gate_fake_provider_does_not_load_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_load_config(_path: str) -> object:
        raise AssertionError("config must not be loaded in fake-provider mode")

    monkeypatch.setattr(cli, "load_config", fail_load_config)
    args = argparse.Namespace(
        enable_real_llm=False,
        fake_provider=True,
        config="config.toml",
        timeout_s=60.0,
    )

    provider, model = cli.build_provider_for_llm_sample(args)

    assert isinstance(provider, cli.ScriptedLLMSampleProvider)
    assert model == "fake-model"


def test_provider_gate_real_llm_is_only_constructing_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[dict[str, Any]] = []

    class _Provider:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

    monkeypatch.setattr(cli.agent_provider, "LLMProvider", _Provider)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda _path: SimpleNamespace(
            api_key="sk-unit-test",
            base_url="https://example.test/v1",
            system_prompt="system",
            extra_body={},
            provider="openai",
            model="unit-model",
        ),
    )
    args = argparse.Namespace(
        enable_real_llm=True,
        fake_provider=False,
        config="config.toml",
        timeout_s=60.0,
    )

    provider, model = cli.build_provider_for_llm_sample(args)

    assert provider is not None
    assert model == "unit-model"
    assert created == [
        {
            "api_key": "sk-unit-test",
            "base_url": "https://example.test/v1",
            "system_prompt": "system",
            "extra_body": {},
            "request_timeout_s": 60.0,
            "provider_name": "openai",
        }
    ]


def test_memory_llm_sample_cli_requires_explicit_gate(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_llm_sample_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--limit",
            "3",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    payload = json.loads((out_dir / "memory_llm_sample_eval.json").read_text())
    assert payload["metrics"]["real_llm_enabled"] is False
    assert payload["metrics"]["case_count"] == 0
    assert (out_dir / "memory_llm_sample_eval.md").exists()


def test_memory_llm_sample_cli_fake_provider_writes_sanitized_reports(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_llm_sample_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--limit",
            "3",
            "--fake-provider",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_llm_sample_eval.json" in completed.stdout
    json_path = out_dir / "memory_llm_sample_eval.json"
    md_path = out_dir / "memory_llm_sample_eval.md"
    payload = json.loads(json_path.read_text())
    assert payload["metrics"]["phase6b_level"] == "real_llm_small_sample"
    assert payload["metrics"]["real_llm_enabled"] is False
    assert payload["metrics"]["case_count"] == 3
    assert payload["metrics"]["passed_case_count"] == 3
    assert md_path.exists()

    combined = json_path.read_text(encoding="utf-8") + "\n" + md_path.read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "你应该用什么语言回答我",
        "用户偏好中文回答",
        "用户在 Telegram 会话偏好中文回答",
        "三路召回结果使用 RRF 融合排序",
        "我应该用中文回答你。",
        "你在 Telegram 会话偏好中文回答。",
        "之前那个第三路方案属于三路召回，排序采用 RRF 融合排序。",
        "sk-test-secret",
        "fake-model-api-key",
    ):
        assert forbidden not in combined


def test_memory_llm_sample_cli_case_filter_repeat_and_answer_debug(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_llm_sample_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--case-id",
            "vague_reference_graph",
            "--repeat-count",
            "2",
            "--evidence-prompt-mode",
            "both",
            "--fake-provider",
            "--include-answer-debug",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "memory_llm_sample_eval.json" in completed.stdout
    payload = json.loads((out_dir / "memory_llm_sample_eval.json").read_text())
    assert payload["metrics"]["case_count"] == 4
    assert payload["metrics"]["repeat_count"] == 2
    assert payload["metrics"]["prompt_variant_mode"] == "both"
    assert payload["metrics"]["pass_count_by_prompt_variant"] == {
        "baseline": 2,
        "coached": 2,
    }
    assert [record["prompt_variant"] for record in payload["case_records"]] == [
        "baseline",
        "coached",
        "baseline",
        "coached",
    ]
    debug_files = sorted((workspace / "answer_debug").glob("*.json"))
    assert [path.name for path in debug_files] == [
        "0000-baseline-vague_reference_graph.json",
        "0001-coached-vague_reference_graph.json",
        "0002-baseline-vague_reference_graph.json",
        "0003-coached-vague_reference_graph.json",
    ]
    debug_payload = json.loads(debug_files[0].read_text(encoding="utf-8"))
    assert "answer_text" in debug_payload
    regular_report = (
        (out_dir / "memory_llm_sample_eval.json").read_text(encoding="utf-8")
        + (out_dir / "memory_llm_sample_eval.md").read_text(encoding="utf-8")
    )
    assert debug_payload["answer_text"] not in regular_report


def test_memory_llm_sample_cli_rejects_unknown_case_id(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_llm_sample_eval.py",
            "--case-root",
            "tests/fixtures/memory_eval_cases",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--case-id",
            "missing_case",
            "--fake-provider",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "unknown case_id" in completed.stderr
