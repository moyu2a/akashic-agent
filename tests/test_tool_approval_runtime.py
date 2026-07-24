from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.policies.tool_approval import build_approval_payload
from agent.policies.tool_approval_context import trusted_approval_from_runtime
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore


UTC = timezone.utc


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _runtime(tmp_path: Path, clock: MutableClock | None = None) -> ToolApprovalRuntime:
    return ToolApprovalRuntime(
        ToolApprovalStore(tmp_path / "approvals.db"),
        now_factory=clock or MutableClock(),
        approval_ttl=timedelta(minutes=5),
    )


def test_runtime_records_defer_and_payload_has_request_id_and_expiry(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    arguments = {"path": "notes.md", "content": "private"}

    record = runtime.record_defer_request(
        request_id="req-1",
        session_key="cli:session-1",
        channel="cli",
        chat_id="chat-1",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments=arguments,
    )
    payload = build_approval_payload(
        tool_name="write_file",
        arguments=arguments,
        action="defer",
        reason="risk_strategy_write_requires_approval",
        risk="write",
        approval_scope="tool_call",
        approval_request_id=record.approval_request_id,
        expires_at=record.expires_at,
    )

    assert record.approval_request_id
    assert record.expires_at
    assert payload["approval_request"]["approval_request_id"] == (
        record.approval_request_id
    )
    assert payload["approval_request"]["expires_at"] == record.expires_at
    assert "private" not in str(payload["approval_request"]["args_summary"])


def test_runtime_consume_requires_trusted_context(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    decision = runtime.consume_for_execution(
        trusted_context=None,
        request_id="req-1",
        session_key="cli:session-1",
        tool_name="write_file",
        approval_scope="tool_call",
        arguments={"path": "notes.md", "content": "private"},
    )

    assert decision.action == "not_applicable"
    assert decision.allows_invoker is False


def test_untrusted_model_supplied_approval_id_does_not_consume(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    arguments = {"path": "notes.md", "content": "private"}
    record = runtime.record_defer_request(
        request_id="req-1",
        session_key="cli:session-1",
        channel="cli",
        chat_id="chat-1",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments=arguments,
    )
    runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="user",
        now=datetime(2026, 7, 24, 10, 1, tzinfo=UTC),
    )

    decision = runtime.consume_for_execution(
        trusted_context=None,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        arguments={**arguments, "approval_request_id": record.approval_request_id},
    )

    assert decision.action == "not_applicable"
    assert runtime.store.get_request(record.approval_request_id).status == "approved"


def test_runtime_consume_requires_same_request_id_and_scope(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    arguments = {"path": "notes.md", "content": "private"}
    record = runtime.record_defer_request(
        request_id="req-1",
        session_key="cli:session-1",
        channel="cli",
        chat_id="chat-1",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments=arguments,
    )
    runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="user",
        now=datetime(2026, 7, 24, 10, 1, tzinfo=UTC),
    )
    trusted = trusted_approval_from_runtime(
        approval_request_id=record.approval_request_id,
        actor="user",
        source="status_command",
    )

    decision = runtime.consume_for_execution(
        trusted_context=trusted,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope="different_scope",
        arguments=arguments,
    )

    assert decision.action == "mismatch"
    assert decision.allows_invoker is False


def test_runtime_consume_expires_approved_request_at_resume_time(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    runtime = ToolApprovalRuntime(
        ToolApprovalStore(tmp_path / "approvals.db"),
        now_factory=clock,
        approval_ttl=timedelta(seconds=1),
    )
    arguments = {"path": "notes.md", "content": "private"}
    record = runtime.record_defer_request(
        request_id="req-1",
        session_key="cli:session-1",
        channel="cli",
        chat_id="chat-1",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments=arguments,
    )
    runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="user",
        now=clock(),
    )
    clock.now = clock.now + timedelta(seconds=2)
    trusted = trusted_approval_from_runtime(
        approval_request_id=record.approval_request_id,
        actor="user",
        source="status_command",
    )

    decision = runtime.consume_for_execution(
        trusted_context=trusted,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        arguments=arguments,
    )

    assert decision.action == "expired"
    assert decision.allows_invoker is False


def test_approval_db_path_from_workspace_resolves_and_creates_parent(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    db_path = ToolApprovalRuntime.approval_db_path_from_workspace(workspace)

    assert db_path == workspace.resolve() / "tool_approvals" / "approvals.db"
    assert db_path.parent.is_dir()
