from __future__ import annotations

from pathlib import Path

from agent.policies.file_change_plan import (
    apply_file_change,
    prepare_file_change,
    rollback_file_change,
)


def test_prepare_write_file_creates_snapshot_and_diff_without_applying(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.md"
    target.write_text("before\n", encoding="utf-8")

    preview = prepare_file_change(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        tool_name="write_file",
        arguments={"path": "notes.md", "content": "after\n"},
    )

    assert target.read_text(encoding="utf-8") == "before\n"
    assert preview.before_exists is True
    assert preview.before_hash
    assert preview.after_hash
    assert "-before" in preview.diff_text
    assert "+after" in preview.diff_text
    assert preview.snapshot_path is not None


def test_apply_and_rollback_write_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.md"
    target.write_text("before\n", encoding="utf-8")
    preview = prepare_file_change(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        tool_name="write_file",
        arguments={"path": "notes.md", "content": "after\n"},
    )

    applied = apply_file_change(preview)
    rolled_back = rollback_file_change(preview)

    assert applied.ok is True
    assert target.read_text(encoding="utf-8") == "before\n"
    assert rolled_back.ok is True


def test_apply_rejects_when_file_changed_after_preview(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.md"
    target.write_text("before\n", encoding="utf-8")
    preview = prepare_file_change(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        tool_name="write_file",
        arguments={"path": "notes.md", "content": "after\n"},
    )
    target.write_text("external change\n", encoding="utf-8")

    applied = apply_file_change(preview)

    assert applied.ok is False
    assert applied.reason == "snapshot_conflict"
    assert target.read_text(encoding="utf-8") == "external change\n"


def test_prepare_edit_file_requires_exact_old_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.md"
    target.write_text("alpha\nbeta\n", encoding="utf-8")

    preview = prepare_file_change(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        tool_name="edit_file",
        arguments={"path": "notes.md", "old_text": "beta\n", "new_text": "gamma\n"},
    )

    assert "-beta" in preview.diff_text
    assert "+gamma" in preview.diff_text
