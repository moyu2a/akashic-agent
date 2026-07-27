from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from agent.policies.shell_sandbox_plan import ShellSandboxPreview

_MAX_OUTPUT_BYTES = 30_000
_STREAM_CHUNK_BYTES = 8_192


@dataclass(frozen=True)
class SandboxRunResult:
    ok: bool
    reason: str
    exit_code: int | None
    stdout_path: str
    stderr_path: str
    stdout_hash: str
    stderr_hash: str
    stdout_bytes: int
    stderr_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    duration_ms: int


class SandboxRunner(Protocol):
    def run(self, preview: ShellSandboxPreview, command: str) -> SandboxRunResult: ...


@dataclass(frozen=True)
class _StreamOutput:
    stdout: bytes
    stderr: bytes
    stdout_bytes: int
    stderr_bytes: int
    stdout_hash: str
    stderr_hash: str
    stdout_truncated: bool
    stderr_truncated: bool
    returncode: int


class _BoundedCapture:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.digest = hashlib.sha256()
        self.total_bytes = 0
        self.truncated = False

    def add(self, chunk: bytes) -> None:
        self.digest.update(chunk)
        self.total_bytes += len(chunk)
        remaining = _MAX_OUTPUT_BYTES - len(self.buffer)
        if remaining > 0:
            self.buffer.extend(chunk[:remaining])
        if len(chunk) > remaining:
            self.truncated = True


