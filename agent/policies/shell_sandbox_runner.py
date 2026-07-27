from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO, Protocol

from agent.policies.shell_sandbox_plan import ShellSandboxPolicy, ShellSandboxPreview

_MAX_OUTPUT_BYTES = 30_000
_STREAM_CHUNK_BYTES = 8_192
_CLEANUP_TIMEOUT_SECONDS = 5
_IMAGE_INSPECT_TIMEOUT_SECONDS = 5
_MAX_MEMORY_BYTES = 512 * 1024 * 1024
_MEMORY_LIMIT_PATTERN = re.compile(r"^([1-9][0-9]*)([bkmg])$", re.IGNORECASE)
_MEMORY_MULTIPLIERS = {
    "b": 1,
    "k": 1024,
    "m": 1024 * 1024,
    "g": 1024 * 1024 * 1024,
}


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


class SandboxStatePersistenceError(RuntimeError):
    def __init__(
        self, *, execution_succeeded: bool, execution_status: str
    ) -> None:
        super().__init__("shell sandbox output state could not be persisted")
        self.execution_succeeded = execution_succeeded
        self.execution_status = execution_status


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
            timeout=_IMAGE_INSPECT_TIMEOUT_SECONDS,
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
        if not _sandbox_policy_valid(preview):
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
                timeout=_CLEANUP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            pass
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
            _terminate_process(proc)
            self._cleanup_container(self.container_name(preview))
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


def _terminate_process(proc: subprocess.Popen[bytes]) -> None:
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=1)
    except Exception:
        pass


def _sandbox_policy_valid(preview: ShellSandboxPreview) -> bool:
    policy = ShellSandboxPolicy()
    if (
        preview.image != policy.image
        or preview.network_mode != policy.network_mode
        or preview.workspace_mount_mode != policy.workspace_mount_mode
        or preview.background_requested
        or preview.background_allowed
    ):
        return False
    if not _non_root_user(preview.user):
        return False
    memory_bytes = _memory_limit_bytes(preview.memory_limit)
    if memory_bytes is None or memory_bytes > _MAX_MEMORY_BYTES:
        return False
    try:
        cpus = Decimal(preview.cpus)
    except (InvalidOperation, TypeError, ValueError):
        return False
    if not cpus.is_finite() or cpus <= 0 or cpus > Decimal(policy.cpus):
        return False
    if (
        isinstance(preview.pids_limit, bool)
        or not isinstance(preview.pids_limit, int)
        or not 1 <= preview.pids_limit <= policy.pids_limit
    ):
        return False
    if (
        isinstance(preview.timeout_seconds, bool)
        or not isinstance(preview.timeout_seconds, int)
        or not 1 <= preview.timeout_seconds <= policy.max_timeout_seconds
    ):
        return False
    try:
        workspace = preview.workspace_root.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return workspace == preview.workspace_root and workspace.is_dir()


def _non_root_user(value: str) -> bool:
    match = re.fullmatch(r"([0-9]+)(?::([0-9]+))?", value)
    if match is None:
        return False
    uid = int(match.group(1))
    gid = int(match.group(2) or match.group(1))
    return uid > 0 and gid > 0


def _memory_limit_bytes(value: str) -> int | None:
    match = _MEMORY_LIMIT_PATTERN.fullmatch(value)
    if match is None:
        return None
    return int(match.group(1)) * _MEMORY_MULTIPLIERS[match.group(2).lower()]


def _write_output(
    preview: ShellSandboxPreview,
    output: _StreamOutput,
    exit_code: int | None,
    reason: str,
    started: float,
) -> SandboxRunResult:
    stdout_path = preview.artifact_dir / "stdout.txt"
    stderr_path = preview.artifact_dir / "stderr.txt"
    try:
        _validate_artifact_directory(preview)
        _write_private_file(stdout_path, output.stdout)
        _write_private_file(stderr_path, output.stderr)
    except Exception as exc:
        raise SandboxStatePersistenceError(
            execution_succeeded=reason == "sandbox_executed",
            execution_status=reason,
        ) from exc
    return SandboxRunResult(
        ok=reason == "sandbox_executed",
        reason=reason,
        exit_code=exit_code,
        stdout_path=str(stdout_path.relative_to(preview.artifact_dir)),
        stderr_path=str(stderr_path.relative_to(preview.artifact_dir)),
        stdout_hash=output.stdout_hash,
        stderr_hash=output.stderr_hash,
        stdout_bytes=output.stdout_bytes,
        stderr_bytes=output.stderr_bytes,
        stdout_truncated=output.stdout_truncated,
        stderr_truncated=output.stderr_truncated,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def _write_private_file(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
            raise OSError("shell artifact must be a singly-linked regular file")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as file:
            file.write(content)
            file.flush()
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    finally:
        os.close(fd)


def _validate_artifact_directory(preview: ShellSandboxPreview) -> None:
    expected = (
        preview.workspace_root
        / "tool_side_effects"
        / "artifacts"
        / preview.preview_id
    )
    if preview.artifact_dir != expected:
        raise ValueError("shell artifact directory is outside managed workspace")
    current = preview.workspace_root
    for name in ("tool_side_effects", "artifacts", preview.preview_id):
        current = current / name
        current_stat = current.lstat()
        if stat.S_ISLNK(current_stat.st_mode) or not stat.S_ISDIR(
            current_stat.st_mode
        ):
            raise ValueError("shell artifact directory contains symlink")
    if current.resolve(strict=True) != expected:
        raise ValueError("shell artifact directory escapes managed workspace")
