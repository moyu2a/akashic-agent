from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from eval.agent_harness.legacy_adapters.cost_latency import CostLatencyAdapter
from eval.agent_harness.legacy_adapters.deep_live import DeepLiveAdapter
from eval.agent_harness.legacy_adapters.live_ipc import IpcLiveAdapter
from eval.agent_harness.legacy_adapters.memory import MemoryOfflineAdapter
from eval.agent_harness.legacy_adapters.shadow import ShadowAdapter
from eval.agent_harness.protocol import RunManifest, TaskSpec
from eval.agent_harness.replay import verify_replay


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="cross-runner",
        git_sha="abc123",
        dataset_version="test",
        dataset_hash="hash",
        model="fixture",
        provider="fixture",
        config_hash="cfg",
        governance_profile="shadow",
        environment_kind="adapter",
        seed=1,
        repeat_index=0,
        runner_version="agent-harness-v2",
    )


def test_all_adapter_event_outputs_are_replay_and_privacy_safe() -> None:
    manifest = _manifest()
    live = IpcLiveAdapter(source_path=Path("legacy.py")).convert_result(
        {
            "case_id": "live-1",
            "status": "pass",
            "step_results": [
                {
                    "channel": "cli",
                    "text": "secret input",
                    "response": "secret reply",
                    "turn": {
                        "id": 1,
                        "tool_names": ["read_file"],
                        "tool_count": 1,
                    },
                }
            ],
        },
        task=TaskSpec(case_id="live-1", category="live"),
        manifest=manifest,
    )
    deep = DeepLiveAdapter(source_path=Path("legacy.py")).convert_result(
        {
            "case_id": "deep-1",
            "status": "pass",
            "step_results": [],
            "judge": {"verdict": "pass", "reason": "safe"},
        },
        task=TaskSpec(case_id="deep-1", category="deep"),
        manifest=manifest,
    )
    memory = MemoryOfflineAdapter().adapt_case_result(
        SimpleNamespace(
            case_id="memory-1",
            category="memory",
            profiles={},
            failures=(),
            passed=True,
        ),
        task=TaskSpec(case_id="memory-1", category="memory"),
        manifest=manifest,
    )
    cost = CostLatencyAdapter().adapt_records(
        [
            SimpleNamespace(
                phase="A",
                profile="baseline",
                case_id="cost-1",
                correctness="PASS",
                actual_prompt_tokens_sum=1,
                actual_total_tokens_sum=2,
                turn_duration_ms=3,
                llm_duration_ms_sum=1,
                react_iteration_count=1,
                tool_error_count=0,
                actual_tools=(),
            )
        ],
        manifest=manifest,
    )[0]
    shadow = ShadowAdapter().adapt_external_benchmark(
        name="fixture",
        case_id="shadow-1",
        metrics={"score": 1.0},
        passed=True,
        manifest=manifest,
        historical=True,
    )

    for result in (live, deep, memory, cost, shadow):
        assert verify_replay(result.events) is True
        rendered = json.dumps(result.events, ensure_ascii=False)
        assert "secret input" not in rendered
        assert "secret reply" not in rendered
