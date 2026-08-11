from __future__ import annotations

from eval.agent_harness.compatibility import (
    LegacyAdapterContract,
    LegacySourceRegistry,
    LegacySourceStatus,
    assert_legacy_adapter_contract,
)
from eval.agent_harness.protocol import EpisodeResult, LegacySourceRecord, TaskSpec

__all__ = [
    "EpisodeResult",
    "LegacyAdapterContract",
    "LegacySourceRecord",
    "LegacySourceRegistry",
    "LegacySourceStatus",
    "TaskSpec",
    "assert_legacy_adapter_contract",
]
