from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Iterable, Mapping

from ..events import EventLedger, event_to_dict
from ..legacy import (
    ExecutionMode,
    IntegrationStatus,
    LegacyRunEnvelope,
    LegacySourceRecord,
    hash_input,
)
from ..protocol import EpisodeResult, RunManifest, TaskSpec

_STATUS_MAP = {
    "pass": "PASS",
    "partial": "PARTIAL",
    "fail": "FAIL",
    "n/a": "SKIP",
}


class OfflineTraceAdapter:
    """Converts the existing offline trace evaluator into Harness records."""

    def __init__(
        self,
        *,
        source_path: Path,
        source_commit: str = "df566c9",
        last_modified: str = "2026-07-07",
    ) -> None:
        self.source_path = source_path
        self.source = LegacySourceRecord(
            source_name="offline_trace_eval",
            source_path=str(source_path),
            source_commit=source_commit,
            last_modified=last_modified,
            compatibility_status="ADAPTER_REQUIRED",
            integration_status=IntegrationStatus.ADAPTER_PASS,
            execution_mode=ExecutionMode.OFFLINE_TRACE,
            real_llm=None,
            fake_provider=False,
            main_gate_allowed=False,
            adapter_name="offline_trace",
            report_kind="offline_markdown",
            notes="Recorded trace only; token and latency are unavailable unless present in trace.",
        )

    def audit(self) -> LegacySourceRecord:
        return self.source

    def load_cases(self, source: Path) -> list[TaskSpec]:
        payload = json.loads(source.read_text(encoding="utf-8"))
        raw_cases = payload.get("cases", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_cases, list):
            raise ValueError("offline case source must contain a list or cases list")
        tasks: list[TaskSpec] = []
        for item in raw_cases:
            if isinstance(item, Mapping):
                tasks.append(TaskSpec.from_dict(item))
        return tasks

    def task_from_case_result(self, raw_result: object) -> TaskSpec:
        case_id = str(getattr(raw_result, "case_id", "")).strip()
        if not case_id:
            raise ValueError("offline case result has no case_id")
        return TaskSpec(
            case_id=case_id,
            category="legacy_offline_trace",
            expected_outcome={"legacy_status": str(getattr(raw_result, "status", ""))},
            grader_names=("outcome", "cost"),
        )

    def convert_result(
        self,
        raw_result: object,
        *,
        task: TaskSpec,
        manifest: RunManifest,
    ) -> EpisodeResult:
        raw_status = str(getattr(raw_result, "status", "")).strip().lower()
        status = _STATUS_MAP.get(raw_status, "ERROR")
        issue = str(getattr(raw_result, "issue", "") or "").strip()
        turn_ids = [
            int(value)
            for value in (getattr(raw_result, "turn_ids", None) or [])
            if str(value).isdigit()
        ]
        score = float(getattr(raw_result, "score", 0.0) or 0.0)
        envelope = LegacyRunEnvelope(
            source_name=self.source.source_name,
            source_version=self.source.source_commit,
            source_commit=self.source.source_commit,
            source_run_id=manifest.run_id,
            case_id=task.case_id,
            repeat_index=manifest.repeat_index,
            input_hash=hash_input({"case_id": task.case_id}),
            raw_status=raw_status,
            raw_report_ref=None,
            trace_ref=(
                f"observe.turns:{','.join(str(item) for item in turn_ids)}"
                if turn_ids
                else None
            ),
            execution_mode=ExecutionMode.OFFLINE_TRACE,
            real_llm=None,
            fake_provider=False,
            metric_provenance={
                "prompt_tokens": "unavailable",
                "completion_tokens": "unavailable",
                "total_tokens": "unavailable",
                "latency_ms": "unavailable",
            },
            metrics={
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "latency_ms": None,
            },
        )
        metrics = {
            **envelope.metrics,
            "metric_provenance": envelope.metric_provenance,
            "execution_mode": envelope.execution_mode.value,
            "real_llm": envelope.real_llm,
            "fake_provider": envelope.fake_provider,
            "raw_status": raw_status,
            "score": score,
            "turn_ids": turn_ids,
            "excluded_from_score": raw_status == "n/a",
            "source_name": self.source.source_name,
        }
        return EpisodeResult(
            episode_id=task.case_id,
            status=status,
            outcome_passed=status == "PASS",
            failures=(issue,) if issue else (),
            events=self.convert_events(raw_result),
            metrics=metrics,
        )

    def convert_events(self, raw_result: object) -> tuple[dict[str, object], ...]:
        case_id = str(getattr(raw_result, "case_id", ""))
        turn_ids = [
            int(value)
            for value in (getattr(raw_result, "turn_ids", None) or [])
            if str(value).isdigit()
        ]
        ledger = EventLedger(run_id="legacy-offline", episode_id=case_id)
        ledger.append(
            "episode_started",
            "offline_trace_adapter",
            {"case_id": case_id, "execution_mode": "offline_trace"},
        )
        for turn_id in turn_ids:
            ledger.append("turn_observed", "offline_trace", {"turn_id": turn_id})
        ledger.append(
            "episode_finished",
            "offline_trace_adapter",
            {"status": str(getattr(raw_result, "status", ""))},
        )
        return tuple(event_to_dict(event) for event in ledger.events)

    def convert_results(
        self,
        raw_results: Iterable[object],
        *,
        manifest: RunManifest,
    ) -> tuple[TaskSpec, tuple[EpisodeResult, ...]]:
        result_list = list(raw_results)
        tasks = tuple(self.task_from_case_result(item) for item in result_list)
        results = tuple(
            self.convert_result(item, task=task, manifest=manifest)
            for item, task in zip(result_list, tasks, strict=True)
        )
        return tasks, results

    def run(
        self,
        workspace: Path,
        *,
        manifest: RunManifest,
    ) -> tuple[TaskSpec, tuple[EpisodeResult, ...]]:
        module = _load_runner_module(self.source_path)
        store = module.TraceStore(workspace)
        raw_results = module.evaluate(store)
        return self.convert_results(raw_results, manifest=manifest)


def _load_runner_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("legacy_offline_trace_eval", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load offline trace runner: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
