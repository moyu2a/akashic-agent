from __future__ import annotations

from pathlib import Path
from typing import Any

from .live_ipc import IpcLiveAdapter, _load_runner_module, _value
from ..events import EventLedger, event_to_dict
from ..legacy import ExecutionMode


class DeepLiveAdapter(IpcLiveAdapter):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.source = self.source.__class__(
            source_name="deep_live_eval_runner",
            source_path=self.source.source_path,
            source_commit=self.source.source_commit,
            last_modified=self.source.last_modified,
            compatibility_status=self.source.compatibility_status,
            integration_status=self.source.integration_status,
            execution_mode=ExecutionMode.DEEP_LIVE,
            real_llm=self.real_llm,
            fake_provider=False,
            main_gate_allowed=False,
            adapter_name="deep_live",
            report_kind="deep_live_json_markdown",
            notes="Deep live adapter; judge is quality-only and never a hard security decision.",
        )
        self._event_run_id = "legacy-deep-live"

    def convert_result(self, raw_result: object, *, task, manifest):
        result = super().convert_result(raw_result, task=task, manifest=manifest)
        judge = _value(raw_result, "judge", None)
        judge_payload = None
        if judge is not None:
            judge_payload = {
                "verdict": str(_value(judge, "verdict", "skipped")),
                "score": float(_value(judge, "score", 0.0) or 0.0),
                "reason": str(_value(judge, "reason", "") or ""),
                "failure_type": str(
                    _value(judge, "failure_type", "judge_skipped") or "judge_skipped"
                ),
            }
        metrics = dict(result.metrics)
        metrics["quality_judge"] = judge_payload
        metrics["execution_mode"] = ExecutionMode.DEEP_LIVE.value
        return result.__class__(
            episode_id=result.episode_id,
            status=result.status,
            outcome_passed=result.outcome_passed,
            failures=result.failures,
            final_reply=result.final_reply,
            events=result.events,
            metrics=metrics,
        )

    async def run_case(
        self,
        case: dict[str, Any],
        *,
        workspace: Path,
        endpoint: str,
        timeout: float,
        dry_run: bool = False,
        judge_enabled: bool = False,
    ) -> object:
        module = _load_runner_module(
            self.source_path,
            module_name="legacy_deep_live",
        )
        trace_cls = getattr(module, "TraceStore", None)
        runner = getattr(module, "run_case", None)
        if not callable(trace_cls) or not callable(runner):
            raise AttributeError(
                "legacy deep runner must expose TraceStore and async run_case"
            )
        trace = trace_cls(workspace)
        return await runner(
            dict(case),
            endpoint=endpoint,
            trace=trace,
            timeout=timeout,
            dry_run=dry_run,
            judge_enabled=judge_enabled,
        )
