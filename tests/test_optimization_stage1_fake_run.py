from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from agent.optimization.stage1_fake_run import (
    DEFAULT_STAGE1_CASES,
    Stage1Case,
    run_stage1_fake_profile_ab,
    write_stage1_report_json,
    write_stage1_report_markdown,
)
from agent.config_models import Config, WiringConfig
from agent.optimization.real_ab_run import (
    REAL_AB_PHASES,
    RealABRecord,
    expected_fast_path_for_profile,
    sanitize_preview,
    select_cost_latency_cases,
    select_real_ab_cases,
    summarize_real_ab_records,
    write_real_ab_json,
    write_real_ab_markdown,
)
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry


class _NamedTool(Tool):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"{self._name} test tool"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return "ok"


def test_stage1_fake_run_covers_mixed_cases_and_profiles() -> None:
    report = run_stage1_fake_profile_ab()

    assert report.metrics["mode"] == "fake"
    assert report.metrics["profile_count"] == 2
    assert report.metrics["case_count"] == len(DEFAULT_STAGE1_CASES)
    assert report.metrics["turn_count"] == 34
    assert report.metrics["all_profiles_pass"] is True
    assert set(report.profile_summaries) == {
        "baseline",
        "simple_fast_path",
    }
    assert report.profile_summaries["baseline"]["fast_hits"] == 0
    assert report.profile_summaries["simple_fast_path"]["fast_hits"] == 4
    assert report.profile_summaries["simple_fast_path"]["fail_count"] == 0


def test_stage1_fake_run_fast_path_only_hits_simple_cases() -> None:
    report = run_stage1_fake_profile_ab()

    optimized_records = [
        r for r in report.records if r.profile == "simple_fast_path"
    ]
    assert optimized_records
    assert all(
        record.category == "simple_no_tool"
        for record in optimized_records
        if record.simple_fast_path
    )
    assert all(
        not record.simple_fast_path
        for record in optimized_records
        if record.category != "simple_no_tool"
    )


