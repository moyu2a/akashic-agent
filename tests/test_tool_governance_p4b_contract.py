from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent.lifecycle.types import TurnState
from agent.policies.approved_shell_side_effect_runtime import (
    ApprovedShellSideEffectRuntime,
)
from agent.policies.approved_side_effect_store import ApprovedSideEffectStore
from agent.policies.shell_sandbox_runner import SandboxRunResult
from agent.policies.side_effect_payload_vault import SideEffectPayloadVault
from agent.policies.tool_approval_context import trusted_approval_from_runtime
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_approval_store import ToolApprovalStore
from agent.tool_hooks import ToolExecutionRequest, ToolExecutor
from bus.events import InboundMessage
from plugins.observe.plugin import _slim_tool_chain
from plugins.status_commands.plugin import (
    ToolApprovalCommandModule,
    _side_effect_lifecycle_event,
)


@dataclass
class RecordingSandboxRunner:
    called: bool = False
    commands: list[str] = field(default_factory=list)

    def backend_name(self) -> str:
        return "podman"

    def run(self, preview, command: str) -> SandboxRunResult:
        self.called = True
        self.commands.append(command)
        stdout = b"bounded fake stdout text\n"
        stderr = b"bounded fake stderr text\n"
        preview.artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_private_artifact(preview.artifact_dir / "stdout.txt", stdout)
        _write_private_artifact(preview.artifact_dir / "stderr.txt", stderr)
        return SandboxRunResult(
            ok=True,
            reason="sandbox_executed",
            exit_code=0,
            stdout_path="stdout.txt",
            stderr_path="stderr.txt",
            stdout_hash=hashlib.sha256(stdout).hexdigest(),
            stderr_hash=hashlib.sha256(stderr).hexdigest(),
            stdout_bytes=len(stdout),
            stderr_bytes=len(stderr),
            stdout_truncated=False,
            stderr_truncated=False,
            duration_ms=100,
        )


class RecordingInvoker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, tool_name: str, arguments: dict[str, Any]) -> object:
        self.calls.append((tool_name, dict(arguments)))
        return {"ok": True}


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _write_private_artifact(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as artifact:
        artifact.write(content)
    os.chmod(path, 0o600)


def _runtime(workspace: Path) -> ToolApprovalRuntime:
    return ToolApprovalRuntime(
        ToolApprovalStore(ToolApprovalRuntime.approval_db_path_from_workspace(workspace)),
        side_effect_vault=SideEffectPayloadVault(
            SideEffectPayloadVault.root_for_workspace(workspace)
        ),
    )


def _shell_request(
    workspace: Path,
    *,
    command: str = "echo hi",
    trusted_approval_id: str | None = None,
) -> ToolExecutionRequest:
    trusted = None
    if trusted_approval_id is not None:
        trusted = trusted_approval_from_runtime(
            approval_request_id=trusted_approval_id,
            actor="status_command",
            source="status_command",
        )
    return ToolExecutionRequest(
        call_id="call-shell",
        tool_name="shell",
        arguments={"command": command, "description": "say hi"},
        source="passive",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        registered=True,
        registry_risk="external-side-effect",
        trusted_approval_context=trusted,
        resource_roots=(str(workspace),),
    )


def _approve(approval_runtime: ToolApprovalRuntime, approval_id: str) -> None:
    record = approval_runtime.store.get_request(approval_id)
    assert record is not None
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


async def _run_status_command(
    module: ToolApprovalCommandModule, content: str
) -> Any:
    msg = InboundMessage(
        channel="cli",
        sender="user",
        chat_id="test",
        content=content,
        timestamp=datetime(2026, 7, 27, tzinfo=UTC),
    )
    state = TurnState(msg=msg, session_key="cli:test", dispatch_outbound=True)
    frame = SimpleNamespace(slots={}, input=state)
    await module.run(frame)
    ctx = frame.slots["session:ctx"]
    assert ctx.abort is True
    return ctx


def test_p4b_shell_approval_requires_sandbox_runtime_and_never_host_invoker(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    approval_runtime = _runtime(workspace)
    invoker = RecordingInvoker()
    deferred = _run(
        ToolExecutor(approval_runtime=approval_runtime).execute(
            _shell_request(workspace),
            invoker,
        )
    )
    approval_id = json.loads(deferred.output)["approval_request"]["approval_request_id"]
    _approve(approval_runtime, approval_id)

    direct = _run(
        ToolExecutor(approval_runtime=approval_runtime).execute(
            _shell_request(workspace, trusted_approval_id=approval_id),
            invoker,
        )
    )
    runner = RecordingSandboxRunner()
    shell_runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        sandbox_runner=runner,
    )
    applied = shell_runtime.apply(
        approval_id, "cli:test", "status_command", workspace, (str(workspace),)
    )

    assert deferred.status == "deferred"
    assert approval_runtime.side_effect_vault is not None
    assert approval_runtime.side_effect_vault.get_payload(approval_id) is not None
    assert direct.status == "deferred"
    assert direct.invoker_reached is False
    assert invoker.calls == []
    assert applied.ok
    assert runner.called is True


def test_p4b_shell_fails_closed_when_sandbox_unavailable(tmp_path: Path) -> None:
    workspace = tmp_path
    approval_runtime = _runtime(workspace)
    record = approval_runtime.record_defer_request(
        request_id="call-shell",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        source="passive",
        tool_name="shell",
        risk="external-side-effect",
        approval_scope="tool_call",
        policy_reason="risk_strategy_shell_requires_approval",
        arguments={"command": "echo hi", "description": "say hi"},
    )
    approval_runtime.record_managed_side_effect_payload(
        record,
        arguments={"command": "echo hi", "description": "say hi"},
    )
    _approve(approval_runtime, record.approval_request_id)
    shell_runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        sandbox_runner=None,
    )

    result = shell_runtime.apply(
        record.approval_request_id,
        "cli:test",
        "status_command",
        workspace,
        (str(workspace),),
    )

    assert result.ok is False
    assert result.reason == "shell_sandbox_unavailable"
    assert approval_runtime.store.get_request(record.approval_request_id).status == "approved"


