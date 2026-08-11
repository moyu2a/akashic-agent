from __future__ import annotations

import pytest

from miniroute.routing import (
    IntentDecision,
    RoutePropertyDecision,
    ToolRegistry,
    build_route_label,
    normalize_tool_scopes,
    operation_for_intent,
    route_label_from_payloads,
    reconcile_tool_scopes,
)


def test_operation_mapping_and_compound_request_are_internal_route_fields() -> None:
    assert operation_for_intent("memory_query") == "query"
    assert operation_for_intent("profile_update") == "update"
    assert operation_for_intent("tool_execution") == "execute"

    decision = IntentDecision(
        intent="task_plan",
        operation="plan",
        request_mode="compound",
    )
    assert decision.to_dict() == {
        "intent": "task_plan",
        "operation": "plan",
        "request_mode": "compound",
    }


def test_multiple_tool_scopes_are_deduplicated_and_none_is_removed() -> None:
    assert normalize_tool_scopes(
        ["none", "memory_tools", "content_tools", "memory_tools"]
    ) == ["memory_tools", "content_tools"]


def test_route_label_derives_need_tools_from_tool_scope() -> None:
    label = build_route_label(
        IntentDecision("file_read", "read"),
        RoutePropertyDecision(
            need_memory=False,
            tool_scope=["file_read_tools"],
            risk_level="read_only",
        ),
    )

    assert label.to_dict() == {
        "intent": "file_read",
        "need_memory": False,
        "need_tools": True,
        "tool_scope": ["file_read_tools"],
        "risk_level": "read_only",
    }


def test_unavailable_known_scope_is_rewritten_to_unknown_tools() -> None:
    registry = ToolRegistry.from_scopes(["memory_tools", "task_tools"])

    scopes, unavailable = reconcile_tool_scopes(
        ["memory_tools", "file_read_tools"],
        registry,
    )

    assert scopes == ["memory_tools", "unknown_tools"]
    assert unavailable == ("file_read_tools",)


def test_unknown_tool_scope_is_preserved_and_never_becomes_shell() -> None:
    registry = ToolRegistry.from_scopes(["shell_tools"])

    scopes, unavailable = reconcile_tool_scopes(["unknown_tools"], registry)

    assert scopes == ["unknown_tools"]
    assert unavailable == ()


def test_invalid_tool_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown tool scope"):
        normalize_tool_scopes(["calendar_tools"])


def test_route_label_can_be_composed_from_model_json_payloads() -> None:
    label = route_label_from_payloads(
        {
            "intent": "tool_execution",
            "operation": "execute",
            "request_mode": "single",
        },
        {
            "need_memory": False,
            "tool_scope": ["unknown_tools"],
            "risk_level": "read_only",
        },
    )

    assert label.tool_scope == ["unknown_tools"]
    assert label.need_tools is True
