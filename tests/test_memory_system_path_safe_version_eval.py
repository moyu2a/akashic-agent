from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from memory2.eval_quantitative_cases import build_quantitative_eval_cases


def _walk_report_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for child in value.values():
            keys.update(_walk_report_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_walk_report_keys(child))
        return keys
    return set()


def _raw_fixture_strings(cases: list[object]) -> list[str]:
    values: list[str] = []
    for case in cases:
        setup = getattr(case, "setup")
        query = str(setup.get("query") or "").strip()
        if query:
            values.append(query)
        for item in setup.get("memory_items", []):
            if isinstance(item, dict):
                summary = str(item.get("summary") or "").strip()
                if summary:
                    values.append(summary)
        for replacement in setup.get("memory_replacements", []):
            if isinstance(replacement, dict):
                for key in ("old_summary", "new_summary"):
                    summary = str(replacement.get(key) or "").strip()
                    if summary:
                        values.append(summary)
    return values


def _assert_report_is_private(payload: dict[str, object], markdown: str) -> None:
    forbidden_keys = {
        "raw_prompt",
        "prompt",
        "full_answer",
        "raw_answer",
        "session_text",
        "memory_summary",
        "raw_memory_summary",
    }
    assert not (forbidden_keys & _walk_report_keys(payload))
    selected_cases = (
        build_quantitative_eval_cases("common", case_pack="standard", limit=2)
        + build_quantitative_eval_cases("hard", case_pack="standard", limit=2)
    )
    report_text = json.dumps(payload, ensure_ascii=False) + "\n" + markdown
    for raw_value in _raw_fixture_strings(selected_cases):
        assert raw_value not in report_text
    assert (
        "根据 system path safe version governed contract，应只使用 allowed_evidence 回答。"
        not in report_text
    )
    assert "根据系统路径注入记忆回答。" not in report_text
    assert "没有可用记忆，无法确认。" not in report_text


