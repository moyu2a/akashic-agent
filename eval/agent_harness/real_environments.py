from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import shutil
from pathlib import Path

from .real_executor import G10AExecutionAuthorization

_DEFAULT_PRODUCTION_SOCKET = Path("/tmp/akashic.sock")


@dataclass(frozen=True)
class G10ARealEnvironment:
    authorization: G10AExecutionAuthorization
    run_id: str
    profile_name: str
    case_id: str
    workspace: Path
    config_path: Path
    socket_path: Path
    session_key: str
    observe_db_path: Path
    sessions_db_path: Path
    memory_db_path: Path
    tool_audit_db_path: Path
    runtime_config: dict[str, object]

    def cleanup(self) -> None:
        if self.workspace.exists():
            shutil.rmtree(self.workspace)


def prepare_real_environment(
    authorization: G10AExecutionAuthorization,
    *,
    run_id: str,
    profile_name: str,
    case_id: str | None = None,
    workspace_root: Path | None = None,
    socket_path: Path | None = None,
) -> G10ARealEnvironment:
    root = Path(workspace_root or ".akashic/eval_runs").resolve()
    case = str(case_id or authorization.case_id)
    workspace = root / str(run_id) / str(profile_name) / case
    workspace.mkdir(parents=True, exist_ok=True)

    selected_socket = (
        Path(socket_path) if socket_path is not None else _default_socket(workspace)
    )
    _validate_socket_path(selected_socket, workspace)

    config_path = workspace / "config.toml"
    config_path.write_text(
        "# g10a real executor workspace\n",
        encoding="utf-8",
    )

    observe_db_path = workspace / "observe" / "observe.db"
    sessions_db_path = workspace / "sessions.db"
    memory_db_path = workspace / "memory" / "memory2.db"
    tool_audit_db_path = workspace / "tool_audit.db"
    _touch(observe_db_path)
    _touch(sessions_db_path)
    _touch(memory_db_path)
    _touch(tool_audit_db_path)

    runtime_config = {
        "adapter_name": authorization.entry.adapter_name,
        "case_id": case,
        "environment_kind": authorization.environment_kind,
        "run_id": str(run_id),
        "workspace": str(workspace),
        "socket": str(selected_socket),
        "runtime_profile": asdict(authorization.runtime_profile),
        "manifest_metadata": dict(authorization.manifest_metadata),
    }
    (workspace / "runtime-config.json").write_text(
        json.dumps(runtime_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return G10ARealEnvironment(
        authorization=authorization,
        run_id=str(run_id),
        profile_name=str(profile_name),
        case_id=case,
        workspace=workspace,
        config_path=config_path,
        socket_path=selected_socket,
        session_key=f"g10a:{run_id}:{profile_name}:{case}",
        observe_db_path=observe_db_path,
        sessions_db_path=sessions_db_path,
        memory_db_path=memory_db_path,
        tool_audit_db_path=tool_audit_db_path,
        runtime_config=runtime_config,
    )


def classify_real_environment_failure(error: str) -> str | None:
    value = str(error).lower()
    if (
        "connection refused" in value
        or "stale socket" in value
        or "econnrefused" in value
    ):
        return "infra_stale_socket"
    if "timeout" in value:
        return "infra_timeout"
    return None


def _default_socket(workspace: Path) -> Path:
    return workspace / "ipc" / "g10a.sock"


def _validate_socket_path(socket_path: Path, workspace: Path) -> None:
    resolved = socket_path.resolve(strict=False)
    if resolved == _DEFAULT_PRODUCTION_SOCKET.resolve(strict=False):
        raise ValueError("socket path cannot use the production default socket")
    try:
        workspace_resolved = workspace.resolve(strict=False)
    except OSError:
        workspace_resolved = workspace
    if workspace_resolved not in resolved.parents and resolved != workspace_resolved:
        raise ValueError("socket path must stay under the eval workspace")


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
