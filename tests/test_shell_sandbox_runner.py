from __future__ import annotations

import io
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest

from agent.policies.shell_sandbox_plan import prepare_shell_sandbox_preview
from agent.policies.shell_sandbox_runner import (
    DockerPodmanSandboxRunner,
    _stream_output,
)


def test_docker_podman_runner_builds_fail_closed_read_only_no_network_command(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        arguments={"command": "echo hi", "description": "say hi"},
    )
    runner = DockerPodmanSandboxRunner(binary="podman")

    argv = runner.build_argv(preview)

    assert argv[:3] == ["podman", "run", "--rm"]
    assert "--network" in argv
    assert "none" in argv
    assert "--pull" in argv
    assert "never" in argv
    assert "--read-only" in argv
    assert "--cap-drop" in argv
    assert "ALL" in argv
    assert "--security-opt" in argv
    assert "no-new-privileges" in argv
    assert "--pids-limit" in argv
    assert "128" in argv
    assert "--memory" in argv
    assert "512m" in argv
    assert "--cpus" in argv
    assert "1.0" in argv
    assert "--user" in argv
    assert "65532:65532" in argv
    joined = " ".join(argv)
    assert f"{workspace}:/workspace:ro" in joined
    assert "echo hi" not in joined
    assert f"{preview.artifact_dir}:/artifacts:rw" not in joined
    assert "--privileged" not in argv
    assert "/var/run/docker.sock" not in joined
    assert "--entrypoint" in argv
    assert argv[argv.index("--entrypoint") + 1] == "sh"
    assert argv[-1] == "-s"


def test_docker_podman_runner_returns_unavailable_without_binary(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert DockerPodmanSandboxRunner.find_available() is None


def test_docker_podman_runner_checks_local_image_without_pull(monkeypatch) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr("subprocess.run", fake_run)
    runner = DockerPodmanSandboxRunner(binary="podman")
    preview = prepare_shell_sandbox_preview(
        workspace_root=Path("/workspace"),
        artifact_root=Path("/tmp/artifacts"),
        arguments={"command": "echo hi", "description": "say hi"},
    )

    assert runner.image_available(preview) is True
    assert calls == [["podman", "image", "inspect", "python:3.14-slim"]]


def test_docker_podman_runner_reports_image_unavailable_without_running(
    monkeypatch, tmp_path: Path
) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return type("Completed", (), {"returncode": 1})()

    monkeypatch.setattr("subprocess.run", fake_run)
    runner = DockerPodmanSandboxRunner(binary="podman")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        arguments={"command": "echo hi", "description": "say hi"},
    )

    result = runner.run(preview, "echo hi")

    assert result.ok is False
    assert result.reason == "shell_sandbox_image_unavailable"
    assert calls == [["podman", "image", "inspect", "python:3.14-slim"]]


def test_docker_podman_runner_handles_image_inspect_errors(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("podman")

    monkeypatch.setattr("subprocess.run", fake_run)
    runner = DockerPodmanSandboxRunner(binary="podman")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        arguments={"command": "echo hi", "description": "say hi"},
    )

    result = runner.run(preview, "echo hi")

    assert result.ok is False
    assert result.reason == "shell_sandbox_launch_failed"


def test_docker_podman_runner_streams_large_output_incrementally(
    monkeypatch, tmp_path: Path
) -> None:
    import io

    class FakeProc:
        def __init__(self) -> None:
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(b"x" * 40000)
            self.stderr = io.BytesIO(b"y" * 5)
            self.returncode = 0

        def wait(self, timeout=None) -> int:
            return 0

        def poll(self) -> int:
            return 0

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        arguments={"command": "echo hi", "description": "say hi"},
    )
    runner = DockerPodmanSandboxRunner(binary="podman")
    monkeypatch.setattr(runner, "image_available", lambda preview: True)
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: FakeProc())

    result = runner.run(preview, "echo hi")

    assert result.ok is True
    assert result.reason == "sandbox_executed"
    assert result.stdout_bytes == 40000
    assert result.stdout_truncated is True
    assert result.stderr_bytes == 5
    assert result.stderr_truncated is False


def test_docker_podman_runner_surfaces_launch_failure_without_consuming_output(
    monkeypatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        arguments={"command": "echo hi", "description": "say hi"},
    )
    runner = DockerPodmanSandboxRunner(binary="podman")
    monkeypatch.setattr(runner, "image_available", lambda preview: True)

    def fake_popen(*args, **kwargs):
        raise FileNotFoundError("podman")

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = runner.run(preview, "echo hi")

    assert result.ok is False
    assert result.reason == "shell_sandbox_launch_failed"


