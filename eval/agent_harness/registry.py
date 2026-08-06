from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .legacy import IntegrationStatus, LegacySourceRecord


class AuditableAdapter(Protocol):
    def audit(self) -> LegacySourceRecord: ...


@dataclass(frozen=True)
class AdapterRegistryEntry:
    adapter_name: str
    source: LegacySourceRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            **self.source.to_dict(),
        }


class LegacyAdapterRegistry:
    def __init__(self, adapters: Iterable[AuditableAdapter] = ()) -> None:
        self._entries: dict[str, AdapterRegistryEntry] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: AuditableAdapter) -> AdapterRegistryEntry:
        source = adapter.audit()
        adapter_name = source.adapter_name or source.source_name
        if adapter_name in self._entries:
            raise ValueError(f"duplicate adapter_name: {adapter_name}")
        entry = AdapterRegistryEntry(adapter_name=adapter_name, source=source)
        self._entries[adapter_name] = entry
        return entry

    def entries(self) -> tuple[AdapterRegistryEntry, ...]:
        return tuple(self._entries.values())

    def adapter_ready(self) -> tuple[AdapterRegistryEntry, ...]:
        return tuple(
            entry for entry in self._entries.values() if entry.source.adapter_ready
        )

    def main_gate_ready(self) -> tuple[AdapterRegistryEntry, ...]:
        return tuple(
            entry
            for entry in self._entries.values()
            if entry.source.adapter_ready
            and entry.source.is_main_gate_executor()
            and entry.source.integration_status is IntegrationStatus.MAIN_GATE_READY
            and entry.source.main_gate_allowed
        )

    def require_g10a_candidate(self, adapter_name: str) -> AdapterRegistryEntry:
        entry = self._entries.get(adapter_name)
        if entry is None or not _is_g10a_candidate(entry):
            raise PermissionError(
                f"adapter is not authorized as a G10-A candidate: {adapter_name}"
            )
        return entry

    def require_main_gate_ready(self, adapter_name: str) -> AdapterRegistryEntry:
        for entry in self.main_gate_ready():
            if entry.adapter_name == adapter_name:
                return entry
        raise PermissionError(
            f"adapter is not authorized for the main gate: {adapter_name}"
        )

    def to_dict(self) -> dict[str, object]:
        entries = [entry.to_dict() for entry in self.entries()]
        return {
            "entry_count": len(entries),
            "adapter_ready_count": len(self.adapter_ready()),
            "main_gate_ready_count": len(self.main_gate_ready()),
            "entries": entries,
        }


def _is_g10a_candidate(entry: AdapterRegistryEntry) -> bool:
    source = entry.source
    return (
        source.integration_status is IntegrationStatus.ADAPTER_PASS
        and source.adapter_ready is False
        and source.main_gate_allowed is False
        and source.fake_provider is False
        and source.real_llm is not False
        and source.is_main_gate_executor()
    )
