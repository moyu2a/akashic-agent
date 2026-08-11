from __future__ import annotations

import json

from miniroute.evaluation.eval_route_v4 import (
    evaluate_text_pairs,
    extract_json,
    route_post_processing_chat,
    schema_valid,
)


def test_extract_json_distinguishes_strict_and_embedded_json() -> None:
    strict_obj, strict = extract_json('{"scene": "chat"}')
    embedded_obj, embedded = extract_json('说明：{"scene": "chat"}')

    assert strict_obj == {"scene": "chat"}
    assert strict is True
    assert embedded_obj == {"scene": "chat"}
    assert embedded is False


def test_schema_valid_accepts_only_v4_three_field_protocol() -> None:
    assert schema_valid(
        {"scene": "memory", "operation": "query", "request_mode": "single"}
    )
    assert not schema_valid(
        {
            "intent": "memory_query",
            "need_memory": True,
            "need_tools": False,
            "tool_scope": ["memory_tools"],
            "risk_level": "read_only",
        }
    )
    assert not schema_valid(
        {
            "scene": "trace",
            "operation": "query",
            "request_mode": "single",
        }
    )


def test_route_post_processing_chat_removes_empty_think_blocks() -> None:
    assert (
        route_post_processing_chat("<think>\n\n</think>\n\n用户请求")
        == "用户请求"
    )


def test_evaluate_text_pairs_reports_v4_metrics_and_danger_confusions() -> None:
    pairs = [
        (
            json.dumps({"scene": "chat", "operation": "answer", "request_mode": "single"}),
            json.dumps({"scene": "chat", "operation": "answer", "request_mode": "single"}),
        ),
        (
            json.dumps({"scene": "chat", "operation": "answer", "request_mode": "single"}),
            "解释文字\n"
            + json.dumps({"scene": "action", "operation": "execute", "request_mode": "single"}),
        ),
        (
            json.dumps({"scene": "unknown", "operation": "unknown", "request_mode": "single"}),
            json.dumps({"scene": "action", "operation": "execute", "request_mode": "single"}),
        ),
    ]

    result = evaluate_text_pairs(pairs)

    assert result.metrics["total"] == 3
    assert result.metrics["strict_json_ok"] == 2
    assert result.metrics["json_extract_ok"] == 3
    assert result.metrics["schema_ok"] == 3
    assert result.metrics["exact_ok"] == 1
    assert result.metrics["field_ok"]["scene"] == 1
    assert result.metrics["danger_confusions"]["chat_to_action"] == 1
    assert result.metrics["danger_confusions"]["unknown_to_action"] == 1
    assert len(result.errors) == 2
