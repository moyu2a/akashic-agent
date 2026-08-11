from __future__ import annotations

from typing import Any, Literal

from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry


class _Tool(Tool):
    name = "probe"
    description = "probe tool"
    parameters = {"type": "object", "properties": {}}
    capabilities = frozenset({"probe.read"})

    async def execute(self, **kwargs: Any) -> str:
        return "ok"


class _RecoveryProbe:
    async def probe(
        self,
        *,
        tool_name: str,
        recovery_ref: str,
        arguments: dict[str, Any],
        metadata: dict[str, object],
    ) -> Literal["succeeded", "failed", "unknown"]:
        return "unknown"


def test_read_only_tool_defaults_to_idempotent_without_side_effect() -> None:
    registry = ToolRegistry()
    registry.register(_Tool(), risk="read-only")

    metadata = registry.get_invocation_metadata("probe")

    assert metadata["idempotent"] is True
    assert metadata["side_effect"] is False
    assert metadata["pollable"] is False
    assert metadata["recovery_ref_strategy"] == "tool_call_id"


def test_write_tool_defaults_to_side_effect_and_not_idempotent() -> None:
    registry = ToolRegistry()
    registry.register(_Tool(), risk="write")

    metadata = registry.get_invocation_metadata("probe")

    assert metadata["idempotent"] is False
    assert metadata["side_effect"] is True


def test_explicit_recovery_metadata_overrides_risk_defaults() -> None:
    registry = ToolRegistry()
    registry.register(
        _Tool(),
        risk="write",
        idempotent=True,
        side_effect=False,
        pollable=True,
        recovery_ref="remote-job",
        recovery_ref_strategy="external_request_id",
    )

    metadata = registry.get_invocation_metadata("probe")

    assert metadata["idempotent"] is True
    assert metadata["side_effect"] is False
    assert metadata["pollable"] is True
    assert metadata["recovery_ref"] == "remote-job"
    assert metadata["recovery_ref_strategy"] == "external_request_id"


def test_recovery_probe_can_be_registered_and_queried() -> None:
    registry = ToolRegistry()
    probe = _RecoveryProbe()
    registry.register(_Tool(), risk="read-only", pollable=True)

    assert registry.get_recovery_probe("probe") is None
    registry.register_recovery_probe("probe", probe)

    assert registry.get_recovery_probe("probe") is probe
