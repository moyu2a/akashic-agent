from __future__ import annotations

from pathlib import Path

import pytest

from eval.agent_harness.compatibility import CompatibilityStatus
from eval.agent_harness.legacy import (
    ExecutionMode,
    IntegrationStatus,
    LegacyRunEnvelope,
    LegacySourceRecord,
    hash_input,
    load_source_registry,
    validate_source_registry,
    write_source_registry,
)


def _source(**overrides: object) -> LegacySourceRecord:
    values: dict[str, object] = {
        "source_name": "offline_trace",
        "source_path": "my_md/test_docs/eval_suite/offline_trace_eval.py",
        "source_commit": "df566c9",
        "last_modified": "2026-07-07",
        "compatibility_status": CompatibilityStatus.ADAPTER_REQUIRED,
        "integration_status": IntegrationStatus.NOT_STARTED,
        "execution_mode": ExecutionMode.OFFLINE_TRACE,
        "real_llm": None,
        "fake_provider": False,
        "main_gate_allowed": False,
        "report_kind": "offline_trace",
    }
    values.update(overrides)
    return LegacySourceRecord(**values)


def test_source_record_round_trips_explicit_status_and_provenance() -> None:
    record = _source()

    restored = LegacySourceRecord.from_dict(record.to_dict())

    assert restored == record
    assert restored.compatibility_status is CompatibilityStatus.ADAPTER_REQUIRED
    assert restored.integration_status is IntegrationStatus.NOT_STARTED
    assert restored.execution_mode is ExecutionMode.OFFLINE_TRACE


def test_main_gate_requires_adapter_and_admission() -> None:
    with pytest.raises(ValueError, match="MAIN_GATE_READY"):
        _source(
            integration_status=IntegrationStatus.MAIN_GATE_READY,
            main_gate_allowed=True,
        )

    with pytest.raises(ValueError, match="adapter_name"):
        _source(
            compatibility_status=CompatibilityStatus.MATCH,
            integration_status=IntegrationStatus.MAIN_GATE_READY,
            main_gate_allowed=True,
        )


def test_adapter_ready_is_distinct_from_direct_compatibility() -> None:
    record = _source(
        integration_status=IntegrationStatus.ADAPTER_PASS,
        adapter_ready=True,
        adapter_name="offline_trace",
    )

    restored = LegacySourceRecord.from_dict(record.to_dict())

    assert restored.adapter_ready is True
    assert restored.compatibility_status is CompatibilityStatus.ADAPTER_REQUIRED
    assert restored.integration_status is IntegrationStatus.ADAPTER_PASS
    assert restored.main_gate_allowed is False


def test_validated_adapter_required_source_can_enter_main_gate() -> None:
    record = _source(
        source_name="live_eval_runner",
        source_path="my_md/test_docs/eval_suite/live_eval_runner.py",
        source_commit="df566c9",
        integration_status=IntegrationStatus.MAIN_GATE_READY,
        execution_mode=ExecutionMode.IPC_LIVE,
        real_llm=True,
        adapter_ready=True,
        adapter_name="ipc_live",
        main_gate_allowed=True,
    )

    assert record.main_gate_allowed is True
    assert record.compatibility_status is CompatibilityStatus.ADAPTER_REQUIRED


def test_main_gate_rejects_unvalidated_adapter_required_source() -> None:
    with pytest.raises(ValueError, match="adapter_ready"):
        _source(
            integration_status=IntegrationStatus.MAIN_GATE_READY,
            adapter_name="ipc_live",
            main_gate_allowed=True,
        )


def test_main_gate_rejects_report_only_execution_mode() -> None:
    with pytest.raises(ValueError, match="approved live adapter"):
        _source(
            integration_status=IntegrationStatus.MAIN_GATE_READY,
            adapter_ready=True,
            adapter_name="offline_trace",
            real_llm=True,
            main_gate_allowed=True,
        )


def test_adapter_ready_rejects_stale_compatibility() -> None:
    with pytest.raises(ValueError, match="compatibility"):
        _source(
            compatibility_status=CompatibilityStatus.STALE,
            integration_status=IntegrationStatus.ADAPTER_PASS,
            adapter_ready=True,
            adapter_name="offline_trace",
        )


def test_main_gate_rejects_untrusted_source_provenance() -> None:
    with pytest.raises(ValueError, match="approved live adapter"):
        _source(
            source_name="live_eval_runner",
            source_path="/tmp/untrusted.py",
            source_commit="forged",
            integration_status=IntegrationStatus.MAIN_GATE_READY,
            execution_mode=ExecutionMode.IPC_LIVE,
            real_llm=True,
            adapter_ready=True,
            adapter_name="ipc_live",
            main_gate_allowed=True,
        )


def test_main_gate_requires_real_provider() -> None:
    with pytest.raises(ValueError, match="real provider"):
        _source(
            source_name="live_eval_runner",
            source_path="my_md/test_docs/eval_suite/live_eval_runner.py",
            source_commit="df566c9",
            integration_status=IntegrationStatus.MAIN_GATE_READY,
            execution_mode=ExecutionMode.IPC_LIVE,
            real_llm=False,
            adapter_ready=True,
            adapter_name="ipc_live",
            main_gate_allowed=True,
        )


def test_from_dict_rejects_non_boolean_gate_flags() -> None:
    payload = _source().to_dict()
    payload["adapter_ready"] = "false"

    with pytest.raises(ValueError, match="adapter_ready must be a boolean"):
        LegacySourceRecord.from_dict(payload)


def test_new_gate_field_preserves_old_positional_constructor_order() -> None:
    record = LegacySourceRecord(
        "offline_trace",
        "offline.py",
        "abc123",
        "2026-08-06",
        CompatibilityStatus.ADAPTER_REQUIRED,
        IntegrationStatus.NOT_STARTED,
        ExecutionMode.OFFLINE_TRACE,
        None,
        False,
        False,
        "offline_trace",
        "offline",
        "legacy positional record",
    )

    assert record.adapter_name == "offline_trace"
    assert record.report_kind == "offline"
    assert record.notes == "legacy positional record"
    assert record.adapter_ready is False


def test_source_registry_rejects_declared_entry_count_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "compatibility-baseline.json"
    write_source_registry(path, [_source()], generated_at="2026-08-06")
    payload = path.read_text(encoding="utf-8").replace(
        '"entry_count": 1', '"entry_count": 2'
    )
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="entry_count"):
        load_source_registry(path)


def test_source_registry_rejects_duplicate_sources() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_source_registry((_source(), _source()))


def test_source_registry_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "compatibility-baseline.json"
    write_source_registry(path, [_source()], generated_at="2026-08-06")

    loaded = load_source_registry(path)

    assert loaded == (_source(),)


def test_hash_input_is_deterministic() -> None:
    assert hash_input({"b": 2, "a": 1}) == hash_input({"a": 1, "b": 2})


def test_envelope_keeps_missing_metrics_unavailable_not_zero() -> None:
    with pytest.raises(ValueError, match="cannot be represented as zero"):
        LegacyRunEnvelope(
            source_name="offline_trace",
            source_version="df566c9",
            source_commit="df566c9",
            source_run_id="run-1",
            case_id="case-1",
            repeat_index=0,
            input_hash=hash_input({"case": "case-1"}),
            raw_status="pass",
            raw_report_ref=None,
            trace_ref=None,
            execution_mode=ExecutionMode.OFFLINE_TRACE,
            real_llm=None,
            fake_provider=False,
            metric_provenance={"prompt_tokens": "unavailable"},
            metrics={"prompt_tokens": 0},
        )
