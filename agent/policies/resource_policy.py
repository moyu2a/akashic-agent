from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from agent.tools.execution_context import TASK_EXECUTION_PROTECTED_KEYS

ResourcePolicyAction = Literal["allow", "deny", "defer", "not_applicable"]

_ACTIONS = frozenset({"allow", "deny", "defer", "not_applicable"})
_FILE_PATH_ARGUMENTS = {
    "read_file": "path",
    "list_dir": "path",
    "write_file": "path",
    "edit_file": "path",
}
_PROTECTED_ARGUMENT_KEYS = frozenset(
    {
        "_session_key",
        "_request_id",
        "_attempt_id",
        "_transport_request_id",
    }
) | TASK_EXECUTION_PROTECTED_KEYS
_SHELL_TOOL_NAMES = frozenset({"shell"})
_SHELL_COMMAND_ARG = "command"
_SHELL_TOP_LEVEL_OPERATORS = frozenset({"|", ";", "&&", "||", ">", ">>", "<"})
_SHELL_DESTRUCTIVE_COMMANDS = frozenset(
    {"rm", "rmdir", "unlink", "shred", "dd", "mkfs", "chmod", "chown", "truncate"}
)
_SHELL_INLINE_INTERPRETERS = frozenset(
    {"python", "python3", "bash", "sh", "zsh", "node", "perl", "ruby", "php"}
)
_SHELL_WRAPPER_COMMANDS = frozenset({"sudo", "doas", "env", "command", "time", "nohup"})
_INLINE_DANGEROUS_MARKERS = (
    "os.remove",
    "os.unlink",
    "shutil.rmtree",
    "subprocess",
    "os.system",
    "exec(",
    "eval(",
)
_PROTECTED_PREFIXES = (
    Path("/etc"),
    Path("/root"),
    Path("/proc"),
    Path("/sys"),
    Path("/dev"),
)


@dataclass(frozen=True)
class ResourcePolicyContext:
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    resource_roots: tuple[str, ...] = ()
    source: str = "passive"
    registry_risk: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))
        object.__setattr__(self, "resource_roots", tuple(self.resource_roots))


@dataclass(frozen=True)
class ResourcePolicyDecision:
    action: ResourcePolicyAction
    reason: str
    resource_type: str = ""
    target: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action not in _ACTIONS:
            raise ValueError("unsupported resource policy action")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def effective(self) -> bool:
        return self.action != "not_applicable"

    def to_trace_metadata(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "resource_type": self.resource_type,
            "target": self.target,
            "metadata": dict(self.metadata),
        }


class ResourcePolicyEngine:
    policy_name = "ResourcePolicyEngine"

    def evaluate(self, context: ResourcePolicyContext) -> ResourcePolicyDecision:
        protected_key = _first_protected_argument(context.arguments)
        if protected_key is not None:
            return ResourcePolicyDecision(
                action="deny",
                reason="resource_policy_protected_argument_forged",
                resource_type="runtime_context",
                target=protected_key,
                metadata={
                    "tool_name": context.tool_name,
                    "argument": protected_key,
                    "invoker_reached": False,
                },
            )
        if context.tool_name in _SHELL_TOOL_NAMES:
            return _evaluate_shell_command(context)
        path_arg = _FILE_PATH_ARGUMENTS.get(context.tool_name)
        if path_arg is None:
            return ResourcePolicyDecision(
                action="not_applicable",
                reason="resource_policy_not_applicable",
            )
        path_value = context.arguments.get(path_arg)
        if not isinstance(path_value, str) or not path_value.strip():
            return ResourcePolicyDecision(
                action="not_applicable",
                reason="resource_policy_missing_path_argument",
                resource_type="file",
                metadata={"tool_name": context.tool_name, "path_arg": path_arg},
            )
        roots = _normalized_roots(context.resource_roots)
        if not roots:
            return ResourcePolicyDecision(
                action="allow",
                reason="resource_policy_no_roots_compat_allow",
                resource_type="file",
                target=path_value,
                metadata={
                    "tool_name": context.tool_name,
                    "path_arg": path_arg,
                    "within_roots": None,
                },
            )
        try:
            target = _resolve_candidate(path_value, roots)
        except (OSError, RuntimeError, ValueError) as exc:
            return ResourcePolicyDecision(
                action="deny",
                reason="resource_policy_invalid_file_path",
                resource_type="file",
                target=path_value,
                metadata={
                    "tool_name": context.tool_name,
                    "path_arg": path_arg,
                    "error": type(exc).__name__,
                    "invoker_reached": False,
                },
            )
        for protected in _PROTECTED_PREFIXES:
            if target == protected or _is_within(target, protected):
                return ResourcePolicyDecision(
                    action="deny",
                    reason="resource_policy_protected_system_path",
                    resource_type="file",
                    target=str(target),
                    metadata={
                        "tool_name": context.tool_name,
                        "path_arg": path_arg,
                        "protected_prefix": str(protected),
                        "invoker_reached": False,
                    },
                )
        if not any(target == root or _is_within(target, root) for root in roots):
            return ResourcePolicyDecision(
                action="deny",
                reason="resource_policy_file_path_outside_roots",
                resource_type="file",
                target=str(target),
                metadata={
                    "tool_name": context.tool_name,
                    "path_arg": path_arg,
                    "allowed_roots": [str(root) for root in roots],
                    "within_roots": False,
                    "invoker_reached": False,
                },
            )
        return ResourcePolicyDecision(
            action="allow",
            reason="resource_policy_file_path_allowed",
            resource_type="file",
            target=str(target),
            metadata={
                "tool_name": context.tool_name,
                "path_arg": path_arg,
                "allowed_roots": [str(root) for root in roots],
                "within_roots": True,
            },
        )


