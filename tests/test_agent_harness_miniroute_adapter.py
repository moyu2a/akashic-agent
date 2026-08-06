from __future__ import annotations

import json

from eval.agent_harness.adapters import task_from_miniroute_record


def test_miniroute_adapter_keeps_five_field_schema() -> None:
    record = {
        "conversations": [
            {
                "role": "user",
                "content": "只输出 JSON。\n\n用户请求：查记忆",
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "intent": "memory_query",
                        "need_memory": True,
                        "need_tools": False,
                        "tool_scope": ["memory_tools"],
                        "risk_level": "read_only",
                    }
                ),
            },
        ]
    }

    task = task_from_miniroute_record(record, case_id="route-001")

    assert task.router_parse_ok is True
    assert task.router_decision is not None
    assert set(task.router_decision) == {
        "intent",
        "need_memory",
        "need_tools",
        "tool_scope",
        "risk_level",
    }
    assert "json_valid" not in task.router_decision


def test_miniroute_adapter_keeps_parse_failure_outside_decision() -> None:
    record = {
        "conversations": [
            {"role": "user", "content": "只输出 JSON。\n\n用户请求：查记忆"},
            {"role": "assistant", "content": "{not-json"},
        ]
    }

    task = task_from_miniroute_record(record, case_id="route-002")

    assert task.router_parse_ok is False
    assert task.router_decision is None
    assert task.router_parse_errors
