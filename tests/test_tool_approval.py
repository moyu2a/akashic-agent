from __future__ import annotations

import json

from agent.policies.tool_approval import (
    build_approval_payload,
    summarize_arguments,
)


def test_argument_summary_hashes_sensitive_values() -> None:
    summary = summarize_arguments(
        {
            "path": "/workspace/report.md",
            "content": "secret-content" * 100,
            "token": "abc123",
        }
    )

    assert summary["path"] == "/workspace/report.md"
    assert summary["content"]["kind"] == "text"
    assert summary["content"]["length"] > 100
    assert summary["content"]["sha256"]
    assert "preview" not in summary["content"]
    assert summary["token"] == {"redacted": True}


def test_argument_summary_does_not_preview_shell_command() -> None:
    command = "echo a | xargs rm file.txt"

    summary = summarize_arguments({"command": command})

    assert summary["command"]["kind"] == "text"
    assert summary["command"]["length"] == len(command)
    assert summary["command"]["sha256"]
    assert "preview" not in summary["command"]


def test_argument_summary_redacts_nested_sensitive_values() -> None:
    summary = summarize_arguments({"headers": {"Authorization": "Bearer secret"}})

    assert summary["headers"]["Authorization"] == {"redacted": True}


def test_argument_summary_hashes_unknown_strings_without_preview() -> None:
    summary = summarize_arguments({"freeform": "possibly sensitive short text"})

    assert summary["freeform"]["kind"] == "text"
    assert summary["freeform"]["length"] == len("possibly sensitive short text")
    assert "preview" not in summary["freeform"]


def test_approval_payload_is_json_safe_and_non_executed() -> None:
    payload = build_approval_payload(
        tool_name="write_file",
        arguments={"path": "notes.md", "content": "hello"},
        action="defer",
        reason="risk_strategy_write_requires_approval",
        risk="write",
        approval_scope="tool_call",
    )

    encoded = json.dumps(payload, ensure_ascii=False)
    decoded = json.loads(encoded)
    assert decoded["ok"] is False
    assert decoded["deferred"] is True
    assert decoded["invoker_reached"] is False
    assert decoded["approval_request"]["tool_name"] == "write_file"
    assert decoded["approval_request"]["args_hash"]
    assert "preview" not in decoded["approval_request"]["args_summary"]["content"]