def _first_protected_argument(arguments: Mapping[str, Any]) -> str | None:
    for key in sorted(_PROTECTED_ARGUMENT_KEYS):
        if key in arguments:
            return key
    return None


def _evaluate_shell_command(context: ResourcePolicyContext) -> ResourcePolicyDecision:
    command = context.arguments.get(_SHELL_COMMAND_ARG)
    if not isinstance(command, str) or not command.strip():
        return ResourcePolicyDecision(
            action="not_applicable",
            reason="resource_policy_missing_shell_command",
            resource_type="shell",
            metadata={
                "tool_name": context.tool_name,
                "command_arg": _SHELL_COMMAND_ARG,
            },
        )
    try:
        tokens = _shell_tokens(command)
    except ValueError as exc:
        return ResourcePolicyDecision(
            action="deny",
            reason="resource_policy_shell_invalid_command",
            resource_type="shell",
            target=command,
            metadata={
                "tool_name": context.tool_name,
                "error": type(exc).__name__,
                "invoker_reached": False,
            },
        )
    if not tokens:
        return ResourcePolicyDecision(
            action="not_applicable",
            reason="resource_policy_missing_shell_command",
            resource_type="shell",
            metadata={
                "tool_name": context.tool_name,
                "command_arg": _SHELL_COMMAND_ARG,
            },
        )
    has_operator = any(token in _SHELL_TOP_LEVEL_OPERATORS for token in tokens)
    executables = _shell_executables(tokens)
    destructive_executable = next(
        (exe for exe in executables if exe in _SHELL_DESTRUCTIVE_COMMANDS),
        "",
    )
    if destructive_executable:
        return ResourcePolicyDecision(
            action="deny",
            reason=(
                "resource_policy_shell_destructive_compound_denied"
                if has_operator
                else "resource_policy_shell_destructive_command_denied"
            ),
            resource_type="shell",
            target=command,
            metadata={
                "tool_name": context.tool_name,
                "executable": destructive_executable,
                "invoker_reached": False,
            },
        )
    for executable in executables:
        if executable in _SHELL_INLINE_INTERPRETERS and "-c" in tokens:
            inline = " ".join(tokens)
            if any(marker in inline for marker in _INLINE_DANGEROUS_MARKERS):
                return ResourcePolicyDecision(
                    action="deny",
                    reason="resource_policy_shell_inline_interpreter_denied",
                    resource_type="shell",
                    target=command,
                    metadata={
                        "tool_name": context.tool_name,
                        "executable": executable,
                        "invoker_reached": False,
                    },
                )
    return ResourcePolicyDecision(
        action="allow",
        reason="resource_policy_shell_command_allowed",
        resource_type="shell",
        target=command,
        metadata={"tool_name": context.tool_name},
    )


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _shell_executables(tokens: list[str]) -> list[str]:
    executables: list[str] = []
    segment: list[str] = []
    for token in tokens:
        if token in _SHELL_TOP_LEVEL_OPERATORS:
            executables.extend(_segment_executables(segment))
            segment = []
            continue
        segment.append(token)
    executables.extend(_segment_executables(segment))
    return executables


def _segment_executables(segment: list[str]) -> list[str]:
    executable = _first_segment_executable(segment)
    if not executable:
        return []
    executables = [executable]
    if executable == "xargs":
        target = _xargs_target_executable(segment[1:])
        if target:
            executables.append(target)
    return executables


def _first_segment_executable(segment: list[str]) -> str:
    index = 0
    while index < len(segment):
        token = segment[index]
        executable = token.rsplit("/", 1)[-1]
        if (
            "=" in token
            and not token.startswith("-")
            and token.split("=", 1)[0].isidentifier()
        ):
            index += 1
            continue
        if executable in _SHELL_WRAPPER_COMMANDS:
            index += 1
            while index < len(segment) and segment[index].startswith("-"):
                index += 1
            continue
        return executable
    return ""


def _xargs_target_executable(tokens: list[str]) -> str:
    for token in tokens:
        if token.startswith("-"):
            continue
        return token.rsplit("/", 1)[-1]
    return ""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalized_roots(values: tuple[str, ...]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        roots.append(Path(value).expanduser().resolve(strict=False))
    return tuple(roots)


def _resolve_candidate(path_value: str, roots: tuple[Path, ...]) -> Path:
    raw = Path(path_value).expanduser()
    base = roots[0] if roots and not raw.is_absolute() else None
    candidate = (base / raw) if base is not None else raw
    return _resolve_existing_prefix(candidate)


def _resolve_existing_prefix(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except FileNotFoundError:
        missing_parts: list[str] = []
        cursor = path
        while not cursor.exists():
            missing_parts.append(cursor.name)
            parent = cursor.parent
            if parent == cursor:
                break
            cursor = parent
        resolved = cursor.resolve(strict=False)
        for part in reversed(missing_parts):
            resolved = resolved / part
        return resolved
