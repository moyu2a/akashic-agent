from __future__ import annotations

import difflib
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

_MAX_DIFF_CHARS = 20_000


@dataclass(frozen=True)
class FileChangePreview:
    preview_id: str
    tool_name: str
    target_path: Path
    display_path: str
    before_exists: bool
    before_hash: str
    after_hash: str
    snapshot_path: Path | None
    after_path: Path
    diff_path: Path
    diff_text: str
    diff_truncated: bool


@dataclass(frozen=True)
class FileApplyResult:
    ok: bool
    reason: str
    target_path: Path
    after_hash: str = ""


@dataclass(frozen=True)
class FileRollbackResult:
    ok: bool
    reason: str
    target_path: Path
    restored_hash: str = ""


def prepare_file_change(
    *,
    workspace_root: Path,
    artifact_root: Path,
    tool_name: str,
    arguments: dict[str, Any],
) -> FileChangePreview:
    workspace = workspace_root.expanduser().resolve()
    artifact_root = artifact_root.expanduser().resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    target = _resolve_workspace_path(workspace, str(arguments.get("path") or ""))
    if target.exists() and target.is_dir():
        raise IsADirectoryError(str(target))
    if tool_name == "write_file":
        after_text = _require_string(arguments, "content")
    elif tool_name == "edit_file":
        after_text = _edited_content(target, arguments)
    else:
        raise ValueError(f"unsupported file side-effect tool: {tool_name}")

    before_exists = target.exists()
    before_bytes = target.read_bytes() if before_exists else b""
    after_bytes = after_text.encode("utf-8")
    preview_id = f"preview_{uuid4().hex}"
    preview_dir = artifact_root / preview_id
    preview_dir.mkdir(parents=True, exist_ok=False)

    snapshot_path = preview_dir / "before.bin" if before_exists else None
    if snapshot_path is not None:
        snapshot_path.write_bytes(before_bytes)
        os.chmod(snapshot_path, 0o600)
    after_path = preview_dir / "after.bin"
    after_path.write_bytes(after_bytes)
    os.chmod(after_path, 0o600)

    display_path = str(target.relative_to(workspace))
    before_text = before_bytes.decode("utf-8", errors="replace")
    diff_text, diff_truncated = _diff_text(before_text, after_text, display_path)
    diff_path = preview_dir / "change.diff"
    diff_path.write_text(diff_text, encoding="utf-8")
    os.chmod(diff_path, 0o600)

    return FileChangePreview(
        preview_id=preview_id,
        tool_name=tool_name,
        target_path=target,
        display_path=display_path,
        before_exists=before_exists,
        before_hash=_sha256(before_bytes),
        after_hash=_sha256(after_bytes),
        snapshot_path=snapshot_path,
        after_path=after_path,
        diff_path=diff_path,
        diff_text=diff_text,
        diff_truncated=diff_truncated,
    )


def apply_file_change(preview: FileChangePreview) -> FileApplyResult:
    current_exists = preview.target_path.exists()
    current = preview.target_path.read_bytes() if current_exists else b""
    if current_exists != preview.before_exists or _sha256(current) != preview.before_hash:
        return FileApplyResult(
            ok=False,
            reason="snapshot_conflict",
            target_path=preview.target_path,
        )
    preview.target_path.parent.mkdir(parents=True, exist_ok=True)
    after = preview.after_path.read_bytes()
    preview.target_path.write_bytes(after)
    return FileApplyResult(
        ok=True,
        reason="file_change_applied",
        target_path=preview.target_path,
        after_hash=_sha256(after),
    )


def rollback_file_change(preview: FileChangePreview) -> FileRollbackResult:
    if preview.snapshot_path is None:
        if preview.target_path.exists():
            preview.target_path.unlink()
        return FileRollbackResult(
            ok=True,
            reason="created_file_removed",
            target_path=preview.target_path,
        )
    before = preview.snapshot_path.read_bytes()
    preview.target_path.parent.mkdir(parents=True, exist_ok=True)
    preview.target_path.write_bytes(before)
    return FileRollbackResult(
        ok=True,
        reason="snapshot_restored",
        target_path=preview.target_path,
        restored_hash=_sha256(before),
    )


def _resolve_workspace_path(workspace: Path, path: str) -> Path:
    if not path.strip():
        raise ValueError("path is required")
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    target = candidate.resolve()
    if target != workspace and workspace not in target.parents:
        raise ValueError("file path outside workspace")
    return target


def _require_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} is required")
    return value


def _edited_content(target: Path, arguments: dict[str, Any]) -> str:
    if not target.exists():
        raise FileNotFoundError(str(target))
    raw_content = target.read_bytes().decode("utf-8")
    content, has_bom = _strip_utf8_bom(raw_content)
    old_text = _require_string(arguments, "old_text")
    new_text = _require_string(arguments, "new_text")
    matched_old_text = old_text
    replacement_text = new_text

    if matched_old_text not in content and _supports_crlf_compat(content):
        compat_old_text = old_text.replace("\n", "\r\n")
        if compat_old_text in content:
            matched_old_text = compat_old_text
            replacement_text = new_text.replace("\n", "\r\n")

    if matched_old_text not in content:
        raise ValueError("old_text not found")

    replace_all = bool(arguments.get("replace_all", False))
    count = content.count(matched_old_text)
    if count > 1 and not replace_all:
        raise ValueError("old_text appears multiple times")
    new_content = (
        content.replace(matched_old_text, replacement_text)
        if replace_all
        else content.replace(matched_old_text, replacement_text, 1)
    )
    return _restore_utf8_bom(new_content, has_bom)


def _diff_text(before_text: str, after_text: str, display_path: str) -> tuple[str, bool]:
    lines = list(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=f"{display_path} (before)",
            tofile=f"{display_path} (after)",
            lineterm="",
        )
    )
    text = "\n".join(lines)
    if not text:
        text = f"No textual diff for {display_path}"
    if len(text) <= _MAX_DIFF_CHARS:
        return text, False
    return text[:_MAX_DIFF_CHARS] + "\n...[diff truncated]", True


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strip_utf8_bom(value: str) -> tuple[str, bool]:
    if value.startswith("\ufeff"):
        return value[1:], True
    return value, False


def _restore_utf8_bom(value: str, had_bom: bool) -> str:
    return f"\ufeff{value}" if had_bom else value


def _supports_crlf_compat(value: str) -> bool:
    return "\r\n" in value
