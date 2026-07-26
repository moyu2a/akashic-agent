from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from pathlib import Path

from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_approval import canonical_args_hash


def test_payload_vault_stores_exact_file_tool_arguments_privately(
    tmp_path: Path,
) -> None:
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))
    arguments = {"path": "notes.md", "content": "raw-secret-content"}

    record = vault.put_payload(
        approval_request_id="approval-1",
        request_id="call-1",
        session_key="cli:test",
        tool_name="write_file",
        approval_scope="tool_call",
        args_hash=canonical_args_hash(arguments),
        arguments=arguments,
        created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        expires_at="2026-07-26T09:15:00+00:00",
    )
    loaded = vault.get_payload("approval-1")

    assert loaded is not None
    assert loaded.record == record
    assert loaded.arguments == arguments
    assert (
        json.loads(record.payload_path.read_text(encoding="utf-8"))["arguments"]
        == arguments
    )
    assert stat.S_IMODE(record.payload_path.stat().st_mode) == 0o600


def test_payload_vault_rejects_unsupported_tools(tmp_path: Path) -> None:
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))

    try:
        vault.put_payload(
            approval_request_id="approval-shell",
            request_id="call-1",
            session_key="cli:test",
            tool_name="shell",
            approval_scope="tool_call",
            args_hash="hash",
            arguments={"command": "echo hi"},
            created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
            expires_at="2026-07-26T09:15:00+00:00",
        )
    except ValueError as exc:
        assert "unsupported managed side-effect tool" in str(exc)
    else:
        raise AssertionError("shell payload should not be accepted by P4 file vault")


def test_payload_vault_hash_mismatch_returns_none(tmp_path: Path) -> None:
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))
    arguments = {"path": "notes.md", "content": "raw-secret-content"}
    record = vault.put_payload(
        approval_request_id="approval-1",
        request_id="call-1",
        session_key="cli:test",
        tool_name="write_file",
        approval_scope="tool_call",
        args_hash=canonical_args_hash(arguments),
        arguments=arguments,
        created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        expires_at="2026-07-26T09:15:00+00:00",
    )
    payload = json.loads(record.payload_path.read_text(encoding="utf-8"))
    payload["args_hash"] = "tampered"
    record.payload_path.write_text(json.dumps(payload), encoding="utf-8")

    assert vault.get_payload("approval-1") is None
