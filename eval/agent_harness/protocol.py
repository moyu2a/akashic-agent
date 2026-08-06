from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

_ROUTER_KEYS = {
    "intent",
    "need_memory",
    "need_tools",
    "tool_scope",
    "risk_level",
}


def _copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value[key] for key in value}


def _validate_router_decision(value: Mapping[str, Any] | None) -> None:
    if value is None:
        return
    keys = set(value)
    extra = keys - _ROUTER_KEYS
    missing = _ROUTER_KEYS - keys
    if extra:
        raise ValueError(
            "router_decision has unsupported fields: "
            + ", ".join(sorted(str(item) for item in extra))
        )
    if missing:
        raise ValueError(
            "router_decision is missing fields: "
            + ", ".join(sorted(str(item) for item in missing))
        )
    if not isinstance(value["intent"], str):
        raise ValueError("router_decision.intent must be str")
    if not isinstance(value["need_memory"], bool):
        raise ValueError("router_decision.need_memory must be bool")
    if not isinstance(value["need_tools"], bool):
        raise ValueError("router_decision.need_tools must be bool")
    if not isinstance(value["tool_scope"], list) or not all(
        isinstance(item, str) for item in value["tool_scope"]
    ):
        raise ValueError("router_decision.tool_scope must be list[str]")
    if not isinstance(value["risk_level"], str):
        raise ValueError("router_decision.risk_level must be str")


@dataclass(frozen=True)
class TaskSpec:
    case_id: str
    category: str
    steps: tuple[dict[str, str], ...] = ()
    router_decision: dict[str, Any] | None = None
    router_parse_ok: bool | None = None
    router_parse_errors: tuple[str, ...] = ()
    expected_outcome: dict[str, Any] = field(default_factory=dict)
    expected_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    expected_policy_actions: tuple[str, ...] = ()
    risk_level: str = "none"
    grader_names: tuple[str, ...] = ()
    repeat_count: int = 1

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if not self.category.strip():
            raise ValueError("category must not be empty")
        if self.repeat_count < 1:
            raise ValueError("repeat_count must be at least 1")
        _validate_router_decision(self.router_decision)
        if self.router_parse_ok is False and not self.router_parse_errors:
            raise ValueError(
                "router_parse_errors is required when router_parse_ok is false"
            )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TaskSpec:
        router = value.get("router_decision")
        return cls(
            case_id=str(value["case_id"]),
            category=str(value["category"]),
            steps=tuple(dict(step) for step in value.get("steps", ())),
            router_decision=(
                _copy_mapping(router) if isinstance(router, Mapping) else None
            ),
            router_parse_ok=value.get("router_parse_ok"),
            router_parse_errors=tuple(
                str(item) for item in value.get("router_parse_errors", ())
            ),
            expected_outcome=dict(value.get("expected_outcome", {})),
            expected_tools=tuple(str(item) for item in value.get("expected_tools", ())),
            forbidden_tools=tuple(
                str(item) for item in value.get("forbidden_tools", ())
            ),
            expected_policy_actions=tuple(
                str(item) for item in value.get("expected_policy_actions", ())
            ),
            risk_level=str(value.get("risk_level", "none")),
            grader_names=tuple(str(item) for item in value.get("grader_names", ())),
            repeat_count=int(value.get("repeat_count", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    git_sha: str
    dataset_version: str
    dataset_hash: str
    model: str
    provider: str
    config_hash: str
    governance_profile: str
    environment_kind: str
    seed: int
    repeat_index: int
    runner_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EpisodeResult:
    episode_id: str
    status: str
    outcome_passed: bool
    failures: tuple[str, ...] = ()
    final_reply: str = ""
    events: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