def test_system_path_safe_version_cli_fake_provider_writes_sanitized_report(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--modes",
            "current,safe_version_shadow,safe_version_replace",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (out_dir / "system_path_safe_version_eval.md").read_text(
        encoding="utf-8"
    )
    assert markdown.startswith("# System Path Safe Version Governed")
    assert payload["metrics"]["evaluation_level"] == "system_path_safe_version_governed"
    assert payload["metrics"]["unique_case_count"] == 4
    assert payload["metrics"]["mode_count"] == 3
    assert payload["metrics"]["case_count"] == 12
    assert payload["metrics"]["fake_provider_enabled"] is True
    assert payload["metrics"]["real_llm_enabled"] is False
    assert "answer_rule_pass_rate" in payload["metrics"]
    assert "memory_grounding_pass_rate" in payload["metrics"]
    assert "forbidden_violation_rate" in payload["metrics"]
    assert "token_metrics_available" in payload["metrics"]
    assert payload["metrics"]["raw_query_included"] is False
    assert payload["metrics"]["raw_memory_summary_included"] is False
    assert payload["metrics"]["prompt_included"] is False
    assert payload["metrics"]["complete_response_included"] is False
    assert payload["metrics"]["conversation_log_included"] is False
    assert "safe_version_replace" in payload["metrics"]["mode_summaries"]
    assert (
        payload["metrics"]["mode_summaries"]["safe_version_shadow"][
            "contract_generation_success_rate"
        ]
        == 100.0
    )
    assert (
        payload["metrics"]["mode_summaries"]["safe_version_shadow"][
            "post_check_shadow_enabled_rate"
        ]
        == 100.0
    )
    assert (
        payload["metrics"]["mode_summaries"]["safe_version_replace"][
            "post_check_shadow_enabled_rate"
        ]
        == 100.0
    )
    assert (
        payload["metrics"]["mode_summaries"]["current"][
            "post_check_shadow_enabled_rate"
        ]
        == 0.0
    )
    current = payload["metrics"]["mode_summaries"]["current"]
    replace = payload["metrics"]["mode_summaries"]["safe_version_replace"]
    assert "answer_success_count" in current
    assert "answer_rule_pass_rate" in current
    assert "memory_grounding_pass_rate" in current
    assert "forbidden_violation_rate" in current
    assert "avg_total_token_count" in current
    assert "avg_latency_ms" in current
    assert replace["contract_generation_success_rate"] == 100.0
    assert replace["post_check_shadow_enabled_rate"] == 100.0
    assert (
        "| mode | cases | answer_success | answer_rate | grounding_rate | "
        "forbidden_rate | contract_success | post_check_shadow | avg_tokens | "
        "avg_latency_ms |"
    ) in markdown
    assert all("post_check_shadow" in row for row in payload["cases"])
    for row in payload["cases"]:
        assert "answer_rule_passed" in row
        assert "memory_grounding_passed" in row
        assert "expected_memory_used" in row
        assert "forbidden_contains_violation_count" in row
        assert "failures" in row
        assert "answer_passed" not in row
    assert payload["metrics"]["replacement_seeded_count"] > 0
    version_rows = [
        row
        for row in payload["cases"]
        if row["mode"] in {"safe_version_shadow", "safe_version_replace"}
        and row.get("replacement_seeded_count", 0) > 0
    ]
    assert version_rows
    assert all(
        row["safe_version_contract"]["version_boundary"]["replacement_count"] > 0
        for row in version_rows
    )
    _assert_report_is_private(payload, markdown)


def test_system_path_safe_version_cli_rejects_fake_and_real_flags(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--enable-real-llm",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert (
        "--fake-provider and --enable-real-llm cannot be used together"
        in completed.stderr
    )


def test_system_path_safe_version_fake_provider_rows_are_answer_scored(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--modes",
            "current,safe_version_replace",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(
            encoding="utf-8"
        )
    )
    metrics = payload["metrics"]
    assert metrics["fake_provider_enabled"] is True
    assert metrics["real_llm_enabled"] is False
    assert "answer_rule_pass_rate" in metrics
    assert "memory_grounding_pass_rate" in metrics
    assert "forbidden_violation_rate" in metrics
    assert "token_metrics_available" in metrics
    for row in payload["cases"]:
        assert "answer_rule_passed" in row
        assert "memory_grounding_passed" in row
        assert "expected_memory_used" in row
        assert "forbidden_contains_violation_count" in row
        assert "failures" in row
        assert "answer_passed" not in row


def test_system_path_safe_version_real_provider_builder_requires_api_key(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    import scripts.run_memory_system_path_safe_version_eval as cli

    args = SimpleNamespace(
        fake_provider=False,
        enable_real_llm=True,
        config=str(tmp_path / "config.toml"),
        timeout_s=60.0,
    )
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: SimpleNamespace(
            api_key="",
            model="real-model",
            base_url="https://example.invalid",
            system_prompt="",
            extra_body={},
            provider="test-provider",
        ),
    )

    provider, model = cli.build_provider_for_system_path_safe_version(args)

    assert provider is None
    assert model == "real-model"


def test_system_path_safe_version_real_provider_builder_uses_config(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    import scripts.run_memory_system_path_safe_version_eval as cli

    created: dict[str, object] = {}

    class FakeRealProvider:
        def __init__(self, **kwargs: object) -> None:
            created.update(kwargs)

    args = SimpleNamespace(
        fake_provider=False,
        enable_real_llm=True,
        config=str(tmp_path / "config.toml"),
        timeout_s=12.5,
    )
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: SimpleNamespace(
            api_key="secret-key",
            model="real-model",
            base_url="https://example.invalid",
            system_prompt="system",
            extra_body={"x": 1},
            provider="test-provider",
        ),
    )
    monkeypatch.setattr(cli.agent_provider, "LLMProvider", FakeRealProvider)

    provider, model = cli.build_provider_for_system_path_safe_version(args)

    assert isinstance(provider, FakeRealProvider)
    assert model == "real-model"
    assert created["api_key"] == "secret-key"
    assert created["request_timeout_s"] == 12.5
    assert created["provider_name"] == "test-provider"
