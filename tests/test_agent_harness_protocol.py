from __future__ import annotations

import json

import pytest

from eval.agent_harness.events import EventLedger, event_to_dict
from eval.agent_harness.protocol import RunManifest, TaskSpec


def test_task_spec_preserves_current_miniroute_schema_without_json_valid() -> None:
    task = TaskSpec(
        case_id="route-001",
        category="router",
        router_decision={
            "intent": "memory_query",
            "need_memory": True,
            "need_tools": False,
            "tool_scope": ["memory_tools"],
            "risk_level": "read_only",
        },
        router_parse_ok=True,
    )

    payload = task.to_dict()

    assert payload["router_decision"]["tool_scope"] == ["memory_tools"]
    assert "json_valid" not in payload["router_decision"]
    assert task.router_parse_errors == ()


def test_task_spec_rejects_json_valid_inside_router_decision() -> None:
    with pytest.raises(ValueError, match="json_valid"):
        TaskSpec(
            case_id="route-002",
            category="router",
            router_decision={
                "intent": "chat",
                "need_memory": False,
                "need_tools": False,
                "tool_scope": ["none"],
                "risk_level": "none",
                "json_valid": True,
            },
        )


def test_manifest_and_task_spec_round_trip_json() -> None:
    task = TaskSpec(
        case_id="case-001",
        category="tool",
        steps=({"role": "user", "text": "列出当前目录"},),
        expected_tools=("list_dir",),
        forbidden_tools=("shell",),
        expected_outcome={"state": {"tool_called": "list_dir"}},
        grader_names=("outcome", "security"),
        repeat_count=3,
    )
    manifest = RunManifest(
        run_id="run-001",
        git_sha="abc123",
        dataset_version="v2",
        dataset_hash="hash",
        model="test-model",
        provider="fake",
        config_hash="cfg",
        governance_profile="full_governance",
        environment_kind="fake",
        seed=7,
        repeat_index=1,
        runner_version="0.1",
    )

    assert json.loads(json.dumps(task.to_dict()))["case_id"] == "case-001"
    assert json.loads(json.dumps(manifest.to_dict()))["run_id"] == "run-001"


def test_event_ledger_redacts_sensitive_values_and_hashes_payload() -> None:
    ledger = EventLedger(run_id="run-001", episode_id="case-001")
    event = ledger.append(
        "tool_requested",
        component="tool_executor",
        payload={
            "tool": "send_webhook",
            "api_key": "secret-value",
            "nested": {"password": "pw", "url": "https://example.test"},
        },
        turn_index=2,
    )

    rendered = event_to_dict(event)

    assert rendered["payload"]["api_key"] == "[REDACTED]"
    assert rendered["payload"]["nested"]["password"] == "[REDACTED]"
    assert rendered["payload"]["nested"]["url"] == "https://example.test"
    assert len(rendered["payload_hash"]) == 64
    assert rendered["event_index"] == 0


def test_event_ledger_event_indexes_are_monotonic() -> None:
    ledger = EventLedger(run_id="run-001", episode_id="case-001")
    first = ledger.append("episode_started", "runner", {})
    second = ledger.append("episode_finished", "runner", {})

    assert [first.event_index, second.event_index] == [0, 1]
