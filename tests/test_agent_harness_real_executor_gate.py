from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from eval.agent_harness.compatibility import CompatibilityStatus
from eval.agent_harness.legacy import (
    ExecutionMode,
    IntegrationStatus,
    LegacySourceRecord,
)
from eval.agent_harness.real_executor import G10ARealExecutorGate
from eval.agent_harness.registry import LegacyAdapterRegistry


class Auditable:
    def __init__(self, source: LegacySourceRecord) -> None:
        self.source = source

    def audit(self) -> LegacySourceRecord:
        return self.source


def _source(
    *,
    source_name: str = "live_eval_runner",
    source_path: str = "my_md/test_docs/eval_suite/live_eval_runner.py",
    source_commit: str = "df566c9",
    execution_mode: ExecutionMode | str = ExecutionMode.IPC_LIVE,
    real_llm: bool | None = None,
    fake_provider: bool = False,
    main_gate_allowed: bool = False,
    adapter_ready: bool = False,
    adapter_name: str = "ipc_live",
    integration_status: IntegrationStatus = IntegrationStatus.ADAPTER_PASS,
) -> LegacySourceRecord:
    return LegacySourceRecord(
        source_name=source_name,
        source_path=source_path,
        source_commit=source_commit,
        last_modified="2026-08-06",
        compatibility_status=CompatibilityStatus.ADAPTER_REQUIRED,
        integration_status=integration_status,
        execution_mode=execution_mode,
        real_llm=real_llm,
        fake_provider=fake_provider,
        main_gate_allowed=main_gate_allowed,
        adapter_ready=adapter_ready,
        adapter_name=adapter_name,
    )


def test_g10a_candidate_allows_approved_adapter_pass_without_main_gate() -> None:
    registry = LegacyAdapterRegistry([Auditable(_source())])

    entry = registry.require_g10a_candidate("ipc_live")

    assert entry.adapter_name == "ipc_live"
    assert entry.source.integration_status is IntegrationStatus.ADAPTER_PASS
    assert entry.source.adapter_ready is False
    assert entry.source.main_gate_allowed is False
    with pytest.raises(PermissionError, match="main gate"):
        registry.require_main_gate_ready("ipc_live")


@pytest.mark.parametrize(
    "source",
    [
        _source(source_name="offline_trace_eval", source_path="offline.py"),
        _source(execution_mode=ExecutionMode.OFFLINE_TRACE, adapter_name="offline"),
        _source(real_llm=False),
        _source(fake_provider=True),
        _source(source_commit="wrong"),
        _source(source_path="wrong/path.py"),
    ],
)
def test_g10a_candidate_rejects_unapproved_or_non_real_sources(
    source: LegacySourceRecord,
) -> None:
    registry = LegacyAdapterRegistry([Auditable(source)])

    with pytest.raises(PermissionError, match="G10-A candidate"):
        registry.require_g10a_candidate(source.adapter_name or source.source_name)


def test_real_executor_rejects_unauthorized_adapter_name(tmp_path: Path) -> None:
    gate = G10ARealExecutorGate(LegacyAdapterRegistry())

    with pytest.raises(PermissionError, match="G10-A candidate"):
        gate.prepare(
            adapter_name="ipc_live",
            governance_profile="budget_limited",
            environment_kind="ipc_live",
            workspace=tmp_path,
            case_id="case-1",
        )


def test_real_executor_rejects_fake_environment_label(tmp_path: Path) -> None:
    gate = G10ARealExecutorGate(LegacyAdapterRegistry([Auditable(_source())]))

    with pytest.raises(ValueError, match="fake"):
        gate.prepare(
            adapter_name="ipc_live",
            governance_profile="budget_limited",
            environment_kind="fake",
            workspace=tmp_path,
            case_id="case-1",
        )


def test_real_executor_attaches_profile_metadata_before_execution(
    tmp_path: Path,
) -> None:
    gate = G10ARealExecutorGate(LegacyAdapterRegistry([Auditable(_source())]))

    authorization = gate.prepare(
        adapter_name="ipc_live",
        governance_profile="budget_limited",
        environment_kind="ipc_live",
        workspace=tmp_path,
        case_id="case-1",
    )

    assert authorization.entry.adapter_name == "ipc_live"
    assert authorization.runtime_profile.governance_profile == "budget_limited"
    assert authorization.workspace == tmp_path
    assert authorization.manifest_metadata["case_id"] == "case-1"
    assert authorization.manifest_metadata["environment_kind"] == "ipc_live"
    assert authorization.manifest_metadata["adapter_name"] == "ipc_live"
    assert authorization.manifest_metadata["runtime_profile"] == asdict(
        authorization.runtime_profile
    )
