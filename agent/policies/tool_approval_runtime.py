from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.policies.tool_approval import canonical_args_hash
from agent.policies.tool_approval_context import TrustedApprovalContext
from agent.policies.tool_approval_decision import ToolApprovalDecision
from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerEvent,
    ToolAuditLedgerStore,
    record_tool_audit_event_fail_open,
)
from agent.policies.side_effect_payload_vault import (
    MANAGED_SIDE_EFFECT_TOOLS,
    SideEffectPayloadVault,
)
from agent.policies.tool_audit import build_tool_approval_audit_event
from agent.policies.tool_approval_store import (
    ToolApprovalRequestRecord,
    ToolApprovalStore,
)

logger = logging.getLogger(__name__)


class ToolApprovalRuntime:
    def __init__(
        self,
        store: ToolApprovalStore,
        *,
        side_effect_vault: SideEffectPayloadVault | None = None,
        audit_ledger_store: ToolAuditLedgerStore | None = None,
        now_factory: Callable[[], datetime] | None = None,
        approval_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        self._store = store
        self.side_effect_vault = side_effect_vault
        self._audit_ledger_store = audit_ledger_store
        self._now_factory = now_factory or _utcnow
        self._approval_ttl = approval_ttl

    @staticmethod
    def approval_db_path_from_workspace(workspace: str | Path) -> Path:
        path = (
            Path(workspace).expanduser().resolve() / "tool_approvals" / "approvals.db"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def side_effect_vault_from_workspace(
        workspace: str | Path,
    ) -> SideEffectPayloadVault:
        return SideEffectPayloadVault(
            SideEffectPayloadVault.root_for_workspace(workspace)
        )

    @property
    def store(self) -> ToolApprovalStore:
        return self._store

    def record_defer_request(
        self,
        *,
        request_id: str,
        session_key: str,
        channel: str,
        chat_id: str,
        source: str,
        tool_name: str,
        risk: str,
        approval_scope: str,
        policy_reason: str,
        arguments: Mapping[str, object],
    ) -> ToolApprovalRequestRecord:
        record = self._store.create_or_get_pending_request(
            request_id=request_id,
            session_key=session_key,
            channel=channel,
            chat_id=chat_id,
            source=source,
            tool_name=tool_name,
            risk=risk,
            approval_scope=approval_scope,
            policy_reason=policy_reason,
            arguments=arguments,
            now=self._now(),
            ttl=self._approval_ttl,
        )
        self._record_approval_event_from_record(
            "tool_approval_requested",
            record,
            approval_status="requested",
            actor="model",
        )
        return record

    def expire_pending_requests(self) -> list[ToolApprovalDecision]:
        decisions = self._store.expire_pending_requests(now=self._now())
        for decision in decisions:
            self._record_approval_event_from_decision(
                "tool_approval_expired",
                decision,
                approval_status="expired",
            )
        return decisions

    def approve_request(
        self,
        *,
        approval_request_id: str,
        session_key: str,
        actor: str,
    ) -> ToolApprovalDecision:
        record = self._store.get_request(approval_request_id)
        if record is None or record.session_key != session_key:
            return ToolApprovalDecision(
                action="not_found",
                reason="approval_request_not_found",
                approval_request_id=approval_request_id,
                session_key=session_key,
            )
        decision = self._store.approve_request(
            approval_request_id=record.approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            args_hash=record.args_hash,
            actor=actor,
            now=self._now(),
        )
        if decision.action == "approved":
            self._record_approval_event_from_decision(
                "tool_approval_approved",
                decision,
                approval_status="approved",
                actor=actor,
            )
        return decision

    def deny_request(
        self,
        *,
        approval_request_id: str,
        session_key: str,
        actor: str,
        reason: str,
    ) -> ToolApprovalDecision:
        record = self._store.get_request(approval_request_id)
        if record is None or record.session_key != session_key:
            return ToolApprovalDecision(
                action="not_found",
                reason="approval_request_not_found",
                approval_request_id=approval_request_id,
                session_key=session_key,
            )
        decision = self._store.deny_request(
            approval_request_id=record.approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            args_hash=record.args_hash,
            actor=actor,
            reason=reason,
            now=self._now(),
        )
        if decision.action == "denied":
            self._record_approval_event_from_decision(
                "tool_approval_denied",
                decision,
                approval_status="denied",
                actor=actor,
            )
        return decision

    def record_managed_side_effect_payload(
        self,
        record: ToolApprovalRequestRecord,
        *,
        arguments: Mapping[str, object],
    ) -> None:
        if self.side_effect_vault is None:
            return
        if record.tool_name not in MANAGED_SIDE_EFFECT_TOOLS:
            return
        self.side_effect_vault.put_payload(
            approval_request_id=record.approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            args_hash=record.args_hash,
            arguments=dict(arguments),
            created_at=self._now(),
            expires_at=record.expires_at,
        )

    def record_deferred_tool_payload(
        self,
        record: ToolApprovalRequestRecord,
        *,
        arguments: Mapping[str, object],
    ) -> None:
        if self.side_effect_vault is None:
            return
        if record.tool_name in MANAGED_SIDE_EFFECT_TOOLS:
            self.record_managed_side_effect_payload(record, arguments=arguments)
            return
        if record.risk != "write":
            return
        self.side_effect_vault.put_deferred_tool_payload(
            approval_request_id=record.approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            args_hash=record.args_hash,
            arguments=dict(arguments),
            created_at=self._now(),
            expires_at=record.expires_at,
        )

    def consume_for_execution(
        self,
        *,
        trusted_context: TrustedApprovalContext | None,
        request_id: str,
        session_key: str,
        tool_name: str,
        approval_scope: str,
        arguments: Mapping[str, object],
    ) -> ToolApprovalDecision:
        if trusted_context is None:
            return ToolApprovalDecision(
                action="not_applicable",
                reason="trusted_approval_context_missing",
                request_id=request_id,
                session_key=session_key,
                tool_name=tool_name,
                approval_scope=approval_scope or "tool_call",
                args_hash=canonical_args_hash(arguments),
            )
        decision = self._store.consume_approved_request(
            approval_request_id=trusted_context.approval_request_id,
            request_id=request_id,
            session_key=session_key,
            tool_name=tool_name,
            approval_scope=approval_scope,
            args_hash=canonical_args_hash(arguments),
            actor=trusted_context.actor,
            now=self._now(),
        )
        if decision.action == "consumed":
            self._record_approval_event_from_decision(
                "tool_approval_consumed",
                decision,
                approval_status="consumed",
                actor=trusted_context.actor,
            )
        elif decision.action == "expired":
            self._record_approval_event_from_decision(
                "tool_approval_expired",
                decision,
                approval_status="expired",
                actor=trusted_context.actor,
            )
        return decision

    def finalize_execution(
        self,
        *,
        approval_request_id: str,
        request_id: str,
        session_key: str,
        tool_name: str,
        approval_scope: str,
        arguments: Mapping[str, object],
        execution_status: str,
    ) -> ToolApprovalDecision:
        decision = self._store.finalize_consumed_request(
            approval_request_id=approval_request_id,
            request_id=request_id,
            session_key=session_key,
            tool_name=tool_name,
            approval_scope=approval_scope,
            args_hash=canonical_args_hash(arguments),
            execution_status=execution_status,
            now=self._now(),
        )
        if decision.action in {"executed", "execution_failed"}:
            self._record_approval_event_from_decision(
                (
                    "tool_approval_executed"
                    if decision.action == "executed"
                    else "tool_approval_execution_failed"
                ),
                decision,
                approval_status=decision.action,
            )
        return decision

    @staticmethod
    def lifecycle_event_from_record(
        record: ToolApprovalRequestRecord,
        *,
        status: str,
        actor: str = "model",
    ) -> dict[str, object]:
        decision = ToolApprovalDecision(
            action="pending",
            reason=f"approval_{status}",
            approval_request_id=record.approval_request_id,
            request_id=record.request_id,
            session_key=record.session_key,
            tool_name=record.tool_name,
            approval_scope=record.approval_scope,
            args_hash=record.args_hash,
            metadata={
                "actor": actor,
                "source": record.source,
                "risk": record.risk,
                "policy_reason": record.policy_reason,
                "created_at": record.created_at,
                "decided_at": record.decided_at,
                "consumed_at": record.consumed_at,
                "executed_at": record.executed_at,
            },
        )
        return build_tool_approval_audit_event(
            decision,
            status=status,
            actor=actor,
        ).to_trace_metadata()

    def lifecycle_event_from_decision(
        self,
        decision: ToolApprovalDecision,
        *,
        actor: str = "",
    ) -> dict[str, object]:
        if decision.approval_request_id:
            record = self._store.get_request(decision.approval_request_id)
            if record is not None:
                return self.lifecycle_event_from_record(
                    record,
                    status=decision.action,
                    actor=actor or str(decision.metadata.get("actor") or ""),
                )
        return build_tool_approval_audit_event(
            decision,
            actor=actor,
        ).to_trace_metadata()

    def _record_approval_event_from_record(
        self,
        event_type: str,
        record: ToolApprovalRequestRecord,
        *,
        approval_status: str,
        actor: str = "",
    ) -> None:
        if self._audit_ledger_store is None:
            return
        record_tool_audit_event_fail_open(
            self._audit_ledger_store,
            ToolAuditLedgerEvent(
                event_type=event_type,
                session_key=record.session_key,
                channel=record.channel,
                chat_id=record.chat_id,
                request_id=record.request_id,
                tool_name=record.tool_name,
                source=record.source,
                risk=record.risk,
                policy_reason=record.policy_reason,
                approval_request_id=record.approval_request_id,
                approval_scope=record.approval_scope,
                approval_status=approval_status,
                actor=actor,
                args_hash=record.args_hash,
            ),
            logger,
        )

    def _record_approval_event_from_decision(
        self,
        event_type: str,
        decision: ToolApprovalDecision,
        *,
        approval_status: str,
        actor: str = "",
    ) -> None:
        if self._audit_ledger_store is None:
            return
        record = (
            self._store.get_request(decision.approval_request_id)
            if decision.approval_request_id
            else None
        )
        if record is not None:
            self._record_approval_event_from_record(
                event_type,
                record,
                approval_status=approval_status,
                actor=actor,
            )
            return
        record_tool_audit_event_fail_open(
            self._audit_ledger_store,
            ToolAuditLedgerEvent(
                event_type=event_type,
                session_key=decision.session_key,
                request_id=decision.request_id,
                tool_name=decision.tool_name,
                approval_request_id=decision.approval_request_id,
                approval_scope=decision.approval_scope,
                approval_status=approval_status,
                actor=actor,
                args_hash=decision.args_hash,
            ),
            logger,
        )

    def _now(self) -> datetime:
        value = self._now_factory()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _utcnow() -> datetime:
    return datetime.now(UTC)
