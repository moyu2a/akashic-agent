from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from agent.optimization.real_ab_run import RealABRecord

from ..events import EventLedger, event_to_dict
from ..legacy import ExecutionMode, IntegrationStatus, LegacySourceRecord
from ..protocol import EpisodeResult, RunManifest


def _value(raw: object, key: str, default: Any = None) -> Any:
    if isinstance(raw, dict):
        return raw.get(key, default)
    return getattr(raw, key, default)


class CostLatencyAdapter:
    """Converts A/B records; it deliberately has no episode execution method."""

    def __init__(self) -> None:
        self.source = LegacySourceRecord(
            source_name="optimization_real_ab",
            source_path="agent/optimization/real_ab_run.py",
            source_commit="d80e74a",
            last_modified="2026-08-05",
            compatibility_status="ADAPTER_REQUIRED",
            integration_status=IntegrationStatus.ADAPTER_PASS,
            execution_mode=ExecutionMode.REPORT_ADAPTER,
            real_llm=None,
            fake_provider=False,
            main_gate_allowed=False,
            adapter_name="cost_latency",
            report_kind="real_ab_json_markdown",
            notes="Report adapter only; does not execute AgentLoop.",
        )

    def audit(self) -> LegacySourceRecord:
        return self.source

    def load_records(self, path: Path) -> tuple[RealABRecord, ...]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_records = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(raw_records, list):
            raise ValueError("real A/B report must contain a records list")
        records: list[RealABRecord] = []
        for raw in raw_records:
            if not isinstance(raw, dict):
                raise ValueError("real A/B records must be objects")
            normalized = dict(raw)
            normalized["actual_tools"] = tuple(normalized.get("actual_tools", ()) or ())
            normalized["expected_tools"] = tuple(
                normalized.get("expected_tools", ()) or ()
            )
            records.append(RealABRecord(**normalized))
        return tuple(records)

    def adapt_report_file(
        self,
        path: Path,
        *,
        manifest: RunManifest,
    ) -> tuple[EpisodeResult, ...]:
        return self.adapt_records(self.load_records(path), manifest=manifest)

    def adapt_records(
        self,
        records: Iterable[object],
        *,
        manifest: RunManifest,
    ) -> tuple[EpisodeResult, ...]:
        rows = list(records)
        baseline_by_key = {
            (
                str(_value(row, "phase", "")),
                str(_value(row, "case_id", "")),
            ): row
            for row in rows
            if str(_value(row, "profile", "")) == "baseline"
        }
        results: list[EpisodeResult] = []
        for row in rows:
            phase = str(_value(row, "phase", ""))
            profile = str(_value(row, "profile", ""))
            case_id = str(_value(row, "case_id", ""))
            baseline = baseline_by_key.get((phase, case_id))
            ab_pair = None
            if baseline is not None and profile != "baseline":
                ab_pair = {
                    "baseline_total_tokens": _value(
                        baseline, "actual_total_tokens_sum"
                    ),
                    "candidate_total_tokens": _value(row, "actual_total_tokens_sum"),
                    "total_tokens_delta": _delta(
                        _value(row, "actual_total_tokens_sum"),
                        _value(baseline, "actual_total_tokens_sum"),
                    ),
                    "turn_latency_delta_ms": _delta(
                        _value(row, "turn_duration_ms"),
                        _value(baseline, "turn_duration_ms"),
                    ),
                }
            ledger = EventLedger(
                run_id=manifest.run_id, episode_id=f"{case_id}-{profile}"
            )
            ledger.append(
                "episode_started",
                "cost_latency_adapter",
                {"case_id": case_id, "profile": profile},
            )
            ledger.append(
                "episode_finished",
                "cost_latency_adapter",
                {"status": str(_value(row, "correctness", ""))},
            )
            status = "PASS" if str(_value(row, "correctness", "")) == "PASS" else "FAIL"
            results.append(
                EpisodeResult(
                    episode_id=f"{case_id}-{profile}",
                    status=status,
                    outcome_passed=status == "PASS",
                    events=tuple(event_to_dict(event) for event in ledger.events),
                    metrics={
                        "execution_mode": "cost_latency_report",
                        "report_only": True,
                        "paired": ab_pair is not None,
                        "ab_pair": ab_pair,
                        "prompt_tokens": _value(row, "actual_prompt_tokens_sum"),
                        "total_tokens": _value(row, "actual_total_tokens_sum"),
                        "latency_ms": _value(row, "turn_duration_ms"),
                        "llm_duration_ms": _value(row, "llm_duration_ms_sum"),
                        "react_iteration_count": _value(row, "react_iteration_count"),
                        "tool_error_count": _value(row, "tool_error_count", 0),
                        "actual_tools": tuple(_value(row, "actual_tools", ()) or ()),
                        "metric_provenance": {
                            "prompt_tokens": "real_ab_record",
                            "total_tokens": "real_ab_record",
                            "latency_ms": "real_ab_record",
                        },
                    },
                )
            )
        return tuple(results)


def _delta(candidate: Any, baseline: Any) -> int | None:
    if candidate is None or baseline is None:
        return None
    return int(candidate) - int(baseline)
