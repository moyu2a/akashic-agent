from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.policies.approved_shell_side_effect_runtime import (
    ApprovedShellSideEffectRuntime,
)
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.shell_sandbox_runner import SandboxRunResult
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerQuery,
    ToolAuditLedgerStore,
)
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore


@dataclass
class RecordingSandboxRunner:
    called: bool = False
    commands: list[str] = field(default_factory=list)

    def backend_name(self) -> str:
        return "podman"

    def run(self, preview, command: str) -> SandboxRunResult:
        self.called = True
        self.commands.append(command)
        return SandboxRunResult(
            ok=True,
            reason="sandbox_executed",
            exit_code=0,
            stdout_path="stdout.txt",
            stderr_path="stderr.txt",
            stdout_hash="stdout-hash",
            stderr_hash="stderr-hash",
            stdout_bytes=3,
            stderr_bytes=0,
            stdout_truncated=False,
            stderr_truncated=False,
            duration_ms=100,
        )


class TimeoutSandboxRunner(RecordingSandboxRunner):
    def run(self, preview, command: str) -> SandboxRunResult:
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)


class _FailingLedger:
    def record_event(self, _event):
        raise RuntimeError("ledger down")


class FailingExecutionFailedStore(ApprovedSideEffectStore):
    def mark_execution_failed(self, *args, **kwargs):
        raise RuntimeError("side effect store down")


def _approval_runtime(workspace: Path, audit_ledger_store=None) -> ToolApprovalRuntime:
    return ToolApprovalRuntime(
        ToolApprovalStore(ToolApprovalRuntime.approval_db_path_from_workspace(workspace)),
        side_effect_vault=SideEffectPayloadVault(
            SideEffectPayloadVault.root_for_workspace(workspace)
        ),
        audit_ledger_store=audit_ledger_store,
    )


def _approved_shell(runtime: ToolApprovalRuntime, arguments: dict[str, object]) -> str:
    record = runtime.record_defer_request(
        request_id="call-shell-1",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        source="passive",
        tool_name="shell",
        risk="external-side-effect",
        approval_scope="tool_call",
        policy_reason="risk_strategy_shell_requires_approval",
        arguments=arguments,
    )
    assert runtime.side_effect_vault is not None
    runtime.side_effect_vault.put_payload(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        arguments=arguments,
        created_at=runtime._now(),
        expires_at=record.expires_at,
    )
    runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=runtime._now(),
    )
    return record.approval_request_id


def _runtime(
    workspace: Path, sandbox_runner: object | None, audit_ledger_store=None
) -> ApprovedShellSideEffectRuntime:
    return ApprovedShellSideEffectRuntime(
        approval_runtime=_approval_runtime(workspace, audit_ledger_store),
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        sandbox_runner=sandbox_runner,
        audit_ledger_store=audit_ledger_store,
    )


def test_approved_shell_runtime_prepares_and_runs_in_sandbox(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(
        approval_runtime,
        {"command": "echo hi", "description": "say hi", "timeout": 30},
    )
    runner = RecordingSandboxRunner()
    store = ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace))
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=runner,
    )

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", workspace, (str(workspace),))
    applied = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert prepared.ok
    assert prepared.reason == "shell_sandbox_preview_ready"
    assert "echo hi" not in prepared.message
    assert applied.ok
    assert applied.reason == "sandbox_executed"
    assert runner.called is True
    assert approval_runtime.store.get_request(approval_id).status == "executed"
    stored = store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "executed"
    assert stored.stdout_ref.startswith(f"artifacts/{stored.preview_id}/")
    assert stored.stderr_ref.startswith(f"artifacts/{stored.preview_id}/")
    assert b"echo hi" not in store.db_path.read_bytes()


def test_shell_side_effect_runtime_ledger_failure_does_not_change_result(
    tmp_path: Path,
) -> None:
    runtime = _runtime(
        tmp_path,
        sandbox_runner=RecordingSandboxRunner(),
        audit_ledger_store=_FailingLedger(),
    )
    approval_id = _approved_shell(
        runtime.approval_runtime, {"command": "echo hi", "timeout": 30}
    )

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", tmp_path, (str(tmp_path),))
    applied = runtime.apply(approval_id, "cli:test", "status_command", tmp_path, (str(tmp_path),))

    assert prepared.ok is True
    assert applied.ok is True
    assert runtime.approval_runtime.store.get_request(approval_id).status == "executed"


