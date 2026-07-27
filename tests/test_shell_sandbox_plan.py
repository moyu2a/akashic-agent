from __future__ import annotations

from pathlib import Path

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
        artifact_root=tmp_path / "artifacts",
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
    assert preview.timeout_seconds == 30
    assert not any(preview.artifact_dir.iterdir())
    assert command not in str(preview.to_metadata())
    assert not hasattr(preview, "command_ref")


def test_prepare_shell_sandbox_preview_caps_timeout_and_records_background_request(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
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
