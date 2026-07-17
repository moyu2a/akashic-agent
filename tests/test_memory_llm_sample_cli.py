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
