from __future__ import annotations

import asyncio
import json

import pytest

from infra.channels.ipc_protocol import (
    IPC_FRAME_MAGIC,
    IPC_FRAME_LIMIT_BYTES,
    ProtocolError,
    build_cli_outbound_payload,
    build_hello_payload,
    build_tool_summary,
    chat_id_from_hello,
    encode_frame,
    project_cli_metadata,
    read_frame,
)


class _Reader:
    def __init__(self, payload: bytes) -> None:
        self._payload = bytearray(payload)

    async def readexactly(self, n: int) -> bytes:
        if len(self._payload) < n:
            raise asyncio.IncompleteReadError(bytes(self._payload), n)
        out = bytes(self._payload[:n])
        del self._payload[:n]
        return out


@pytest.mark.asyncio
async def test_encode_read_frame_roundtrip() -> None:
    payload = {"type": "user", "request_id": "req-v2", "content": "你好"}
    frame = encode_frame(payload)
    assert frame.startswith(IPC_FRAME_MAGIC)
    decoded = await read_frame(_Reader(frame))  # type: ignore[arg-type]
    assert decoded == payload


@pytest.mark.asyncio
async def test_read_frame_rejects_oversized_payload() -> None:
    too_large_len = IPC_FRAME_MAGIC + (IPC_FRAME_LIMIT_BYTES + 1).to_bytes(4, "big")
    with pytest.raises(ProtocolError, match="frame too large"):
        await read_frame(_Reader(too_large_len), limit=IPC_FRAME_LIMIT_BYTES)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_read_frame_rejects_invalid_magic() -> None:
    bad = b"NOPE2" + (2).to_bytes(4, "big") + b"{}"
    with pytest.raises(ProtocolError, match="invalid frame magic"):
        await read_frame(_Reader(bad))  # type: ignore[arg-type]


def test_hello_payload_and_chat_id_are_stable_and_sanitized() -> None:
    hello = build_hello_payload("client/abc", "rag smoke")
    assert hello["type"] == "hello"
    assert hello["protocol"] == 2
    assert (
        chat_id_from_hello(hello["client_id"], hello["session_id"])
        == "cli-client-abc-rag-smoke"
    )


def _large_tool_chain() -> list[dict[str, object]]:
    return [
        {
            "text": "model text " + "x" * 1000,
            "calls": [
                {
                    "name": "read_file",
                    "arguments": {"path": "/tmp/a.py", "description": "read"},
                    "result": "R" * 50000,
                    "ok": True,
                },
                {
                    "name": "search_docs",
                    "arguments": {"query": "agent runtime"},
                    "result": {"hits": [{"chunk_id": "c1", "text": "T" * 5000}]},
                    "ok": True,
                },
            ],
        }
    ]


def test_build_tool_summary_drops_large_arguments_and_results() -> None:
    summary = build_tool_summary(_large_tool_chain())
    assert summary["count"] == 2
    assert summary["names"] == ["read_file", "search_docs"]
    assert summary["calls"][0] == {"name": "read_file", "ok": True}
    assert "result" not in json.dumps(summary, ensure_ascii=False)
    assert "arguments" not in json.dumps(summary, ensure_ascii=False)


def test_project_cli_metadata_replaces_tool_chain_with_tool_summary() -> None:
    projected = project_cli_metadata(
        {
            "tools_used": ["read_file", "search_docs"],
            "tool_chain": _large_tool_chain(),
            "reasoning_content": "hidden",
            "small": "kept",
        }
    )
    assert "tool_chain" not in projected
    assert "reasoning_content" not in projected
    assert projected["tool_summary"]["count"] == 2
    assert projected["small"] == "kept"


def test_build_cli_outbound_payload_is_bounded_after_projection() -> None:
    payload = build_cli_outbound_payload(
        "answer", {"tool_chain": _large_tool_chain() * 20}
    )
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert payload["type"] == "assistant"
    assert payload["content"] == "answer"
    assert "tool_summary" in payload["metadata"]
    assert "tool_chain" not in payload["metadata"]
    assert len(encoded) < 64 * 1024
