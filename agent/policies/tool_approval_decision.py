from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ApprovalDecisionAction = Literal[
    "pending",
    "approved",
    "denied",
    "expired",
    "consumed",
    "executed",
    "execution_failed",
    "not_found",
    "mismatch",
    "not_applicable",
]


@dataclass(frozen=True)
class ToolApprovalDecision:
    action: ApprovalDecisionAction
    reason: str
    approval_request_id: str = ""
    request_id: str = ""
    session_key: str = ""
    tool_name: str = ""
    approval_scope: str = "tool_call"
    args_hash: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def allows_invoker(self) -> bool:
        return self.action == "consumed"
