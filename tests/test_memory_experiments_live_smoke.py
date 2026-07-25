from __future__ import annotations

import asyncio
import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from infra.channels.ipc_protocol import (
    build_hello_payload,
    encode_frame,
    read_frame,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY_CONFIG = (
    PROJECT_ROOT / "plugins" / "default_memory" / "config.local.toml"
)
CONFIG_LOCK = Path("/tmp/akashic-memory-experiments-config.lock")

pytestmark = pytest.mark.skipif(
    os.environ.get("AKASHIC_RUN_LIVE_SMOKE") != "1",
    reason="opt-in live smoke; set AKASHIC_RUN_LIVE_SMOKE=1 to enable",
)


class _FakeOpenAI:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.chat_count = 0
        self.base_url = ""
        self._server: asyncio.AbstractServer | None = None
        self._handlers: set[asyncio.Task[Any]] = set()

    async def __aenter__(self) -> "_FakeOpenAI":
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        assert self._server.sockets
        host, port = self._server.sockets[0].getsockname()[:2]
        self.base_url = f"http://{host}:{port}/v1"
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()
        if self._handlers:
            await asyncio.gather(*self._handlers, return_exceptions=True)
        await asyncio.sleep(0)

    async def _handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._handlers.add(task)
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            header_text = headers.decode("utf-8", "ignore")
            first = header_text.splitlines()[0] if header_text else ""
            parts = first.split(" ")
            path = parts[1] if len(parts) >= 2 else "/"
            content_length = _parse_content_length(header_text)
            body = await reader.readexactly(content_length) if content_length else b""
            payload = json.loads(body.decode("utf-8") or "{}") if body else {}
            self.requests.append({"path": path, "payload": payload})
            if path.endswith("/embeddings"):
                response = self._embedding_response(payload)
            elif path.endswith("/chat/completions"):
                response = self._chat_response(payload)
            else:
                response = {"ok": True, "path": path}
            raw = json.dumps(response, ensure_ascii=False).encode("utf-8")
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(raw)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + raw
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            if task is not None:
                self._handlers.discard(task)

    def _embedding_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("input") or [""]
        if isinstance(inputs, str):
            inputs = [inputs]
        return {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "index": idx,
                    "embedding": [0.01] * 1024,
                }
                for idx, _ in enumerate(inputs)
            ],
            "model": payload.get("model") or "fake-embedding",
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        }

    def _chat_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.chat_count += 1
        messages = payload.get("messages") or []
        has_tool_result = any(
            isinstance(message, dict)
            and (
                message.get("role") in {"tool", "function"}
                or bool(message.get("tool_call_id"))
            )
            for message in messages
        )
        latest_user_text = ""
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                latest_user_text = str(message.get("content") or "")
                break
        tool_names = {
            str(tool.get("function", {}).get("name") or "")
            for tool in payload.get("tools", [])
            if isinstance(tool, dict)
        }
        should_memorize = (
            "记住" in latest_user_text or "memorize" in latest_user_text.lower()
        ) and "memorize" in tool_names and not has_tool_result
        if should_memorize:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_memorize_1",
                        "type": "function",
                        "function": {
                            "name": "memorize",
                            "arguments": json.dumps(
                                {
                                    "summary": "用户明确要求记住：喜欢中文回答",
                                    "memory_type": "preference",
                                },
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
            }
            finish_reason = "tool_calls"
        else:
            message = {
                "role": "assistant",
                "content": "已记录你的偏好。",
            }
            finish_reason = "stop"
        return {
            "id": f"chatcmpl-smoke-{self.chat_count}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model") or "fake-chat",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }


def _parse_content_length(header_text: str) -> int:
    for line in header_text.splitlines()[1:]:
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() == "content-length":
            return int(value.strip())
    return 0


