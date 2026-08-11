from __future__ import annotations

from dataclasses import asdict


def test_legacy_adapter_contract_requires_case_result_and_event_converters() -> None:
    from eval.agent_harness.compatibility import (
        LegacyAdapterContract,
        LegacySourceStatus,
        assert_legacy_adapter_contract,
    )
    from eval.agent_harness.protocol import EpisodeResult, LegacySourceRecord, TaskSpec

    class MinimalLegacyAdapter:
        def load_cases(self) -> tuple[TaskSpec, ...]:
            return (
                TaskSpec(
                    case_id="legacy-case-1",
                    category="memory",
                    steps=({"role": "user", "text": "What changed?"},),
                    expected_outcome={"reply": "answer"},
                ),
            )

        def convert_result(self, raw_result: dict[str, object]) -> EpisodeResult:
            return EpisodeResult(
                episode_id=str(raw_result["case_id"]),
                status="PASS",
                outcome_passed=True,
                metrics={
                    "prompt_tokens": raw_result.get("prompt_tokens"),
                    "completion_tokens": raw_result.get("completion_tokens"),
                    "total_tokens": raw_result.get("total_tokens"),
                    "latency_ms": raw_result.get("latency_ms"),
                },
            )

        def convert_events(
            self, raw_result: dict[str, object]
        ) -> tuple[dict[str, object], ...]:
            return (
                {
                    "event_type": "legacy_result_loaded",
                    "component": "legacy_adapter",
                    "payload": {"case_id": raw_result["case_id"]},
                },
            )

        def source_record(self) -> LegacySourceRecord:
            return LegacySourceRecord(
                name="minimal_legacy_adapter",
                path="legacy/minimal.jsonl",
                source_commit="3333333333333333333333333333333333333333",
                input_hash="sha256:" + "1" * 64,
                status=LegacySourceStatus.ADAPTER_REQUIRED,
                provenance={"adapter": "minimal"},
                historical=True,
                shadow=True,
            )

    adapter = MinimalLegacyAdapter()

    assert isinstance(adapter, LegacyAdapterContract)
    assert_legacy_adapter_contract(adapter)
    assert [case.case_id for case in adapter.load_cases()] == ["legacy-case-1"]

    result = adapter.convert_result(
        {
            "case_id": "legacy-case-1",
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "latency_ms": None,
        }
    )

    assert result.metrics == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "latency_ms": None,
    }
    assert adapter.convert_events({"case_id": "legacy-case-1"})[0]["event_type"]
    assert asdict(adapter.source_record())["shadow"] is True


def test_adapter_contract_rejects_partial_legacy_adapter() -> None:
    from eval.agent_harness.compatibility import assert_legacy_adapter_contract

    class MissingEventConverter:
        def load_cases(self) -> tuple[object, ...]:
            return ()

        def convert_result(self, raw_result: dict[str, object]) -> object:
            return raw_result

    try:
        assert_legacy_adapter_contract(MissingEventConverter())
    except TypeError as exc:
        assert "convert_events" in str(exc)
    else:
        raise AssertionError("partial legacy adapters must fail contract validation")
