from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Sequence, cast
from unittest.mock import MagicMock

from agent.looping.core import AgentLoop
from agent.looping.ports import (
    AgentLoopConfig,
    AgentLoopDeps,
    LLMConfig,
    MemoryConfig,
    MemoryServices,
)
from agent.tools.registry import ToolRegistry
from bus.event_bus import EventBus
from core.memory.engine import (
    ExplicitRetrievalRequest,
    ExplicitRetrievalResult,
    ForgetRequest,
    ForgetResult,
    InterestRetrievalRequest,
    InterestRetrievalResult,
    MemoryEngineRetrieveRequest,
    MemoryEngineRetrieveResult,
    MemoryIngestRequest,
    MemoryIngestResult,
    RememberRequest,
    RememberResult,
)
from memory2.eval_answer_post_check import (
    answer_post_check_shadow_to_dict,
    build_answer_post_check_shadow,
)
from memory2.eval_cases import EvalCase
from memory2.eval_llm_sample import (
    _RecordingProvider,
    _extract_token_counts,
    answer_expectation_from_case,
    score_answer_text,
)
from memory2.store import MemoryStore2
from plugins.default_memory.engine import DefaultMemoryEngine
from session.manager import SessionManager


MODE_TO_SAFE_VERSION = {
    "current": "off",
    "safe_version_shadow": "shadow",
    "safe_version_replace": "replace",
}


@dataclass(frozen=True)
class SystemPathSafeVersionReport:
    cases: tuple[dict[str, object], ...]
    metrics: dict[str, object]


