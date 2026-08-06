from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from eval.agent_harness.protocol import RunManifest, TaskSpec


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="run-legacy",
        git_sha="abc123",
        dataset_version="duck-fixtures",
        dataset_hash="hash",
        model="fixture-model",
        provider="fixture-provider",
        config_hash="cfg",
        governance_profile="shadow-only",
        environment_kind="legacy-adapter",
        seed=11,
        repeat_index=0,
        runner_version="phase1b",
    )


def _task(case_id: str = "case-001", category: str = "memory") -> TaskSpec:
    return TaskSpec(case_id=case_id, category=category)


def _event_types(result: object) -> list[str]:
    return [str(event["event_type"]) for event in result.events]


def test_memory_offline_adapter_marks_retrieval_shadow_without_tool_execution() -> None:
    from eval.agent_harness.legacy_adapters.memory import MemoryOfflineAdapter

    trace = SimpleNamespace(
        feature_name="tri_retrieval",
        baseline_result={"ids": ["m1"]},
        experimental_result={"ids": ["m1", "m2"]},
        metrics={
            "recall_at_k": None,
            "secret": "do-not-copy",
            "raw_prompt": "user private prompt",
        },
    )
    profile = SimpleNamespace(
        profile="all",
        enabled=True,
        trace_features=("tri_retrieval",),
        traces={"tri_retrieval": trace},
        recalled_ids=("m1",),
        injected_ids=("m1", "m2"),
        metrics={"trace_count": 1, "latency_ms": None},
        failures=(),
        passed=True,
    )
    case_result = SimpleNamespace(
        case_id="mem-offline-001",
        category="memory",
        phase_targets=("retrieval",),
        profiles={"all": profile},
        failures=(),
        passed=True,
    )

    result = MemoryOfflineAdapter().adapt_case_result(
        case_result,
        task=_task("mem-offline-001"),
        manifest=_manifest(),
    )

    assert result.status == "PASS"
    assert result.outcome_passed is True
    assert result.final_reply == ""
    assert result.metrics["execution_mode"] == "memory_offline"
    assert result.metrics["real_llm"] is False
    assert result.metrics["trace_kind"] == "retrieval_shadow"
    assert result.metrics["latency_ms"] is None
    assert result.metrics["metric_provenance"]["latency_ms"] == "missing:not_recorded"
    assert "retrieval_shadow_observed" in _event_types(result)
    assert "tool_executed" not in _event_types(result)
    rendered_events = repr(result.events)
    assert "raw_prompt" not in rendered_events
    assert "do-not-copy" not in rendered_events


def test_memory_online_adapter_preserves_real_usage_and_splits_failure_types() -> None:
    from eval.agent_harness.legacy_adapters.memory import MemoryOnlineAdapter

    infra_case = SimpleNamespace(
        case_id="mem-online-timeout",
        category="memory",
        profile_name="chain_all_on",
        prompt_variant="coached",
        repeat_index=0,
        passed=False,
        answer_rule_passed=False,
        memory_grounding_passed=False,
        expected_memory_used=False,
        forbidden_contains_violation_count=0,
        latency_ms=823,
        prompt_token_count=101,
        completion_token_count=22,
        total_token_count=123,
        token_metrics_available=True,
        provider_error=False,
        timeout=True,
        answer_length=0,
        evidence_source="real AgentLoop answer scoring",
        used_memory_id_count=0,
        failures=("provider timeout",),
        answer_post_check_shadow={"shadow_enabled": True},
    )
    business_case = SimpleNamespace(
        **{
            **infra_case.__dict__,
            "case_id": "mem-online-business",
            "passed": False,
            "provider_error": False,
            "timeout": False,
            "failures": ("memory_grounding_failed",),
        }
    )

    infra = MemoryOnlineAdapter().adapt_case_result(
        infra_case,
        task=_task("mem-online-timeout"),
        manifest=_manifest(),
    )
    business = MemoryOnlineAdapter().adapt_case_result(
        business_case,
        task=_task("mem-online-business"),
        manifest=_manifest(),
    )

    assert infra.metrics["execution_mode"] == "memory_online"
    assert infra.metrics["real_llm"] is True
    assert infra.metrics["latency_ms"] == 823
    assert infra.metrics["prompt_tokens"] == 101
    assert infra.metrics["completion_tokens"] == 22
    assert infra.metrics["total_tokens"] == 123
    assert infra.metrics["token_metrics_available"] is True
    assert infra.metrics["provider_error"] is False
    assert infra.metrics["timeout"] is True
    assert infra.metrics["failure_class"] == "infra"
    assert infra.failures == ("infra:timeout", "provider timeout")
    assert business.metrics["failure_class"] == "business"
    assert business.failures == ("business:memory_grounding_failed",)