@pytest.mark.parametrize(
    ("policy_field", "unsafe_value"),
    [("network_mode", "bridge"), ("workspace_mount_mode", "rw")],
)
def test_docker_podman_runner_rejects_unsafe_preview_policy(
    monkeypatch, tmp_path: Path, policy_field: str, unsafe_value: str
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        arguments={"command": "echo hi", "description": "say hi"},
    )
    unsafe_preview = replace(preview, **{policy_field: unsafe_value})
    runner = DockerPodmanSandboxRunner(binary="podman")
    popen_calls = []
    monkeypatch.setattr(runner, "image_available", lambda preview: True)
    monkeypatch.setattr(
        "subprocess.Popen", lambda *args, **kwargs: popen_calls.append(args)
    )

    with pytest.raises(ValueError, match="unsupported shell sandbox policy"):
        runner.build_argv(unsafe_preview)

    result = runner.run(unsafe_preview, "echo hi")

    assert result.ok is False
    assert result.reason == "shell_sandbox_policy_invalid"
    assert popen_calls == []


def test_docker_podman_runner_cleans_up_named_container_after_timeout(
    monkeypatch, tmp_path: Path
) -> None:
    class TimeoutProc:
        def __init__(self) -> None:
            self.args = ["podman", "run"]
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(b"partial stdout")
            self.stderr = io.BytesIO(b"partial stderr")
            self.returncode = 137
            self.killed = False

        def wait(self, timeout=None) -> int:
            if timeout is not None:
                raise subprocess.TimeoutExpired(self.args, timeout)
            return self.returncode

        def kill(self) -> None:
            self.killed = True

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = prepare_shell_sandbox_preview(
        workspace_root=workspace,
        artifact_root=tmp_path / "artifacts",
        arguments={"command": "echo hi", "description": "say hi"},
    )
    runner = DockerPodmanSandboxRunner(binary="podman")
    proc = TimeoutProc()
    cleaned_containers = []
    monkeypatch.setattr(runner, "image_available", lambda preview: True)
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: proc)
    monkeypatch.setattr(runner, "_cleanup_container", cleaned_containers.append)

    result = runner.run(preview, "echo hi")

    assert result.reason == "sandbox_timeout"
    assert proc.killed is True
    assert cleaned_containers == [runner.container_name(preview)]


def test_docker_podman_runner_times_out_when_stdin_write_blocks(
    monkeypatch, tmp_path: Path
) -> None:
    class BlockingStdin:
        def write(self, data: bytes) -> int:
            time.sleep(0.05)
            return len(data)

        def close(self) -> None:
            return None

    class ExitedProc:
        def __init__(self) -> None:
            self.args = ["podman", "run"]
            self.stdin = BlockingStdin()
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            self.returncode = 0
            self.killed = False

        def wait(self, timeout=None) -> int:
            return self.returncode

        def kill(self) -> None:
            self.killed = True

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    preview = replace(
        prepare_shell_sandbox_preview(
            workspace_root=workspace,
            artifact_root=tmp_path / "artifacts",
            arguments={"command": "echo hi", "description": "say hi"},
        ),
        timeout_seconds=0.01,
    )
    runner = DockerPodmanSandboxRunner(binary="podman")
    proc = ExitedProc()
    cleaned_containers = []
    monkeypatch.setattr(runner, "image_available", lambda preview: True)
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: proc)
    monkeypatch.setattr(runner, "_cleanup_container", cleaned_containers.append)

    result = runner.run(preview, "echo hi")

    assert result.reason == "sandbox_timeout"
    assert proc.killed is True
    assert cleaned_containers == [runner.container_name(preview)]


def test_stream_output_preserves_partial_streams_on_timeout() -> None:
    class TimeoutProc:
        def __init__(self) -> None:
            self.args = ["podman", "run"]
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(b"partial stdout")
            self.stderr = io.BytesIO(b"partial stderr")
            self.returncode = 137

        def wait(self, timeout=None) -> int:
            if timeout is not None:
                raise subprocess.TimeoutExpired(self.args, timeout)
            return self.returncode

        def kill(self) -> None:
            return None

    with pytest.raises(subprocess.TimeoutExpired) as raised:
        _stream_output(TimeoutProc(), b"echo hi", timeout_seconds=1)

    assert raised.value.output == b"partial stdout"
    assert raised.value.stderr == b"partial stderr"
