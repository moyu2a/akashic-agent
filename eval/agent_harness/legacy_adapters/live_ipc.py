from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping

from ..events import EventLedger, event_to_dict
from ..legacy import (
    ExecutionMode,
    IntegrationStatus,
    LegacyRunnerAdapter,
    LegacySourceRecord,
)
from ..protocol import EpisodeResult, RunManifest, TaskSpec


def _value(raw: object, key: str, default: Any = None) -> Any:
    if isinstance(raw, Mapping):
        return raw.get(key, default)
    return getattr(raw, key, default)


def _turns(raw: object) -> list[object]:
    return list(_value(raw, "step_results", []) or [])


def _turn_value(step: object, key: str, default: Any = None) -> Any:
    turn = _value(step, "turn", {})
    return _value(turn, key, default)


def classify_live_error(error: str) -> str | None:
    value = error.lower()
    if "timeout" in value:
        return "timeout"
    if "connection" in value or "ipc" in value and "closed" in value:
        return "connection"
    if "observe.db" in value or "observe turn" in value:
        return "observe_missing"
    return None


@dataclass
class IpcLiveAdapter:
    source_path: Path
    source_commit: str = "df566c9"
    last_modified: str = "2026-07-07"
    real_llm: bool | None = None

    def __post_init__(self) -> None:
        self.source = LegacySourceRecord(
            source_name="live_eval_runner",
            source_path=str(self.source_path),
            source_commit=self.source_commit,
            last_modified=self.last_modified,
            compatibility_status="ADAPTER_REQUIRED",
            integration_status=IntegrationStatus.ADAPTER_PASS,
            execution_mode=ExecutionMode.IPC_LIVE,
            real_llm=self.real_llm,
            fake_provider=False,
            main_gate_allowed=False,
            adapter_name="ipc_live",
            report_kind="live_markdown",
            notes="Safe IPC cases only until runtime and observe contracts pass.",
        )
        self._event_run_id = "legacy-live"

    def audit(self) -> LegacySourceRecord:
        return self.source

    def load_cases(self, source: Path) -> list[TaskSpec]:
        if source.suffix.lower() not in {".json", ".jsonl"}:
            module = self._legacy_module()
            loader = getattr(module, "load_cases", None)
            if not callable(loader):
                raise AttributeError(
                    f"legacy runner has no load_cases: {self.source_path}"
                )
            raw_cases = loader(source)
            if not isinstance(raw_cases, list):
                raise ValueError("legacy live loader must return a list")
            return [
                self.task_from_case(item)
                for item in raw_cases
                if isinstance(item, Mapping)
            ]
        payload = json.loads(source.read_text(encoding="utf-8"))
        raw_cases = payload.get("cases", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_cases, list):
            raise ValueError("live case source must contain a list or cases list")
        return [
            self.task_from_case(item) for item in raw_cases if isinstance(item, Mapping)
        ]

    def select_cases(
        self,
        cases: list[Mapping[str, Any]],
        *,
        include_guarded: bool = False,
    ) -> list[Mapping[str, Any]]:
        selected: list[Mapping[str, Any]] = []
        for case in cases:
            if str(case.get("execution_mode", "live")) != "live":
                continue
            risk = str(case.get("risk_level", "safe"))
            if risk != "safe" and not (include_guarded and risk == "guarded"):
                continue
            selected.append(case)
        return selected

    def task_from_case(self, case: Mapping[str, Any]) -> TaskSpec:
        case_id = str(case.get("id") or case.get("case_id") or "").strip()
        if not case_id:
            raise ValueError("live case has no id")
        raw_input = case.get("input", {})
        steps: list[dict[str, str]] = []
        if isinstance(raw_input, Mapping) and isinstance(raw_input.get("steps"), list):
            for item in raw_input["steps"]:
                if isinstance(item, Mapping) and str(item.get("text", "")).strip():
                    steps.append(
                        {
                            "role": "user",
                            "text": str(item["text"]).strip(),
                        }
                    )
        elif isinstance(raw_input, Mapping) and str(raw_input.get("text", "")).strip():
            steps.append({"role": "user", "text": str(raw_input["text"]).strip()})
        expected = case.get("expected", {})
        tool_calls = (
            expected.get("tool_calls", {}) if isinstance(expected, Mapping) else {}
        )
        return TaskSpec(
            case_id=case_id,
            category=str(case.get("category", "live")),
            steps=tuple(steps),
            expected_tools=tuple(
                str(item)
                for item in tool_calls.get("must_include", [])
                if isinstance(tool_calls, Mapping)
            ),
            forbidden_tools=tuple(
                str(item)
                for item in tool_calls.get("must_not_include", [])
                if isinstance(tool_calls, Mapping)
            ),
            risk_level=str(case.get("risk_level", "safe")),
            grader_names=("outcome", "trajectory", "security", "cost"),
        )

    async def run_case(
        self,
        case: Mapping[str, Any],
        *,
        workspace: Path,
        endpoint: str,
        timeout: float,
        dry_run: bool = False,
    ) -> object:
        module = self._legacy_module()
        observe_cls = getattr(module, "ObserveStore", None)
        runner = getattr(module, "run_case", None)
        if not callable(observe_cls) or not callable(runner):
            raise AttributeError(
                "legacy live runner must expose ObserveStore and async run_case"
            )
        observe = observe_cls(workspace)
        return await runner(
            dict(case),
            endpoint=endpoint,
            observe=observe,
            timeout=timeout,
            dry_run=dry_run,
        )

    def _legacy_module(self) -> ModuleType:
        return _load_runner_module(self.source_path, module_name="legacy_ipc_live")

    def convert_result(
        self,
        raw_result: object,
        *,
        task: TaskSpec,
        manifest: RunManifest,
    ) -> EpisodeResult:
        raw_status = str(_value(raw_result, "status", "")).lower()
        dry_run = raw_status == "dry_run"
        errors = [
            str(_turn_value(step, "error", "") or "")
            for step in _turns(raw_result)
            if str(_turn_value(step, "error", "") or "")
        ]
        failure_types = [
            failure_type
            for error in errors
            if (failure_type := classify_live_error(error)) is not None
        ]
        if dry_run:
            status = "SKIP"
        elif failure_types:
            status = "ERROR"
        elif raw_status == "pass":
            status = "PASS"
        else:
            status = "FAIL"
        prompt_tokens = [
            _turn_value(step, "prompt_tokens")
            for step in _turns(raw_result)
            if _turn_value(step, "prompt_tokens") is not None
        ]
        iteration_counts = [
            int(value)
            for step in _turns(raw_result)
            if (value := _turn_value(step, "iteration_count")) is not None
        ]
        tool_count = sum(
            int(_value(step, "tool_count", 0) or 0) for step in _turns(raw_result)
        )
        return EpisodeResult(
            episode_id=task.case_id,
            status=status,
            outcome_passed=status == "PASS",
            failures=(
                tuple(f"{item}: {item}" for item in failure_types)
                if failure_types
                else tuple(
                    str(item) for item in (_value(raw_result, "issues", []) or [])
                )
            ),
            events=self.convert_events(raw_result),
            metrics={
                "execution_mode": ExecutionMode.IPC_LIVE.value,
                "real_llm": self.source.real_llm,
                "fake_provider": False,
                "dry_run": dry_run,
                "guarded_case": task.risk_level == "guarded",
                "failure_type": failure_types[0] if failure_types else None,
                "prompt_tokens": sum(prompt_tokens) if prompt_tokens else None,
                "latency_ms": None,
                "react_iterations": sum(iteration_counts) if iteration_counts else None,
                "tool_count": tool_count,
                "metric_provenance": {
                    "prompt_tokens": "observe.turns" if prompt_tokens else "missing",
                    "latency_ms": "missing",
                },
            },
        )

    def convert_events(self, raw_result: object) -> tuple[dict[str, object], ...]:
        case_id = str(_value(raw_result, "case_id", ""))
        ledger = EventLedger(run_id=self._event_run_id, episode_id=case_id)
        ledger.append(
            "episode_started",
            "ipc_live_adapter",
            {"case_id": case_id, "execution_mode": ExecutionMode.IPC_LIVE.value},
        )
        for step in _turns(raw_result):
            turn_id = _turn_value(step, "id")
            tool_names = list(_value(step, "tool_names", []) or [])
            payload: dict[str, object] = {
                "turn_id": turn_id,
                "tool_count": len(tool_names),
                "tool_names": [str(item) for item in tool_names],
            }
            ledger.append("turn_observed", "observe", payload)
            for tool_name in tool_names:
                ledger.append("tool_executed", "observe", {"tool": str(tool_name)})
            error = str(_turn_value(step, "error", "") or "")
            if error:
                ledger.append(
                    "tool_failed",
                    "observe",
                    {"failure_type": classify_live_error(error) or "runtime"},
                )
        ledger.append(
            "episode_finished",
            "ipc_live_adapter",
            {"status": str(_value(raw_result, "status", ""))},
        )
        return tuple(event_to_dict(event) for event in ledger.events)


def _load_runner_module(path: Path, *, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load legacy live runner: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
