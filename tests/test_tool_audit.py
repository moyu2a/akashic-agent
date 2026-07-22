from __future__ import annotations

from agent.policies.tool_audit import build_tool_audit_event


def test_audit_event_contains_decision_and_argument_hash() -> None:
    event = build_tool_audit_event(
        request_id="call_1",
        session_key="cli:session",
        channel="cli",
        chat_id="chat",
        tool_name="write_file",
        source="passive",
        risk="write",
        policy_action="defer",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"path": "notes.md", "content": "hello"},
        invoker_reached=False,
        invoker_succeeded=False,
    )

    trace = event.to_trace_metadata()
    assert trace["event_type"] == "tool_invocation_policy_decision"
    assert trace["tool_name"] == "write_file"
    assert trace["policy_action"] == "defer"
    assert trace["args_hash"]
    assert trace["args_summary"]["content"]["sha256"]
    assert "preview" not in trace["args_summary"]["content"]
    assert trace["invoker_reached"] is False
