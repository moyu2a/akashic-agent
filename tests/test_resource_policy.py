from __future__ import annotations

from pathlib import Path

from agent.policies.resource_policy import (
    ResourcePolicyContext,
    ResourcePolicyEngine,
)


def test_non_file_tool_is_not_applicable(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="search_docs",
            arguments={"query": "agent runtime"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "not_applicable"
    assert decision.reason == "resource_policy_not_applicable"


def test_file_tool_without_path_is_not_applicable(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="read_file",
            arguments={},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "not_applicable"
    assert decision.reason == "resource_policy_missing_path_argument"


def test_workspace_relative_read_is_allowed(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("ok", encoding="utf-8")

    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="read_file",
            arguments={"path": "README.md"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "allow"
    assert decision.reason == "resource_policy_file_path_allowed"
    assert decision.target == str(target.resolve())
    assert decision.metadata["within_roots"] is True


def test_parent_escape_is_denied(tmp_path: Path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="read_file",
            arguments={"path": "../secret.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_file_path_outside_roots"
    assert decision.metadata["invoker_reached"] is False


def test_protected_system_path_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="write_file",
            arguments={"path": "/etc/passwd"},
            resource_roots=(str(tmp_path),),
            registry_risk="write",
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_protected_system_path"


def test_symlink_escape_is_denied(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "link-out"
    link.symlink_to(outside, target_is_directory=True)

    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="read_file",
            arguments={"path": "link-out/secret.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_file_path_outside_roots"


def test_absolute_path_inside_root_is_allowed(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "note.md"
    target.parent.mkdir()
    target.write_text("ok", encoding="utf-8")

    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="read_file",
            arguments={"path": str(target)},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "allow"
    assert decision.target == str(target.resolve())


def test_missing_file_inside_existing_root_is_allowed_for_tool_to_report(
    tmp_path: Path,
) -> None:
    target = tmp_path / "missing.md"

    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="read_file",
            arguments={"path": "missing.md"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "allow"
    assert decision.target == str(target.resolve(strict=False))


def test_missing_write_parent_inside_root_is_allowed_for_tool_to_report(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-dir" / "note.md"

    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="write_file",
            arguments={"path": "new-dir/note.md"},
            resource_roots=(str(tmp_path),),
            registry_risk="write",
        )
    )

    assert decision.action == "allow"
    assert decision.target == str(target.resolve(strict=False))


def test_invalid_file_path_is_denied_instead_of_raising(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="read_file",
            arguments={"path": "bad\0path"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_invalid_file_path"
    assert decision.metadata["invoker_reached"] is False


def test_protected_runtime_argument_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="tool_search",
            arguments={"query": "x", "_session_key": "forged"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_protected_argument_forged"
    assert decision.metadata["argument"] == "_session_key"
    assert decision.metadata["invoker_reached"] is False


def test_task_execution_protected_attempt_argument_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="finish_task_step_execution",
            arguments={"_task_execution_attempt_id": "forged"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_protected_argument_forged"
    assert decision.metadata["argument"] == "_task_execution_attempt_id"


def test_all_known_protected_runtime_arguments_are_denied(tmp_path: Path) -> None:
    from agent.tools.execution_context import TASK_EXECUTION_PROTECTED_KEYS

    keys = sorted(
        {
            "_request_id",
            "_attempt_id",
            "_transport_request_id",
            *TASK_EXECUTION_PROTECTED_KEYS,
        }
    )

    for key in keys:
        decision = ResourcePolicyEngine().evaluate(
            ResourcePolicyContext(
                tool_name="tool_search",
                arguments={"query": "x", key: "forged"},
                resource_roots=(str(tmp_path),),
            )
        )
        assert decision.action == "deny", key
        assert decision.reason == "resource_policy_protected_argument_forged"


def test_simple_shell_read_command_is_allowed(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "pwd"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "allow"
    assert decision.reason == "resource_policy_shell_command_allowed"


def test_shell_pipe_xargs_rm_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "echo a | xargs rm file.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_shell_destructive_compound_denied"


def test_shell_unspaced_pipe_xargs_rm_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "echo a|xargs rm file.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_shell_destructive_compound_denied"


def test_shell_unspaced_semicolon_rm_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "echo ok;rm file.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_shell_destructive_compound_denied"


def test_shell_rm_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "rm file.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_shell_destructive_command_denied"


def test_shell_sudo_rm_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "sudo -n rm file.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_shell_destructive_command_denied"


def test_shell_xargs_rm_without_pipe_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "xargs rm file.txt"},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_shell_destructive_command_denied"


def test_shell_python_inline_remove_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "python -c \"import os\\nos.remove('/tmp/a')\""},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_shell_inline_interpreter_denied"


def test_shell_quoted_semicolon_is_not_treated_as_compound(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "python -c \"print('a;b')\""},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "allow"
    assert decision.reason == "resource_policy_shell_command_allowed"


def test_shell_quoted_command_substitution_text_is_allowed(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="shell",
            arguments={"command": "python -c \"print('$(not shell)')\""},
            resource_roots=(str(tmp_path),),
        )
    )

    assert decision.action == "allow"
    assert decision.reason == "resource_policy_shell_command_allowed"


def test_public_https_url_is_allowed(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="web_fetch",
            arguments={"url": "https://example.com/page"},
            resource_roots=(str(tmp_path),),
            registry_risk="read-only",
        )
    )

    assert decision.action == "allow"
    assert decision.reason == "resource_policy_url_allowed"


def test_file_url_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="web_fetch",
            arguments={"url": "file:///etc/passwd"},
            resource_roots=(str(tmp_path),),
            registry_risk="read-only",
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_url_scheme_denied"


def test_localhost_url_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="web_fetch",
            arguments={"url": "http://localhost:8080"},
            resource_roots=(str(tmp_path),),
            registry_risk="read-only",
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_url_local_target_denied"


def test_localhost_trailing_dot_url_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="web_fetch",
            arguments={"url": "http://localhost./"},
            resource_roots=(str(tmp_path),),
            registry_risk="read-only",
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_url_local_target_denied"


def test_dot_local_url_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="web_fetch",
            arguments={"url": "http://device.local/status"},
            resource_roots=(str(tmp_path),),
            registry_risk="read-only",
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_url_local_target_denied"


def test_private_ip_url_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="web_fetch",
            arguments={"url": "http://10.0.0.5/data"},
            resource_roots=(str(tmp_path),),
            registry_risk="read-only",
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_url_private_ip_denied"


def test_http_url_without_hostname_is_denied(tmp_path: Path) -> None:
    decision = ResourcePolicyEngine().evaluate(
        ResourcePolicyContext(
            tool_name="web_fetch",
            arguments={"url": "https:///missing-host"},
            resource_roots=(str(tmp_path),),
            registry_risk="read-only",
        )
    )

    assert decision.action == "deny"
    assert decision.reason == "resource_policy_url_invalid"
