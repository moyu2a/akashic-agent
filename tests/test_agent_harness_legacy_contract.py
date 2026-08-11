from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pytest


def test_legacy_source_registry_requires_explicit_source_status() -> None:
    from eval.agent_harness.compatibility import (
        LegacySourceRegistry,
        LegacySourceStatus,
    )
    from eval.agent_harness.protocol import LegacySourceRecord

    registry = LegacySourceRegistry(
        sources=(
            LegacySourceRecord(
                name="memory_eval_runner",
                path="eval/personamem/run.py",
                source_commit="0123456789abcdef0123456789abcdef01234567",
                input_hash="sha256:" + "a" * 64,
                status=LegacySourceStatus.ADAPTER_REQUIRED,
                provenance={"owner": "legacy-personamem", "phase": "G0"},
                historical=True,
                shadow=True,
                reason="legacy runner needs harness adapter before reuse",
            ),
        )
    )

    record = registry.require("memory_eval_runner")

    assert record.status is LegacySourceStatus.ADAPTER_REQUIRED
    assert registry.summary()["statuses"] == {"ADAPTER_REQUIRED": 1}
    assert registry.summary()["main_gate_ready"] is False


def test_legacy_source_record_rejects_implicit_or_unknown_status() -> None:
    from eval.agent_harness.protocol import LegacySourceRecord

    with pytest.raises(ValueError, match="status"):
        LegacySourceRecord(
            name="ambiguous_legacy_source",
            path="scripts/run_memory_eval.py",
            source_commit="0123456789abcdef0123456789abcdef01234567",
            input_hash="sha256:" + "b" * 64,
            status="",
        )

    with pytest.raises(ValueError, match="status"):
        LegacySourceRecord(
            name="unknown_legacy_source",
            path="scripts/run_memory_eval.py",
            source_commit="0123456789abcdef0123456789abcdef01234567",
            input_hash="sha256:" + "c" * 64,
            status="REUSE_MAYBE",
        )


def test_legacy_source_record_preserves_provenance_and_shadow_flags() -> None:
    from eval.agent_harness.compatibility import LegacySourceStatus
    from eval.agent_harness.protocol import LegacySourceRecord

    record = LegacySourceRecord(
        name="quantitative_uplift_csv",
        path="memory2/eval_quantitative_uplift.py",
        source_commit="fedcba9876543210fedcba9876543210fedcba98",
        input_hash="sha256:" + "d" * 64,
        status=LegacySourceStatus.STALE,
        provenance={
            "dataset": "memory_quantitative_uplift",
            "profile": "chain_version_provenance",
            "source_case_id": "case-017",
        },
        historical=True,
        shadow=True,
        reason="historical shadow measurement, not a main-gate result",
    )

    payload = asdict(record)

    assert payload["source_commit"] == "fedcba9876543210fedcba9876543210fedcba98"
    assert payload["input_hash"] == "sha256:" + "d" * 64
    assert payload["provenance"] == {
        "dataset": "memory_quantitative_uplift",
        "profile": "chain_version_provenance",
        "source_case_id": "case-017",
    }
    assert payload["historical"] is True
    assert payload["shadow"] is True


def test_legacy_source_record_keeps_missing_tokens_and_latency_as_none() -> None:
    from eval.agent_harness.compatibility import LegacySourceStatus
    from eval.agent_harness.protocol import LegacySourceRecord

    record = LegacySourceRecord(
        name="legacy_jsonl_without_usage",
        path="reports/legacy.jsonl",
        source_commit="1111111111111111111111111111111111111111",
        input_hash="sha256:" + "e" * 64,
        status=LegacySourceStatus.MATCH,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        latency_ms=None,
    )

    payload = asdict(record)

    assert payload["prompt_tokens"] is None
    assert payload["completion_tokens"] is None
    assert payload["total_tokens"] is None
    assert payload["latency_ms"] is None
    assert 0 not in (
        payload["prompt_tokens"],
        payload["completion_tokens"],
        payload["total_tokens"],
        payload["latency_ms"],
    )


def test_legacy_source_registry_fails_on_duplicate_names() -> None:
    from eval.agent_harness.compatibility import (
        LegacySourceRegistry,
        LegacySourceStatus,
    )
    from eval.agent_harness.protocol import LegacySourceRecord

    kwargs: dict[str, Any] = {
        "name": "duplicated",
        "path": "reports/legacy.jsonl",
        "source_commit": "2222222222222222222222222222222222222222",
        "input_hash": "sha256:" + "f" * 64,
        "status": LegacySourceStatus.MATCH,
    }

    with pytest.raises(ValueError, match="duplicated"):
        LegacySourceRegistry(
            sources=(
                LegacySourceRecord(**kwargs),
                LegacySourceRecord(**{**kwargs, "path": "reports/other.jsonl"}),
            )
        )
