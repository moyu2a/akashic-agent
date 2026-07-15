"""
IPC server channel.

Uses a Unix domain socket on POSIX systems and loopback TCP on Windows so the
local CLI can talk to the running agent process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.config import _normalize_cli_socket_endpoint
from bus.events import InboundMessage, OutboundMessage
from bus.queue import MessageBus
from infra.channels.ipc_protocol import (
    IPC_FRAME_MAGIC,
    ProtocolError,
    build_cli_outbound_payload,
    chat_id_from_hello,
    encode_frame,
    encode_legacy_line,
    read_frame,
    read_frame_after_magic,
)

if TYPE_CHECKING:
    from proactive_v2.loop import ProactiveLoop

logger = logging.getLogger(__name__)

CHANNEL = "cli"
_REQUEST_ID_RE = re.compile(r"[0-9a-fA-F]{32}")


@dataclass(slots=True)
class _ClientState:
    writer: asyncio.StreamWriter
    protocol: int


def _parse_tcp_endpoint(endpoint: str) -> tuple[str, int] | None:
    if endpoint.count(":") != 1:
        return None
    host, port = endpoint.rsplit(":", 1)
    if not host:
        return None
    try:
        return host, int(port)
    except ValueError:
        return None


def _normalize_endpoint(endpoint: str) -> str:
    return _normalize_cli_socket_endpoint(endpoint)


class IPCServerChannel:
    def __init__(
        self,
        bus: MessageBus,
        socket_path: str,
        proactive_loop: "ProactiveLoop | None" = None,
    ) -> None:
        self._bus = bus
        self._socket_path = _normalize_endpoint(socket_path)
        self._proactive_loop = proactive_loop
        self._writers: dict[str, _ClientState] = {}
        self._server: asyncio.AbstractServer | None = None
        bus.subscribe_outbound(CHANNEL, self._on_response)

    async def start(self) -> None:
        tcp_endpoint = _parse_tcp_endpoint(self._socket_path)
        if tcp_endpoint is not None:
            host, port = tcp_endpoint
            self._server = await asyncio.start_server(
                self._handle_connection,
                host=host,
                port=port,
            )
            logger.info("IPC server listening on tcp://%s:%s", host, port)
            return

        if not hasattr(asyncio, "start_unix_server"):
            raise RuntimeError("Unix sockets are unavailable on this platform; use a host:port endpoint instead.")
        Path(self._socket_path).unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            path=self._socket_path,
        )
        os.chmod(self._socket_path, 0o600)
        logger.info("IPC server listening on %s", self._socket_path)

    async def stop(self) -> None:
        if not self._server:
            return
        self._server.close()
        await self._server.wait_closed()
        if _parse_tcp_endpoint(self._socket_path) is None:
            Path(self._socket_path).unlink(missing_ok=True)

    def set_proactive_loop(self, proactive_loop: "ProactiveLoop") -> None:
        self._proactive_loop = proactive_loop
        logger.info("[cli] ProactiveLoop attached")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername") or "local"
        chat_id = f"cli-{id(writer)}"
        protocol = 1
        registered = False
        try:
            try:
                first_payload, protocol = await self._read_first_payload(reader)
            except asyncio.IncompleteReadError:
                return
            except (ProtocolError, json.JSONDecodeError) as exc:
                logger.warning("[cli] protocol error from peer=%s: %s", peer, exc)
                return

            if first_payload and first_payload.get("type") == "hello" and protocol == 2:
                chat_id = chat_id_from_hello(
                    first_payload.get("client_id"),
                    first_payload.get("session_id"),
                )
                logger.info("[cli] v2 hello session=%s peer=%s", chat_id, peer)
                first_payload = None

            self._writers[chat_id] = _ClientState(writer=writer, protocol=protocol)
            registered = True
            logger.info(
                "[cli] client connected session=%s peer=%s protocol=v%s",
                chat_id,
                peer,
                protocol,
            )

            pending = first_payload
            while True:
                data = pending
                pending = None
                if data is None:
                    try:
                        data = await self._read_next_payload(reader, protocol)
                    except asyncio.IncompleteReadError:
                        break
                    except (ProtocolError, json.JSONDecodeError) as exc:
                        logger.warning("[cli] protocol error session=%s: %s", chat_id, exc)
                        break
                if not data:
                    break
                await self._handle_payload(data, chat_id, writer, protocol=protocol)
        finally:
            if registered:
                self._writers.pop(chat_id, None)
            writer.close()
            await writer.wait_closed()
            logger.info("[cli] client disconnected session=%s", chat_id)

    async def _read_first_payload(
        self,
        reader: asyncio.StreamReader,
    ) -> tuple[dict[str, Any] | None, int]:
        prefix = await reader.readexactly(len(IPC_FRAME_MAGIC))
        if prefix == IPC_FRAME_MAGIC:
            return await read_frame_after_magic(reader), 2
        if not prefix.startswith(b"{"):
            raise ProtocolError("unknown IPC protocol prefix")
        line = prefix + await reader.readline()
        return self._decode_legacy_line(line), 1

    async def _read_next_payload(
        self,
        reader: asyncio.StreamReader,
        protocol: int,
    ) -> dict[str, Any] | None:
        if protocol == 2:
            return await read_frame(reader)
        line = await reader.readline()
        if not line:
            return None
        return self._decode_legacy_line(line)

    @staticmethod
    def _decode_legacy_line(line: bytes) -> dict[str, Any] | None:
        if not line:
            return None
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("[cli] received non-JSON payload")
            return {}
        return data if isinstance(data, dict) else {}

    async def _handle_payload(
        self,
        data: dict[str, Any],
        chat_id: str,
        writer: asyncio.StreamWriter,
        *,
        protocol: int,
    ) -> None:
        if data.get("type") == "command":
            await self._handle_command(data, chat_id, writer, protocol=protocol)
            return
        content = str(data.get("content", "")).strip()
        if not content:
            return
        raw_request_id = data.get("request_id")
        request_id = (
            raw_request_id.lower()
            if isinstance(raw_request_id, str)
            and _REQUEST_ID_RE.fullmatch(raw_request_id)
            else ""
        )
        metadata = {"_transport_request_id": request_id} if request_id else {}
        preview = content[:60] + "..." if len(content) > 60 else content
        logger.info("[cli] received session=%s content=%r", chat_id, preview)
        await self._bus.publish_inbound(
            InboundMessage(
                channel=CHANNEL,
                sender="cli-user",
                chat_id=chat_id,
                content=content,
                metadata=metadata,
            )
        )

    async def _handle_command(
        self,
        data: dict[str, Any],
        chat_id: str,
        writer: asyncio.StreamWriter,
        *,
        protocol: int,
    ) -> None:
        cmd = data.get("command", "")
        logger.info("[cli] received command cmd=%r session=%s", cmd, chat_id)
        await self._write_command_result(
            writer,
            ok=False,
            message=f"unknown command: {cmd!r}",
            protocol=protocol,
        )

    @staticmethod
    async def _write_command_result(
        writer: asyncio.StreamWriter,
        *,
        ok: bool,
        message: str,
        protocol: int,
    ) -> None:
        payload = {"type": "command_result", "ok": ok, "message": message}
        writer.write(encode_frame(payload) if protocol == 2 else encode_legacy_line(payload))
        await writer.drain()

    async def _on_response(self, msg: OutboundMessage) -> None:
        state = self._writers.get(msg.chat_id)
        if state is None:
            return
        writer = state.writer
        if writer.is_closing():
            return
        payload = build_cli_outbound_payload(msg.content, msg.metadata or {})
        data = encode_frame(payload) if state.protocol == 2 else encode_legacy_line(payload)
        writer.write(data)
        await writer.drain()
