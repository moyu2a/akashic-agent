from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent.policies.tool_approval import canonical_args_hash

MANAGED_FILE_SIDE_EFFECT_TOOLS = frozenset({"write_file", "edit_file"})
MANAGED_SHELL_SIDE_EFFECT_TOOLS = frozenset({"shell"})
MANAGED_SIDE_EFFECT_TOOLS = (
    MANAGED_FILE_SIDE_EFFECT_TOOLS | MANAGED_SHELL_SIDE_EFFECT_TOOLS
)


@dataclass(frozen=True)
class SideEffectPayloadRecord:
    approval_request_id: str
    request_id: str
    session_key: str
    tool_name: str
    approval_scope: str
    args_hash: str
    payload_path: Path
    created_at: str
    expires_at: str


@dataclass(frozen=True)
class SideEffectPayload:
    record: SideEffectPayloadRecord
    arguments: dict[str, Any]


class SideEffectPayloadVault:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().absolute()
        self._ensure_private_dir(self.root)
        if self.root.resolve(strict=True) != self.root:
            raise ValueError("side-effect payload vault root contains symlink")

    @staticmethod
    def root_for_workspace(workspace: str | Path) -> Path:
        resolved_workspace = Path(workspace).expanduser().resolve(strict=True)
        current = resolved_workspace
        for name in ("tool_side_effects", "payloads"):
            current = current / name
            try:
                current_stat = current.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(current_stat.st_mode):
                raise ValueError("side-effect payload vault root contains symlink")
            if not stat.S_ISDIR(current_stat.st_mode):
                raise ValueError(
                    "side-effect payload vault root contains non-directory"
                )
        return resolved_workspace / "tool_side_effects" / "payloads"

    def put_payload(
        self,
        *,
        approval_request_id: str,
        request_id: str,
        session_key: str,
        tool_name: str,
        approval_scope: str,
        args_hash: str,
        arguments: dict[str, Any],
        created_at: datetime,
        expires_at: str,
    ) -> SideEffectPayloadRecord:
        if tool_name not in MANAGED_SIDE_EFFECT_TOOLS:
            raise ValueError(f"unsupported managed side-effect tool: {tool_name}")
        return self._put_payload(
            approval_request_id=approval_request_id,
            request_id=request_id,
            session_key=session_key,
            tool_name=tool_name,
            approval_scope=approval_scope,
            args_hash=args_hash,
            arguments=arguments,
            created_at=created_at,
            expires_at=expires_at,
        )

    def put_deferred_tool_payload(
        self,
        *,
        approval_request_id: str,
        request_id: str,
        session_key: str,
        tool_name: str,
        approval_scope: str,
        args_hash: str,
        arguments: dict[str, Any],
        created_at: datetime,
        expires_at: str,
    ) -> SideEffectPayloadRecord:
        if tool_name in MANAGED_SIDE_EFFECT_TOOLS:
            return self.put_payload(
                approval_request_id=approval_request_id,
                request_id=request_id,
                session_key=session_key,
                tool_name=tool_name,
                approval_scope=approval_scope,
                args_hash=args_hash,
                arguments=arguments,
                created_at=created_at,
                expires_at=expires_at,
            )
        return self._put_payload(
            approval_request_id=approval_request_id,
            request_id=request_id,
            session_key=session_key,
            tool_name=tool_name,
            approval_scope=approval_scope,
            args_hash=args_hash,
            arguments=arguments,
            created_at=created_at,
            expires_at=expires_at,
        )

    def _put_payload(
        self,
        *,
        approval_request_id: str,
        request_id: str,
        session_key: str,
        tool_name: str,
        approval_scope: str,
        args_hash: str,
        arguments: dict[str, Any],
        created_at: datetime,
        expires_at: str,
    ) -> SideEffectPayloadRecord:
        if canonical_args_hash(arguments) != args_hash:
            raise ValueError("side-effect payload args hash mismatch")
        payload_path = self._payload_path(approval_request_id)
        record = SideEffectPayloadRecord(
            approval_request_id=approval_request_id,
            request_id=request_id,
            session_key=session_key,
            tool_name=tool_name,
            approval_scope=approval_scope or "tool_call",
            args_hash=args_hash,
            payload_path=payload_path,
            created_at=created_at.isoformat(),
            expires_at=expires_at,
        )
        raw = {
            "approval_request_id": record.approval_request_id,
            "request_id": record.request_id,
            "session_key": record.session_key,
            "tool_name": record.tool_name,
            "approval_scope": record.approval_scope,
            "args_hash": record.args_hash,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
            "arguments": dict(arguments),
        }
        encoded = json.dumps(raw, ensure_ascii=False).encode("utf-8")
        self._atomic_write(payload_path, encoded)
        return record

    def get_payload(self, approval_request_id: str) -> SideEffectPayload | None:
        return self._get_payload(approval_request_id, managed_only=True)

    def get_deferred_tool_payload(
        self, approval_request_id: str
    ) -> SideEffectPayload | None:
        return self._get_payload(approval_request_id, managed_only=False)

    def _get_payload(
        self, approval_request_id: str, *, managed_only: bool
    ) -> SideEffectPayload | None:
        path = self._payload_path(approval_request_id)
        try:
            raw = json.loads(self._read_private_file(path).decode("utf-8"))
        except OSError, ValueError:
            return None
        if not isinstance(raw, dict):
            return None
        arguments = raw.get("arguments")
        if not isinstance(arguments, dict):
            return None
        args_hash = str(raw.get("args_hash") or "")
        if canonical_args_hash(arguments) != args_hash:
            return None
        tool_name = str(raw.get("tool_name") or "")
        if managed_only and tool_name not in MANAGED_SIDE_EFFECT_TOOLS:
            return None
        record = SideEffectPayloadRecord(
            approval_request_id=str(raw.get("approval_request_id") or ""),
            request_id=str(raw.get("request_id") or ""),
            session_key=str(raw.get("session_key") or ""),
            tool_name=tool_name,
            approval_scope=str(raw.get("approval_scope") or "tool_call"),
            args_hash=args_hash,
            payload_path=path,
            created_at=str(raw.get("created_at") or ""),
            expires_at=str(raw.get("expires_at") or ""),
        )
        if record.approval_request_id != approval_request_id:
            return None
        return SideEffectPayload(record=record, arguments=dict(arguments))

    def delete_payload(self, approval_request_id: str) -> bool:
        path = self._payload_path(approval_request_id)
        try:
            root_fd = self._open_root()
        except OSError:
            return False
        try:
            os.unlink(path.name, dir_fd=root_fd)
            return True
        except FileNotFoundError:
            return False
        finally:
            os.close(root_fd)

    def _payload_path(self, approval_request_id: str) -> Path:
        clean = "".join(
            ch for ch in approval_request_id if ch.isalnum() or ch in {"_", "-"}
        )
        if not clean:
            raise ValueError("approval_request_id is required")
        return self.root / f"{clean}.json"

    @staticmethod
    def _ensure_private_dir(path: Path) -> None:
        missing: list[Path] = []
        cursor = path
        while True:
            try:
                cursor_stat = cursor.lstat()
            except FileNotFoundError:
                missing.append(cursor)
                parent = cursor.parent
                if parent == cursor:
                    raise ValueError("side-effect payload vault root is invalid")
                cursor = parent
                continue
            if stat.S_ISLNK(cursor_stat.st_mode):
                raise ValueError("side-effect payload vault root contains symlink")
            if not stat.S_ISDIR(cursor_stat.st_mode):
                raise ValueError(
                    "side-effect payload vault root contains non-directory"
                )
            break
        for directory in reversed(missing):
            os.mkdir(directory, 0o700)
            directory_stat = directory.lstat()
            if stat.S_ISLNK(directory_stat.st_mode) or not stat.S_ISDIR(
                directory_stat.st_mode
            ):
                raise ValueError("side-effect payload vault root contains symlink")
        os.chmod(path, 0o700)

    def _atomic_write(self, payload_path: Path, content: bytes) -> None:
        root_fd = self._open_root()
        temp_name = f".{payload_path.name}.{uuid4().hex}.tmp"
        file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            file_flags |= os.O_NOFOLLOW
        temp_created = False
        try:
            fd = os.open(temp_name, file_flags, 0o600, dir_fd=root_fd)
            temp_created = True
            try:
                file_stat = os.fstat(fd)
                if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
                    raise OSError("payload must be a singly-linked regular file")
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb", closefd=False) as file:
                    file.write(content)
                    file.flush()
                    os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(
                temp_name,
                payload_path.name,
                src_dir_fd=root_fd,
                dst_dir_fd=root_fd,
            )
            temp_created = False
            final_fd = os.open(
                payload_path.name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=root_fd,
            )
            try:
                final_stat = os.fstat(final_fd)
                if not stat.S_ISREG(final_stat.st_mode) or final_stat.st_nlink != 1:
                    raise OSError("published payload must be a regular file")
                if stat.S_IMODE(final_stat.st_mode) != 0o600:
                    raise OSError("published payload mode is not private")
            finally:
                os.close(final_fd)
        finally:
            if temp_created:
                try:
                    os.unlink(temp_name, dir_fd=root_fd)
                except OSError:
                    pass
            os.close(root_fd)

    def _read_private_file(self, path: Path) -> bytes:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        root_fd = self._open_root()
        try:
            fd = os.open(path.name, flags, dir_fd=root_fd)
            try:
                file_stat = os.fstat(fd)
                if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
                    raise OSError("payload is not a singly-linked regular file")
                with os.fdopen(fd, "rb", closefd=False) as file:
                    return file.read()
            finally:
                os.close(fd)
        finally:
            os.close(root_fd)

    def _open_root(self) -> int:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        root_fd = os.open(self.root, flags)
        root_stat = os.fstat(root_fd)
        if not stat.S_ISDIR(root_stat.st_mode):
            os.close(root_fd)
            raise OSError("side-effect payload vault root is not a directory")
        return root_fd
