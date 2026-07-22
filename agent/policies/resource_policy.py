from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

ResourcePolicyAction = Literal["allow", "deny", "defer", "not_applicable"]

_ACTIONS = frozenset({"allow", "deny", "defer", "not_applicable"})
_FILE_PATH_ARGUMENTS = {
    "read_file": "path",
    "list_dir": "path",
    "write_file": "path",
    "edit_file": "path",
}
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
