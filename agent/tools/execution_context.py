from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


TASK_EXECUTION_PROTECTED_KEYS = frozenset(
    {
        "_session_key",
        "_task_execution_request_id",
        "_task_execution_action",
        "_task_execution_target_step_id",
        "_task_execution_attempt_id",
        "_tool_execution_context_active",
    }
)


@dataclass(frozen=True)
class ToolExecutionContext:
    """Runtime-owned values for one registry execution call only."""

    protected: Mapping[str, object] = field(default_factory=dict)
    propagate_tool_errors: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "protected", MappingProxyType(dict(self.protected)))
