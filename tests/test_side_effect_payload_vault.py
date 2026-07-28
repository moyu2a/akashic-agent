from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent.policies import side_effect_payload_vault as vault_module
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


def test_payload_vault_stores_exact_shell_arguments_privately(tmp_path: Path) -> None:
    vault_root = SideEffectPayloadVault.root_for_workspace(tmp_path)
    shared_parent = vault_root.parent
    shared_parent.mkdir(parents=True)
    os.chmod(shared_parent, 0o755)
    vault = SideEffectPayloadVault(vault_root)
    arguments = {
        "command": "pytest tests/test_shell.py -q",
        "description": "run shell tests",
        "timeout": 30,
    }

    record = vault.put_payload(
        approval_request_id="approval-shell-1",
        request_id="call-shell-1",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash=canonical_args_hash(arguments),
        arguments=arguments,
        created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        expires_at="2026-07-26T09:15:00+00:00",
    )
    loaded = vault.get_payload("approval-shell-1")

    assert loaded is not None
    assert loaded.record == record
    assert loaded.arguments == arguments
    assert stat.S_IMODE(shared_parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(vault_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(record.payload_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(record.payload_path.stat().st_mode) == 0o600
    assert b"pytest tests/test_shell.py -q" in record.payload_path.read_bytes()


def test_payload_vault_rejects_unsupported_tools(tmp_path: Path) -> None:
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))

    try:
        vault.put_payload(
            approval_request_id="approval-shell",
            request_id="call-1",
            session_key="cli:test",
            tool_name="browser",
            approval_scope="tool_call",
            args_hash="hash",
            arguments={"command": "echo hi"},
            created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
            expires_at="2026-07-26T09:15:00+00:00",
        )
    except ValueError as exc:
        assert "unsupported managed side-effect tool" in str(exc)
    else:
        raise AssertionError("unsupported tool payload should not be accepted")


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


@pytest.mark.parametrize("symlink_component", ["tool_side_effects", "payloads"])
def test_payload_vault_rejects_managed_directory_symlink(
    tmp_path: Path, symlink_component: str
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    if symlink_component == "tool_side_effects":
        (tmp_path / "tool_side_effects").symlink_to(
            outside, target_is_directory=True
        )
    else:
        managed = tmp_path / "tool_side_effects"
        managed.mkdir()
        (managed / "payloads").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))

    assert list(outside.iterdir()) == []


def test_payload_vault_atomically_replaces_symlink_leaf_without_following_it(
    tmp_path: Path,
) -> None:
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))
    outside = tmp_path / "outside.json"
    outside.write_text("outside must remain unchanged", encoding="utf-8")
    payload_path = vault.root / "approval-leaf.json"
    payload_path.symlink_to(outside)
    arguments = {"command": "echo private"}

    record = vault.put_payload(
        approval_request_id="approval-leaf",
        request_id="call-leaf",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash=canonical_args_hash(arguments),
        arguments=arguments,
        created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        expires_at="2026-07-26T09:15:00+00:00",
    )

    assert outside.read_text(encoding="utf-8") == "outside must remain unchanged"
    assert record.payload_path.is_file()
    assert record.payload_path.is_symlink() is False
    assert vault.get_payload("approval-leaf").arguments == arguments


def test_payload_vault_creates_private_temp_file_before_atomic_replace(
    tmp_path: Path, monkeypatch
) -> None:
    open_calls = []
    replace_calls = []
    real_open = vault_module.os.open
    real_replace = vault_module.os.replace

    def recording_open(path, flags, mode=0o777, **kwargs):
        open_calls.append((Path(path), flags, mode))
        return real_open(path, flags, mode, **kwargs)

    def recording_replace(src, dst, **kwargs):
        replace_calls.append((Path(src), Path(dst)))
        return real_replace(src, dst, **kwargs)

    monkeypatch.setattr(vault_module.os, "open", recording_open)
    monkeypatch.setattr(vault_module.os, "replace", recording_replace)
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))
    arguments = {"command": "echo private"}

    record = vault.put_payload(
        approval_request_id="approval-mode",
        request_id="call-mode",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash=canonical_args_hash(arguments),
        arguments=arguments,
        created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        expires_at="2026-07-26T09:15:00+00:00",
    )

    assert any(
        mode == 0o600 and flags & os.O_EXCL and flags & os.O_CREAT
        for _, flags, mode in open_calls
    )
    assert replace_calls and replace_calls[-1][1].name == record.payload_path.name
    assert stat.S_IMODE(record.payload_path.stat().st_mode) == 0o600


def test_payload_vault_resolves_workspace_symlink_before_managed_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_link = tmp_path / "workspace-link"
    workspace_link.symlink_to(workspace, target_is_directory=True)

    root = SideEffectPayloadVault.root_for_workspace(workspace_link)
    vault = SideEffectPayloadVault(root)

    assert vault.root == workspace.resolve() / "tool_side_effects" / "payloads"


def test_payload_vault_read_rejects_root_replaced_with_symlink(
    tmp_path: Path,
) -> None:
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))
    arguments = {"command": "echo private"}
    record = vault.put_payload(
        approval_request_id="approval-read-root",
        request_id="call-read-root",
        session_key="cli:test",
        tool_name="shell",
        approval_scope="tool_call",
        args_hash=canonical_args_hash(arguments),
        arguments=arguments,
        created_at=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        expires_at="2026-07-26T09:15:00+00:00",
    )
    moved_root = vault.root.with_name("payloads-original")
    vault.root.rename(moved_root)
    attacker_root = tmp_path / "attacker-payloads"
    attacker_root.mkdir()
    (attacker_root / record.payload_path.name).write_bytes(
        moved_root.joinpath(record.payload_path.name).read_bytes()
    )
    vault.root.symlink_to(attacker_root, target_is_directory=True)

    assert vault.get_payload("approval-read-root") is None


def test_payload_vault_delete_rejects_root_replaced_with_symlink(
    tmp_path: Path,
) -> None:
    vault = SideEffectPayloadVault(SideEffectPayloadVault.root_for_workspace(tmp_path))
    moved_root = vault.root.with_name("payloads-original")
    vault.root.rename(moved_root)
    attacker_root = tmp_path / "attacker-payloads"
    attacker_root.mkdir()
    attacker_payload = attacker_root / "approval-delete-root.json"
    attacker_payload.write_text("must remain", encoding="utf-8")
    vault.root.symlink_to(attacker_root, target_is_directory=True)

    assert vault.delete_payload("approval-delete-root") is False
    assert attacker_payload.read_text(encoding="utf-8") == "must remain"
