from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ShellSandboxPolicy:
    image: str = "python:3.14-slim"
    network_mode: str = "none"
    user: str = "65532:65532"
    memory_limit: str = "512m"
    cpus: str = "1.0"
    pids_limit: int = 128
    max_timeout_seconds: int = 120
    workspace_mount_mode: str = "ro"
    allow_background: bool = False


@dataclass(frozen=True)
class ShellSandboxPreview:
    preview_id: str
    command_hash: str
    command_preview: str
    workspace_root: Path
    cwd_display: str
    artifact_dir: Path
    image: str
    network_mode: str
    user: str
    memory_limit: str
    cpus: str
    pids_limit: int
    timeout_seconds: int
    workspace_mount_mode: str
    background_requested: bool
    background_allowed: bool

    def to_metadata(self) -> dict[str, object]:
        return {
            "preview_id": self.preview_id,
            "command_hash": self.command_hash,
            "command_preview": self.command_preview,
            "cwd_display": self.cwd_display,
            "image": self.image,
            "network_mode": self.network_mode,
            "user": self.user,
            "memory_limit": self.memory_limit,
            "cpus": self.cpus,
            "pids_limit": self.pids_limit,
            "timeout_seconds": self.timeout_seconds,
            "workspace_mount_mode": self.workspace_mount_mode,
            "background_requested": self.background_requested,
            "background_allowed": self.background_allowed,
        }


def prepare_shell_sandbox_preview(
    *,
    workspace_root: Path,
    artifact_root: Path,
    arguments: dict[str, Any],
    policy: ShellSandboxPolicy | None = None,
) -> ShellSandboxPreview:
    resolved_policy = policy or ShellSandboxPolicy()
    command_value = arguments.get("command")
    if not isinstance(command_value, str) or not command_value.strip():
        raise ValueError("shell command is required")
    command = command_value

    workspace = workspace_root.expanduser().resolve(strict=True)
    artifact_base = _managed_artifact_root(workspace, artifact_root)
    preview_id = f"shell_preview_{uuid4().hex}"
    artifact_dir = artifact_base / preview_id
    os.mkdir(artifact_dir, 0o700)
    artifact_stat = artifact_dir.lstat()
    if not stat.S_ISDIR(artifact_stat.st_mode) or stat.S_ISLNK(artifact_stat.st_mode):
        raise ValueError("shell artifact preview directory is invalid")

    requested_timeout = int(
        arguments.get("timeout") or resolved_policy.max_timeout_seconds
    )
    timeout_seconds = max(1, min(requested_timeout, resolved_policy.max_timeout_seconds))
    background_requested = bool(arguments.get("run_in_background", False))

    return ShellSandboxPreview(
        preview_id=preview_id,
        command_hash=shell_command_hash(command),
        command_preview="[redacted_shell_command]",
        workspace_root=workspace,
        cwd_display=workspace.name or ".",
        artifact_dir=artifact_dir,
        image=resolved_policy.image,
        network_mode=resolved_policy.network_mode,
        user=resolved_policy.user,
        memory_limit=resolved_policy.memory_limit,
        cpus=resolved_policy.cpus,
        pids_limit=resolved_policy.pids_limit,
        timeout_seconds=timeout_seconds,
        workspace_mount_mode=resolved_policy.workspace_mount_mode,
        background_requested=background_requested,
        background_allowed=resolved_policy.allow_background,
    )


def shell_command_hash(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def _managed_artifact_root(workspace: Path, artifact_root: Path) -> Path:
    expected = workspace / "tool_side_effects" / "artifacts"
    requested = artifact_root.expanduser()
    requested_absolute = Path(os.path.abspath(requested))
    if requested_absolute != expected and requested.resolve(strict=False) != expected:
        raise ValueError("shell artifact root must be under resolved workspace")
    current = workspace
    for name in ("tool_side_effects", "artifacts"):
        current = current / name
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            os.mkdir(current, 0o700)
            current_stat = current.lstat()
        if stat.S_ISLNK(current_stat.st_mode):
            raise ValueError("shell artifact root contains symlink")
        if not stat.S_ISDIR(current_stat.st_mode):
            raise ValueError("shell artifact root contains non-directory")
    resolved = current.resolve(strict=True)
    if resolved != expected or workspace not in resolved.parents:
        raise ValueError("shell artifact root escapes resolved workspace")
    return resolved