def test_cost_latency_adapter_is_report_only_and_keeps_paired_ab_metrics() -> None:
    from eval.agent_harness.legacy_adapters.cost_latency import CostLatencyAdapter

    baseline = SimpleNamespace(
        run_id="real-ab",
        phase="A",
        profile="baseline",
        case_id="tool-001",
        category="tool_task",
        prompt_preview="api_key=should-not-enter-events",
        reply_preview="secret reply",
        correctness="PASS",
        simple_fast_path=False,
        expected_fast_path=False,
        tool_error_count=0,
        actual_prompt_tokens_sum=200,
        actual_total_tokens_sum=260,
        turn_duration_ms=1000,
        llm_duration_ms_sum=700,
        react_iteration_count=4,
        actual_tools=("search",),
        expected_tools=("search",),
        denied_tool_attempt_count=0,
        unregistered_tool_count=0,
        forbidden_reply_pattern_count=0,
        expected_tool_missing_count=0,
        note="",
    )
    candidate = SimpleNamespace(
        **{
            **baseline.__dict__,
            "profile": "simple_fast_path",
            "actual_prompt_tokens_sum": 150,
            "actual_total_tokens_sum": 190,
            "turn_duration_ms": 750,
            "llm_duration_ms_sum": 500,
            "react_iteration_count": 2,
            "tool_error_count": 1,
        }
    )

    adapter = CostLatencyAdapter()
    results = adapter.adapt_records([baseline, candidate], manifest=_manifest())
    candidate_result = [
        item for item in results if item.episode_id.endswith("simple_fast_path")
    ][0]

    assert not hasattr(adapter, "run_episode")
    assert candidate_result.metrics["execution_mode"] == "cost_latency_report"
    assert candidate_result.metrics["report_only"] is True
    assert candidate_result.metrics["paired"] is True
    assert candidate_result.metrics["ab_pair"]["baseline_total_tokens"] == 260
    assert candidate_result.metrics["ab_pair"]["candidate_total_tokens"] == 190
    assert candidate_result.metrics["ab_pair"]["total_tokens_delta"] == -70
    assert candidate_result.metrics["ab_pair"]["turn_latency_delta_ms"] == -250
    assert candidate_result.metrics["react_iteration_count"] == 2
    assert candidate_result.metrics["tool_error_count"] == 1
    assert candidate_result.metrics["actual_tools"] == ("search",)
    assert "tool_executed" not in _event_types(candidate_result)
    assert "should-not-enter-events" not in repr(candidate_result.events)
    assert "secret reply" not in repr(candidate_result.events)


def test_cost_latency_adapter_reads_real_ab_json_records(tmp_path: Path) -> None:
    import json

    from eval.agent_harness.legacy_adapters.cost_latency import CostLatencyAdapter

    report = {
        "metrics": {"real_llm": True},
        "records": [
            {
                "run_id": "real-ab",
                "phase": "A",
                "profile": "baseline",
                "case_id": "tool-001",
                "category": "tool_task",
                "prompt_preview": "safe preview",
                "reply_preview": "safe reply",
                "correctness": "PASS",
                "simple_fast_path": False,
                "expected_fast_path": False,
                "tool_error_count": 0,
                "actual_prompt_tokens_sum": 200,
                "actual_total_tokens_sum": 260,
                "turn_duration_ms": 1000,
                "llm_duration_ms_sum": 700,
                "react_iteration_count": 4,
                "actual_tools": ["search"],
                "expected_tools": ["search"],
                "denied_tool_attempt_count": 0,
                "unregistered_tool_count": 0,
                "forbidden_reply_pattern_count": 0,
                "expected_tool_missing_count": 0,
                "note": "",
            }
        ],
    }
    path = tmp_path / "real-ab.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    results = CostLatencyAdapter().adapt_report_file(path, manifest=_manifest())

    assert len(results) == 1
    assert results[0].episode_id == "tool-001-baseline"
    assert results[0].metrics["report_only"] is True
    assert results[0].metrics["metric_provenance"]["total_tokens"] == "real_ab_record"


