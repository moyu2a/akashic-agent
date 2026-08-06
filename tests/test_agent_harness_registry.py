from __future__ import annotations

from eval.agent_harness.compatibility import CompatibilityStatus
from eval.agent_harness.legacy import IntegrationStatus, LegacySourceRecord
import pytest

from eval.agent_harness.legacy_adapters.live_ipc import IpcLiveAdapter
from eval.agent_harness.legacy_adapters.memory import MemoryOfflineAdapter
from eval.agent_harness.registry import LegacyAdapterRegistry


def test_registry_keeps_adapter_progress_separate_from_main_gate() -> None:
    registry = LegacyAdapterRegistry(
        [IpcLiveAdapter(source_path=__import__("pathlib").Path("legacy.py"))]
    )

    payload = registry.to_dict()

    assert payload["entry_count"] == 1
    assert payload["adapter_ready_count"] == 0
    assert payload["main_gate_ready_count"] == 0
    assert payload["entries"][0]["integration_status"] == "ADAPTER_PASS"


def test_registry_admits_validated_adapter_required_source() -> None:
    source = LegacySourceRecord(
        source_name="live_eval_runner",
        source_path="my_md/test_docs/eval_suite/live_eval_runner.py",
        source_commit="df566c9",
        last_modified="2026-08-06",
        compatibility_status=CompatibilityStatus.ADAPTER_REQUIRED,
        integration_status=IntegrationStatus.MAIN_GATE_READY,
        execution_mode="ipc_live",
        real_llm=True,
        fake_provider=False,
        main_gate_allowed=True,
        adapter_ready=True,
        adapter_name="ipc_live",
    )

    class Auditable:
        def audit(self) -> LegacySourceRecord:
            return source

    registry = LegacyAdapterRegistry([Auditable()])
    payload = registry.to_dict()

    assert payload["adapter_ready_count"] == 1
    assert payload["main_gate_ready_count"] == 1
    assert payload["entries"][0]["adapter_ready"] is True
    assert registry.require_main_gate_ready("ipc_live") == registry.entries()[0]


def test_registry_excludes_report_only_source_even_with_ready_flags() -> None:
    source = LegacySourceRecord(
        source_name="offline_trace",
        source_path="offline.py",
        source_commit="abc123",
        last_modified="2026-08-06",
        compatibility_status=CompatibilityStatus.ADAPTER_REQUIRED,
        integration_status=IntegrationStatus.ADAPTER_PASS,
        execution_mode="offline_trace",
        real_llm=None,
        fake_provider=False,
        main_gate_allowed=False,
        adapter_ready=True,
        adapter_name="offline_trace",
    )

    class Auditable:
        def audit(self) -> LegacySourceRecord:
            return source

    registry = LegacyAdapterRegistry([Auditable()])

    assert registry.adapter_ready()
    assert registry.main_gate_ready() == ()
    with pytest.raises(PermissionError, match="not authorized"):
        registry.require_main_gate_ready("offline_trace")


def test_registry_rejects_duplicate_adapter_names() -> None:
    adapter = MemoryOfflineAdapter()
    registry = LegacyAdapterRegistry([adapter])

    with pytest.raises(ValueError, match="duplicate"):
        registry.register(adapter)
