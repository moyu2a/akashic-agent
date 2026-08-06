from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping

from ..events import EventLedger, event_to_dict
from ..legacy import ExecutionMode, IntegrationStatus, LegacySourceRecord
from ..protocol import EpisodeResult, RunManifest, TaskSpec


def _value(raw: object, key: str, default: Any = None) -> Any:
    if isinstance(raw, Mapping):
        return raw.get(key, default)
    return getattr(raw, key, default)


class MemoryOfflineAdapter:
    def __init__(self, *, source_path: Path | None = None) -> None:
        self.source_path = source_path or Path("memory2/eval_runner.py")
        self.source = LegacySourceRecord(
            source_name="memory_eval_runner",
            source_path=str(self.source_path),
            source_commit="7ee506b",
            last_modified="2026-08-02",
            compatibility_status="ADAPTER_REQUIRED",
            integration_status=IntegrationStatus.ADAPTER_PASS,
            execution_mode=ExecutionMode.MEMORY_OFFLINE,
            real_llm=False,
            fake_provider=False,
            main_gate_allowed=False,
            adapter_name="memory_offline",
            report_kind="memory_json",
            notes="Retrieval shadow only; not a real AgentLoop trajectory.",
        )

    def audit(self) -> LegacySourceRecord:
        return self.source

    def task_from_case_result(self, raw_result: object) -> TaskSpec:
        return TaskSpec(
            case_id=str(_value(raw_result, "case_id", "")),
            category=str(_value(raw_result, "category", "memory")),
            grader_names=("outcome", "security", "cost"),
        )

    def adapt_case_result(
        self,
        raw_result: object,
        *,
        task: TaskSpec,
        manifest: RunManifest,
    ) -> EpisodeResult:
        passed = bool(_value(raw_result, "passed", False))
        profiles = _value(raw_result, "profiles", {}) or {}
        recalled_count = 0
        injected_count = 0
        trace_count = 0
        for profile in profiles.values() if isinstance(profiles, Mapping) else ():
            recalled_count += len(_value(profile, "recalled_ids", ()) or ())
            injected_count += len(_value(profile, "injected_ids", ()) or ())
            trace_count += len(_value(profile, "trace_features", ()) or ())
        ledger = EventLedger(run_id=manifest.run_id, episode_id=task.case_id)
        ledger.append(
            "episode_started",
            "memory_offline_adapter",
            {"case_id": task.case_id, "execution_mode": "memory_offline"},
        )
        for profile_name, profile in (
            profiles.items() if isinstance(profiles, Mapping) else ()
        ):
            for feature_name in _value(profile, "trace_features", ()) or ():
                ledger.append(
                    "retrieval_shadow_observed",
                    "memory_offline",
                    {
                        "profile": str(profile_name),
                        "feature": str(feature_name),
                    },
                )
        ledger.append(
            "episode_finished",
            "memory_offline_adapter",
            {"status": "PASS" if passed else "FAIL"},
        )
        return EpisodeResult(
            episode_id=task.case_id,
            status="PASS" if passed else "FAIL",
            outcome_passed=passed,
            failures=tuple(
                str(item) for item in (_value(raw_result, "failures", ()) or ())
            ),
            events=tuple(event_to_dict(event) for event in ledger.events),
            metrics={
                "execution_mode": ExecutionMode.MEMORY_OFFLINE.value,
                "real_llm": False,
                "fake_provider": False,
                "trace_kind": "retrieval_shadow",
                "trace_count": trace_count,
                "recalled_id_count": recalled_count,
                "injected_id_count": injected_count,
                "latency_ms": None,
                "prompt_tokens": None,
                "total_tokens": None,
                "metric_provenance": {
                    "latency_ms": "missing:not_recorded",
                    "prompt_tokens": "missing:not_recorded",
                    "total_tokens": "missing:not_recorded",
                },
            },
        )

    def run(
        self,
        root: Path,
        *,
        manifest: RunManifest,
    ) -> tuple[tuple[TaskSpec, ...], tuple[EpisodeResult, ...]]:
        module = _load_runner_module(
            self.source_path,
            module_name="legacy_memory_offline",
        )
        runner = getattr(module, "run_eval_case_files", None)
        if not callable(runner):
            raise AttributeError(
                "legacy memory offline runner must expose run_eval_case_files"
            )
        report = runner(root)
        raw_cases = list(_value(report, "cases", ()) or ())
        tasks = tuple(self.task_from_case_result(item) for item in raw_cases)
        results = tuple(
            self.adapt_case_result(item, task=task, manifest=manifest)
            for item, task in zip(raw_cases, tasks, strict=True)
        )
        return tasks, results


