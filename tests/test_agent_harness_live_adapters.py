from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from eval.agent_harness.protocol import RunManifest


@dataclass
class _TurnEvidence:
    id: int | None = 42
    session_key: str = "session-a"
    user_msg: str = "private user text"
    output: str = "private assistant reply"
    tool_names: list[str] = field(default_factory=lambda: ["read_file"])
    tool_count: int = 1
    error: str = ""
    iteration_count: int | None = 3
    prompt_tokens: int | None = None
    cache_hit_tokens: int | None = None
    cache_prompt_tokens: int | None = None


@dataclass
class _StepResult:
    channel: str = "cli"
    text: str = "private user text"
    response: str = "private assistant reply"
    turn: _TurnEvidence = field(default_factory=_TurnEvidence)


@dataclass
class _JudgeResult:
    verdict: str = "fail"
    score: float = 0.1
    reason: "str" = "style issue only"
    failure_type: str = "judge_uncertain"


@dataclass
class _DeepCaseResult:
    case_id: str = "deep-001"
    title: str = "guarded boundary"
    category: str = "security"
    priority: str = "P0"
    risk_level: str = "guarded"
    status: str = "pass"
    score: float = 1.0
    failure_type: str = "none"
    step_results: list[_StepResult] = field(default_factory=lambda: [_StepResult()])
    issues: list[str] = field(default_factory=list)
    judge: _JudgeResult = field(default_factory=_JudgeResult)


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="live-run",
        git_sha="abc123",
        dataset_version="live",
        dataset_hash="hash",
        model="unknown",
        provider="legacy_ipc",
        config_hash="cfg",
        governance_profile="shadow",
        environment_kind="ipc_live",
        seed=0,
        repeat_index=0,
        runner_version="agent-harness-v2",
    )


def test_ipc_live_adapter_audit_and_json_load_cases(tmp_path: Path) -> None:
    from eval.agent_harness.legacy_adapters.live_ipc import (
        IntegrationStatus,
        IpcLiveAdapter,
        LegacyRunnerAdapter,
    )

    dataset = tmp_path / "cases.json"
    dataset.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "safe-001",
                        "title": "Safe case",
                        "category": "memory",
                        "priority": "P0",
                        "risk_level": "safe",
                        "execution_mode": "live",
                        "input": {"text": "remember this"},
                        "expected": {
                            "tool_calls": {
                                "must_include": ["read_file"],
                                "must_not_include": ["shell"],
                            }
                        },
                    },
                    {
                        "id": "guarded-001",
                        "category": "security",
                        "risk_level": "guarded",
                        "execution_mode": "live",
                        "input": {"text": "danger"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    adapter = IpcLiveAdapter(
        source_path=Path("my_md/test_docs/eval_suite/live_eval_runner.py")
    )

    source = adapter.audit()
    tasks = adapter.load_cases(dataset)

    assert isinstance(adapter, LegacyRunnerAdapter)
    assert source.source_name == "ipc_live"
    assert source.integration_status is IntegrationStatus.NOT_STARTED
    assert source.main_gate_allowed is False
    assert [task.case_id for task in tasks] == ["safe-001", "guarded-001"]
    assert tasks[0].steps == ({"role": "user", "text": "remember this"},)
    assert tasks[0].expected_tools == ("read_file",)
    assert tasks[0].forbidden_tools == ("shell",)
    assert tasks[1].risk_level == "guarded"


def test_ipc_live_adapter_dry_run_and_guarded_boundary(tmp_path: Path) -> None:
    from eval.agent_harness.legacy_adapters.live_ipc import IpcLiveAdapter

    adapter = IpcLiveAdapter(source_path=Path("legacy.py"))
    cases = [
        {"id": "safe", "risk_level": "safe", "execution_mode": "live"},
        {"id": "guarded", "risk_level": "guarded", "execution_mode": "live"},
        {"id": "offline", "risk_level": "safe", "execution_mode": "offline"},
    ]

    assert [case["id"] for case in adapter.select_cases(cases)] == ["safe"]
    assert [case["id"] for case in adapter.select_cases(cases, include_guarded=True)] == [
        "safe",
        "guarded",
    ]

    dry_result = adapter.convert_result(
        {
            "case_id": "safe",
            "status": "dry_run",
            "score": 0.0,
            "step_results": [],
            "issues": [],
        },
        task=adapter.task_from_case({"id": "safe", "category": "memory"}),
        manifest=_manifest(),
    )

    assert dry_result.status == "SKIP"
    assert dry_result.outcome_passed is False
    assert dry_result.metrics["dry_run"] is True
    assert dry_result.metrics["guarded_case"] is False


def test_ipc_live_adapter_classifies_timeout_connection_and_observe_errors() -> None:
    from eval.agent_harness.legacy_adapters.live_ipc import IpcLiveAdapter

    adapter = IpcLiveAdapter(source_path=Path("legacy.py"))
    task = adapter.task_from_case({"id": "ipc-errors", "category": "infra"})

    for raw_error, expected in (
        ("TimeoutError: waiting for reply", "timeout"),
        ("ConnectionError: IPC connection closed", "connection"),
        ("observe.db not found", "observe_missing"),
        ("observe turn not found", "observe_missing"),
    ):
        raw = {
            "case_id": "ipc-errors",
            "status": "fail",
            "score": 0.0,
            "issues": ["turn error exists"],
            "step_results": [
                {
                    "channel": "cli",
                    "text": "secret input",
                    "response": "",
                    "turn": {"error": raw_error},
                }
            ],
        }

        result = adapter.convert_result(raw, task=task, manifest=_manifest())

        assert result.status == "ERROR"
        assert result.metrics["failure_type"] == expected


def test_deep_live_adapter_keeps_judge_as_quality_and_events_replay_safe() -> None:
    from eval.agent_harness.legacy_adapters.deep_live import DeepLiveAdapter

    adapter = DeepLiveAdapter(
        source_path=Path("my_md/test_docs/eval_suite/deep_live_eval_runner.py")
    )
    task = adapter.task_from_case(
        {
            "id": "deep-001",
            "category": "security",
            "risk_level": "guarded",
            "expected": {
                "tool_calls": {
                    "must_include": ["read_file"],
                    "must_not_include": ["shell"],
                }
            },
        }
    )

    result = adapter.convert_result(_DeepCaseResult(), task=task, manifest=_manifest())

    assert result.status == "PASS"
    assert result.outcome_passed is True
    assert result.metrics["quality_judge"] == {
        "verdict": "fail",
        "score": 0.1,
        "reason": "style issue only",
        "failure_type": "judge_uncertain",
    }
    assert result.metrics["metric_provenance"]["prompt_tokens"] == "missing"
    assert result.metrics["prompt_tokens"] is None
    assert result.metrics["latency_ms"] is None
    assert all(event["run_id"] == "legacy-deep-live" for event in result.events)
    assert all("payload_hash" in event for event in result.events)
    for event in result.events:
        rendered = json.dumps(event["payload"], ensure_ascii=False)
        assert "private user text" not in rendered
        assert "private assistant reply" not in rendered
