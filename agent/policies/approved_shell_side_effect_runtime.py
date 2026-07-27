from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from agent.policies.approved_side_effect_store import (
    ApprovedSideEffectRecord,
    ApprovedSideEffectStore,
)
from agent.policies.resource_policy import ResourcePolicyContext, ResourcePolicyEngine
from agent.policies.shell_sandbox_plan import (
    ShellSandboxPreview,
    prepare_shell_sandbox_preview,
    shell_command_hash,
)
from agent.policies.shell_sandbox_runner import SandboxRunner
from agent.policies.side_effect_payload_vault import (
    MANAGED_SHELL_SIDE_EFFECT_TOOLS,
    SideEffectPayload,
)
from agent.policies.tool_approval_context import trusted_approval_from_runtime
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalRequestRecord


@dataclass(frozen=True)
class ApprovedShellSideEffectResult:
    ok: bool
    reason: str
    approval_request_id: str
    message: str
    preview_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


class ApprovedShellSideEffectRuntime:
    def __init__(
        self,
        *,
        approval_runtime: ToolApprovalRuntime,
        side_effect_store: ApprovedSideEffectStore,
        sandbox_runner: SandboxRunner | None,
    ) -> None:
        self.approval_runtime = approval_runtime
        self.side_effect_store = side_effect_store
        self.sandbox_runner = sandbox_runner
        self._resource_policy = ResourcePolicyEngine()

    def now(self) -> datetime:
        return datetime.now(UTC)

    def prepare(
        self,
        approval_request_id: str,
        session_key: str,
        actor: str,
        workspace_root: Path,
        resource_roots: tuple[str, ...],
    ) -> ApprovedShellSideEffectResult:
        resolved = self._resolve_approved_payload(
            approval_request_id, session_key, resource_roots
        )
        if isinstance(resolved, ApprovedShellSideEffectResult):
            return resolved
        record, payload = resolved
        if self.sandbox_runner is None:
            return self._error(
                approval_request_id,
                "shell_sandbox_unavailable",
                "Shell sandbox is unavailable.",
            )

        workspace = workspace_root.expanduser().resolve()
        existing = self.side_effect_store.get_by_approval_id(approval_request_id)
        if existing is None:
            self.side_effect_store.record_payload(
                approval_request_id=record.approval_request_id,
                request_id=record.request_id,
                session_key=record.session_key,
                tool_name=record.tool_name,
                approval_scope=record.approval_scope,
                args_hash=record.args_hash,
                payload_ref=_workspace_ref(workspace, payload.record.payload_path),
                actor=actor,
                now=self.now(),
            )
        try:
            preview = prepare_shell_sandbox_preview(
                workspace_root=workspace,
                artifact_root=_artifact_root(workspace),
                arguments=payload.arguments,
            )
            self.side_effect_store.record_shell_preview(
                approval_request_id=record.approval_request_id,
                preview_id=preview.preview_id,
                command_hash=preview.command_hash,
                sandbox_backend=self.sandbox_runner.backend_name(),
                sandbox_image=preview.image,
                sandbox_user=preview.user,
                sandbox_memory_limit=preview.memory_limit,
                sandbox_cpus=preview.cpus,
                sandbox_pids_limit=preview.pids_limit,
                network_mode=preview.network_mode,
                workspace_mount_mode=preview.workspace_mount_mode,
                timeout_seconds=preview.timeout_seconds,
                background_requested=preview.background_requested,
                background_allowed=preview.background_allowed,
                actor=actor,
                now=self.now(),
            )
        except (FileNotFoundError, PermissionError):
            return self._error(
                approval_request_id,
                "shell_sandbox_unavailable",
                "Shell sandbox is unavailable.",
            )
        except Exception:
            return self._error(
                approval_request_id,
                "shell_sandbox_preview_failed",
                "Shell sandbox preview could not be prepared.",
            )
        return ApprovedShellSideEffectResult(
            ok=True,
            reason="shell_sandbox_preview_ready",
            approval_request_id=approval_request_id,
            message="Approved shell sandbox preview is ready.",
            preview_id=preview.preview_id,
            metadata=_preview_metadata(record.tool_name, record.args_hash, preview),
        )

    def apply(
        self,
        approval_request_id: str,
        session_key: str,
        actor: str,
        workspace_root: Path,
        resource_roots: tuple[str, ...],
    ) -> ApprovedShellSideEffectResult:
        if self.sandbox_runner is None:
            return self._error(
                approval_request_id,
                "shell_sandbox_unavailable",
                "Shell sandbox is unavailable.",
            )
        side_effect = self.side_effect_store.get_by_approval_id(approval_request_id)
        if side_effect is None or not side_effect.preview_id:
            prepared = self.prepare(
                approval_request_id,
                session_key,
                actor,
                workspace_root,
                resource_roots,
            )
            if not prepared.ok:
                return prepared
            side_effect = self.side_effect_store.get_by_approval_id(approval_request_id)
        if side_effect is None:
            return self._error(
                approval_request_id,
                "shell_sandbox_preview_missing",
                "Shell sandbox preview was not found.",
            )

        resolved = self._resolve_approved_payload(
            approval_request_id, session_key, resource_roots
        )
        if isinstance(resolved, ApprovedShellSideEffectResult):
            return resolved
        record, payload = resolved
        try:
            preview = self._preview_from_record(
                workspace_root.expanduser().resolve(), side_effect, payload.arguments
            )
        except Exception:
            return self._error(
                approval_request_id,
                "shell_sandbox_preview_invalid",
                "Shell sandbox preview is invalid.",
            )

        consume = self.approval_runtime.consume_for_execution(
            trusted_context=trusted_approval_from_runtime(
                approval_request_id=approval_request_id,
                actor=actor,
                source="approved_shell_side_effect_runtime",
            ),
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            arguments=payload.arguments,
        )
        if not consume.allows_invoker:
            return self._error(
                approval_request_id,
                consume.reason,
                "Approved shell request could not be consumed.",
            )

        command = str(payload.arguments["command"])
        try:
            result = self.sandbox_runner.run(preview, command)
        except (FileNotFoundError, PermissionError):
            return self._finalize_failure(
                record, payload.arguments, actor, "shell_sandbox_unavailable", side_effect.preview_id
            )
        except subprocess.TimeoutExpired:
            return self._finalize_failure(
                record, payload.arguments, actor, "sandbox_timeout", side_effect.preview_id
            )
        except Exception:
            return self._finalize_failure(
                record, payload.arguments, actor, "sandbox_execution_failed", side_effect.preview_id
            )

        try:
            stdout_ref = _artifact_ref(preview, result.stdout_path)
            stderr_ref = _artifact_ref(preview, result.stderr_path)
            self.side_effect_store.mark_shell_executed(
                approval_request_id=approval_request_id,
                execution_status=result.reason,
                exit_code=result.exit_code,
                stdout_ref=stdout_ref,
                stderr_ref=stderr_ref,
                stdout_hash=result.stdout_hash,
                stderr_hash=result.stderr_hash,
                stdout_bytes=result.stdout_bytes,
                stderr_bytes=result.stderr_bytes,
                stdout_truncated=result.stdout_truncated,
                stderr_truncated=result.stderr_truncated,
                duration_ms=result.duration_ms,
                actor=actor,
                now=self.now(),
            )
        except Exception:
            return self._finalize_failure(
                record,
                payload.arguments,
                actor,
                "shell_artifact_path_invalid",
                side_effect.preview_id,
            )

        execution_status = "executed" if result.ok else "execution_failed"
        self.approval_runtime.finalize_execution(
            approval_request_id=approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            arguments=payload.arguments,
            execution_status=execution_status,
        )
        if not result.ok:
            return self._error(
                approval_request_id,
                result.reason,
                "Approved shell execution failed.",
                preview_id=side_effect.preview_id,
            )
        return ApprovedShellSideEffectResult(
            ok=True,
            reason=result.reason,
            approval_request_id=approval_request_id,
            message="Approved shell command executed in sandbox.",
            preview_id=side_effect.preview_id,
            metadata={
                "tool_name": record.tool_name,
                "args_hash": record.args_hash,
                "exit_code": result.exit_code,
                "stdout_hash": result.stdout_hash,
                "stderr_hash": result.stderr_hash,
                "duration_ms": result.duration_ms,
            },
        )

    def rollback(
        self,
        approval_request_id: str,
        session_key: str,
        actor: str,
        workspace_root: Path,
        resource_roots: tuple[str, ...],
    ) -> ApprovedShellSideEffectResult:
        return self._error(
            approval_request_id,
            "rollback_not_supported_for_shell",
            "Rollback is not supported for shell side effects.",
        )

    def _resolve_approved_payload(
        self,
        approval_request_id: str,
        session_key: str,
        resource_roots: tuple[str, ...],
    ) -> tuple[ToolApprovalRequestRecord, SideEffectPayload] | ApprovedShellSideEffectResult:
        record = self.approval_runtime.store.get_request(approval_request_id)
        if record is None or record.session_key != session_key:
            return self._error(
                approval_request_id,
                "approval_request_not_found",
                "Approved shell request was not found.",
            )
        if record.status != "approved":
            return self._error(
                approval_request_id,
                f"approval_status_{record.status}",
                "Approval request is not approved.",
            )
        if record.tool_name not in MANAGED_SHELL_SIDE_EFFECT_TOOLS:
            return self._error(
                approval_request_id,
                "managed_shell_side_effect_tool_unsupported",
                "Managed shell runtime supports only shell.",
            )
        if record.approval_scope == "task_execution_step":
            return self._error(
                approval_request_id,
                "task_execution_shell_resume_not_supported",
                "Task execution shell resume is not supported.",
            )
        payload = self._payload(approval_request_id)
        if payload is None:
            return self._error(
                approval_request_id,
                "managed_side_effect_payload_missing",
                "Approved shell payload was not found.",
            )
        if (
            payload.record.request_id != record.request_id
            or payload.record.session_key != record.session_key
            or payload.record.tool_name != record.tool_name
            or payload.record.approval_scope != record.approval_scope
            or payload.record.args_hash != record.args_hash
        ):
            return self._error(
                approval_request_id,
                "managed_side_effect_payload_binding_mismatch",
                "Approved shell payload does not match approval record.",
            )
        if bool(payload.arguments.get("run_in_background", False)):
            return self._error(
                approval_request_id,
                "shell_background_not_supported",
                "Background shell execution is not supported.",
            )
        decision = self._resource_policy.evaluate(
            ResourcePolicyContext(
                tool_name=record.tool_name,
                arguments=payload.arguments,
                resource_roots=resource_roots,
                source="passive",
                registry_risk=record.risk,
            )
        )
        if decision.action != "allow":
            return self._error(
                approval_request_id,
                decision.reason,
                "Resource policy denied approved shell execution.",
                metadata={"resource_policy": _sanitized_resource_metadata(decision)},
            )
        return record, payload

    def _payload(self, approval_request_id: str) -> SideEffectPayload | None:
        if self.approval_runtime.side_effect_vault is None:
            return None
        return self.approval_runtime.side_effect_vault.get_payload(approval_request_id)

    def _preview_from_record(
        self,
        workspace: Path,
        record: ApprovedSideEffectRecord,
        arguments: dict[str, object],
    ) -> ShellSandboxPreview:
        if shell_command_hash(str(arguments.get("command") or "")) != record.command_hash:
            raise ValueError("shell command hash mismatch")
        preview_dir = _artifact_root(workspace) / record.preview_id
        return ShellSandboxPreview(
            preview_id=record.preview_id,
            command_hash=record.command_hash,
            command_preview="[redacted_shell_command]",
            workspace_root=workspace,
            cwd_display=workspace.name or ".",
            artifact_dir=preview_dir,
            image=record.sandbox_image,
            network_mode=record.network_mode,
            user=record.sandbox_user,
            memory_limit=record.sandbox_memory_limit,
            cpus=record.sandbox_cpus,
            pids_limit=record.sandbox_pids_limit,
            timeout_seconds=record.timeout_seconds,
            workspace_mount_mode=record.workspace_mount_mode,
            background_requested=record.background_requested,
            background_allowed=record.background_allowed,
        )

    def _finalize_failure(
        self,
        record: ToolApprovalRequestRecord,
        arguments: dict[str, object],
        actor: str,
        reason: str,
        preview_id: str,
    ) -> ApprovedShellSideEffectResult:
        self.approval_runtime.finalize_execution(
            approval_request_id=record.approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            arguments=arguments,
            execution_status="execution_failed",
        )
        return self._error(
            record.approval_request_id,
            reason,
            "Approved shell execution failed.",
            preview_id=preview_id,
        )

    def _error(
        self,
        approval_request_id: str,
        reason: str,
        message: str,
        *,
        preview_id: str = "",
        metadata: dict[str, object] | None = None,
    ) -> ApprovedShellSideEffectResult:
        return ApprovedShellSideEffectResult(
            ok=False,
            reason=reason,
            approval_request_id=approval_request_id,
            message=message,
            preview_id=preview_id,
            metadata=dict(metadata or {}),
        )


def _artifact_root(workspace: Path) -> Path:
    path = workspace / "tool_side_effects" / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _workspace_ref(workspace: Path, path: Path) -> str:
    resolved = path.expanduser().resolve()
    return str(resolved.relative_to(workspace))


def _artifact_ref(preview: ShellSandboxPreview, raw_path: str) -> str:
    artifact_dir = preview.artifact_dir.resolve()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = artifact_dir / candidate
    resolved = candidate.resolve()
    if resolved == artifact_dir or artifact_dir not in resolved.parents:
        raise ValueError("shell artifact path outside sandbox artifact directory")
    return str(resolved.relative_to(artifact_dir.parent.parent))


def _sanitized_resource_metadata(decision: Any) -> dict[str, object]:
    return {
        "action": decision.action,
        "reason": decision.reason,
        "resource_type": decision.resource_type,
    }


def _preview_metadata(tool_name: str, args_hash: str, preview: ShellSandboxPreview) -> dict[str, object]:
    return {
        "tool_name": tool_name,
        "args_hash": args_hash,
        **preview.to_metadata(),
    }