def test_shell_side_effect_runtime_records_bounded_sandbox_metadata(
    tmp_path: Path,
) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    runtime = _runtime(
        tmp_path,
        sandbox_runner=RecordingSandboxRunner(),
        audit_ledger_store=ledger,
    )
    approval_id = _approved_shell(
        runtime.approval_runtime, {"command": "echo raw-secret", "timeout": 30}
    )

    prepared = runtime.prepare(approval_id, "cli:test", "status_command", tmp_path, (str(tmp_path),))
    applied = runtime.apply(approval_id, "cli:test", "status_command", tmp_path, (str(tmp_path),))

    assert prepared.ok is True
    assert applied.ok is True
    events = ledger.query_events(ToolAuditLedgerQuery(approval_request_id=approval_id, limit=20))
    serialized = "\n".join(str(event.metadata) for event in events)
    assert "command_hash" in serialized
    assert "stdout_hash" in serialized
    assert "echo raw-secret" not in serialized


def test_shell_side_effect_runtime_records_sandbox_unavailable_and_timeout(
    tmp_path: Path,
) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    unavailable_runtime = _runtime(
        tmp_path / "unavailable", sandbox_runner=None, audit_ledger_store=ledger
    )
    unavailable_id = _approved_shell(
        unavailable_runtime.approval_runtime, {"command": "echo hi", "timeout": 30}
    )
    unavailable = unavailable_runtime.prepare(
        unavailable_id,
        "cli:test",
        "status_command",
        tmp_path / "unavailable",
        (str(tmp_path),),
    )
    assert unavailable.ok is False

    timeout_runtime = _runtime(
        tmp_path / "timeout",
        sandbox_runner=TimeoutSandboxRunner(),
        audit_ledger_store=ledger,
    )
    timeout_id = _approved_shell(
        timeout_runtime.approval_runtime, {"command": "sleep 999", "timeout": 1}
    )
    timeout = timeout_runtime.apply(
        timeout_id,
        "cli:test",
        "status_command",
        tmp_path / "timeout",
        (str(tmp_path),),
    )
    assert timeout.ok is False

    events = ledger.query_events(ToolAuditLedgerQuery(limit=50))
    assert {event.event_type for event in events} >= {
        "approved_shell_sandbox_unavailable",
        "approved_shell_sandbox_timeout",
    }


def test_shell_side_effect_runtime_does_not_record_timeout_before_state_persists(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    approval_runtime = _approval_runtime(workspace, ledger)
    approval_id = _approved_shell(
        approval_runtime, {"command": "sleep 999", "timeout": 1}
    )
    store = FailingExecutionFailedStore(
        ApprovedSideEffectStore.db_path_from_workspace(workspace)
    )
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=TimeoutSandboxRunner(),
        audit_ledger_store=ledger,
    )

    result = runtime.apply(
        approval_id,
        "cli:test",
        "status_command",
        workspace,
        (str(workspace),),
    )

    events = ledger.query_events(ToolAuditLedgerQuery(approval_request_id=approval_id, limit=20))
    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert "approved_shell_sandbox_timeout" not in {
        event.event_type for event in events
    }
    assert "approved_shell_state_persistence_failed" in {
        event.event_type for event in events
    }


def test_approved_shell_runtime_fails_closed_without_sandbox_runner(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=None,
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_sandbox_unavailable"
    assert approval_runtime.store.get_request(approval_id).status == "approved"


def test_approved_shell_runtime_denies_destructive_command_before_runner(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "rm -rf notes", "description": "remove notes"})
    runner = RecordingSandboxRunner()
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=runner,
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "resource_policy_shell_destructive_command_denied"
    assert runner.called is False
    assert approval_runtime.store.get_request(approval_id).status == "approved"
    assert "rm -rf" not in str(result.metadata)


@pytest.mark.parametrize(
    "command",
    [
        "sh -c 'rm -rf /tmp/x'",
        "dash -c 'rm -rf /tmp/x'",
        "sudo -u nobody sh -c 'rm -rf /tmp/x'",
        "env -u HOME sh -c 'rm -rf /tmp/x'",
        "echo $(rm -rf /tmp/x)",
        "if true; then rm -rf /tmp/x; fi",
        "cat <<'EOF'\nsecret\nEOF",
        "(echo hi)",
        "cat <(echo hi)",
    ],
)
def test_approved_shell_runtime_denies_unsupported_nested_syntax_without_consuming(
    tmp_path: Path, command: str
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": command})
    runner = RecordingSandboxRunner()
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        sandbox_runner=runner,
    )

    result = runtime.apply(
        approval_id, "cli:test", "status_command", workspace, (str(workspace),)
    )

    assert result.ok is False
    assert result.reason.startswith("resource_policy_shell_")
    assert runner.called is False
    assert approval_runtime.store.get_request(approval_id).status == "approved"


