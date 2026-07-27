from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from plugins.observe.plugin import _slim_tool_chain
from plugins.status_commands.plugin import _side_effect_lifecycle_event


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


class RecordingInvoker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, tool_name: str, arguments: dict[str, Any]) -> object:
        self.calls.append((tool_name, dict(arguments)))
        return {"ok": True}


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


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
    result = _run(
        ToolExecutor(approval_runtime=_runtime(tmp_path)).execute(
            _shell_request(
                tmp_path,
                command="rm -rf notes",
                trusted_approval_id="approval-shell",
            ),
            RecordingInvoker(),
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False


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
    shell_runtime = ApprovedShellSideEffectRuntime(
        approval_runtime=approval_runtime,
        side_effect_store=side_effect_store,
        sandbox_runner=RecordingSandboxRunner(),
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
