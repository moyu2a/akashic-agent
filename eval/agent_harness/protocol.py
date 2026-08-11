from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eval.agent_harness.compatibility import LegacySourceStatus


@dataclass(frozen=True)
class TaskSpec:
    case_id: str
    category: str
    steps: tuple[dict[str, object], ...]
    expected_outcome: dict[str, object]


@dataclass(frozen=True)
class EpisodeResult:
    episode_id: str
    status: str
    outcome_passed: bool
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LegacySourceRecord:
    name: str
    path: str
    source_commit: str
    input_hash: str
    status: "LegacySourceStatus | str"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    historical: bool = False
    shadow: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        from eval.agent_harness.compatibility import LegacySourceStatus

        if not isinstance(self.status, LegacySourceStatus):
            raise ValueError("status must be an explicit LegacySourceStatus")
        if not self.name:
            raise ValueError("name is required")
        if not self.path:
            raise ValueError("path is required")
        if not self.source_commit:
            raise ValueError("source_commit is required")
        if not self.input_hash:
            raise ValueError("input_hash is required")
