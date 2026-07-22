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


async def _echo_invoker(tool_name: str, arguments: dict[str, Any]) -> object:
    return {"tool": tool_name, "arguments": arguments}


def test_executor_denies_outside_root_file_path_before_invoker(
    tmp_path: Path,
) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-outside-root",
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

    assert result.status == "denied"
    assert result.invoker_reached is False
    payload = json.loads(result.output)
    assert payload["blocked"] is True
    assert payload["policy"]["reason"] == "resource_policy_file_path_outside_roots"
    assert payload["policy"]["metadata"]["resource_policy"]["metadata"][
        "invoker_reached"
    ] is False


def test_executor_allows_workspace_file_path_to_invoker(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("ok", encoding="utf-8")

    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-inside-root",
                tool_name="read_file",
                arguments={"path": "README.md"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                resource_roots=(str(tmp_path),),
            ),
            _echo_invoker,
        )
    )

    assert result.status == "success"
    assert result.invoker_reached is True


def test_executor_denies_write_file_outside_root_before_invoker(
    tmp_path: Path,
) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-write-outside-root",
                tool_name="write_file",
                arguments={"path": "../secret.txt", "content": "secret"},
                source="passive",
                registered=True,
                registry_risk="write",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False


def test_executor_denies_edit_file_outside_root_before_invoker(
    tmp_path: Path,
) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-edit-outside-root",
                tool_name="edit_file",
                arguments={
                    "path": "../secret.txt",
                    "old_text": "a",
                    "new_text": "b",
                },
                source="passive",
                registered=True,
                registry_risk="write",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False


def test_executor_denies_list_dir_outside_root_before_invoker(
    tmp_path: Path,
) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-list-outside-root",
                tool_name="list_dir",
                arguments={"path": "../outside"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False


def test_executor_denies_invalid_file_path_as_json_before_invoker(
    tmp_path: Path,
) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-invalid-path",
                tool_name="read_file",
                arguments={"path": "bad\0path"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    payload = json.loads(result.output)
    assert payload["policy"]["reason"] == "resource_policy_invalid_file_path"
    assert payload["invoker_reached"] is False


def test_executor_denies_protected_argument_before_invoker(tmp_path: Path) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-protected",
                tool_name="tool_search",
                arguments={"query": "x", "_session_key": "forged"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    payload = json.loads(result.output)
    assert payload["policy"]["reason"] == "resource_policy_protected_argument_forged"
    assert (
        payload["policy"]["metadata"]["resource_policy"]["metadata"]["argument"]
        == "_session_key"
    )


def test_executor_denies_shell_pipe_before_invoker(tmp_path: Path) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-shell-pipe",
                tool_name="shell",
                arguments={"command": "echo a|xargs rm file.txt"},
                source="passive",
                registered=True,
                registry_risk="external-side-effect",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    payload = json.loads(result.output)
    assert (
        payload["policy"]["reason"]
        == "resource_policy_shell_destructive_compound_denied"
    )


def test_executor_denies_localhost_web_fetch_before_invoker(tmp_path: Path) -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-url-localhost",
                tool_name="web_fetch",
                arguments={"url": "http://localhost:8080"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                resource_roots=(str(tmp_path),),
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    payload = json.loads(result.output)
    assert payload["policy"]["reason"] == "resource_policy_url_local_target_denied"