def test_shadow_adapter_keeps_boundaries_and_excludes_shadow_from_main_gate() -> None:
    from eval.agent_harness.legacy_adapters.shadow import ShadowAdapter

    adapter = ShadowAdapter()
    external = adapter.adapt_external_benchmark(
        name="external-suite",
        case_id="ext-001",
        metrics={"latency_ms": None, "score": 0.77},
        passed=True,
        manifest=_manifest(),
        historical=True,
    )
    governance = adapter.adapt_tool_governance_branch(
        branch_name="tool-governance-p4",
        case_id="gov-001",
        decision={"policy_action": "deny", "risk_level": "high_risk"},
        metrics={"tool_error_count": None},
        passed=False,
        manifest=_manifest(),
    )
    miniroute = adapter.adapt_miniroute_envelope(
        case_id="route-001",
        parse_envelope={
            "json_valid": True,
            "errors": [],
            "decision": {
                "intent": "memory_query",
                "need_memory": True,
                "need_tools": False,
                "tool_scope": ["memory_tools"],
                "risk_level": "read_only",
                "json_valid": False,
                "extra": "drop-me",
            },
        },
        manifest=_manifest(),
    )

    assert external.metrics["benchmark_kind"] == "external"
    assert external.metrics["historical"] is True
    assert external.metrics["main_gate_eligible"] is False
    assert (
        external.metrics["metric_provenance"]["latency_ms"] == "missing:external-suite"
    )
    assert governance.metrics["benchmark_kind"] == "tool_governance_branch"
    assert governance.metrics["main_gate_eligible"] is False
    assert governance.metrics["tool_error_count"] is None
    assert miniroute.metrics["benchmark_kind"] == "miniroute_shadow"
    assert miniroute.metrics["parse_envelope"]["json_valid"] is True
    assert set(miniroute.metrics["decision"]) == {
        "intent",
        "need_memory",
        "need_tools",
        "tool_scope",
        "risk_level",
    }
    assert "json_valid" not in miniroute.metrics["decision"]
    assert miniroute.metrics["main_gate_eligible"] is False
    assert all("tool_executed" != event for event in _event_types(miniroute))


def test_shadow_adapter_builds_a_formal_non_gate_summary() -> None:
    from eval.agent_harness.legacy_adapters.shadow import ShadowAdapter

    adapter = ShadowAdapter()
    observations = [
        adapter.adapt_external_benchmark(
            name="longmemeval",
            case_id="long-001",
            metrics={"score": 0.8},
            passed=True,
            manifest=_manifest(),
            historical=True,
        ),
        adapter.adapt_tool_governance_branch(
            branch_name="governance",
            case_id="gov-001",
            decision={"policy_action": "deny"},
            metrics={"forbidden_execution": 0},
            passed=True,
            manifest=_manifest(),
        ),
    ]

    summary = adapter.summarize(observations)

    assert summary["episode_count"] == 2
    assert summary["main_gate_eligible"] is False
    assert summary["by_kind"] == {
        "external": {"count": 1, "passed": 1, "failed": 0},
        "tool_governance_branch": {"count": 1, "passed": 1, "failed": 0},
    }


def test_memory_offline_adapter_invokes_the_legacy_eval_runner(tmp_path: Path) -> None:
    from eval.agent_harness.legacy_adapters.memory import MemoryOfflineAdapter

    runner = tmp_path / "legacy_memory_runner.py"
    runner.write_text(
        """
from pathlib import Path

def run_eval_case_files(root):
    Path(root / "offline-called.txt").write_text("legacy-offline", encoding="utf-8")
    return SimpleReport()

class SimpleReport:
    cases = []
""",
        encoding="utf-8",
    )
    adapter = MemoryOfflineAdapter(source_path=runner)

    tasks, results = adapter.run(tmp_path, manifest=_manifest())

    assert tasks == ()
    assert results == ()
    assert (tmp_path / "offline-called.txt").read_text(
        encoding="utf-8"
    ) == "legacy-offline"


def test_memory_online_adapter_invokes_the_legacy_comprehensive_runner(
    tmp_path: Path,
) -> None:
    from eval.agent_harness.legacy_adapters.memory import MemoryOnlineAdapter

    runner = tmp_path / "legacy_memory_online.py"
    runner.write_text(
        """
from pathlib import Path

async def run_comprehensive_online_eval(
    specs, workspace, provider, model, **kwargs
):
    Path(workspace / "online-called.txt").write_text(
        f"{len(specs)}|{model}|{kwargs['timeout_s']}|{kwargs['real_llm_enabled']}",
        encoding="utf-8",
    )
    return SimpleReport()

class SimpleReport:
    cases = []
""",
        encoding="utf-8",
    )
    adapter = MemoryOnlineAdapter(source_path=runner)

    report = asyncio.run(
        adapter.run(
            specs=[{"case_id": "case-1"}],
            workspace=tmp_path,
            provider=object(),
            model="real-model",
            timeout_s=23.0,
            real_llm_enabled=True,
        )
    )

    assert report.cases == []
    assert (tmp_path / "online-called.txt").read_text(encoding="utf-8") == (
        "1|real-model|23.0|True"
    )
