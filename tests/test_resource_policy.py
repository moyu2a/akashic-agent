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