class DockerPodmanSandboxRunner:
    def __init__(self, *, binary: str) -> None:
        self.binary = binary

    @classmethod
    def find_available(cls) -> DockerPodmanSandboxRunner | None:
        for name in ("podman", "docker"):
            path = shutil.which(name)
            if path:
                return cls(binary=path)
        return None

    def image_available(self, preview: ShellSandboxPreview) -> bool:
        completed = subprocess.run(
            [self.binary, "image", "inspect", preview.image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return completed.returncode == 0

    def backend_name(self) -> str:
        return Path(self.binary).name

    def container_name(self, preview: ShellSandboxPreview) -> str:
        normalized_preview_id = re.sub(
            r"[^a-z0-9_.-]+", "-", preview.preview_id.lower()
        )
        normalized_preview_id = normalized_preview_id.strip(".-") or "preview"
        preview_hash = hashlib.sha256(preview.preview_id.encode("utf-8")).hexdigest()[
            :12
        ]
        return f"shell-sandbox-{normalized_preview_id[:36]}-{preview_hash}"

    def build_argv(self, preview: ShellSandboxPreview) -> list[str]:
        if preview.network_mode != "none" or preview.workspace_mount_mode != "ro":
            raise ValueError("unsupported shell sandbox policy")

        return [
            self.binary,
            "run",
            "--rm",
            "--name",
            self.container_name(preview),
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(preview.pids_limit),
            "--memory",
            preview.memory_limit,
            "--cpus",
            preview.cpus,
            "--user",
            preview.user,
            "--workdir",
            "/workspace",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--entrypoint",
            "sh",
            "-v",
            f"{preview.workspace_root}:/workspace:ro",
            preview.image,
            "-s",
        ]

    def _cleanup_container(self, container_name: str) -> None:
        try:
            subprocess.run(
                [self.binary, "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def run(self, preview: ShellSandboxPreview, command: str) -> SandboxRunResult:
        started = time.monotonic()
        try:
            argv = self.build_argv(preview)
        except ValueError:
            return _write_output(
                preview,
                _empty_stream_output(),
                None,
                "shell_sandbox_policy_invalid",
                started,
            )

        try:
            image_ready = self.image_available(preview)
        except Exception:
            return _write_output(
                preview,
                _empty_stream_output(),
                None,
                "shell_sandbox_launch_failed",
                started,
            )
        if not image_ready:
            return _write_output(
                preview,
                _empty_stream_output(),
                None,
                "shell_sandbox_image_unavailable",
                started,
            )

        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            return _write_output(
                preview,
                _empty_stream_output(),
                None,
                "shell_sandbox_launch_failed",
                started,
            )

        try:
            output = _stream_output(
                proc,
                command.encode("utf-8"),
                timeout_seconds=preview.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            output = getattr(exc, "stream_output", _empty_stream_output())
            self._cleanup_container(self.container_name(preview))
            return _write_output(preview, output, None, "sandbox_timeout", started)
        except Exception:
            return _write_output(
                preview,
                _empty_stream_output(),
                None,
                "sandbox_execution_failed",
                started,
            )

        reason = (
            "sandbox_executed" if output.returncode == 0 else "sandbox_exit_nonzero"
        )
        return _write_output(preview, output, output.returncode, reason, started)


def _stream_output(
    proc: subprocess.Popen[bytes], command_bytes: bytes, *, timeout_seconds: float
) -> _StreamOutput:
    if proc.stdin is None or proc.stdout is None or proc.stderr is None:
        raise RuntimeError("sandbox process pipes are unavailable")

    stdout_capture = _BoundedCapture()
    stderr_capture = _BoundedCapture()
    stdout_thread = threading.Thread(
        target=_drain_stream, args=(proc.stdout, stdout_capture), daemon=True
    )
    stderr_thread = threading.Thread(
        target=_drain_stream, args=(proc.stderr, stderr_capture), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()
    writer_done = threading.Event()
    writer_errors: list[BaseException] = []

    def write_stdin() -> None:
        try:
            proc.stdin.write(command_bytes)
            proc.stdin.close()
        except BaseException as exc:
            writer_errors.append(exc)
        finally:
            writer_done.set()

    writer_thread = threading.Thread(target=write_stdin, daemon=True)
    writer_thread.start()
    deadline = time.monotonic() + timeout_seconds

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout_seconds)

            if writer_done.is_set():
                if writer_errors:
                    raise writer_errors[0]
                returncode = proc.wait(timeout=remaining)
                break

            try:
                returncode = proc.wait(timeout=min(remaining, 0.01))
            except subprocess.TimeoutExpired:
                continue

            if not writer_done.wait(remaining):
                raise subprocess.TimeoutExpired(proc.args, timeout_seconds)
            if writer_errors:
                raise writer_errors[0]
            break
    except subprocess.TimeoutExpired as exc:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        output = _captured_output(
            stdout_capture,
            stderr_capture,
            proc.returncode if proc.returncode is not None else -1,
        )
        timeout = subprocess.TimeoutExpired(
            proc.args, exc.timeout, output=output.stdout, stderr=output.stderr
        )
        timeout.stream_output = output
        raise timeout from exc

    stdout_thread.join()
    stderr_thread.join()
    return _captured_output(stdout_capture, stderr_capture, returncode)


def _drain_stream(stream: BinaryIO, capture: _BoundedCapture) -> None:
    while chunk := stream.read(_STREAM_CHUNK_BYTES):
        capture.add(chunk)


def _captured_output(
    stdout_capture: _BoundedCapture, stderr_capture: _BoundedCapture, returncode: int
) -> _StreamOutput:
    return _StreamOutput(
        stdout=bytes(stdout_capture.buffer),
        stderr=bytes(stderr_capture.buffer),
        stdout_bytes=stdout_capture.total_bytes,
        stderr_bytes=stderr_capture.total_bytes,
        stdout_hash=stdout_capture.digest.hexdigest(),
        stderr_hash=stderr_capture.digest.hexdigest(),
        stdout_truncated=stdout_capture.truncated,
        stderr_truncated=stderr_capture.truncated,
        returncode=returncode,
    )


def _empty_stream_output() -> _StreamOutput:
    digest = hashlib.sha256(b"").hexdigest()
    return _StreamOutput(b"", b"", 0, 0, digest, digest, False, False, 0)


def _write_output(
    preview: ShellSandboxPreview,
    output: _StreamOutput,
    exit_code: int | None,
    reason: str,
    started: float,
) -> SandboxRunResult:
    stdout_path = preview.artifact_dir / "stdout.txt"
    stderr_path = preview.artifact_dir / "stderr.txt"
    _write_private_file(stdout_path, output.stdout)
    _write_private_file(stderr_path, output.stderr)
    return SandboxRunResult(
        ok=reason == "sandbox_executed",
        reason=reason,
        exit_code=exit_code,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        stdout_hash=output.stdout_hash,
        stderr_hash=output.stderr_hash,
        stdout_bytes=output.stdout_bytes,
        stderr_bytes=output.stderr_bytes,
        stdout_truncated=output.stdout_truncated,
        stderr_truncated=output.stderr_truncated,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def _write_private_file(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(content)
    os.chmod(path, 0o600)
