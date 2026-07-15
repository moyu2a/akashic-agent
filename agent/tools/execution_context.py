from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True)
class ToolExecutionContext:
    """Runtime-owned values for one registry execution call only."""

    protected: Mapping[str, object] = field(default_factory=dict)
    propagate_tool_errors: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "protected", MappingProxyType(dict(self.protected)))