class MemoryOnlineAdapter:
    def __init__(self, *, source_path: Path | None = None) -> None:
        self.source_path = source_path or Path("memory2/eval_comprehensive_online.py")
        self.source = LegacySourceRecord(
            source_name="memory_comprehensive_online_eval",
            source_path=str(self.source_path),
            source_commit="7bb3b06",
            last_modified="2026-07-28",
            compatibility_status="ADAPTER_REQUIRED",
            integration_status=IntegrationStatus.ADAPTER_PASS,
            execution_mode=ExecutionMode.REAL_LLM,
            real_llm=True,
            fake_provider=False,
            main_gate_allowed=False,
            adapter_name="memory_online",
            report_kind="memory_online_json_markdown",
            notes="Real AgentLoop memory answer evaluation with provider usage.",
        )

    def audit(self) -> LegacySourceRecord:
        return self.source

    def adapt_case_result(
        self,
        raw_result: object,
        *,
        task: TaskSpec,
        manifest: RunManifest,
    ) -> EpisodeResult:
        provider_error = bool(_value(raw_result, "provider_error", False))
        timeout = bool(_value(raw_result, "timeout", False))
        passed = bool(_value(raw_result, "passed", False))
        failure_class = "infra" if provider_error or timeout else "business"
        if provider_error:
            status = "ERROR"
            infra_failure = "provider_error"
        elif timeout:
            status = "ERROR"
            infra_failure = "timeout"
        else:
            status = "PASS" if passed else "FAIL"
            infra_failure = None
        token_available = bool(_value(raw_result, "token_metrics_available", False))
        prompt_tokens = (
            _value(raw_result, "prompt_token_count") if token_available else None
        )
        completion_tokens = (
            _value(raw_result, "completion_token_count") if token_available else None
        )
        total_tokens = (
            _value(raw_result, "total_token_count") if token_available else None
        )
        raw_failures = tuple(
            str(item) for item in (_value(raw_result, "failures", ()) or ())
        )
        if infra_failure:
            failures = (f"infra:{infra_failure}",) + raw_failures
        else:
            failures = tuple(f"business:{item}" for item in raw_failures)
        ledger = EventLedger(run_id=manifest.run_id, episode_id=task.case_id)
        ledger.append(
            "episode_started",
            "memory_online_adapter",
            {"case_id": task.case_id, "execution_mode": "memory_online"},
        )
        ledger.append(
            "answer_scored",
            "memory_online",
            {
                "answer_rule_passed": bool(
                    _value(raw_result, "answer_rule_passed", False)
                ),
                "memory_grounding_passed": bool(
                    _value(raw_result, "memory_grounding_passed", False)
                ),
            },
        )
        ledger.append(
            "episode_finished",
            "memory_online_adapter",
            {"status": status},
        )
        return EpisodeResult(
            episode_id=task.case_id,
            status=status,
            outcome_passed=passed,
            failures=failures,
            events=tuple(event_to_dict(event) for event in ledger.events),
            metrics={
                "execution_mode": "memory_online",
                "real_llm": True,
                "fake_provider": False,
                "latency_ms": _value(raw_result, "latency_ms"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "token_metrics_available": token_available,
                "provider_error": provider_error,
                "timeout": timeout,
                "failure_class": failure_class,
                "infra_failure": infra_failure,
                "metric_provenance": {
                    "latency_ms": "real_agent_loop",
                    "prompt_tokens": (
                        "provider_usage" if token_available else "unavailable"
                    ),
                    "completion_tokens": (
                        "provider_usage" if token_available else "unavailable"
                    ),
                    "total_tokens": (
                        "provider_usage" if token_available else "unavailable"
                    ),
                },
            },
        )

    async def run(
        self,
        specs: list[object],
        *,
        workspace: Path,
        provider: object,
        model: str,
        timeout_s: float = 60.0,
        real_llm_enabled: bool = True,
        **kwargs: Any,
    ) -> object:
        module = _load_runner_module(
            self.source_path,
            module_name="legacy_memory_online",
        )
        runner = getattr(module, "run_comprehensive_online_eval", None)
        if not callable(runner):
            raise AttributeError(
                "legacy memory online runner must expose "
                "run_comprehensive_online_eval"
            )
        return await runner(
            specs,
            workspace,
            provider,
            model,
            timeout_s=timeout_s,
            real_llm_enabled=real_llm_enabled,
            **kwargs,
        )

    def adapt_report(
        self,
        report: object,
        *,
        manifest: RunManifest,
    ) -> tuple[TaskSpec, tuple[EpisodeResult, ...]]:
        raw_cases = list(_value(report, "cases", ()) or ())
        tasks: list[TaskSpec] = []
        results: list[EpisodeResult] = []
        for raw_case in raw_cases:
            case_id = str(_value(raw_case, "case_id", "")).strip()
            profile = str(_value(raw_case, "profile_name", "")).strip()
            prompt_variant = str(_value(raw_case, "prompt_variant", "")).strip()
            repeat_index = int(_value(raw_case, "repeat_index", 0) or 0)
            task = TaskSpec(
                case_id=f"{case_id}:{profile}:{prompt_variant}:r{repeat_index}",
                category="memory_online",
                grader_names=("outcome", "quality", "cost"),
            )
            tasks.append(task)
            results.append(
                self.adapt_case_result(
                    raw_case,
                    task=task,
                    manifest=manifest,
                )
            )
        return tuple(tasks), tuple(results)


def _load_runner_module(path: Path, *, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load legacy memory runner: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