def test_approved_shell_runtime_executes_exact_command_with_surrounding_whitespace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    command = "  printf exact-command\n"
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": command})
    runner = RecordingSandboxRunner()
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        sandbox_runner=runner,
    )

    result = runtime.apply(
        approval_id, "cli:test", "status_command", workspace, (str(workspace),)
    )

    assert result.ok is True
    assert runner.commands == [command]


def test_approved_shell_runtime_denies_protected_arguments_before_runner(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(
        approval_runtime,
        {"command": "echo hi", "description": "say hi", "_session_key": "cli:forged"},
    )
    runner = RecordingSandboxRunner()
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=runner,
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "resource_policy_protected_argument_forged"
    assert runner.called is False
    assert approval_runtime.store.get_request(approval_id).status == "approved"


def test_approved_shell_runtime_rejects_task_execution_scope_without_resume(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    args = {"command": "echo hi", "description": "say hi"}
    record = approval_runtime.record_defer_request(
        request_id="call-shell-1",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        source="task_execution",
        tool_name="shell",
        risk="external-side-effect",
        approval_scope="task_execution_step",
        policy_reason="task_execution_side_effect_requires_authorization",
        arguments=args,
    )
    assert approval_runtime.side_effect_vault is not None
    approval_runtime.side_effect_vault.put_payload(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        arguments=args,
        created_at=approval_runtime._now(),
        expires_at=record.expires_at,
    )
    approval_runtime.store.approve_request(
        approval_request_id=record.approval_request_id,
        request_id=record.request_id,
        session_key=record.session_key,
        tool_name=record.tool_name,
        approval_scope=record.approval_scope,
        args_hash=record.args_hash,
        actor="status_command",
        now=approval_runtime._now(),
    )
    runner = RecordingSandboxRunner()
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=runner,
    )

    result = runtime.apply(record.approval_request_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "task_execution_shell_resume_not_supported"
    assert runner.called is False
    assert approval_runtime.store.get_request(record.approval_request_id).status == "approved"


def test_approved_shell_runtime_rejects_background_request_before_runner(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(
        approval_runtime,
        {"command": "echo hi", "description": "say hi", "run_in_background": True},
    )
    runner = RecordingSandboxRunner()
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=runner,
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_background_not_supported"
    assert runner.called is False
    assert approval_runtime.store.get_request(approval_id).status == "approved"


def test_approved_shell_runtime_finalizes_failed_execution_on_runner_exception(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})

    class FailingSandboxRunner:
        def backend_name(self) -> str:
            return "podman"

        def run(self, preview, command: str) -> SandboxRunResult:
            raise FileNotFoundError("podman not available")

    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=FailingSandboxRunner(),
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_sandbox_unavailable"
    assert approval_runtime.store.get_request(approval_id).status == "execution_failed"
    stored = runtime.side_effect_store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "execution_failed"


def test_approved_shell_runtime_preserves_approval_when_failure_state_persistence_raises(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})

    class FailingSideEffectStore(ApprovedSideEffectStore):
        def mark_execution_failed(self, **kwargs):
            raise RuntimeError("side-effect store unavailable")

    class FailingSandboxRunner:
        def backend_name(self) -> str:
            return "podman"

        def run(self, preview, command: str) -> SandboxRunResult:
            raise RuntimeError("runner failed after approval consumption")

    store = FailingSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace))
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=FailingSandboxRunner(),
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "preview_ready"


def test_approved_shell_runtime_rejects_out_of_tree_artifact_refs_before_store_update(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})

    class BadArtifactRunner:
        def backend_name(self) -> str:
            return "podman"

        def run(self, preview, command: str) -> SandboxRunResult:
            return SandboxRunResult(
                ok=True,
                reason="sandbox_executed",
                exit_code=0,
                stdout_path="/tmp/stdout.txt",
                stderr_path="../stderr.txt",
                stdout_hash="stdout-hash",
                stderr_hash="stderr-hash",
                stdout_bytes=3,
                stderr_bytes=0,
                stdout_truncated=False,
                stderr_truncated=False,
                duration_ms=100,
            )

    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=BadArtifactRunner(),
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = runtime.side_effect_store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "executed"
    assert stored.execution_status == "sandbox_executed"
    assert stored.stdout_ref == ""
    assert stored.stderr_ref == ""


