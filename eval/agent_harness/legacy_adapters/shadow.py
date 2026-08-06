from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..events import EventLedger, event_to_dict
from ..legacy import ExecutionMode, IntegrationStatus, LegacySourceRecord
from ..protocol import EpisodeResult, RunManifest

_ROUTER_KEYS = {
    "intent",
    "need_memory",
    "need_tools",
    "tool_scope",
    "risk_level",
}


class ShadowAdapter:
    def __init__(self) -> None:
        self.source = LegacySourceRecord(
            source_name="shadow_sources",
            source_path="external-and-branch-evaluators",
            source_commit="multiple",
            last_modified="2026-08-06",
            compatibility_status="ADAPTER_REQUIRED",
            integration_status=IntegrationStatus.CONTRACT_PASS,
            execution_mode=ExecutionMode.SHADOW,
            real_llm=None,
            fake_provider=False,
            main_gate_allowed=False,
            adapter_name="shadow",
            report_kind="shadow_envelope",
            notes="External, branch-only, and MiniRoute sources never authorize production tools.",
        )

    def audit(self) -> LegacySourceRecord:
        return self.source

    def adapt_external_benchmark(
        self,
        *,
        name: str,
        case_id: str,
        metrics: Mapping[str, Any],
        passed: bool,
        manifest: RunManifest,
        historical: bool,
    ) -> EpisodeResult:
        merged = {
            **dict(metrics),
            "benchmark_kind": "external",
            "benchmark_name": name,
            "historical": historical,
            "main_gate_eligible": False,
            "metric_provenance": {
                key: f"missing:{name}" if value is None else f"external:{name}"
                for key, value in metrics.items()
            },
        }
        return self._result(case_id, passed, merged, manifest)

    def adapt_tool_governance_branch(
        self,
        *,
        branch_name: str,
        case_id: str,
        decision: Mapping[str, Any],
        metrics: Mapping[str, Any],
        passed: bool,
        manifest: RunManifest,
    ) -> EpisodeResult:
        return self._result(
            case_id,
            passed,
            {
                **dict(metrics),
                "benchmark_kind": "tool_governance_branch",
                "branch_name": branch_name,
                "decision": dict(decision),
                "main_gate_eligible": False,
                "metric_provenance": {
                    key: (
                        f"missing:{branch_name}"
                        if value is None
                        else f"branch:{branch_name}"
                    )
                    for key, value in metrics.items()
                },
            },
            manifest,
        )

    def adapt_miniroute_envelope(
        self,
        *,
        case_id: str,
        parse_envelope: Mapping[str, Any],
        manifest: RunManifest,
    ) -> EpisodeResult:
        decision = parse_envelope.get("decision")
        filtered = None
        if isinstance(decision, Mapping) and set(decision) >= _ROUTER_KEYS:
            candidate = {key: decision[key] for key in _ROUTER_KEYS}
            if isinstance(candidate["tool_scope"], list) and all(
                isinstance(item, str) for item in candidate["tool_scope"]
            ):
                filtered = candidate
        metrics = {
            "benchmark_kind": "miniroute_shadow",
            "main_gate_eligible": False,
            "parse_envelope": {
                "json_valid": bool(parse_envelope.get("json_valid", False)),
                "errors": list(parse_envelope.get("errors", []) or []),
            },
            "decision": filtered,
            "metric_provenance": {
                "json_valid": "miniroute_parse_envelope",
                "decision": "miniroute_route_label" if filtered else "parse_failure",
            },
        }
        return self._result(case_id, filtered is not None, metrics, manifest)

    def _result(
        self,
        case_id: str,
        passed: bool,
        metrics: dict[str, Any],
        manifest: RunManifest,
    ) -> EpisodeResult:
        ledger = EventLedger(run_id=manifest.run_id, episode_id=case_id)
        ledger.append("episode_started", "shadow_adapter", {"case_id": case_id})
        ledger.append(
            "shadow_observed",
            "shadow_adapter",
            {"benchmark_kind": metrics.get("benchmark_kind", "shadow")},
        )
        ledger.append(
            "episode_finished",
            "shadow_adapter",
            {"status": "PASS" if passed else "FAIL"},
        )
        return EpisodeResult(
            episode_id=case_id,
            status="PASS" if passed else "FAIL",
            outcome_passed=passed,
            events=tuple(event_to_dict(event) for event in ledger.events),
            metrics=metrics,
        )

    def summarize(self, results: Iterable[EpisodeResult]) -> dict[str, object]:
        by_kind: dict[str, dict[str, int]] = {}
        result_list = list(results)
        for result in result_list:
            kind = str(result.metrics.get("benchmark_kind", "shadow"))
            row = by_kind.setdefault(kind, {"count": 0, "passed": 0, "failed": 0})
            row["count"] += 1
            if result.status == "PASS":
                row["passed"] += 1
            else:
                row["failed"] += 1
        return {
            "episode_count": len(result_list),
            "main_gate_eligible": False,
            "real_llm_used": any(
                result.metrics.get("real_llm") is True for result in result_list
            ),
            "by_kind": dict(sorted(by_kind.items())),
        }
