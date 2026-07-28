from __future__ import annotations

from pathlib import Path

import pytest

from agent import policies
from agent.policies.shell_sandbox_plan import (
    ShellSandboxPolicy,
    prepare_shell_sandbox_preview,
    shell_command_hash,
)


def test_prepare_shell_sandbox_preview_redacts_raw_command_and_creates_no_command_artifact(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command = "pytest tests -q"

    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=workspace / "tool_side_effects" / "artifacts",
        arguments={
            "command": command,
            "description": "run tests",
            "timeout": 30,
        },
    )

    assert preview.preview_id.startswith("shell_preview_")
    assert preview.command_hash == shell_command_hash(command)
    assert preview.command_preview == "[redacted_shell_command]"
    assert preview.workspace_mount_mode == "ro"
    assert preview.network_mode == "none"
    assert preview.user == "65532:65532"
    assert preview.cwd_display == workspace.name
    assert preview.timeout_seconds == 30
    assert not any(preview.artifact_dir.iterdir())
    metadata = preview.to_metadata()
    assert metadata["cwd_display"] == workspace.name
    assert str(workspace) not in str(metadata)
    assert command not in str(metadata)
    assert not hasattr(preview, "command_ref")


def test_prepare_shell_sandbox_preview_caps_timeout_and_records_background_request(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=workspace / "tool_side_effects" / "artifacts",
        arguments={
            "command": "echo hi",
            "description": "say hi",
            "timeout": 9999,
            "run_in_background": True,
        },
        policy=ShellSandboxPolicy(max_timeout_seconds=120),
    )

    assert preview.timeout_seconds == 120
    assert preview.background_requested is True
    assert preview.background_allowed is False


def test_shell_sandbox_plan_exports_public_policy_api() -> None:
    assert policies.ShellSandboxPolicy is ShellSandboxPolicy
    assert policies.prepare_shell_sandbox_preview is prepare_shell_sandbox_preview
    assert policies.shell_command_hash is shell_command_hash


def test_prepare_shell_sandbox_preview_hashes_exact_command_bytes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command = "  printf exact-command\n"

    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=workspace / "tool_side_effects" / "artifacts",
        arguments={"command": command},
    )

    assert preview.command_hash == shell_command_hash(command)


def test_prepare_shell_sandbox_preview_rejects_artifact_root_outside_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="artifact root"):
        prepare_shell_sandbox_preview(
            workspace_root=workspace,
            artifact_root=tmp_path / "outside-artifacts",
            arguments={"command": "echo hi"},
        )


@pytest.mark.parametrize("symlink_component", ["tool_side_effects", "artifacts"])
def test_prepare_shell_sandbox_preview_rejects_managed_directory_symlink(
    tmp_path: Path, symlink_component: str
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    if symlink_component == "tool_side_effects":
        (workspace / "tool_side_effects").symlink_to(outside, target_is_directory=True)
    else:
        managed = workspace / "tool_side_effects"
        managed.mkdir()
        (managed / "artifacts").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        prepare_shell_sandbox_preview(
            workspace_root=workspace,
            artifact_root=workspace / "tool_side_effects" / "artifacts",
            arguments={"command": "echo hi"},
        )

    assert list(outside.iterdir()) == []


def test_prepare_shell_sandbox_preview_resolves_workspace_symlink_before_containment(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_link = tmp_path / "workspace-link"
    workspace_link.symlink_to(workspace, target_is_directory=True)

    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace_link,
        artifact_root=workspace_link / "tool_side_effects" / "artifacts",
        arguments={"command": "echo hi"},
    )

    assert preview.workspace_root == workspace.resolve()
    assert preview.artifact_dir.is_relative_to(workspace.resolve())
