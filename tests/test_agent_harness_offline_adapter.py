from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.agent_harness.legacy import ExecutionMode, IntegrationStatus
from eval.agent_harness.legacy_adapters.offline_trace import OfflineTraceAdapter
from eval.agent_harness.protocol import RunManifest


@dataclass
class _RawCaseResult:
    case_id: str = "offline-001"
    title: str = "offline case"
    status: str = "pass"
    score: float = 1.0
    evidence: str = "turn=12"
    issue: str = ""
    turn_ids: list[int] | None = None


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="offline-run",
        git_sha="abc123",
        dataset_version="offline",
        dataset_hash="hash",
        model="unknown",
        provider="recorded_trace",
        config_hash="cfg",
        governance_profile="historical",
        environment_kind="offline_trace",
        seed=0,
        repeat_index=0,
        runner_version="agent-harness-v2",
    )


def test_offline_adapter_converts_case_result_without_fake_cost_metrics() -> None:
    adapter = OfflineTraceAdapter(
        source_path=Path("my_md/test_docs/eval_suite/offline_trace_eval.py")
    )
    task = adapter.task_from_case_result(_RawCaseResult())

    result = adapter.convert_result(_RawCaseResult(), task=task, manifest=_manifest())

    assert task.case_id == "offline-001"
    assert result.status == "PASS"
    assert result.outcome_passed is True
    assert result.metrics["prompt_tokens"] is None
    assert result.metrics["latency_ms"] is None
    assert result.metrics["metric_provenance"]["prompt_tokens"] == "unavailable"
    assert result.metrics["execution_mode"] == ExecutionMode.OFFLINE_TRACE.value
    assert result.metrics["real_llm"] is None


def test_offline_adapter_preserves_partial_and_n_a_statuses() -> None:
    adapter = OfflineTraceAdapter(
        source_path=Path("my_md/test_docs/eval_suite/offline_trace_eval.py")
    )

    partial = adapter.convert_result(
        _RawCaseResult(status="partial", score=0.5, issue="missing evidence"),
        task=adapter.task_from_case_result(_RawCaseResult(status="partial")),
        manifest=_manifest(),
    )
    skipped = adapter.convert_result(
        _RawCaseResult(status="n/a", score=0.0, issue="not implemented"),
        task=adapter.task_from_case_result(_RawCaseResult(status="n/a")),
        manifest=_manifest(),
    )

    assert partial.status == "PARTIAL"
    assert partial.outcome_passed is False
    assert partial.failures == ("missing evidence",)
    assert skipped.status == "SKIP"
    assert skipped.metrics["excluded_from_score"] is True


def test_offline_adapter_emits_trace_events_without_raw_case_text() -> None:
    adapter = OfflineTraceAdapter(
        source_path=Path("my_md/test_docs/eval_suite/offline_trace_eval.py")
    )

    events = adapter.convert_events(_RawCaseResult(turn_ids=[12, 13]))

    assert [event["event_type"] for event in events] == [
        "episode_started",
        "turn_observed",
        "turn_observed",
        "episode_finished",
    ]
    assert events[1]["payload"] == {"turn_id": 12}
    assert "evidence" not in events[0]["payload"]


def test_offline_adapter_has_explicit_not_ready_main_gate_status() -> None:
    adapter = OfflineTraceAdapter(
        source_path=Path("my_md/test_docs/eval_suite/offline_trace_eval.py")
    )

    assert adapter.audit().integration_status is IntegrationStatus.ADAPTER_PASS


def test_offline_adapter_loader_registers_legacy_module_before_execution(
    tmp_path: Path,
) -> None:
    from eval.agent_harness.legacy_adapters.offline_trace import _load_runner_module

    runner = tmp_path / "runner.py"
    runner.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Case:\n"
        "    value: int\n",
        encoding="utf-8",
    )

    module = _load_runner_module(runner)

    assert module.Case(3).value == 3
