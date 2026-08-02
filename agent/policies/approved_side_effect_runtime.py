from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from agent.policies.approved_side_effect_store import (
    ApprovedSideEffectRecord,
    ApprovedSideEffectStore,
)
from agent.policies.file_change_plan import (
    FileChangePreview,
    apply_file_change,
    prepare_file_change,
    rollback_file_change,
)
from agent.policies.resource_policy import ResourcePolicyContext, ResourcePolicyEngine
from agent.policies.side_effect_payload_vault import MANAGED_FILE_SIDE_EFFECT_TOOLS
from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerEvent,
    ToolAuditLedgerStore,
    record_tool_audit_event_fail_open,
)
from agent.policies.tool_approval_context import trusted_approval_from_runtime
from agent.policies.tool_approval_runtime import ToolApprovalRuntime

if TYPE_CHECKING:
    from agent.task_plan.execution_service import TaskExecutionService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovedSideEffectResult:
    ok: bool
    reason: str
    approval_request_id: str
    message: str
    diff_text: str = ""
    preview_id: str = ""
    rollback_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


class ApprovedSideEffectRuntime:
    def __init__(
        self,
        *,
        approval_runtime: ToolApprovalRuntime,
        side_effect_store: ApprovedSideEffectStore,
        task_execution_service: "TaskExecutionService | None" = None,
        audit_ledger_store: ToolAuditLedgerStore | None = None,
    ) -> None:
        self.approval_runtime = approval_runtime
        self.side_effect_store = side_effect_store
        self.task_execution_service = task_execution_service
        self._audit_ledger_store = audit_ledger_store
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
    ) -> ApprovedSideEffectResult:
        record = self.approval_runtime.store.get_request(approval_request_id)
        if record is None or record.session_key != session_key:
            return self._error(
                approval_request_id,
                "approval_request_not_found",
                "Approved side-effect request was not found.",
            )
        if record.status != "approved":
            return self._error(
                approval_request_id,
                f"approval_status_{record.status}",
                "Approval request is not approved.",
            )
        if record.tool_name not in MANAGED_FILE_SIDE_EFFECT_TOOLS:
            return self._error(
                approval_request_id,
                "managed_side_effect_tool_unsupported",
                "P4 managed side-effect runtime supports only file tools.",
            )
        payload = self._payload(approval_request_id)
        if payload is None:
            return self._error(
                approval_request_id,
                "managed_side_effect_payload_missing",
                "Approved side-effect payload was not found.",
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
                "Approved side-effect payload does not match approval record.",
            )
        resource_decision = self._resource_policy.evaluate(
            ResourcePolicyContext(
                tool_name=record.tool_name,
                arguments=payload.arguments,
                resource_roots=resource_roots,
                source="passive",
                registry_risk=record.risk,
            )
        )
        if resource_decision.action != "allow":
            return self._error(
                approval_request_id,
                resource_decision.reason,
                "Resource policy denied approved side-effect preparation.",
                metadata={"resource_policy": resource_decision.to_trace_metadata()},
            )

        workspace = workspace_root.expanduser().resolve()
        artifact_root = _artifact_root(workspace)
        existing = self.side_effect_store.get_by_approval_id(approval_request_id)
        if existing is None:
            self.side_effect_store.record_payload(
                approval_request_id=record.approval_request_id,
                request_id=record.request_id,
                session_key=record.session_key,
                tool_name=record.tool_name,
                approval_scope=record.approval_scope,
                args_hash=record.args_hash,
                payload_ref=_relative_ref(workspace, payload.record.payload_path),
                actor=actor,
                now=self.now(),
            )
            self._record_ledger(
                "approved_side_effect_payload_recorded",
                record,
                side_effect_status="payload_recorded",
            )
        try:
            preview = prepare_file_change(
                workspace_root=workspace,
                artifact_root=artifact_root,
                tool_name=record.tool_name,
                arguments=payload.arguments,
            )
        except Exception:
            logger.warning("approved side-effect preview failed", exc_info=True)
            self._record_ledger(
                "approved_side_effect_preview_failed",
                record,
                side_effect_status="preview_failed",
            )
            return self._error(
                approval_request_id,
                "preview_failed",
                "Approved file side-effect preview failed.",
            )
        self.side_effect_store.record_preview(
            approval_request_id=record.approval_request_id,
            preview_id=preview.preview_id,
            target_path_hash=_sha256_text(preview.display_path),
            before_hash=preview.before_hash,
            after_hash=preview.after_hash,
            diff_ref=_relative_ref(workspace, preview.diff_path),
            diff_truncated=preview.diff_truncated,
            actor=actor,
            now=self.now(),
        )
        self._record_ledger(
            "approved_side_effect_preview_ready",
            record,
            side_effect_status="preview_ready",
            metadata={
                "target_path_hash": _sha256_text(preview.display_path),
                "before_hash": preview.before_hash,
                "after_hash": preview.after_hash,
                "diff_truncated": preview.diff_truncated,
                "preview_id": preview.preview_id,
            },
        )
        return ApprovedSideEffectResult(
            ok=True,
            reason="preview_ready",
            approval_request_id=approval_request_id,
            message="Approved file side-effect preview is ready.",
            diff_text=preview.diff_text,
            preview_id=preview.preview_id,
            metadata={
                "tool_name": record.tool_name,
                "args_hash": record.args_hash,
                "target_path_hash": _sha256_text(preview.display_path),
                "diff_truncated": preview.diff_truncated,
            },
        )

    def apply(
        self,
        approval_request_id: str,
        session_key: str,
        actor: str,
        workspace_root: Path,
        resource_roots: tuple[str, ...],
    ) -> ApprovedSideEffectResult:
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
                "preview_missing",
                "Approved side-effect preview was not found.",
            )
        record = self.approval_runtime.store.get_request(approval_request_id)
        if record is None or record.session_key != session_key:
            return self._error(
                approval_request_id,
                "approval_request_not_found",
                "Approved side-effect request was not found.",
            )
        payload = self._payload(approval_request_id)
        if payload is None:
            return self._error(
                approval_request_id,
                "managed_side_effect_payload_missing",
                "Approved side-effect payload was not found.",
            )
        resource_decision = self._resource_policy.evaluate(
            ResourcePolicyContext(
                tool_name=record.tool_name,
                arguments=payload.arguments,
                resource_roots=resource_roots,
                source="passive",
                registry_risk=record.risk,
            )
        )
        if resource_decision.action != "allow":
            return self._error(
                approval_request_id,
                resource_decision.reason,
                "Resource policy denied approved side-effect apply.",
                metadata={"resource_policy": resource_decision.to_trace_metadata()},
            )
        consume = self.approval_runtime.consume_for_execution(
            trusted_context=trusted_approval_from_runtime(
                approval_request_id=approval_request_id,
                actor=actor,
                source="approved_side_effect_runtime",
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
                "Approved side-effect request could not be consumed.",
            )
        try:
            preview = self._preview_from_record(
                workspace_root.expanduser().resolve(),
                side_effect,
                record.tool_name,
                payload.arguments,
            )
            applied = apply_file_change(preview)
        except Exception:
            logger.warning("approved side-effect apply failed", exc_info=True)
            try:
                self.approval_runtime.finalize_execution(
                    approval_request_id=approval_request_id,
                    request_id=record.request_id,
                    session_key=record.session_key,
                    tool_name=record.tool_name,
                    approval_scope=record.approval_scope,
                    arguments=payload.arguments,
                    execution_status="execution_failed",
                )
            except Exception:
                logger.warning(
                    "failed to finalize approved side-effect apply failure",
                    exc_info=True,
                )
            try:
                self.side_effect_store.mark_execution_failed(
                    approval_request_id=approval_request_id,
                    execution_status="execution_failed",
                    actor=actor,
                    now=self.now(),
                )
            except Exception:
                logger.warning(
                    "failed to mark approved side-effect apply failure",
                    exc_info=True,
                )
            self._record_ledger(
                "approved_side_effect_execution_failed",
                record,
                side_effect_status="execution_failed",
                execution_status="execution_failed",
            )
            return self._error(
                approval_request_id,
                "execution_failed",
                "Approved side-effect apply failed.",
            )
        execution_status = "executed" if applied.ok else "execution_failed"
        self.approval_runtime.finalize_execution(
            approval_request_id=approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            arguments=payload.arguments,
            execution_status=execution_status,
        )
        if not applied.ok:
            self.side_effect_store.mark_execution_failed(
                approval_request_id=approval_request_id,
                execution_status=applied.reason,
                actor=actor,
                now=self.now(),
            )
            self._record_ledger(
                "approved_side_effect_execution_failed",
                record,
                side_effect_status="execution_failed",
                execution_status=applied.reason,
            )
            return self._error(
                approval_request_id,
                applied.reason,
                "Approved side-effect apply failed.",
            )
        rollback_id = f"rollback_{uuid4().hex}"
        self.side_effect_store.mark_executed(
            approval_request_id=approval_request_id,
            rollback_id=rollback_id,
            execution_status=applied.reason,
            actor=actor,
            now=self.now(),
        )
        self._record_ledger(
            "approved_side_effect_executed",
            record,
            side_effect_status="executed",
            execution_status=applied.reason,
            metadata={"rollback_id": rollback_id, "after_hash": applied.after_hash},
        )
        if record.approval_scope == "task_execution_step" and self.task_execution_service is not None:
            self.task_execution_service.complete_authorized_file_side_effect(
                session_key=session_key,
                approval_request_id=approval_request_id,
                tool_name=record.tool_name,
                args_hash=record.args_hash,
                result_preview=applied.reason,
            )
        return ApprovedSideEffectResult(
            ok=True,
            reason=applied.reason,
            approval_request_id=approval_request_id,
            message="Approved file side-effect applied.",
            preview_id=side_effect.preview_id,
            rollback_id=rollback_id,
            metadata={
                "tool_name": record.tool_name,
                "args_hash": record.args_hash,
                "after_hash": applied.after_hash,
            },
        )

    def rollback(
        self,
        approval_request_id: str,
        session_key: str,
        actor: str,
        workspace_root: Path,
        resource_roots: tuple[str, ...],
    ) -> ApprovedSideEffectResult:
        side_effect = self.side_effect_store.get_by_approval_id(approval_request_id)
        if side_effect is None or side_effect.status != "executed":
            return self._error(
                approval_request_id,
                "rollback_not_available",
                "Approved side-effect is not in executed state.",
            )
        if side_effect.session_key != session_key:
            return self._error(
                approval_request_id,
                "approval_request_not_found",
                "Approved side-effect request was not found.",
            )
        payload = self._payload(approval_request_id)
        if payload is None:
            return self._error(
                approval_request_id,
                "managed_side_effect_payload_missing",
                "Approved side-effect payload was not found.",
            )
        resource_decision = self._resource_policy.evaluate(
            ResourcePolicyContext(
                tool_name=side_effect.tool_name,
                arguments=payload.arguments,
                resource_roots=resource_roots,
                source="passive",
                registry_risk="write",
            )
        )
        if resource_decision.action != "allow":
            return self._error(
                approval_request_id,
                resource_decision.reason,
                "Resource policy denied approved side-effect rollback.",
                metadata={"resource_policy": resource_decision.to_trace_metadata()},
            )
        try:
            preview = self._preview_from_record(
                workspace_root.expanduser().resolve(),
                side_effect,
                side_effect.tool_name,
                payload.arguments,
            )
            rolled_back = rollback_file_change(preview)
        except Exception:
            logger.warning("approved side-effect rollback failed", exc_info=True)
            try:
                self.side_effect_store.mark_rollback_failed(
                    approval_request_id=approval_request_id,
                    rollback_status="rollback_failed",
                    actor=actor,
                    now=self.now(),
                )
            except Exception:
                logger.warning(
                    "failed to mark approved side-effect rollback failure",
                    exc_info=True,
                )
            self._record_ledger(
                "approved_side_effect_rollback_failed",
                side_effect,
                side_effect_status="rollback_failed",
                rollback_status="rollback_failed",
            )
            return self._error(
                approval_request_id,
                "rollback_failed",
                "Approved side-effect rollback failed.",
            )
        if not rolled_back.ok:
            self.side_effect_store.mark_rollback_failed(
                approval_request_id=approval_request_id,
                rollback_status=rolled_back.reason,
                actor=actor,
                now=self.now(),
            )
            self._record_ledger(
                "approved_side_effect_rollback_failed",
                side_effect,
                side_effect_status="rollback_failed",
                rollback_status=rolled_back.reason,
            )
            return self._error(
                approval_request_id,
                rolled_back.reason,
                "Approved side-effect rollback failed.",
            )
        self.side_effect_store.mark_rolled_back(
            approval_request_id=approval_request_id,
            rollback_status=rolled_back.reason,
            actor=actor,
            now=self.now(),
        )
        self._record_ledger(
            "approved_side_effect_rolled_back",
            side_effect,
            side_effect_status="rolled_back",
            rollback_status=rolled_back.reason,
        )
        return ApprovedSideEffectResult(
            ok=True,
            reason=rolled_back.reason,
            approval_request_id=approval_request_id,
            message="Approved file side-effect rolled back.",
            preview_id=side_effect.preview_id,
            rollback_id=side_effect.rollback_id,
            metadata={
                "tool_name": side_effect.tool_name,
                "restored_hash": rolled_back.restored_hash,
            },
        )

    def _payload(self, approval_request_id: str):
        if self.approval_runtime.side_effect_vault is None:
            return None
        return self.approval_runtime.side_effect_vault.get_payload(
            approval_request_id
        )

    def _preview_from_record(
        self,
        workspace: Path,
        record: ApprovedSideEffectRecord,
        tool_name: str,
        arguments: dict[str, object],
    ) -> FileChangePreview:
        target = _resolve_workspace_path(workspace, str(arguments.get("path") or ""))
        display_path = str(target.relative_to(workspace))
        if _sha256_text(display_path) != record.target_path_hash:
            raise ValueError("side-effect target path hash mismatch")
        preview_dir = _artifact_root(workspace) / record.preview_id
        snapshot_path = preview_dir / "before.bin"
        diff_path = preview_dir / "change.diff"
        return FileChangePreview(
            preview_id=record.preview_id,
            tool_name=tool_name,
            target_path=target,
            display_path=display_path,
            before_exists=snapshot_path.exists(),
            before_hash=record.before_hash,
            after_hash=record.after_hash,
            snapshot_path=snapshot_path if snapshot_path.exists() else None,
            after_path=preview_dir / "after.bin",
            diff_path=diff_path,
            diff_text=diff_path.read_text(encoding="utf-8") if diff_path.exists() else "",
            diff_truncated=record.diff_truncated,
        )

    def _error(
        self,
        approval_request_id: str,
        reason: str,
        message: str,
        *,
        metadata: dict[str, object] | None = None,
    ) -> ApprovedSideEffectResult:
        return ApprovedSideEffectResult(
            ok=False,
            reason=reason,
            approval_request_id=approval_request_id,
            message=message,
            metadata=dict(metadata or {}),
        )

    def _record_ledger(
        self,
        event_type: str,
        record: object,
        *,
        side_effect_status: str = "",
        execution_status: str = "",
        rollback_status: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self._audit_ledger_store is None:
            return
        record_tool_audit_event_fail_open(
            self._audit_ledger_store,
            ToolAuditLedgerEvent(
                event_type=event_type,
                session_key=str(getattr(record, "session_key", "") or ""),
                request_id=str(getattr(record, "request_id", "") or ""),
                tool_name=str(getattr(record, "tool_name", "") or ""),
                approval_request_id=str(
                    getattr(record, "approval_request_id", "") or ""
                ),
                approval_scope=str(getattr(record, "approval_scope", "") or ""),
                side_effect_status=side_effect_status,
                execution_status=execution_status,
                rollback_status=rollback_status,
                actor="approved_side_effect_runtime",
                args_hash=str(getattr(record, "args_hash", "") or ""),
                metadata=dict(metadata or {}),
            ),
            logger,
        )


def _artifact_root(workspace: Path) -> Path:
    path = workspace / "tool_side_effects" / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _relative_ref(workspace: Path, path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return str(resolved.relative_to(workspace))
    except ValueError:
        return resolved.name


def _resolve_workspace_path(workspace: Path, path: str) -> Path:
    if not path.strip():
        raise ValueError("path is required")
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    target = candidate.resolve()
    if target != workspace and workspace not in target.parents:
        raise ValueError("file path outside workspace")
    return target


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