@contextmanager
def _plugin_memory_experiment_config() -> Iterator[None]:
    CONFIG_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_LOCK.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        original = (
            DEFAULT_MEMORY_CONFIG.read_bytes()
            if DEFAULT_MEMORY_CONFIG.exists()
            else None
        )
        DEFAULT_MEMORY_CONFIG.write_text(
            textwrap.dedent(
                """
                [memory_experiments]
                enabled = true
                mode = "shadow"
                trace_enabled = true
                trace_path = "observe/memory_experiments.jsonl"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        try:
            yield
        finally:
            if original is None:
                DEFAULT_MEMORY_CONFIG.unlink(missing_ok=True)
            else:
                DEFAULT_MEMORY_CONFIG.write_bytes(original)
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _write_agent_config(
    *,
    path: Path,
    workspace: Path,
    socket_path: Path,
    fake_base_url: str,
) -> None:
    del workspace
    path.write_text(
        textwrap.dedent(
            f"""
            provider = "openai"
            model = "fake-chat"
            api_key = "test-key"
            base_url = "{fake_base_url}"

            [llm]
            provider = "openai"

            [llm.main]
            model = "fake-chat"
            api_key = "test-key"
            base_url = "{fake_base_url}"
            multimodal = false

            [llm.fast]
            model = "fake-chat"
            api_key = "test-key"
            base_url = "{fake_base_url}"

            [agent]
            system_prompt = "You are a local smoke-test assistant. Reply briefly in Chinese."
            max_tokens = 256
            max_iterations = 4
            dev_mode = false

            [agent.context]
            memory_window = 8

            [agent.tools]
            search_enabled = false
            spawn_enabled = false

            [agent.maintenance]
            memory_optimizer_enabled = false

            [agent.wiring]
            toolsets = ["meta_common"]

            [channels.cli]
            socket = "{socket_path}"

            [memory]
            enabled = true
            engine = ""

            [memory.embedding]
            model = "fake-embedding"
            api_key = "test-key"
            base_url = "{fake_base_url}"

            [doc_rag]
            enabled = false

            [proactive]
            enabled = false
            profile = "quiet"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


class _AgentProcess:
    def __init__(
        self,
        *,
        config_path: Path,
        workspace: Path,
        socket_path: Path,
        log_path: Path,
    ) -> None:
        self.config_path = config_path
        self.workspace = workspace
        self.socket_path = socket_path
        self.log_path = log_path
        self._log_file = None
        self._proc: subprocess.Popen[str] | None = None

    async def __aenter__(self) -> "_AgentProcess":
        self._log_file = self.log_path.open("w", encoding="utf-8")
        self._proc = subprocess.Popen(
            [
                sys.executable,
                "main.py",
                "--config",
                str(self.config_path),
                "--workspace",
                str(self.workspace),
            ],
            cwd=str(PROJECT_ROOT),
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        await self._wait_for_socket()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        if self._log_file is not None:
            self._log_file.close()

    async def _wait_for_socket(self) -> None:
        assert self._proc is not None
        started = time.monotonic()
        while time.monotonic() - started < 30:
            if self._proc.poll() is not None:
                raise RuntimeError(
                    "agent exited early:\n"
                    + self.log_path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )[-5000:]
                )
            if self.socket_path.exists():
                return
            await asyncio.sleep(0.1)
        raise TimeoutError(
            "agent socket did not appear:\n"
            + self.log_path.read_text(encoding="utf-8", errors="ignore")[-5000:]
        )


async def _send_cli_message(
    *,
    socket_path: Path,
    client_id: str,
    session_id: str,
    text: str,
) -> dict[str, Any]:
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    writer.write(encode_frame(build_hello_payload(client_id, session_id)))
    await writer.drain()
    writer.write(
        encode_frame(
            {
                "type": "user",
                "request_id": "d" * 32,
                "content": text,
            }
        )
    )
    await writer.drain()
    response = await asyncio.wait_for(read_frame(reader), timeout=30)
    writer.close()
    await writer.wait_closed()
    return response


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def _wait_for_jsonl_trace(
    path: Path,
    *,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            rows = _read_jsonl(path)
            if rows:
                return rows
        await asyncio.sleep(0.2)
    raise TimeoutError(f"trace file did not appear or stay empty: {path}")


async def _wait_for_stable_jsonl_trace(
    path: Path,
    *,
    timeout: float = 10.0,
    stable_for: float = 0.8,
    min_rows: int = 1,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last_signature: tuple[int, int] | None = None
    stable_since: float | None = None
    last_rows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        if path.exists():
            rows = _read_jsonl(path)
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            if len(rows) >= min_rows:
                if signature != last_signature:
                    last_signature = signature
                    stable_since = time.monotonic()
                    last_rows = rows
                elif stable_since is not None:
                    if time.monotonic() - stable_since >= stable_for:
                        return rows
        await asyncio.sleep(0.05)
    if last_rows:
        return last_rows
    raise TimeoutError(f"trace file did not appear or stay empty: {path}")


@pytest.mark.asyncio
async def test_wait_for_stable_jsonl_trace_waits_for_late_append(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "memory_experiments.jsonl"

    async def _append_trace_rows() -> None:
        trace_path.write_text('{"idx": 1}\n', encoding="utf-8")
        await asyncio.sleep(0.15)
        with trace_path.open("a", encoding="utf-8") as f:
            f.write('{"idx": 2}\n')

    append_task = asyncio.create_task(_append_trace_rows())
    rows = await _wait_for_stable_jsonl_trace(
        trace_path,
        timeout=2.0,
        stable_for=0.2,
    )
    await append_task

    assert [row["idx"] for row in rows] == [1, 2]


@pytest.mark.asyncio
async def test_memory_experiment_trace_is_written_from_real_agent_runtime(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    config_path = tmp_path / "config.toml"
    socket_path = tmp_path / "agent.sock"
    log_path = tmp_path / "agent.stdout.log"
    client_id = "codexsmoke"
    session_id = "memory-exp"
    expected_session_key = f"cli:cli-{client_id}-{session_id}"

    async with _FakeOpenAI() as fake:
        _write_agent_config(
            path=config_path,
            workspace=workspace,
            socket_path=socket_path,
            fake_base_url=fake.base_url,
        )
        with _plugin_memory_experiment_config():
            async with _AgentProcess(
                config_path=config_path,
                workspace=workspace,
                socket_path=socket_path,
                log_path=log_path,
            ):
                response = await _send_cli_message(
                    socket_path=socket_path,
                    client_id=client_id,
                    session_id=session_id,
                    text="请记住我喜欢中文回答。",
                )
                trace_path = workspace / "observe" / "memory_experiments.jsonl"
                rows = await _wait_for_stable_jsonl_trace(trace_path)

    assert response["content"] == "已记录你的偏好。"

    assert trace_path.exists(), log_path.read_text(encoding="utf-8", errors="ignore")
    assert len(rows) >= 1
    trace = rows[-1]
    assert trace["feature_name"] == "write_value_score"
    assert trace["mode"] == "shadow"
    assert trace["session_key"] == expected_session_key
    assert trace["turn_id"] == f"{expected_session_key}@post_response"
    assert trace["baseline_result"]["attempted_count"] == 1
    assert trace["baseline_result"]["baseline_written_count"] == 1
    assert trace["metrics_json"]["candidate_count"] == 1
    assert trace["metrics_json"]["policy_allow_count"] == 1
    assert trace["metrics_json"]["policy_reject_count"] == 0
    candidate = trace["experimental_result"]["candidates"][0]
    assert candidate["final_score"] >= 0.0
    assert candidate["final_score"] <= 1.0
    assert "signals" in candidate
    assert "reasons" in candidate
    assert "entropy_score" in candidate["signals"]
    assert "similar_memory_count" in candidate
    assert "nearest_memory_ids" in candidate
    assert trace["metrics_json"]["policy_review_count"] == 0
    assert trace["metrics_json"]["avg_final_score"] >= 0.0
    assert "write_reduction_rate" in trace["metrics_json"]

    memory_db = workspace / "memory" / "memory2.db"
    assert memory_db.exists()
    con = sqlite3.connect(memory_db)
    try:
        count = con.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
    finally:
        con.close()
    assert count >= 1


@pytest.mark.asyncio
async def test_memory_experiment_trace_stays_in_memorize_session(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    config_path = tmp_path / "config.toml"
    socket_path = tmp_path / "agent.sock"
    log_path = tmp_path / "agent.stdout.log"
    client_id = "codexsmoke"
    memorize_session = "memory-exp-a"
    plain_session = "memory-exp-b"
    memorize_key = f"cli:cli-{client_id}-{memorize_session}"
    plain_key = f"cli:cli-{client_id}-{plain_session}"

    async with _FakeOpenAI() as fake:
        _write_agent_config(
            path=config_path,
            workspace=workspace,
            socket_path=socket_path,
            fake_base_url=fake.base_url,
        )
        with _plugin_memory_experiment_config():
            async with _AgentProcess(
                config_path=config_path,
                workspace=workspace,
                socket_path=socket_path,
                log_path=log_path,
            ):
                await _send_cli_message(
                    socket_path=socket_path,
                    client_id=client_id,
                    session_id=memorize_session,
                    text="请记住我喜欢中文回答。",
                )
                await _send_cli_message(
                    socket_path=socket_path,
                    client_id=client_id,
                    session_id=plain_session,
                    text="普通问题，不要调用记忆工具。",
                )
                trace_path = workspace / "observe" / "memory_experiments.jsonl"
                rows = await _wait_for_jsonl_trace(trace_path)

    write_value_rows = [
        row for row in rows if row.get("feature_name") == "write_value_score"
    ]
    assert len(write_value_rows) == 1
    assert write_value_rows[0]["session_key"] == memorize_key
    assert write_value_rows[0]["session_key"] != plain_key

    con = sqlite3.connect(workspace / "sessions.db")
    con.row_factory = sqlite3.Row
    try:
        sessions = [
            dict(row)
            for row in con.execute("SELECT key, next_seq FROM sessions ORDER BY key")
        ]
    finally:
        con.close()
    assert {row["key"] for row in sessions} == {memorize_key, plain_key}