def test_stage1_fake_run_writes_json_and_markdown(tmp_path: Path) -> None:
    report = run_stage1_fake_profile_ab()
    json_path = tmp_path / "stage1_fake.json"
    md_path = tmp_path / "stage1_fake.md"

    write_stage1_report_json(report, json_path)
    write_stage1_report_markdown(report, md_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["turn_count"] == 34
    assert payload["metrics"]["real_llm"] is False
    assert "simple_fast_path" in payload["profile_summaries"]
    text = md_path.read_text(encoding="utf-8")
    assert "# Optimization Profile Stage 1 Fake Run" in text
    assert "不代表真实 token/时延收益" in text
    assert "| profile | cases | pass | warn | fail | fast hits |" in text


def test_stage1_fake_run_can_report_warn_and_fail_for_custom_cases() -> None:
    report = run_stage1_fake_profile_ab(
        profiles=("baseline",),
        cases=(
            Stage1Case("warn_case", "simple_no_tool", "一句话说明 token。", True, "WARN"),
            Stage1Case("fail_case", "tool_task", "保存链接 https://example.com", False, "FAIL"),
        ),
    )

    row = report.profile_summaries["baseline"]
    assert report.metrics["all_profiles_pass"] is False
    assert row["warn_count"] == 1
    assert row["fail_count"] == 1


def test_stage1_fake_run_cli_writes_reports(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_optimization_stage1_fake_ab.py",
            "--out-dir",
            str(out_dir),
            "--profiles",
            "baseline,simple_fast_path",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "optimization_stage1_fake_ab.json" in completed.stdout
    payload = json.loads(
        (out_dir / "optimization_stage1_fake_ab.json").read_text(encoding="utf-8")
    )
    assert payload["metrics"]["turn_count"] == 34
    assert (out_dir / "optimization_stage1_fake_ab.md").exists()


def test_stage1_fake_run_cli_rejects_unknown_profile(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_optimization_stage1_fake_ab.py",
            "--out-dir",
            str(tmp_path / "reports"),
            "--profiles",
            "baseline,unknown_profile",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "profile is not allowed for stage 1" in completed.stderr


def test_stage1_fake_run_cli_rejects_later_stage_profile(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_optimization_stage1_fake_ab.py",
            "--out-dir",
            str(tmp_path / "reports"),
            "--profiles",
            "baseline,combined_p1",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "profile is not allowed for stage 1" in completed.stderr


def test_real_ab_phases_are_gated_and_stage_scoped() -> None:
    assert REAL_AB_PHASES["A"].profiles == ("baseline", "simple_fast_path")
    assert REAL_AB_PHASES["B"].profiles == ("baseline", "combined_p1")
    assert REAL_AB_PHASES["C"].profiles == ("baseline", "context20")
    assert REAL_AB_PHASES["D"].profiles == ("baseline", "tool_result_limit")
    assert len(select_real_ab_cases("A")) == 17
    assert {case.category for case in select_real_ab_cases("C")} == {"memory_task"}
    assert {case.category for case in select_real_ab_cases("D")} == {"tool_task"}


def test_real_ab_expected_fast_path_depends_on_profile() -> None:
    simple_case = next(case for case in DEFAULT_STAGE1_CASES if case.case_id == "simple_001")
    tool_case = next(case for case in DEFAULT_STAGE1_CASES if case.case_id == "tool_001")

    assert expected_fast_path_for_profile("baseline", simple_case) is False
    assert expected_fast_path_for_profile("simple_fast_path", simple_case) is True
    assert expected_fast_path_for_profile("combined_p1", simple_case) is True
    assert expected_fast_path_for_profile("simple_fast_path", tool_case) is False


def test_real_ab_cost_latency_cases_exclude_policy_only_cases() -> None:
    cases = select_cost_latency_cases("A")
    case_ids = {case.case_id for case in cases}

    assert "tool_001" not in case_ids
    assert all(case.allow_in_cost_latency for case in cases)
    assert all(case.suite != "disabled_tool_policy" for case in cases)


def test_real_ab_summary_marks_gate_failure_for_zero_usage_and_fast_path_leak() -> None:
    report = summarize_real_ab_records(
        [
            RealABRecord(
                run_id="run_test",
                phase="A",
                profile="simple_fast_path",
                case_id="tool_001",
                category="tool_task",
                prompt_preview="搜索内容",
                reply_preview="ok",
                correctness="PASS",
                simple_fast_path=True,
                expected_fast_path=False,
                tool_error_count=0,
                actual_prompt_tokens_sum=0,
                actual_total_tokens_sum=0,
                turn_duration_ms=1000,
                llm_duration_ms_sum=900,
                react_iteration_count=1,
                actual_tools=(),
                expected_tools=(),
                denied_tool_attempt_count=0,
                unregistered_tool_count=0,
                forbidden_reply_pattern_count=0,
                expected_tool_missing_count=0,
                note="unit",
            )
        ]
    )

    row = report.profile_summaries["simple_fast_path"]
    assert report.metrics["gate_pass"] is False
    assert row["missing_or_zero_usage_count"] == 1
    assert row["unexpected_fast_path_count"] == 1


def test_real_ab_summary_marks_gate_failure_for_functional_gate_violations() -> None:
    report = summarize_real_ab_records(
        [
            RealABRecord(
                run_id="run_test",
                phase="A",
                profile="baseline",
                case_id="tool_001",
                category="tool_task",
                prompt_preview="保存链接",
                reply_preview="<｜｜DSML｜｜tool_calls>",
                correctness="PASS",
                simple_fast_path=False,
                expected_fast_path=False,
                tool_error_count=0,
                actual_prompt_tokens_sum=100,
                actual_total_tokens_sum=120,
                turn_duration_ms=1000,
                llm_duration_ms_sum=900,
                react_iteration_count=1,
                actual_tools=(),
                expected_tools=("save_content_item",),
                denied_tool_attempt_count=1,
                unregistered_tool_count=1,
                forbidden_reply_pattern_count=1,
                expected_tool_missing_count=1,
                note="unit",
            )
        ]
    )

    row = report.profile_summaries["baseline"]
    assert report.metrics["gate_pass"] is False
    assert row["expected_tool_missing_count"] == 1
    assert row["denied_tool_attempt_count"] == 1
    assert row["unregistered_tool_count"] == 1
    assert row["forbidden_reply_pattern_count"] == 1


def test_real_ab_summary_includes_paired_deltas() -> None:
    report = summarize_real_ab_records(
        [
            RealABRecord(
                run_id="run_test",
                phase="A",
                profile="baseline",
                case_id="simple_001",
                category="simple_no_tool",
                prompt_preview="p",
                reply_preview="r",
                correctness="PASS",
                simple_fast_path=False,
                expected_fast_path=False,
                tool_error_count=0,
                actual_prompt_tokens_sum=100,
                actual_total_tokens_sum=120,
                turn_duration_ms=1000,
                llm_duration_ms_sum=900,
                react_iteration_count=1,
                actual_tools=(),
                expected_tools=(),
                denied_tool_attempt_count=0,
                unregistered_tool_count=0,
                forbidden_reply_pattern_count=0,
                expected_tool_missing_count=0,
                note="unit",
            ),
            RealABRecord(
                run_id="run_test",
                phase="A",
                profile="simple_fast_path",
                case_id="simple_001",
                category="simple_no_tool",
                prompt_preview="p",
                reply_preview="r",
                correctness="PASS",
                simple_fast_path=True,
                expected_fast_path=True,
                tool_error_count=0,
                actual_prompt_tokens_sum=40,
                actual_total_tokens_sum=60,
                turn_duration_ms=500,
                llm_duration_ms_sum=450,
                react_iteration_count=1,
                actual_tools=(),
                expected_tools=(),
                denied_tool_attempt_count=0,
                unregistered_tool_count=0,
                forbidden_reply_pattern_count=0,
                expected_tool_missing_count=0,
                note="unit",
            ),
        ]
    )

    delta = report.paired_deltas["simple_fast_path"]
    assert delta["paired_case_count"] == 1
    assert delta["total_tokens_delta_pct"] == -50.0
    assert delta["turn_latency_delta_pct"] == -50.0


def test_real_ab_report_writers_emit_gate_status_without_raw_secret(tmp_path: Path) -> None:
    report = summarize_real_ab_records(
        [
            RealABRecord(
                run_id="run_test",
                phase="A",
                profile="baseline",
                case_id="simple_001",
                category="simple_no_tool",
                prompt_preview=sanitize_preview("token=secret-value 请回答"),
                reply_preview=sanitize_preview("Bearer abcdefghijklmnopqrstuvwxyz"),
                correctness="PASS",
                simple_fast_path=False,
                expected_fast_path=False,
                tool_error_count=0,
                actual_prompt_tokens_sum=100,
                actual_total_tokens_sum=120,
                turn_duration_ms=1000,
                llm_duration_ms_sum=900,
                react_iteration_count=1,
                actual_tools=(),
                expected_tools=(),
                denied_tool_attempt_count=0,
                unregistered_tool_count=0,
                forbidden_reply_pattern_count=0,
                expected_tool_missing_count=0,
                note="unit",
            )
        ]
    )
    json_path = tmp_path / "real_ab.json"
    md_path = tmp_path / "real_ab.md"

    write_real_ab_json(report, json_path)
    write_real_ab_markdown(report, md_path)

    raw_json = json_path.read_text(encoding="utf-8")
    payload = json.loads(raw_json)
    assert payload["metrics"]["gate_pass"] is True
    assert "secret-value" not in raw_json
    assert "abcdefghijklmnopqrstuvwxyz" not in raw_json
    text = md_path.read_text(encoding="utf-8")
    assert "# Optimization Real LLM Gated A/B" in text
    assert "gate_pass" in text


def test_real_ab_cli_requires_explicit_real_llm_gate(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_optimization_real_ab.py",
            "--phase",
            "A",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "--enable-real-llm is required" in completed.stderr


def test_real_ab_cli_rejects_unknown_phase(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_optimization_real_ab.py",
            "--phase",
            "Z",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--enable-real-llm",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "unknown real A/B phase" in completed.stderr


def test_real_ab_runtime_config_disables_noisy_or_side_effect_toolsets() -> None:
    from scripts.run_optimization_real_ab import _sanitize_runtime_config

    cfg = Config(
        provider="fake",
        model="fake-model",
        api_key="fake-key",
        system_prompt="test",
        wiring=WiringConfig(
            toolsets=["meta_common", "spawn", "schedule", "mcp", "doc_rag", "task_plan"]
        ),
    )

    _sanitize_runtime_config(cfg)

    assert cfg.optimization.enabled is True
    assert cfg.peer_agents == []
    assert cfg.memory_optimizer_enabled is False
    assert cfg.spawn_enabled is False
    assert cfg.tool_search_enabled is False
    assert cfg.wiring.toolsets == ["meta_common", "schedule"]


def test_real_ab_cost_latency_runtime_strips_side_effect_tools() -> None:
    from scripts.run_optimization_real_ab import _strip_cost_latency_side_effect_tools

    registry = ToolRegistry()
    for name in (
        "read_file",
        "list_dir",
        "search_messages",
        "recall_memory",
        "shell",
        "task_output",
        "task_stop",
        "write_file",
        "edit_file",
        "message_push",
        "memorize",
        "forget_memory",
    ):
        registry.register(_NamedTool(name), always_on=True)

    runtime = type("_Runtime", (), {"tools": registry})()

    _strip_cost_latency_side_effect_tools(runtime)

    assert {"read_file", "list_dir", "search_messages", "recall_memory"} <= (
        registry.get_registered_names()
    )
    assert not {
        "shell",
        "task_output",
        "task_stop",
        "write_file",
        "edit_file",
        "message_push",
        "memorize",
        "forget_memory",
    } & registry.get_registered_names()
