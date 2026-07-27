from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.policies.approved_shell_side_effect_runtime import (
    ApprovedShellSideEffectRuntime,
)
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.shell_sandbox_runner import SandboxRunResult
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore


@dataclass
class RecordingSandboxRunner:
    called: bool = False

    def backend_name(self) -> str:
        return "podman"

    def run(self, preview, command: str) -> SandboxRunResult:
        self.called = True
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


def _approval_runtime(workspace: Path) -> ToolApprovalRuntime:
    return ToolApprovalRuntime(
        ToolApprovalStore(ToolApprovalRuntime.approval_db_path_from_workspace(workspace)),
        side_effect_vault=SideEffectPayloadVault(
            SideEffectPayloadVault.root_for_workspace(workspace)
        ),
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
    workspace: Path, sandbox_runner: object | None
) -> ApprovedShellSideEffectRuntime:
    return ApprovedShellSideEffectRuntime(
        approval_runtime=_approval_runtime(workspace),
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        sandbox_runner=sandbox_runner,
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
    assert result.reason == "shell_artifact_path_invalid"
    assert approval_runtime.store.get_request(approval_id).status == "execution_failed"
    stored = runtime.side_effect_store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "execution_failed"
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
    assert result.reason == "shell_artifact_path_invalid"
    assert approval_runtime.store.get_request(approval_id).status == "execution_failed"
    stored = runtime.side_effect_store.get_by_approval_id(approval_id)
    assert stored is not None
    assert stored.status == "execution_failed"


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
    assert stored.status == "execution_failed"
    assert stored.execution_status == "shell_execution_state_persistence_failed"


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
    assert stored.execution_status == "shell_execution_state_persistence_failed"


def test_approved_shell_runtime_does_not_support_rollback(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, RecordingSandboxRunner())

    result = runtime.rollback("approval-shell-1", "cli:test", "status_command", tmp_path, (str(tmp_path),))

    assert result.ok is False
    assert result.reason == "rollback_not_supported_for_shell"
