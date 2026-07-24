from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustedApprovalContext:
    approval_request_id: str
    actor: str
    source: str


def trusted_approval_from_runtime(
    *,
    approval_request_id: str,
    actor: str,
    source: str,
) -> TrustedApprovalContext:
    if not approval_request_id or not actor or not source:
        raise ValueError("trusted approval context requires id, actor, and source")
    return TrustedApprovalContext(
        approval_request_id=approval_request_id,
        actor=actor,
        source=source,
    )