def test_p4b_destructive_trusted_shell_is_denied_before_managed_runtime(
    tmp_path: Path,
) -> None:
    raw_command = "rm -rf notes --secret-token=raw-shell-command"
    result = _run(
        ToolExecutor(approval_runtime=_runtime(tmp_path)).execute(
            _shell_request(
                tmp_path,
                command=raw_command,
                trusted_approval_id="approval-shell",
            ),
            RecordingInvoker(),
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    assert "resource_policy_shell_destructive_command_denied" in result.output
    assert "managed runtime" not in result.output.lower()
    assert result.policy_trace["reason"] == "resource_policy_shell_destructive_command_denied"
    assert result.policy_trace["metadata"]["resource_policy"]["reason"] == (
        "resource_policy_shell_destructive_command_denied"
    )
    for public_value in (
        result.output,
        result.final_arguments,
        result.policy_trace,
        result.audit_trace,
        result.policy_trace["metadata"]["resource_policy"],
    ):
        assert raw_command not in json.dumps(public_value, ensure_ascii=False)


def test_p4b_shell_lifecycle_redacts_raw_command_everywhere(tmp_path: Path) -> None:
    workspace = tmp_path
    raw_command = "echo secret-token-value"
    approval_runtime = _runtime(workspace)
    invoker = RecordingInvoker()
    deferred = _run(
        ToolExecutor(approval_runtime=approval_runtime).execute(
            _shell_request(workspace, command=raw_command),
            invoker,
        )
    )
    approval_id = json.loads(deferred.output)["approval_request"]["approval_request_id"]
    _approve(approval_runtime, approval_id)
    side_effect_store = ApprovedSideEffectStore(
        ApprovedSideEffectStore.db_path_from_workspace(workspace)
    )
    runner = RecordingSandboxRunner()
    shell_runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=side_effect_store,
        sandbox_runner=runner,
    )

    prepared = shell_runtime.prepare(
        approval_id, "cli:test", "status_command", workspace, (str(workspace),)
    )
    applied = shell_runtime.apply(
        approval_id, "cli:test", "status_command", workspace, (str(workspace),)
    )
    stored = side_effect_store.get_by_approval_id(approval_id)
    assert stored is not None
    slim_event = _slim_tool_chain(
        [
            {
                "text": "",
                "calls": [
                    {
                        "name": "approved_side_effect_lifecycle",
                        "arguments": {},
                        "result": "",
                        "approved_side_effect_lifecycle": [
                            _side_effect_lifecycle_event(stored)
                        ],
                    }
                ],
            }
        ]
    )[0]["calls"][0]["approved_side_effect_lifecycle"][0]

    assert prepared.ok
    assert applied.ok
    assert raw_command not in deferred.output
    assert raw_command not in json.dumps(deferred.policy_trace, ensure_ascii=False)
    assert raw_command not in json.dumps(deferred.audit_trace, ensure_ascii=False)
    assert raw_command not in prepared.message
    assert raw_command not in applied.message
    assert raw_command.encode() not in ToolApprovalRuntime.approval_db_path_from_workspace(
        workspace
    ).read_bytes()
    assert raw_command.encode() not in side_effect_store.db_path.read_bytes()
    assert all(raw_command not in path.name for path in (workspace / "tool_side_effects").rglob("*"))
    assert raw_command not in json.dumps(slim_event, ensure_ascii=False)
    assert approval_runtime.side_effect_vault is not None
    assert raw_command in approval_runtime.side_effect_vault.get_payload(
        approval_id
    ).arguments["command"]
    assert runner.commands == [raw_command]
    artifact_dir = workspace / "tool_side_effects" / "artifacts" / prepared.preview_id
    stdout_path = artifact_dir / "stdout.txt"
    stderr_path = artifact_dir / "stderr.txt"
    assert stdout_path.read_bytes() == b"bounded fake stdout text\n"
    assert stderr_path.read_bytes() == b"bounded fake stderr text\n"
    assert stdout_path.stat().st_mode & 0o777 == 0o600
    assert stderr_path.stat().st_mode & 0o777 == 0o600
    assert stored.stdout_hash == hashlib.sha256(stdout_path.read_bytes()).hexdigest()
    assert stored.stderr_hash == hashlib.sha256(stderr_path.read_bytes()).hexdigest()
    assert stored.stdout_bytes == stdout_path.stat().st_size
    assert stored.stderr_bytes == stderr_path.stat().st_size
    assert stored.stdout_truncated is False
    assert stored.stderr_truncated is False
    stored_json = json.dumps(_side_effect_lifecycle_event(stored), ensure_ascii=False)
    assert "bounded fake stdout text" not in stored_json
    assert "bounded fake stderr text" not in stored_json
    assert str(stdout_path) not in stored_json
    assert str(stderr_path) not in stored_json


@pytest.mark.asyncio
async def test_p4b_shell_status_commands_expose_safe_lifecycle_without_private_data(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    raw_command = "echo raw-shell-command-secret"
    approval_runtime = _runtime(workspace)
    deferred = await ToolExecutor(approval_runtime=approval_runtime).execute(
        _shell_request(workspace, command=raw_command), RecordingInvoker()
    )
    approval_id = json.loads(deferred.output)["approval_request"]["approval_request_id"]
    _approve(approval_runtime, approval_id)
    runner = RecordingSandboxRunner()
    module = ToolApprovalCommandModule(
        "status_commands",
        approval_runtime.store,
        workspace=workspace,
        side_effect_store=ApprovedSideEffectStore(
            ApprovedSideEffectStore.db_path_from_workspace(workspace)
        ),
        side_effect_vault=approval_runtime.side_effect_vault,
        shell_sandbox_runner=runner,
    )

    prepared = await _run_status_command(module, f"/prepare_tool {approval_id}")
    ran = await _run_status_command(module, f"/run_approved_tool {approval_id}")

    assert "shell_sandbox_preview_ready" in prepared.abort_reply
    assert "sandbox_executed" in ran.abort_reply
    assert runner.commands == [raw_command]
    prepared_event = prepared.extra_metadata["approved_side_effect_lifecycle"][0]
    ran_event = ran.extra_metadata["approved_side_effect_lifecycle"][0]
    for event in (prepared_event, ran_event):
        assert event["command_hash"]
        assert event["sandbox_backend"] == "podman"
        assert event["sandbox_image"]
        assert event["network_mode"] == "none"
        assert event["workspace_mount_mode"] == "ro"
        assert event["timeout_seconds"] > 0
    assert ran_event["exit_code"] == 0
    assert ran_event["stdout_hash"]
    assert ran_event["stderr_hash"]
    assert ran_event["stdout_bytes"] > 0
    assert ran_event["stderr_bytes"] > 0
    assert ran_event["stdout_truncated"] is False
    assert ran_event["stderr_truncated"] is False
    assert ran_event["duration_ms"] == 100
    raw_artifact_paths = (
        str(workspace / "tool_side_effects" / "artifacts"),
        "stdout.txt",
        "stderr.txt",
    )
    for public_value in (
        prepared.abort_reply,
        ran.abort_reply,
        prepared.extra_metadata,
        ran.extra_metadata,
    ):
        encoded = json.dumps(public_value, ensure_ascii=False)
        assert raw_command not in encoded
        assert "bounded fake stdout text" not in encoded
        assert "bounded fake stderr text" not in encoded
        assert "payload_path" not in encoded
        assert all(path not in encoded for path in raw_artifact_paths)
