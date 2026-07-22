from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.policies.tool_approval import canonical_args_hash, summarize_arguments


@dataclass(frozen=True)
class ToolAuditEvent:
    event_type: str
    request_id: str
    session_key: str
    channel: str
    chat_id: str
    tool_name: str
    source: str
    risk: str
    policy_action: str
    policy_reason: str
    args_hash: str
    args_summary: dict[str, object] = field(default_factory=dict)
    invoker_reached: bool = False
    invoker_succeeded: bool = False

    def to_trace_metadata(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "request_id": self.request_id,
            "session_key": self.session_key,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "tool_name": self.tool_name,
            "source": self.source,
            "risk": self.risk,
            "policy_action": self.policy_action,
            "policy_reason": self.policy_reason,
            "args_hash": self.args_hash,
            "args_summary": dict(self.args_summary),
            "invoker_reached": self.invoker_reached,
            "invoker_succeeded": self.invoker_succeeded,
        }


def build_tool_audit_event(
    *,
    request_id: str,
    session_key: str,
    channel: str,
    chat_id: str,
    tool_name: str,
    source: str,
    risk: str,
    policy_action: str,
    policy_reason: str,
    arguments: dict[str, Any],
    invoker_reached: bool,
    invoker_succeeded: bool,
) -> ToolAuditEvent:
    return ToolAuditEvent(
        event_type="tool_invocation_policy_decision",
        request_id=request_id,
        session_key=session_key,
        channel=channel,
        chat_id=chat_id,
        tool_name=tool_name,
        source=source,
        risk=risk,
        policy_action=policy_action,
        policy_reason=policy_reason,
        args_hash=canonical_args_hash(arguments),
        args_summary=summarize_arguments(arguments),
        invoker_reached=invoker_reached,
        invoker_succeeded=invoker_succeeded,
    )
