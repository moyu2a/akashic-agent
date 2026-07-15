"""
Basic CLI client for the local agent.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

from agent.config import DEFAULT_SOCKET, _normalize_cli_socket_endpoint
from infra.channels.ipc_protocol import (
    build_hello_payload,
    encode_frame,
    load_or_create_cli_client_id,
    read_frame,
)

_EXIT_CMDS = {"exit", "quit", "q"}


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


class CLIClient:
    def __init__(self, socket_path: str = DEFAULT_SOCKET) -> None:
        self._socket_path = _normalize_endpoint(socket_path)

    async def run(self) -> None:
        try:
            tcp_endpoint = _parse_tcp_endpoint(self._socket_path)
            if tcp_endpoint is not None:
                reader, writer = await asyncio.open_connection(*tcp_endpoint)
            else:
                if not hasattr(asyncio, "open_unix_connection"):
                    raise OSError("Unix sockets are unavailable on this platform.")
                reader, writer = await asyncio.open_unix_connection(self._socket_path)
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            print(
                f"无法连接到 agent（{self._socket_path}），请先启动主进程：python main.py"
            )
            return

        _print_banner()
        client_id = load_or_create_cli_client_id()
        session_id = os.getenv("AKASHIC_CLI_SESSION", "default")
        writer.write(encode_frame(build_hello_payload(client_id, session_id)))
        await writer.drain()
        receive_task = asyncio.create_task(self._receive(reader))

        try:
            while True:
                text = await _read_line()
                stripped = text.strip()
                if stripped.lower() in _EXIT_CMDS:
                    break
                if not stripped:
                    continue
                writer.write(
                    encode_frame(
                        {
                            "type": "user",
                            "request_id": uuid.uuid4().hex,
                            "content": stripped,
                        }
                    )
                )
                await writer.drain()
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            receive_task.cancel()
            writer.close()
            await writer.wait_closed()
            print("\n再见")

    @staticmethod
    async def _receive(reader: asyncio.StreamReader) -> None:
        while True:
            try:
                data = await read_frame(reader)
            except asyncio.IncompleteReadError:
                print("\n连接已断开")
                break
            print(f"\n{data.get('content', '')}\n> ", end="", flush=True)


def _print_banner() -> None:
    print("akashic Agent CLI  |  输入 exit 退出\n")


async def _read_line() -> str:
    loop = asyncio.get_event_loop()
    sys.stdout.write("> ")
    sys.stdout.flush()
    return await loop.run_in_executor(None, sys.stdin.readline)
