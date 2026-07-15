from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

IPC_PROTOCOL_VERSION = 2
IPC_FRAME_MAGIC = b"AKIP2"
IPC_FRAME_LIMIT_BYTES = 1024 * 1024
CLI_CONTENT_LIMIT_BYTES = 128 * 1024
CLI_METADATA_LIMIT_BYTES = 16 * 1024
IPC_REQUEST_ID_LIMIT = 128
_FRAME_SIZE_BYTES = 4
_SESSION_PART_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class ProtocolError(ValueError):
    pass


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def encode_frame(payload: Mapping[str, Any]) -> bytes:
    body = _json_bytes(payload)
    if len(body) > IPC_FRAME_LIMIT_BYTES:
        raise ProtocolError(f"frame too large: {len(body)} > {IPC_FRAME_LIMIT_BYTES}")
    return IPC_FRAME_MAGIC + len(body).to_bytes(_FRAME_SIZE_BYTES, "big") + body


async def read_frame(
    reader: asyncio.StreamReader,
    *,
    limit: int = IPC_FRAME_LIMIT_BYTES,
) -> dict[str, Any]:
    magic = await reader.readexactly(len(IPC_FRAME_MAGIC))
    if magic != IPC_FRAME_MAGIC:
        raise ProtocolError("invalid frame magic")
    return await read_frame_after_magic(reader, limit=limit)


async def read_frame_after_magic(
    reader: asyncio.StreamReader,
    *,
    limit: int = IPC_FRAME_LIMIT_BYTES,
) -> dict[str, Any]:
    header = await reader.readexactly(_FRAME_SIZE_BYTES)
    size = int.from_bytes(header, "big")
    if size <= 0:
        raise ProtocolError(f"invalid frame size: {size}")
    if size > limit:
        raise ProtocolError(f"frame too large: {size} > {limit}")
    body = await reader.readexactly(size)
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ProtocolError("frame payload must be a JSON object")
    return data


def encode_legacy_line(payload: Mapping[str, Any]) -> bytes:
    return _json_bytes(payload) + b"\n"


def sanitize_session_part(value: object, *, default: str) -> str:
    raw = str(value or "").strip()
    cleaned = _SESSION_PART_RE.sub("-", raw).strip("-._")
    return cleaned[:64] or default


def chat_id_from_hello(client_id: object, session_id: object) -> str:
    client = sanitize_session_part(client_id, default="anonymous")
    session = sanitize_session_part(session_id, default="default")
    return f"cli-{client}-{session}"


def build_hello_payload(client_id: str, session_id: str) -> dict[str, Any]:
    return {
        "type": "hello",
        "protocol": IPC_PROTOCOL_VERSION,
        "client_id": client_id,
        "session_id": session_id,
    }


def default_cli_client_id_path() -> Path:
    return Path(
        os.getenv("AKASHIC_CLI_CLIENT_ID_PATH", "~/.akashic/cli_client_id")
    ).expanduser()


def load_or_create_cli_client_id(path: Path | None = None) -> str:
    target = path or default_cli_client_id_path()
    try:
        existing = target.read_text(encoding="utf-8").strip()
        if existing:
            return sanitize_session_part(existing, default="anonymous")
    except FileNotFoundError:
        pass
    client_id = uuid.uuid4().hex
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(client_id + "\n", encoding="utf-8")
    return client_id


def _encoded_len(value: Mapping[str, Any]) -> int:
    return len(_json_bytes(value))


def _truncate_text(value: object, *, limit: int) -> str:
    text = str(value or "")
    if len(text.encode("utf-8")) <= limit:
        return text
    suffix = "\n\n[truncated for CLI transport]"
    raw = text.encode("utf-8")[: max(0, limit - len(suffix.encode("utf-8")))]
    return raw.decode("utf-8", errors="ignore") + suffix


def build_tool_summary(tool_chain: object) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    names: list[str] = []
    if isinstance(tool_chain, list):
        for group in tool_chain:
            if not isinstance(group, dict):
                continue
            raw_calls = group.get("calls")
            if not isinstance(raw_calls, list):
                continue
            for call in raw_calls:
                if not isinstance(call, dict):
                    continue
                name = str(call.get("name") or "unknown")
                names.append(name)
                item: dict[str, Any] = {"name": name}
                if "ok" in call:
                    item["ok"] = bool(call.get("ok"))
                status = call.get("status")
                if status is not None:
                    item["status"] = str(status)[:32]
                error = call.get("error")
                if error:
                    item["error"] = _truncate_text(error, limit=160)
                calls.append(item)
    return {
        "count": len(calls),
        "names": names[:40],
        "calls": calls[:40],
        "truncated": len(calls) > 40,
    }


def project_cli_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    projected: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in {"tool_chain", "reasoning_content"}:
            continue
        if isinstance(value, str | int | float | bool) or value is None:
            projected[key] = value
        elif key == "tools_used" and isinstance(value, list):
            projected[key] = [str(item) for item in value[:40]]
    tool_chain = metadata.get("tool_chain")
    if tool_chain:
        projected["tool_summary"] = build_tool_summary(tool_chain)
    if _encoded_len(projected) > CLI_METADATA_LIMIT_BYTES:
        slim: dict[str, Any] = {}
        if "tools_used" in projected:
            slim["tools_used"] = projected["tools_used"]
        if "tool_summary" in projected:
            slim["tool_summary"] = projected["tool_summary"]
        slim["transport_warning"] = "metadata trimmed for CLI transport"
        projected = slim
    return projected


def build_cli_outbound_payload(
    content: str,
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "assistant",
        "content": _truncate_text(content, limit=CLI_CONTENT_LIMIT_BYTES),
        "metadata": project_cli_metadata(metadata),
    }
    if _encoded_len(payload) > IPC_FRAME_LIMIT_BYTES:
        payload["metadata"] = {"transport_warning": "metadata dropped for CLI transport"}
    if _encoded_len(payload) > IPC_FRAME_LIMIT_BYTES:
        payload["content"] = _truncate_text(payload["content"], limit=64 * 1024)
    return payload
