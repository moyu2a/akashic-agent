from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.policies.tool_approval import canonical_args_hash

MANAGED_FILE_SIDE_EFFECT_TOOLS = frozenset({"write_file", "edit_file"})


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
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def root_for_workspace(workspace: str | Path) -> Path:
        return Path(workspace).expanduser().resolve() / "tool_side_effects" / "payloads"

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
        if tool_name not in MANAGED_FILE_SIDE_EFFECT_TOOLS:
            raise ValueError(f"unsupported managed side-effect tool: {tool_name}")
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
        payload_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        os.chmod(payload_path, 0o600)
        return record

    def get_payload(self, approval_request_id: str) -> SideEffectPayload | None:
        path = self._payload_path(approval_request_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
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
        if tool_name not in MANAGED_FILE_SIDE_EFFECT_TOOLS:
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
        if not path.exists():
            return False
        path.unlink()
        return True

    def _payload_path(self, approval_request_id: str) -> Path:
        clean = "".join(
            ch for ch in approval_request_id if ch.isalnum() or ch in {"_", "-"}
        )
        if not clean:
            raise ValueError("approval_request_id is required")
        return self.root / f"{clean}.json"