def test_approved_shell_runtime_rejects_absolute_artifact_refs_before_store_update(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})

    class AbsoluteArtifactRunner:
        def backend_name(self) -> str:
            return "podman"

        def run(self, preview, command: str) -> SandboxRunResult:
            return SandboxRunResult(
                ok=True,
                reason="sandbox_executed",
                exit_code=0,
                stdout_path=str(preview.artifact_dir / "stdout.txt"),
                stderr_path=str(preview.artifact_dir / "stderr.txt"),
                stdout_hash="stdout-hash",
                stderr_hash="stderr-hash",
                stdout_bytes=3,
                stderr_bytes=0,
                stdout_truncated=False,
                stderr_truncated=False,
                duration_ms=100,
            )

    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace)),
        sandbox_runner=AbsoluteArtifactRunner(),
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = runtime.side_effect_store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "executed"
    assert stored.execution_status == "sandbox_executed"


def test_approved_shell_runtime_compensates_when_approval_finalize_fails(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})
    store = ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace))
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=RecordingSandboxRunner(),
    )

    def fail_finalize(**kwargs):
        raise RuntimeError("approval db unavailable")

    monkeypatch.setattr(approval_runtime, "finalize_execution", fail_finalize)

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "executed"
    assert stored.execution_status == "sandbox_executed"


def test_approved_shell_runtime_preserves_success_when_result_store_fails(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi"})

    class ResultStoreFailure(ApprovedSideEffectStore):
        def mark_shell_executed(self, **kwargs):
            raise RuntimeError("result persistence unavailable")

    store = ResultStoreFailure(
        ApprovedSideEffectStore.db_path_from_workspace(workspace)
    )
    runner = RecordingSandboxRunner()
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=runner,
    )

    result = runtime.apply(
        approval_id, "cli:test", "status_command", workspace, (str(workspace),)
    )

    assert runner.called is True
    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "executed"
    assert stored.execution_status == "sandbox_executed"


def test_approved_shell_runtime_compensates_when_approval_finalize_returns_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})
    store = ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace))
    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=RecordingSandboxRunner(),
    )
    monkeypatch.setattr(
        approval_runtime,
        "finalize_execution",
        lambda **kwargs: SimpleNamespace(action="mismatch"),
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "executed"
    assert stored.execution_status == "sandbox_executed"


def test_approved_shell_runtime_compensates_failure_path_finalize_failure(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})
    store = ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace))

    class FailingSandboxRunner:
        def backend_name(self) -> str:
            return "podman"

        def run(self, preview, command: str) -> SandboxRunResult:
            raise FileNotFoundError("podman not available")

    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=FailingSandboxRunner(),
    )

    def fail_finalize(**kwargs):
        raise RuntimeError("approval db unavailable")

    monkeypatch.setattr(approval_runtime, "finalize_execution", fail_finalize)

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "execution_failed"
    assert stored.execution_status == "shell_sandbox_unavailable"


def test_approved_shell_runtime_compensates_failure_path_finalize_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path
    approval_runtime = _approval_runtime(workspace)
    approval_id = _approved_shell(approval_runtime, {"command": "echo hi", "description": "say hi"})
    store = ApprovedSideEffectStore(ApprovedSideEffectStore.db_path_from_workspace(workspace))

    class FailingSandboxRunner:
        def backend_name(self) -> str:
            return "podman"

        def run(self, preview, command: str) -> SandboxRunResult:
            raise FileNotFoundError("podman not available")

    runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=store,
        sandbox_runner=FailingSandboxRunner(),
    )
    monkeypatch.setattr(
        approval_runtime,
        "finalize_execution",
        lambda **kwargs: SimpleNamespace(action="mismatch"),
    )

    result = runtime.apply(approval_id, "cli:test", "status_command", workspace, (str(workspace),))

    assert result.ok is False
    assert result.reason == "shell_execution_state_persistence_failed"
    assert approval_runtime.store.get_request(approval_id).status == "consumed"
    stored = store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "execution_failed"
    assert stored.execution_status == "shell_sandbox_unavailable"


def test_approved_shell_runtime_does_not_support_rollback(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, RecordingSandboxRunner())

    result = runtime.rollback("approval-shell-1", "cli:test", "status_command", tmp_path, (str(tmp_path),))

    assert result.ok is False
    assert result.reason == "rollback_not_supported_for_shell"
