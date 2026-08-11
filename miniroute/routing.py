from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from miniroute.v1_schema import INTENTS, RISK_LEVELS, TOOL_SCOPES, RouteLabel


OPERATIONS: tuple[str, ...] = (
    "none",
    "query",
    "update",
    "read",
    "write",
    "execute",
    "plan",
)

REQUEST_MODES: tuple[str, ...] = ("single", "compound")

_INTENT_OPERATIONS: dict[str, str] = {
    "chat": "none",
    "memory_query": "query",
    "profile_update": "update",
    "task_plan": "plan",
    "content_save": "write",
    "file_read": "read",
    "tool_execution": "execute",
    "status_query": "query",
}

_TOOL_SCOPE_ORDER = {scope: index for index, scope in enumerate(TOOL_SCOPES)}


@dataclass(frozen=True, slots=True)
class IntentDecision:
    """Internal MiniRoute output before tool attributes are completed."""

    intent: str
    operation: str
    request_mode: str = "single"

    def __post_init__(self) -> None:
        if self.intent not in INTENTS:
            raise ValueError(f"unknown intent: {self.intent}")
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {self.operation}")
        if self.request_mode not in REQUEST_MODES:
            raise ValueError(f"unknown request mode: {self.request_mode}")

    def to_dict(self) -> dict[str, str]:
        return {
            "intent": self.intent,
            "operation": self.operation,
            "request_mode": self.request_mode,
        }


@dataclass(frozen=True, slots=True)
class RoutePropertyDecision:
    """Internal MiniRoute output for memory, scope, and risk attributes."""

    need_memory: bool
    tool_scope: list[str]
    risk_level: str

    def __post_init__(self) -> None:
        if not isinstance(self.need_memory, bool):
            raise ValueError("need_memory must be bool")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"unknown risk level: {self.risk_level}")

    def to_dict(self) -> dict[str, object]:
        return {
            "need_memory": self.need_memory,
            "tool_scope": normalize_tool_scopes(self.tool_scope),
            "risk_level": self.risk_level,
        }


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    """Runtime inventory of available coarse tool domains.

    The registry is owned by MnemoAgent. MiniRoute does not select concrete
    tools; it only proposes one or more coarse domains.
    """

    available_scopes: frozenset[str]

    @classmethod
    def from_scopes(cls, scopes: Iterable[str]) -> ToolRegistry:
        normalized = normalize_tool_scopes(scopes)
        if normalized == ["none"]:
            return cls(frozenset())
        return cls(frozenset(scope for scope in normalized if scope != "unknown_tools"))

    def has_scope(self, scope: str) -> bool:
        return scope in self.available_scopes


def operation_for_intent(intent: str) -> str:
    try:
        return _INTENT_OPERATIONS[intent]
    except KeyError as exc:
        raise ValueError(f"unknown intent: {intent}") from exc


def normalize_tool_scopes(scopes: Iterable[str]) -> list[str]:
    values = list(scopes)
    if not values:
        return ["none"]

    for scope in values:
        if scope not in TOOL_SCOPES:
            raise ValueError(f"unknown tool scope: {scope}")

    deduplicated = list(dict.fromkeys(values))
    if len(deduplicated) > 1 and "none" in deduplicated:
        deduplicated.remove("none")

    return sorted(deduplicated, key=_TOOL_SCOPE_ORDER.__getitem__)


def reconcile_tool_scopes(
    scopes: Iterable[str],
    registry: ToolRegistry | None,
) -> tuple[list[str], tuple[str, ...]]:
    """Reconcile coarse model scopes with the runtime tool registry.

    A scope that is not available is retained as ``unknown_tools``. Existing
    ``unknown_tools`` is never guessed into ``shell_tools`` or another domain.
    """

    normalized = normalize_tool_scopes(scopes)
    if normalized == ["none"] or registry is None:
        return normalized, ()

    resolved: list[str] = []
    unavailable: list[str] = []
    for scope in normalized:
        if scope == "unknown_tools":
            resolved.append(scope)
        elif registry.has_scope(scope):
            resolved.append(scope)
        else:
            unavailable.append(scope)
            resolved.append("unknown_tools")

    return normalize_tool_scopes(resolved), tuple(unavailable)


def build_route_label(
    intent_decision: IntentDecision,
    property_decision: RoutePropertyDecision,
    registry: ToolRegistry | None = None,
) -> RouteLabel:
    scopes, _ = reconcile_tool_scopes(property_decision.tool_scope, registry)
    label = RouteLabel(
        intent=intent_decision.intent,
        need_memory=property_decision.need_memory,
        need_tools=scopes != ["none"],
        tool_scope=scopes,
        risk_level=property_decision.risk_level,
    )
    errors = validate_route_label(label)
    if errors:
        raise ValueError("; ".join(errors))
    return label


def route_label_from_payloads(
    intent_payload: Mapping[str, object],
    property_payload: Mapping[str, object],
    registry: ToolRegistry | None = None,
) -> RouteLabel:
    """Compose the public five-field label from two model JSON payloads."""

    try:
        intent_decision = IntentDecision(
            intent=str(intent_payload["intent"]),
            operation=str(intent_payload["operation"]),
            request_mode=str(intent_payload.get("request_mode", "single")),
        )
        tool_scope = property_payload["tool_scope"]
        if not isinstance(tool_scope, list):
            raise ValueError("tool_scope must be a list")
        property_decision = RoutePropertyDecision(
            need_memory=property_payload["need_memory"],  # type: ignore[arg-type]
            tool_scope=tool_scope,
            risk_level=str(property_payload["risk_level"]),
        )
    except KeyError as exc:
        raise ValueError(f"missing route field: {exc.args[0]}") from exc

    return build_route_label(intent_decision, property_decision, registry)


def validate_route_label(label: RouteLabel) -> list[str]:
    errors: list[str] = []
    try:
        scopes = normalize_tool_scopes(label.tool_scope)
    except ValueError as exc:
        return [str(exc)]

    if label.need_tools != (scopes != ["none"]):
        errors.append("need_tools must match whether tool_scope is none")
    if "unknown_tools" in scopes and not label.need_tools:
        errors.append("unknown_tools requires need_tools=true")
    if not label.need_tools and label.risk_level != "none":
        errors.append("need_tools=false requires risk_level=none")
    return errors
