from __future__ import annotations

from agent.policies.tool_approval_decision import ToolApprovalDecision
from agent.policies.tool_audit import (
    build_tool_approval_audit_event,
    build_tool_audit_event,
)


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


def test_approval_lifecycle_audit_event_is_bounded() -> None:
    event = build_tool_approval_audit_event(
        ToolApprovalDecision(
            action="approved",
            reason="approval_approved",
            approval_request_id="approval-1",
            request_id="call-1",
            session_key="cli:session",
            tool_name="write_file",
            approval_scope="tool_call",
            args_hash="abc123",
            metadata={
                "actor": "status_command",
                "source": "passive",
                "risk": "write",
                "policy_reason": "risk_strategy_write_requires_approval",
                "created_at": "2026-07-24T01:00:00+00:00",
                "decided_at": "2026-07-24T01:01:00+00:00",
                "args_summary": {"content": {"sha256": "secret"}},
                "command": "rm file.txt",
                "content": "raw secret",
            },
        )
    )

    trace = event.to_trace_metadata()
    assert trace == {
        "event_type": "tool_approval_lifecycle",
        "approval_request_id": "approval-1",
        "request_id": "call-1",
        "session_key": "cli:session",
        "actor": "status_command",
        "source": "passive",
        "tool_name": "write_file",
        "risk": "write",
        "approval_scope": "tool_call",
        "policy_reason": "risk_strategy_write_requires_approval",
        "status": "approved",
        "args_hash": "abc123",
        "created_at": "2026-07-24T01:00:00+00:00",
        "decided_at": "2026-07-24T01:01:00+00:00",
        "consumed_at": "",
        "executed_at": "",
    }
    assert "args_summary" not in trace
    assert "command" not in trace
    assert "content" not in trace
