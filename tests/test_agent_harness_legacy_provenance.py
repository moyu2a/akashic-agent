from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.agent_harness.legacy import (
    ExecutionMode,
    IntegrationStatus,
    LegacyRunnerAdapter,
    LegacySourceRecord,
)
from eval.agent_harness.protocol import EpisodeResult, RunManifest, TaskSpec


@dataclass
class _Adapter:
    source: LegacySourceRecord

    def audit(self) -> LegacySourceRecord:
        return self.source

    def load_cases(self, source: Path) -> list[TaskSpec]:
        return [TaskSpec(case_id=source.stem, category="legacy")]

    def convert_result(
        self,
        raw_result: object,
        *,
        task: TaskSpec,
        manifest: RunManifest,
    ) -> EpisodeResult:
        return EpisodeResult(
            episode_id=task.case_id,
            status="PASS",
            outcome_passed=True,
            metrics={"source_run_id": manifest.run_id},
        )

    def convert_events(
        self,
        raw_result: object,
    ) -> tuple[dict[str, object], ...]:
        return ({"event_type": "episode_finished", "payload": {}},)


def test_legacy_adapter_protocol_contract_can_be_checked() -> None:
    source = LegacySourceRecord(
        source_name="fixture",
        source_path="tests/fixtures/legacy.json",
        source_commit="abc123",
        last_modified="2026-08-06",
        compatibility_status="ADAPTER_REQUIRED",
        integration_status=IntegrationStatus.CONTRACT_PASS,
        execution_mode=ExecutionMode.OFFLINE_TRACE,
        real_llm=False,
        fake_provider=False,
        main_gate_allowed=False,
    )
    adapter = _Adapter(source)

    assert isinstance(adapter, LegacyRunnerAdapter)
    assert adapter.audit().source_name == "fixture"
    assert adapter.load_cases(Path("legacy.json"))[0].case_id == "legacy"