class FixtureRetriever:
    def __init__(self, items: Sequence[dict[str, object]]) -> None:
        self._items = [dict(item) for item in items]

    async def retrieve(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
        return [dict(item) for item in self._items]

    async def retrieve_with_trace(
        self,
        *args: object,
        **kwargs: object,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        items = [dict(item) for item in self._items]
        return (
            items,
            {
                "candidates_by_lane": {
                    "semantic": items,
                    "keyword": [],
                    "provenance": [],
                    "graph": [],
                }
            },
        )

    def build_injection_block(
        self,
        items: Sequence[dict[str, object]],
    ) -> tuple[str, list[str]]:
        ids: list[str] = []
        lines: list[str] = []
        for item in items:
            item_id = str(item.get("id") or "").strip()
            if not item_id:
                continue
            ids.append(item_id)
            lines.append(f"- memory_id={item_id}; summary={item.get('summary') or ''}")
        return "\n".join(lines), ids


class RecordingMemoryEngine:
    def __init__(self, engine: DefaultMemoryEngine) -> None:
        self.engine = engine
        self.latest_retrieve_result: MemoryEngineRetrieveResult | None = None

    async def retrieve(
        self,
        request: MemoryEngineRetrieveRequest,
    ) -> MemoryEngineRetrieveResult:
        result = await self.engine.retrieve(request)
        self.latest_retrieve_result = result
        return result

    async def retrieve_explicit(
        self,
        request: ExplicitRetrievalRequest,
    ) -> ExplicitRetrievalResult:
        return ExplicitRetrievalResult()

    async def retrieve_interest_block(
        self,
        request: InterestRetrievalRequest,
    ) -> InterestRetrievalResult:
        return InterestRetrievalResult()

    async def remember(self, request: RememberRequest) -> RememberResult:
        return RememberResult(item_id="system-path-eval", actual_type=request.memory_type)

    async def forget(self, request: ForgetRequest) -> ForgetResult:
        return ForgetResult(missing_ids=list(request.ids))

    async def ingest(self, request: MemoryIngestRequest) -> MemoryIngestResult:
        return MemoryIngestResult(accepted=True)

    async def refresh_recent_turns(self, request: object) -> None:
        return None

    async def consolidate(self, request: object) -> object:
        return None

    def read_self(self) -> str:
        return ""

    def read_recent_context(self) -> str:
        return ""

    def get_memory_context(self) -> str:
        return ""

    def has_long_term_memory(self) -> bool:
        return False


async def run_system_path_safe_version_cases(
    cases: Sequence[EvalCase],
    workspace: Path,
    provider: object,
    *,
    modes: Sequence[str],
    model: str = "scripted",
    timeout_s: float = 30.0,
    real_llm_enabled: bool = False,
) -> SystemPathSafeVersionReport:
    records: list[dict[str, object]] = []
    for case_index, case in enumerate(cases):
        for mode in modes:
            records.append(
                await _run_case_mode(
                    case=case,
                    case_index=case_index,
                    mode=mode,
                    workspace=workspace / f"case-{case_index:03d}-{mode}",
                    provider=provider,
                    model=model,
                    timeout_s=timeout_s,
                )
            )
    return SystemPathSafeVersionReport(
        cases=tuple(records),
        metrics=_build_metrics(
            records,
            unique_case_count=len(cases),
            modes=modes,
            real_llm_enabled=real_llm_enabled,
        ),
    )


def write_system_path_safe_version_json(
    report: SystemPathSafeVersionReport,
    path: Path,
) -> None:
    _validate_report_privacy(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"metrics": report.metrics, "cases": list(report.cases)},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def write_system_path_safe_version_markdown(
    report: SystemPathSafeVersionReport,
    path: Path,
) -> None:
    _validate_report_privacy(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = report.metrics
    lines = [
        "# System Path Safe Version Governed",
        "",
        "本报告使用 system-path fake/provider validation；不包含原始 query、prompt、memory summary 或完整回答。",
        "",
        f"- evaluation_level: `{metrics['evaluation_level']}`",
        f"- real_llm_enabled: `{metrics['real_llm_enabled']}`",
        f"- unique_case_count: `{metrics['unique_case_count']}`",
        f"- case_count: `{metrics['case_count']}`",
        f"- replacement_seeded_count: `{metrics['replacement_seeded_count']}`",
        "",
        "| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, summary in dict(metrics["mode_summaries"]).items():
        row = cast(dict[str, object], summary)
        lines.append(
            "| "
            + " | ".join(
                (
                    str(mode),
                    str(row["case_count"]),
                    str(row["answer_success_count"]),
                    str(row["answer_rule_pass_rate"]),
                    str(row["memory_grounding_pass_rate"]),
                    str(row["forbidden_violation_rate"]),
                    str(row["contract_generation_success_rate"]),
                    str(row["post_check_shadow_enabled_rate"]),
                    str(row["avg_total_token_count"]),
                    str(row["avg_latency_ms"]),
                )
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run_case_mode(
    *,
    case: EvalCase,
    case_index: int,
    mode: str,
    workspace: Path,
    provider: object,
    model: str,
    timeout_s: float,
) -> dict[str, object]:
    if mode not in MODE_TO_SAFE_VERSION:
        raise ValueError(f"unknown system path mode: {mode}")
    workspace.mkdir(parents=True, exist_ok=True)
    store = MemoryStore2(workspace / "memory.db", vec_dim=2)
    memory_items = [dict(item) for item in case.setup.get("memory_items", [])]
    replacements = [dict(item) for item in case.setup.get("memory_replacements", [])]
    _seed_store(store, memory_items, replacements)
    engine = _build_engine(store=store, items=memory_items)
    recording = RecordingMemoryEngine(engine)
    recording_provider = _RecordingProvider(provider)
    event_bus = EventBus()
    session_manager = SessionManager(workspace)
    loop = AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=recording_provider,  # type: ignore[arg-type]
            light_provider=recording_provider,  # type: ignore[arg-type]
            tools=ToolRegistry(),
            session_manager=session_manager,
            workspace=workspace,
            event_bus=event_bus,
            memory_services=MemoryServices(engine=recording),  # type: ignore[arg-type]
        ),
        AgentLoopConfig(
            llm=LLMConfig(model=model, max_iterations=2),
            memory=MemoryConfig(
                safe_version_governed_mode=MODE_TO_SAFE_VERSION[mode],
                safe_version_governed_replace_allowed=(mode == "safe_version_replace"),
            ),
        ),
    )
    answer = ""
    provider_error = False
    timeout = False
    failures: list[str] = []
    started_at = time.perf_counter()
    try:
        query = (
            str(case.setup.get("query") or "").strip()
            or "system path eval user message"
        )
        answer = await asyncio.wait_for(
            loop.process_direct(
                query,
                session_key=str(case.setup.get("scope", {}).get("session_key") or "cli:local"),
                channel=str(case.setup.get("scope", {}).get("channel") or "cli"),
                chat_id=str(case.setup.get("scope", {}).get("chat_id") or "local"),
                skip_post_memory=True,
                disabled_tools=["message_push"],
            ),
            timeout=timeout_s,
        )
        await event_bus.drain()
    except asyncio.TimeoutError:
        timeout = True
        failures.append("timeout")
    except Exception:
        provider_error = True
        failures.append("provider_error")
    finally:
        await event_bus.aclose()
    if recording_provider.errors and not provider_error:
        provider_error = True
        failures.append("provider_error")

    latest = recording.latest_retrieve_result
    raw = latest.raw if latest is not None else {}
    metadata = cast(dict[str, object], raw.get("safe_version_governed_metadata") or {})
    contract = cast(dict[str, object], raw.get("safe_version_governed_shadow") or {})
    replace_applied = bool(metadata.get("replace_applied", False))
    context_ids = (
        [str(item) for item in contract.get("allowed_evidence_ids", [])]
        if replace_applied
        else [hit.id for hit in (latest.hits if latest is not None else [])]
    )
    post_check = {"shadow_enabled": False}
    if mode in {"safe_version_shadow", "safe_version_replace"} and contract:
        answer_contract = dict(contract)
        answer_contract["production_safe_evidence_contract"] = True
        post_check = answer_post_check_shadow_to_dict(
            build_answer_post_check_shadow(answer, answer_contract, context_ids)
        )
    score = score_answer_text(
        answer,
        answer_expectation_from_case(case),
        context_ids,
    )
    failures.extend(score.failures)
    token_counts = _extract_token_counts(
        recording_provider.responses[-1] if recording_provider.responses else None
    )
    return {
        "case_id": case.id,
        "case_index": case_index,
        "category": case.category,
        "mode": mode,
        "passed": not failures,
        "answer_rule_passed": score.answer_rule_passed,
        "memory_grounding_passed": score.memory_grounding_passed,
        "expected_memory_used": bool(score.expected_memory_used),
        "forbidden_contains_violation_count": score.forbidden_contains_violation_count,
        "failures": tuple(_sanitize_failure(failure) for failure in failures),
        "provider_error": provider_error,
        "timeout": timeout,
        "latency_ms": int((time.perf_counter() - started_at) * 1000),
        "token_count": int(token_counts["total_token_count"]),
        "prompt_token_count": int(token_counts["prompt_token_count"]),
        "completion_token_count": int(token_counts["completion_token_count"]),
        "token_metrics_available": bool(token_counts["token_metrics_available"]),
        "replacement_seeded_count": len(replacements),
        "safe_version_metadata": _sanitize_metadata(metadata),
        "safe_version_contract": _sanitize_contract(contract),
        "post_check_shadow": post_check,
    }


def _build_engine(*, store: MemoryStore2, items: list[dict[str, object]]) -> DefaultMemoryEngine:
    engine = DefaultMemoryEngine.__new__(DefaultMemoryEngine)
    engine._config = SimpleNamespace(model="system-path-eval")
    engine._workspace = Path(".")
    engine._provider = None
    engine._light_provider = None
    engine._light_model = ""
    engine._v2_store = store
    engine._embedder = None
    engine._memorizer = None
    engine._retriever = FixtureRetriever(items)
    engine._tagger = None
    engine._post_response_worker = None
    engine._experiment_runner = None
    engine._event_bus = None
    engine.closeables = []
    engine._wire_memory2_events()
    return engine


def _seed_store(
    store: MemoryStore2,
    items: list[dict[str, object]],
    replacements: list[dict[str, object]],
) -> None:
    now = "2026-07-29T00:00:00+00:00"
    for item in items:
        item_id = str(item.get("id") or "").strip()
        summary = str(item.get("summary") or "").strip()
        memory_type = str(item.get("memory_type") or "event")
        if not item_id or not summary:
            continue
        content_hash = hashlib.md5(f"{memory_type}:{item_id}:{summary}".encode()).hexdigest()
        store._db.execute(
            """INSERT OR REPLACE INTO memory_items
               (id, memory_type, summary, content_hash, embedding, reinforcement,
                emotional_weight, extra_json, source_ref, happened_at, status,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item_id,
                memory_type,
                summary,
                content_hash,
                None,
                1,
                int(item.get("emotional_weight") or 0),
                json.dumps(item.get("extra_json") or {}, ensure_ascii=False),
                item.get("source_ref"),
                item.get("happened_at"),
                str(item.get("status") or "active"),
                now,
                now,
            ),
        )
    for replacement in replacements:
        store._db.execute(
            """INSERT INTO memory_replacements
               (old_item_id, old_memory_type, old_summary, old_source_ref,
                old_happened_at, old_extra_json, new_item_id, new_memory_type,
                new_summary, new_source_ref, new_happened_at, new_extra_json,
                relation_type, source_ref, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                replacement.get("old_item_id"),
                replacement.get("old_memory_type") or "",
                replacement.get("old_summary") or "",
                replacement.get("old_source_ref"),
                replacement.get("old_happened_at"),
                json.dumps(replacement.get("old_extra_json") or {}, ensure_ascii=False),
                replacement.get("new_item_id"),
                replacement.get("new_memory_type") or "",
                replacement.get("new_summary") or "",
                replacement.get("new_source_ref"),
                replacement.get("new_happened_at"),
                json.dumps(replacement.get("new_extra_json") or {}, ensure_ascii=False),
                replacement.get("relation_type") or "supersede",
                replacement.get("source_ref") or replacement.get("new_source_ref"),
                now,
            ),
        )
    store._db.commit()


def _provider_usage(provider: object) -> dict[str, int]:
    calls = getattr(provider, "calls", [])
    if not calls:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    usage = calls[-1].get("usage", {}) if isinstance(calls[-1], dict) else {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }


def _sanitize_metadata(metadata: dict[str, object]) -> dict[str, object]:
    allowed = {
        "mode",
        "contract_generation_success",
        "allowed_evidence_count",
        "deleted_evidence_count",
        "downgrade_count",
        "requires_review_count",
        "forbidden_boundary_count",
        "replacement_requested",
        "replace_allowed",
        "replace_applied",
        "error_type",
    }
    return {key: value for key, value in metadata.items() if key in allowed}


def _sanitize_contract(contract: dict[str, object]) -> dict[str, object]:
    if not contract:
        return {}
    allowed = {
        "profile_name",
        "production_safe",
        "production_safe_evidence_contract",
        "uses_fixture_answer_expectations",
        "candidate_governance_mode",
        "allowed_evidence_ids",
        "likely_relevant_evidence_ids",
        "downgrade_ids",
        "requires_review_ids",
        "stale_warning_ids",
        "conflict_warning_ids",
        "active_version_ids",
        "insufficient_evidence_ids",
        "insufficient_evidence_fallback",
        "forbidden_boundary_ids",
        "deleted_evidence_ids",
        "candidate_risk_tier_counts",
        "accepted_candidate_risk_tier_counts",
        "tiered_deleted_risks_by_reason",
        "version_boundary",
    }
    return {key: value for key, value in contract.items() if key in allowed}


def _build_metrics(
    records: list[dict[str, object]],
    *,
    unique_case_count: int,
    modes: Sequence[str],
    real_llm_enabled: bool,
) -> dict[str, object]:
    mode_summaries = {}
    for mode in modes:
        rows = [record for record in records if record["mode"] == mode]
        answer_success_count = sum(1 for row in rows if row["answer_rule_passed"])
        grounding_success_count = sum(
            1 for row in rows if row["memory_grounding_passed"]
        )
        forbidden_case_count = sum(
            1
            for row in rows
            if int(row.get("forbidden_contains_violation_count", 0) or 0) > 0
        )
        contract_rows = [
            row
            for row in rows
            if row.get("safe_version_metadata")
            and cast(dict[str, object], row["safe_version_metadata"]).get(
                "contract_generation_success"
            )
            is True
        ]
        post_rows = [
            row
            for row in rows
            if cast(dict[str, object], row.get("post_check_shadow") or {}).get(
                "shadow_enabled"
            )
            is True
        ]
        mode_summaries[mode] = {
            "case_count": len(rows),
            "answer_success_count": answer_success_count,
            "grounding_success_count": grounding_success_count,
            "forbidden_case_count": forbidden_case_count,
            "answer_rule_pass_rate": _pct(answer_success_count, len(rows)),
            "memory_grounding_pass_rate": _pct(grounding_success_count, len(rows)),
            "forbidden_violation_rate": _pct(forbidden_case_count, len(rows)),
            "contract_generation_success_rate": _pct(len(contract_rows), len(rows)),
            "post_check_shadow_enabled_rate": _pct(len(post_rows), len(rows)),
            "avg_total_token_count": _avg(
                int(row.get("token_count", 0) or 0) for row in rows
            ),
            "avg_latency_ms": _avg(
                int(row.get("latency_ms", 0) or 0) for row in rows
            ),
            "token_metrics_available": any(
                bool(row.get("token_metrics_available")) for row in rows
            ),
        }
    replacement_seeded_count = sum(
        int(record.get("replacement_seeded_count", 0) or 0) for record in records
    )
    version_boundary_case_count = sum(
        1
        for record in records
        if cast(dict[str, object], record.get("safe_version_contract") or {})
        .get("version_boundary", {})
        .get("replacement_count", 0)
    )
    answer_success_count = sum(1 for row in records if row["answer_rule_passed"])
    grounding_success_count = sum(
        1 for row in records if row["memory_grounding_passed"]
    )
    forbidden_case_count = sum(
        1
        for row in records
        if int(row.get("forbidden_contains_violation_count", 0) or 0) > 0
    )
    return {
        "evaluation_level": "system_path_safe_version_governed",
        "unique_case_count": unique_case_count,
        "mode_count": len(tuple(modes)),
        "case_count": len(records),
        "real_llm_enabled": bool(real_llm_enabled),
        "fake_provider_enabled": not bool(real_llm_enabled),
        "provider_error_count": sum(1 for row in records if row["provider_error"]),
        "timeout_count": sum(1 for row in records if row["timeout"]),
        "answer_rule_pass_rate": _pct(answer_success_count, len(records)),
        "memory_grounding_pass_rate": _pct(grounding_success_count, len(records)),
        "forbidden_violation_rate": _pct(forbidden_case_count, len(records)),
        "avg_latency_ms": _avg(int(row.get("latency_ms", 0) or 0) for row in records),
        "total_token_count": sum(
            int(row.get("token_count", 0) or 0) for row in records
        ),
        "avg_total_token_count": _avg(
            int(row.get("token_count", 0) or 0) for row in records
        ),
        "token_metrics_available": any(
            bool(row.get("token_metrics_available")) for row in records
        ),
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "conversation_log_included": False,
        "complete_response_included": False,
        "replacement_seeded_count": replacement_seeded_count,
        "version_boundary_case_count": version_boundary_case_count,
        "mode_summaries": mode_summaries,
    }


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator * 100.0 / denominator, 4)


def _avg(values: Iterable[object]) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _sanitize_failure(failure: str) -> str:
    if failure.startswith("missing expected answer term:"):
        return "missing_expected_answer_term"
    if failure.startswith("missing expected answer term group:"):
        return "missing_expected_answer_term_group"
    if failure.startswith("found forbidden answer term:"):
        return "found_forbidden_answer_term"
    if failure.startswith("missing expected memory ids:"):
        return "missing_expected_memory_ids"
    if failure == "answer is not detected as Chinese":
        return "answer_language_not_chinese"
    return failure


def _validate_report_privacy(report: SystemPathSafeVersionReport) -> None:
    forbidden = {
        "raw_prompt",
        "prompt",
        "full_answer",
        "raw_answer",
        "session_text",
        "memory_summary",
        "raw_memory_summary",
    }
    keys = _walk_keys({"metrics": report.metrics, "cases": list(report.cases)})
    blocked = forbidden & keys
    if blocked:
        raise ValueError(f"forbidden report keys: {sorted(blocked)}")


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for child in value.values():
            keys.update(_walk_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_walk_keys(child))
        return keys
    return set()
