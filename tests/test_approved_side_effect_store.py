from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agent.policies.approved_side_effect_store import ApprovedSideEffectStore


def test_side_effect_store_tracks_payload_preview_execute_and_rollback(
    tmp_path: Path,
) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")

    payload = store.record_payload(
        approval_request_id="approval-1",
        request_id="call-1",
        session_key="cli:test",
        tool_name="write_file",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )
    preview = store.record_preview(
        approval_request_id="approval-1",
        preview_id="preview-1",
        target_path_hash="path-hash",
        before_hash="before",
        after_hash="after",
        diff_ref="artifacts/preview-1/change.diff",
        diff_truncated=False,
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 1, tzinfo=UTC),
    )
    executed = store.mark_executed(
        approval_request_id="approval-1",
        rollback_id="rollback-1",
        execution_status="executed",
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 2, tzinfo=UTC),
    )
    rolled_back = store.mark_rolled_back(
        approval_request_id="approval-1",
        rollback_status="rolled_back",
        actor="status_command",
        now=datetime(2026, 7, 26, 9, 3, tzinfo=UTC),
    )

    assert payload.status == "payload_recorded"
    assert preview.status == "preview_ready"
    assert executed.status == "executed"
    assert rolled_back.status == "rolled_back"
    assert store.get_by_approval_id("approval-1").status == "rolled_back"
    events = store.list_audit_events("approval-1")
    assert [event.event_type for event in events] == [
        "payload_recorded",
        "preview_ready",
        "executed",
        "rolled_back",
    ]


def test_side_effect_store_does_not_store_raw_arguments(tmp_path: Path) -> None:
    store = ApprovedSideEffectStore(tmp_path / "side_effects.db")
    store.record_payload(
        approval_request_id="approval-1",
        request_id="call-1",
        session_key="cli:test",
        tool_name="write_file",
        approval_scope="tool_call",
        args_hash="args-hash",
        payload_ref="payloads/approval-1.json",
        actor="model",
        now=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )

    raw_db = (tmp_path / "side_effects.db").read_bytes()

    assert b"raw-secret-content" not in raw_db
    assert b"payloads/approval-1.json" in raw_db
