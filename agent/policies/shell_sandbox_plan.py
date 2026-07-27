from __future__ import annotations

import hashlib
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
    command = str(arguments.get("command") or "").strip()
    if not command:
        raise ValueError("shell command is required")

    workspace = workspace_root.expanduser().resolve()
    preview_id = f"shell_preview_{uuid4().hex}"
    artifact_dir = artifact_root.expanduser().resolve() / preview_id
    artifact_dir.mkdir(parents=True, exist_ok=False)

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
