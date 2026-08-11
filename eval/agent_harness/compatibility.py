from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from eval.agent_harness.protocol import EpisodeResult, LegacySourceRecord, TaskSpec


class LegacySourceStatus(Enum):
    MATCH = "MATCH"
    STALE = "STALE"
    ADAPTER_REQUIRED = "ADAPTER_REQUIRED"


@runtime_checkable
class LegacyAdapterContract(Protocol):
    def load_cases(self) -> tuple[TaskSpec, ...]:
        ...

    def convert_result(self, raw_result: dict[str, object]) -> EpisodeResult:
        ...

    def convert_events(
        self, raw_result: dict[str, object]
    ) -> tuple[dict[str, object], ...]:
        ...

    def source_record(self) -> LegacySourceRecord:
        ...


class LegacySourceRegistry:
    def __init__(self, *, sources: tuple[LegacySourceRecord, ...]) -> None:
        records: dict[str, LegacySourceRecord] = {}
        for source in sources:
            if source.name in records:
                raise ValueError(f"duplicated legacy source: {source.name}")
            records[source.name] = source
        self._sources = records

    def require(self, name: str) -> LegacySourceRecord:
        try:
            return self._sources[name]
        except KeyError as exc:
            raise KeyError(f"legacy source not registered: {name}") from exc

    def summary(self) -> dict[str, object]:
        statuses: dict[str, int] = {}
        for source in self._sources.values():
            statuses[source.status.name] = statuses.get(source.status.name, 0) + 1
        return {
            "count": len(self._sources),
            "statuses": statuses,
            "main_gate_ready": all(
                source.status is LegacySourceStatus.MATCH
                and not source.historical
                and not source.shadow
                for source in self._sources.values()
            ),
        }


def assert_legacy_adapter_contract(adapter: object) -> None:
    required = (
        "load_cases",
        "convert_result",
        "convert_events",
        "source_record",
    )
    missing = [name for name in required if not callable(getattr(adapter, name, None))]
    if missing:
        raise TypeError(
            "legacy adapter missing required methods: " + ", ".join(missing)
        )
