from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent.tool_hooks import ToolExecutionRequest, ToolExecutor


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _raising_invoker(tool_name: str, arguments: dict[str, Any]) -> object:
    raise AssertionError(f"invoker reached for {tool_name}: {arguments}")


async def _recording_invoker(tool_name: str, arguments: dict[str, Any]) -> object:
    return {"tool": tool_name, "arguments": dict(arguments)}


def test_p1_denies_workspace_escape_before_real_invoker(tmp_path: Path) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="contract-p1-path",
                tool_name="read_file",
                arguments={"path": "../secret.txt"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    payload = json.loads(result.output)
    assert result.status == "denied"
    assert result.invoker_reached is False
    assert payload["policy"]["reason"] == "resource_policy_file_path_outside_roots"


def test_p1_denies_protected_runtime_argument_before_real_invoker() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="contract-p1-protected-arg",
                tool_name="tool_search",
                arguments={"query": "x", "_session_key": "forged"},
                source="passive",
                registered=True,
                registry_risk="read-only",
            ),
            _raising_invoker,
        )
    )

    payload = json.loads(result.output)
    assert result.status == "denied"
    assert result.invoker_reached is False
    assert payload["policy"]["reason"] == "resource_policy_protected_argument_forged"


def test_p1_denies_destructive_shell_wrapper_before_p2_defer() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="contract-p1-shell",
                tool_name="shell",
                arguments={"command": "echo a | xargs rm file.txt"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                registry_capabilities=frozenset({"shell.execute"}),
            ),
            _raising_invoker,
        )
    )

    payload = json.loads(result.output)
    assert result.status == "denied"
    assert result.invoker_reached is False
    assert (
        payload["policy"]["reason"]
        == "resource_policy_shell_destructive_compound_denied"
    )


def test_p2_allows_read_only_tool_after_resource_policy_passes(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("ok", encoding="utf-8")

    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="contract-p2-read",
                tool_name="read_file",
                arguments={"path": "README.md"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                resource_roots=(str(tmp_path),),
            ),
            _recording_invoker,
        )
    )

    assert result.status == "success"
    assert result.invoker_reached is True
    assert result.invoker_succeeded is True
    assert result.policy_trace["reason"] == "risk_strategy_read_only_allowed"


def test_p2_defers_write_with_approval_request_and_audit_trace(
    tmp_path: Path,
) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="contract-p2-write",
                tool_name="write_file",
                arguments={"path": "notes.md", "content": "private content"},
                source="passive",
                registered=True,
                registry_risk="write",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    payload = json.loads(result.output)
    assert result.status == "deferred"
    assert result.invoker_reached is False
    assert payload["approval_request"]["tool_name"] == "write_file"
    assert payload["approval_request"]["risk"] == "write"
    assert payload["approval_request"]["args_hash"]
    assert "preview" not in payload["approval_request"]["args_summary"]["content"]
    assert result.audit_trace["policy_action"] == "defer"
    assert result.audit_trace["args_hash"] == payload["approval_request"]["args_hash"]
    assert result.audit_trace["invoker_reached"] is False


def test_p2_defers_shell_even_when_command_is_not_p1_denied() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="contract-p2-shell",
                tool_name="shell",
                arguments={"command": "pwd"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                registry_capabilities=frozenset({"shell.execute"}),
            ),
            _raising_invoker,
        )
    )

    payload = json.loads(result.output)
    assert result.status == "deferred"
    assert result.invoker_reached is False
    assert payload["policy"]["reason"] == "risk_strategy_shell_requires_approval"
    assert payload["approval_request"]["tool_name"] == "shell"
