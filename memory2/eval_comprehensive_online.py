from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock

from agent.looping.core import AgentLoop
from agent.looping.ports import AgentLoopConfig, AgentLoopDeps, LLMConfig, MemoryServices
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
    MemoryHit,
    MemoryIngestRequest,
    MemoryIngestResult,
    RememberRequest,
    RememberResult,
)
from memory2.eval_cases import EvalCase
from memory2.eval_llm_sample import (
    LLMSampleAnswerDebugRecord,
    _extract_token_counts,
    _memory_summaries_by_id,
    _query,
    _RecordingProvider,
    _scope,
    answer_expectation_from_case,
    score_answer_text,
    write_llm_sample_answer_debug,
)
from memory2.eval_runner import _baseline_recalled_items
from memory2.eval_quantitative_uplift import (
    BALANCED_SCORE_FORMULA,
    CHAIN_REPORT_PROFILES,
    CHAIN_PROFILES,
    QuantitativeProfileSummary,
    _family_trace_for_case,
    calculate_balanced_scores,
    calculate_main_score,
)
from session.manager import SessionManager


_FIXED_REPORT_TIME = datetime(2026, 7, 19, tzinfo=timezone.utc)

COMPREHENSIVE_CHAIN_PROFILES: tuple[str, ...] = CHAIN_REPORT_PROFILES
METRIC_SOURCES: dict[str, str] = {
    "online_answer_level": "real AgentLoop answer scoring",
    "online_balanced_proxy": "online answer-level fields converted into balanced proxy dimensions",
    "offline_retrieval_proxy": "existing offline trace retrieval metrics",
    "real_db_readonly_sampling_background": "aggregate-only real memory DB sampling status",
}


@dataclass(frozen=True)
class ComprehensiveRunSpec:
    case: EvalCase
    profile_name: str
    prompt_variant: str
    repeat_index: int


@dataclass(frozen=True)
class ComprehensiveCaseResult:
    case_id: str
    category: str
    profile_name: str
    prompt_variant: str
    repeat_index: int
    passed: bool
    answer_rule_passed: bool
    memory_grounding_passed: bool
    expected_memory_used: bool
    forbidden_contains_violation_count: int
    latency_ms: int
    prompt_token_count: int
    completion_token_count: int
    total_token_count: int
    token_metrics_available: bool
    provider_error: bool
    timeout: bool
    answer_length: int
    evidence_source: str
    used_memory_id_count: int
    failures: tuple[str, ...]


@dataclass(frozen=True)
class ComprehensiveOnlineReport:
    run_id: str
    generated_at: str
    cases: tuple[ComprehensiveCaseResult, ...]
    case_records: tuple[dict[str, object], ...]
    failure_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def infra_passed(self) -> bool:
        return bool(self.cases) and all(
            not case.provider_error and not case.timeout for case in self.cases
        )


class ComprehensiveOnlineMemoryEngine:
    def __init__(
        self,
        case: EvalCase,
        *,
        profile_name: str,
        prompt_variant: str,
    ) -> None:
        if prompt_variant not in {"baseline", "coached"}:
            raise ValueError("prompt_variant must be 'baseline' or 'coached'")
        self.case = case
        self.profile_name = profile_name
        self.prompt_variant = prompt_variant
        self.retrieve_requests: list[MemoryEngineRetrieveRequest] = []
        self.used_memory_ids: list[str] = []
        self.last_text_block = ""

    async def retrieve(
        self,
        request: MemoryEngineRetrieveRequest,
    ) -> MemoryEngineRetrieveResult:
        self.retrieve_requests.append(request)
        ids = list(evidence_ids_for_profile(self.case, self.profile_name))
        summaries = _memory_summaries_by_id(self.case)
        self.used_memory_ids = ids
        hits = [
            MemoryHit(
                id=item_id,
                summary=summaries.get(item_id, ""),
                content=summaries.get(item_id, ""),
                score=1.0,
                source_ref="",
                engine_kind="comprehensive_online_eval",
                injected=True,
            )
            for item_id in ids
        ]
        lines = [
            f"- memory_id={item_id}; summary={summaries.get(item_id, '')}"
            for item_id in ids
        ]
        if self.prompt_variant == "coached" and lines:
            lines.insert(
                0,
                "记忆评测说明：请优先使用下列记忆回答；"
                "如果记忆包含具体方案名、排序方式、工具名或关键术语，"
                "请在答案中保留这些关键术语。",
            )
        self.last_text_block = "\n".join(lines)
        return MemoryEngineRetrieveResult(
            text_block=self.last_text_block,
            hits=hits,
            raw={"ids": ids, "evidence_source": profile_evidence_source(self.profile_name)},
        )

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
        return RememberResult(item_id="comprehensive-online-memory", actual_type=request.memory_type)

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


def evidence_ids_for_profile(case: EvalCase, profile_name: str) -> tuple[str, ...]:
    if profile_name == "chain_off":
        return ()
    if profile_name == "chain_memory_base":
        return tuple(str(item.get("id") or "") for item in _baseline_recalled_items(case))
    if profile_name == "chain_write_value":
        return ()
    if profile_name not in COMPREHENSIVE_CHAIN_PROFILES:
        raise ValueError(f"unknown profile_name: {profile_name}")
    if profile_name == "chain_tri_retrieval":
        return _ids_from_trace(case, "tri_retrieval", "fused_ids")
    if profile_name == "chain_graph_retrieval":
        return _ids_from_trace(case, "graph_retrieval", "graph_fused_ids")
    if profile_name == "chain_rerank_injection":
        return _ids_from_trace(
            case,
            "injection_governance_shadow",
            "experimental_injected_ids",
        )
    if profile_name == "chain_version_provenance":
        return _ids_from_trace(case, "version_chain_shadow", "active_leaf_ids")
    if profile_name in {"chain_sleep_consolidation", "chain_all_on"}:
        return _sleep_filtered_ids(case)
    return ()


def profile_evidence_source(profile_name: str) -> str:
    sources = {
        "chain_off": "none",
        "chain_memory_base": "original_memory_baseline",
        "chain_write_value": "none_write_policy_only",
        "chain_tri_retrieval": "tri_retrieval.fused_ids",
        "chain_graph_retrieval": "graph_retrieval.graph_fused_ids",
        "chain_rerank_injection": "injection_governance.experimental_injected_ids",
        "chain_version_provenance": "version_chain.active_leaf_ids",
        "chain_sleep_consolidation": "sleep_consolidation.filtered_active_ids",
        "chain_all_on": "sleep_consolidation.filtered_active_ids",
    }
    if profile_name not in sources:
        raise ValueError(f"unknown profile_name: {profile_name}")
    return sources[profile_name]


def build_comprehensive_run_specs(
    cases: Sequence[EvalCase],
    *,
    repeats: int,
    prompt_variants: Sequence[str],
    profiles: Sequence[str],
) -> tuple[ComprehensiveRunSpec, ...]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    valid_variants = {"baseline", "coached"}
    invalid_variants = [
        variant for variant in prompt_variants if variant not in valid_variants
    ]
    if invalid_variants:
        raise ValueError("unknown prompt_variant(s): " + ", ".join(invalid_variants))
    invalid_profiles = [
        profile for profile in profiles if profile not in COMPREHENSIVE_CHAIN_PROFILES
    ]
    if invalid_profiles:
        raise ValueError("unknown profile_name(s): " + ", ".join(invalid_profiles))
    answer_cases = [
        case
        for case in cases
        if isinstance(case.expectations.get("answer_expectations"), dict)
    ]
    specs: list[ComprehensiveRunSpec] = []
    for case in answer_cases:
        for repeat_index in range(repeats):
            for prompt_variant in prompt_variants:
                for profile_name in profiles:
                    specs.append(
                        ComprehensiveRunSpec(
                            case=case,
                            profile_name=profile_name,
                            prompt_variant=prompt_variant,
                            repeat_index=repeat_index,
                        )
                    )
    return tuple(specs)


async def run_comprehensive_online_eval(
    specs: Sequence[ComprehensiveRunSpec],
    workspace: Path,
    provider: object,
    model: str,
    *,
    timeout_s: float = 60.0,
    real_llm_enabled: bool = False,
    answer_debug_dir: Path | None = None,
    real_memory_sample_metrics: dict[str, object] | None = None,
    checkpoint_jsonl: Path | None = None,
    resume: bool = False,
    concurrency: int = 1,
) -> ComprehensiveOnlineReport:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    workspace.mkdir(parents=True, exist_ok=True)
    existing = (
        _load_checkpoint_results(checkpoint_jsonl, include_infra_failures=False)
        if resume
        else {}
    )
    results: list[ComprehensiveCaseResult] = list(existing.values())
    skipped = 0
    pending: list[tuple[int, ComprehensiveRunSpec, str]] = []
    for index, spec in enumerate(specs):
        key = _spec_key(spec)
        if key in existing:
            skipped += 1
            continue
        pending.append((index, spec, key))

    if concurrency == 1:
        for index, spec, key in pending:
            result = await _run_comprehensive_case(
                spec,
                workspace
                / f"case-{index:04d}-{_safe_name(spec.profile_name)}-{_safe_name(spec.prompt_variant)}-{_safe_name(spec.case.id)}",
                provider,
                model,
                timeout_s=timeout_s,
                case_index=index,
                answer_debug_dir=answer_debug_dir,
            )
            results.append(result)
            _append_checkpoint_result(checkpoint_jsonl, key, result)
    else:
        semaphore = asyncio.Semaphore(concurrency)

        async def run_pending(
            index: int,
            pending_spec: ComprehensiveRunSpec,
            pending_key: str,
        ) -> tuple[str, ComprehensiveCaseResult]:
            async with semaphore:
                return (
                    pending_key,
                    await _run_comprehensive_case(
                        pending_spec,
                        workspace
                        / f"case-{index:04d}-{_safe_name(pending_spec.profile_name)}-{_safe_name(pending_spec.prompt_variant)}-{_safe_name(pending_spec.case.id)}",
                        provider,
                        model,
                        timeout_s=timeout_s,
                        case_index=index,
                        answer_debug_dir=answer_debug_dir,
                    ),
                )

        tasks = [
            asyncio.create_task(run_pending(index, spec, key))
            for index, spec, key in pending
        ]
        for task in asyncio.as_completed(tasks):
            key, result = await task
            results.append(result)
            _append_checkpoint_result(checkpoint_jsonl, key, result)
    return _build_comprehensive_report(
        tuple(results),
        real_llm_enabled=real_llm_enabled,
        completed_call_count=len(results),
        skipped_from_checkpoint_count=skipped,
        real_memory_sample_metrics=real_memory_sample_metrics or {},
        concurrency=concurrency,
    )


def build_gated_comprehensive_online_report(
    reason: str,
    *,
    real_memory_sample_metrics: dict[str, object] | None = None,
) -> ComprehensiveOnlineReport:
    metrics = _empty_metrics(real_memory_sample_metrics or {})
    metrics["gate_reason"] = reason
    return ComprehensiveOnlineReport(
        run_id=_deterministic_run_id(()),
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        cases=(),
        case_records=(),
        failure_records=({"case_id": "", "failure": reason},),
        metrics=metrics,
    )


def build_comprehensive_online_report_from_checkpoint(
    checkpoint_jsonl: Path,
    *,
    real_llm_enabled: bool,
    exclude_infra_failures: bool = False,
    real_memory_sample_metrics: dict[str, object] | None = None,
) -> ComprehensiveOnlineReport:
    rows = _load_checkpoint_rows(checkpoint_jsonl)
    input_count = len(rows)
    loaded = _checkpoint_results_from_rows(rows, include_infra_failures=True)
    results = tuple(loaded.values())
    excluded = 0
    if exclude_infra_failures:
        excluded = sum(
            1 for _key, result in rows if result.timeout or result.provider_error
        )
        kept: dict[str, ComprehensiveCaseResult] = {}
        for key, result in rows:
            if result.timeout or result.provider_error:
                continue
            kept[key] = result
        results = tuple(kept.values())
    report = _build_comprehensive_report(
        results,
        real_llm_enabled=real_llm_enabled,
        completed_call_count=len(results),
        skipped_from_checkpoint_count=0,
        real_memory_sample_metrics=real_memory_sample_metrics or {},
    )
    report.metrics["checkpoint_input_count"] = input_count
    report.metrics["excluded_infra_failure_count"] = excluded
    report.metrics["partial_due_to_infra_failure"] = bool(excluded)
    report.metrics["checkpoint_report_only"] = True
    report.metrics["concurrency"] = "checkpoint_report_only"
    return report


def write_comprehensive_online_json(
    report: ComprehensiveOnlineReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _report_to_dict(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def write_comprehensive_online_markdown(
    report: ComprehensiveOnlineReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = report.metrics
    lines = [
        "# Memory 综合线上评测报告",
        "",
        "本报告使用真实 AgentLoop 的 answer-level 评测链路；如开启真实 LLM，则会记录真实模型回答的规则命中、记忆 grounding、token 和延迟。它不是生产回答准确率。",
        "",
        "## 边界",
        "",
        "- 常规报告不包含原始 query、memory summary、prompt、session 原文或完整回答。",
        "- 真实 memory DB 只读采样只进入聚合指标，不写样本正文。",
        "- 主表使用 answer、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。",
        "",
        "## 总览",
        "",
    ]
    for key in (
        "evaluation_level",
        "real_llm_enabled",
        "case_count",
        "unique_case_count",
        "completed_call_count",
        "skipped_from_checkpoint_count",
        "checkpoint_input_count",
        "excluded_infra_failure_count",
        "partial_due_to_infra_failure",
        "checkpoint_report_only",
        "concurrency",
        "profile_count",
        "prompt_variant_count",
        "repeat_count",
        "answer_rule_pass_rate",
        "memory_grounding_pass_rate",
        "forbidden_violation_rate",
        "avg_latency_ms",
        "total_token_count",
        "avg_total_token_count",
    ):
        lines.append(f"- `{key}`: `{metrics.get(key, 'unavailable')}`")
    if metrics.get("checkpoint_report_only"):
        lines.extend(
            [
                "",
                "## Checkpoint Report Notes",
                "",
                "- 本报告由 checkpoint 重建，没有继续发起新的 LLM 调用。",
                "- `case_count` 只统计进入最终评分的有效样本。",
                "- `checkpoint_input_count` 是 checkpoint 原始条数，`excluded_infra_failure_count` 是被排除的 timeout / provider error 条数。",
                "- 如果 `partial_due_to_infra_failure = True`，只能视为部分真实线上评测，不能视为完整 2560-run 结论。",
            ]
        )
    lines.extend(["", "## Profile Summary", ""])
    profile_summaries = metrics.get("profile_summaries", {})
    if isinstance(profile_summaries, dict):
        lines.extend(
            [
                "| profile | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for profile in COMPREHENSIVE_CHAIN_PROFILES:
            summary = profile_summaries.get(profile)
            if not isinstance(summary, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        profile,
                        _fmt(summary.get("case_count")),
                        _fmt(summary.get("answer_success_count")),
                        _fmt(summary.get("grounding_success_count")),
                        _fmt(summary.get("forbidden_case_count")),
                        _fmt(summary.get("answer_rule_pass_rate")),
                        _fmt(summary.get("memory_grounding_pass_rate")),
                        _fmt(summary.get("forbidden_violation_rate")),
                        _fmt(summary.get("avg_total_token_count")),
                    ]
                )
                + " |"
            )
        control = profile_summaries.get("chain_off")
        if isinstance(control, dict):
            lines.extend(
                [
                    "",
                    "## Disabled Enhancement Control",
                    "",
                    "| control | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                    "| "
                    + " | ".join(
                        [
                            "chain_off",
                            _fmt(control.get("case_count")),
                            _fmt(control.get("answer_success_count")),
                            _fmt(control.get("grounding_success_count")),
                            _fmt(control.get("forbidden_case_count")),
                            _fmt(control.get("answer_rule_pass_rate")),
                            _fmt(control.get("memory_grounding_pass_rate")),
                            _fmt(control.get("forbidden_violation_rate")),
                            _fmt(control.get("avg_total_token_count")),
                        ]
                    )
                    + " |",
                ]
            )
    lines.extend(
        [
            "",
            "## 原始评分字段",
            "",
            "- `main_score`、profile uplift 和 online balanced proxy 保留在 JSON 输出中以兼容既有消费者，不作为本报告主表的解释口径。",
        ]
    )
    lines.extend(["", "## Metric Sources", ""])
    for key, value in METRIC_SOURCES.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Real Memory Readonly Sampling", ""])
    real_memory = metrics.get("real_memory_sample_metrics", {})
    if isinstance(real_memory, dict):
        for key in sorted(real_memory):
            lines.append(f"- `{key}`: `{real_memory[key]}`")
    lines.extend(["", "## 结论", ""])
    lines.append(
        "- 如果某个中后段 profile 的 answer-level 增益不明显，需要结合 offline retrieval proxy 和 online balanced proxy 看治理、证据和效率价值。"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run_comprehensive_case(
    spec: ComprehensiveRunSpec,
    workspace: Path,
    provider: object,
    model: str,
    *,
    timeout_s: float,
    case_index: int,
    answer_debug_dir: Path | None,
) -> ComprehensiveCaseResult:
    workspace.mkdir(parents=True, exist_ok=True)
    memory = ComprehensiveOnlineMemoryEngine(
        spec.case,
        profile_name=spec.profile_name,
        prompt_variant=spec.prompt_variant,
    )
    recording_provider = _RecordingProvider(provider)
    event_bus = EventBus()
    session_manager = SessionManager(workspace)
    tools = ToolRegistry()
    loop = AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=recording_provider,  # type: ignore[arg-type]
            light_provider=recording_provider,  # type: ignore[arg-type]
            tools=tools,
            session_manager=session_manager,
            workspace=workspace,
            event_bus=event_bus,
            memory_services=MemoryServices(engine=memory),  # type: ignore[arg-type]
        ),
        AgentLoopConfig(llm=LLMConfig(model=model, max_iterations=2)),
    )
    scope = _scope(spec.case)
    query = _query(spec.case)
    started = time.perf_counter()
    answer = ""
    provider_error = False
    timeout = False
    failures: list[str] = []
    try:
        answer = await asyncio.wait_for(
            loop.process_direct(
                query,
                session_key=scope["session_key"],
                channel=scope["channel"],
                chat_id=scope["chat_id"],
                skip_post_memory=True,
            ),
            timeout=max(0.001, float(timeout_s)),
        )
        await event_bus.drain()
    except TimeoutError:
        timeout = True
        failures.append("timeout")
    except Exception:
        provider_error = True
        failures.append("provider_error")
    finally:
        await event_bus.aclose()
    latency_ms = int((time.perf_counter() - started) * 1000)
    if recording_provider.errors and not provider_error:
        provider_error = True
        failures.append("provider_error")

    score = score_answer_text(
        answer,
        answer_expectation_from_case(spec.case),
        memory.used_memory_ids,
    )
    failures.extend(score.failures)
    token_counts = _extract_token_counts(
        recording_provider.responses[-1] if recording_provider.responses else None
    )
    result = ComprehensiveCaseResult(
        case_id=spec.case.id,
        category=spec.case.category,
        profile_name=spec.profile_name,
        prompt_variant=spec.prompt_variant,
        repeat_index=spec.repeat_index,
        passed=not failures,
        answer_rule_passed=score.answer_rule_passed,
        memory_grounding_passed=score.memory_grounding_passed,
        expected_memory_used=score.expected_memory_used,
        forbidden_contains_violation_count=score.forbidden_contains_violation_count,
        latency_ms=latency_ms,
        prompt_token_count=int(token_counts["prompt_token_count"]),
        completion_token_count=int(token_counts["completion_token_count"]),
        total_token_count=int(token_counts["total_token_count"]),
        token_metrics_available=bool(token_counts["token_metrics_available"]),
        provider_error=provider_error,
        timeout=timeout,
        answer_length=len(answer),
        evidence_source=profile_evidence_source(spec.profile_name),
        used_memory_id_count=len(memory.used_memory_ids),
        failures=tuple(failures),
    )
    if answer_debug_dir is not None:
        write_llm_sample_answer_debug(
            LLMSampleAnswerDebugRecord(
                case_id=spec.case.id,
                case_index=case_index,
                prompt_variant=f"{spec.profile_name}-{spec.prompt_variant}",
                session_key=scope["session_key"],
                evidence_block_text=memory.last_text_block,
                answer_text=answer,
                answer_length=len(answer),
                used_memory_ids=tuple(memory.used_memory_ids),
                matched_expected_terms=score.matched_expected_terms,
                missing_expected_terms=score.missing_expected_terms,
                matched_any_groups=score.matched_any_groups,
                missing_any_groups=score.missing_any_groups,
                failures=tuple(failures),
                answer_rule_passed=score.answer_rule_passed,
                memory_grounding_passed=score.memory_grounding_passed,
            ),
            answer_debug_dir
            / f"{case_index:04d}-{_safe_name(spec.profile_name)}-{_safe_name(spec.prompt_variant)}-{_safe_name(spec.case.id)}.json",
        )
    return result


def _build_comprehensive_report(
    results: tuple[ComprehensiveCaseResult, ...],
    *,
    real_llm_enabled: bool,
    completed_call_count: int,
    skipped_from_checkpoint_count: int,
    real_memory_sample_metrics: dict[str, object],
    concurrency: int = 1,
) -> ComprehensiveOnlineReport:
    metrics = _metrics_from_results(
        results,
        real_llm_enabled=real_llm_enabled,
        completed_call_count=completed_call_count,
        skipped_from_checkpoint_count=skipped_from_checkpoint_count,
        real_memory_sample_metrics=real_memory_sample_metrics,
        concurrency=concurrency,
    )
    return ComprehensiveOnlineReport(
        run_id=_deterministic_run_id(results),
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        cases=results,
        case_records=tuple(_case_record(result) for result in results),
        failure_records=_failure_records(results),
        metrics=metrics,
    )


def _metrics_from_results(
    results: tuple[ComprehensiveCaseResult, ...],
    *,
    real_llm_enabled: bool,
    completed_call_count: int,
    skipped_from_checkpoint_count: int,
    real_memory_sample_metrics: dict[str, object],
    concurrency: int = 1,
) -> dict[str, object]:
    count = len(results)
    profiles = _profiles_in_order(results)
    variants = sorted({result.prompt_variant for result in results})
    profile_summaries = _profile_summaries(results, profiles)
    uplift = _profile_uplift_vs_memory_base(profile_summaries)
    adjacent = _chain_adjacent_uplift(profile_summaries)
    return {
        "evaluation_level": "comprehensive_online_agentloop",
        "real_llm_enabled": real_llm_enabled,
        "case_count": count,
        "unique_case_count": len({result.case_id for result in results}),
        "completed_call_count": completed_call_count,
        "skipped_from_checkpoint_count": skipped_from_checkpoint_count,
        "concurrency": concurrency,
        "infra_passed": bool(results)
        and all(not result.provider_error and not result.timeout for result in results),
        "answer_quality_passed": bool(results) and all(result.passed for result in results),
        "profile_count": len(profiles),
        "prompt_variant_count": len(variants),
        "repeat_count": max((result.repeat_index for result in results), default=-1) + 1,
        "passed_case_count": sum(1 for result in results if result.passed),
        "failed_answer_case_count": sum(
            1
            for result in results
            if not result.answer_rule_passed and not result.provider_error and not result.timeout
        ),
        "provider_error_count": sum(1 for result in results if result.provider_error),
        "timeout_count": sum(1 for result in results if result.timeout),
        "answer_rule_pass_rate": _rate(
            sum(1 for result in results if result.answer_rule_passed),
            count,
        ),
        "memory_grounding_pass_rate": _rate(
            sum(1 for result in results if result.memory_grounding_passed),
            count,
        ),
        "forbidden_violation_rate": _rate(
            sum(1 for result in results if result.forbidden_contains_violation_count > 0),
            count,
        ),
        "avg_latency_ms": _avg(result.latency_ms for result in results),
        "total_token_count": sum(result.total_token_count for result in results),
        "avg_total_token_count": _avg(result.total_token_count for result in results),
        "token_metrics_available": any(result.token_metrics_available for result in results),
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "session_text_included": False,
        "full_answer_included": False,
        "profile_summaries": profile_summaries,
        "baseline_profile": "chain_memory_base",
        "control_profile": "chain_off",
        "profile_uplift_vs_memory_base": uplift,
        "profile_uplift_vs_off": _profile_uplift_vs_off(profile_summaries),
        "chain_adjacent_uplift": adjacent,
        "online_balanced_proxy_summaries": _online_balanced_proxy_summaries(
            profile_summaries,
        ),
        "metric_sources": dict(METRIC_SOURCES),
        "real_memory_sample_metrics": real_memory_sample_metrics,
    }


def _empty_metrics(real_memory_sample_metrics: dict[str, object]) -> dict[str, object]:
    return {
        "evaluation_level": "comprehensive_online_agentloop",
        "real_llm_enabled": False,
        "case_count": 0,
        "unique_case_count": 0,
        "completed_call_count": 0,
        "skipped_from_checkpoint_count": 0,
        "concurrency": 1,
        "infra_passed": False,
        "answer_quality_passed": False,
        "profile_count": 0,
        "prompt_variant_count": 0,
        "repeat_count": 0,
        "passed_case_count": 0,
        "failed_answer_case_count": 0,
        "provider_error_count": 0,
        "timeout_count": 0,
        "answer_rule_pass_rate": 0.0,
        "memory_grounding_pass_rate": 0.0,
        "forbidden_violation_rate": 0.0,
        "avg_latency_ms": 0.0,
        "total_token_count": 0,
        "avg_total_token_count": 0.0,
        "token_metrics_available": False,
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "session_text_included": False,
        "full_answer_included": False,
        "profile_summaries": {},
        "baseline_profile": "chain_memory_base",
        "control_profile": "chain_off",
        "profile_uplift_vs_memory_base": {},
        "profile_uplift_vs_off": {},
        "chain_adjacent_uplift": {},
        "online_balanced_proxy_summaries": {},
        "metric_sources": dict(METRIC_SOURCES),
        "real_memory_sample_metrics": real_memory_sample_metrics,
    }


def _profile_summaries(
    results: tuple[ComprehensiveCaseResult, ...],
    profiles: tuple[str, ...],
) -> dict[str, dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    for profile in profiles:
        rows = [result for result in results if result.profile_name == profile]
        count = len(rows)
        answer = _rate(sum(1 for row in rows if row.answer_rule_passed), count)
        grounding = _rate(sum(1 for row in rows if row.memory_grounding_passed), count)
        forbidden = _rate(
            sum(1 for row in rows if row.forbidden_contains_violation_count > 0),
            count,
        )
        summaries[profile] = {
            "case_count": count,
            "answer_success_count": sum(
                1 for row in rows if row.answer_rule_passed
            ),
            "grounding_success_count": sum(
                1 for row in rows if row.memory_grounding_passed
            ),
            "forbidden_case_count": sum(
                1
                for row in rows
                if row.forbidden_contains_violation_count > 0
            ),
            "answer_rule_pass_rate": answer,
            "memory_grounding_pass_rate": grounding,
            "forbidden_violation_rate": forbidden,
            "main_score": calculate_main_score(
                answer_rule_pass_rate=answer,
                memory_grounding_pass_rate=grounding,
                forbidden_violation_rate=forbidden,
            ),
            "avg_latency_ms": _avg(row.latency_ms for row in rows),
            "avg_total_token_count": _avg(row.total_token_count for row in rows),
            "token_metrics_available": any(row.token_metrics_available for row in rows),
            "evidence_source": profile_evidence_source(profile),
        }
    return summaries


def _profile_uplift_vs_off(
    summaries: dict[str, dict[str, object]],
) -> dict[str, float | str]:
    off = summaries.get("chain_off")
    if not off:
        return {profile: "unavailable" for profile in summaries}
    baseline = float(off["main_score"])
    return {
        profile: round(float(summary["main_score"]) - baseline, 4)
        for profile, summary in summaries.items()
    }


def _profile_uplift_vs_memory_base(
    summaries: dict[str, dict[str, object]],
) -> dict[str, float | str]:
    baseline_row = summaries.get("chain_memory_base")
    if not baseline_row:
        return {profile: "unavailable" for profile in summaries}
    baseline = float(baseline_row["main_score"])
    return {
        profile: round(float(summary["main_score"]) - baseline, 4)
        for profile, summary in summaries.items()
    }


def _chain_adjacent_uplift(
    summaries: dict[str, dict[str, object]],
) -> dict[str, float | str]:
    result: dict[str, float | str] = {}
    previous_score: float | None = None
    for profile in COMPREHENSIVE_CHAIN_PROFILES:
        summary = summaries.get(profile)
        if summary is None:
            continue
        current_score = float(summary["main_score"])
        result[profile] = (
            0.0 if previous_score is None else round(current_score - previous_score, 4)
        )
        previous_score = current_score
    return result


def _online_balanced_proxy_summaries(
    summaries: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    off_tokens = _first_summary_value(summaries, "chain_off", "avg_total_token_count")
    result: dict[str, dict[str, object]] = {}
    previous_score: float | None = None
    for profile in COMPREHENSIVE_CHAIN_PROFILES:
        summary = summaries.get(profile)
        if summary is None:
            continue
        current_tokens = summary.get("avg_total_token_count")
        token_signal_value: float | str = "unavailable"
        token_signal_kind = "unavailable"
        if isinstance(current_tokens, (int, float)) and isinstance(off_tokens, (int, float)):
            token_signal_kind = "prompt_token_delta"
            token_signal_value = round(float(current_tokens) - float(off_tokens), 4)
        row = QuantitativeProfileSummary(
            profile_name=profile,
            feature_name=profile,
            case_set="overall",
            case_count=int(summary["case_count"]),
            target_count=int(summary["case_count"]),
            success_count=int(
                round(
                    float(summary["answer_rule_pass_rate"])
                    / 100.0
                    * int(summary["case_count"])
                )
            ),
            miss_count=max(
                0,
                int(summary["case_count"])
                - int(
                    round(
                        float(summary["answer_rule_pass_rate"])
                        / 100.0
                        * int(summary["case_count"])
                    )
                ),
            ),
            recall_rate=float(summary["answer_rule_pass_rate"]),
            grounding_count=int(
                round(
                    float(summary["memory_grounding_pass_rate"])
                    / 100.0
                    * int(summary["case_count"])
                )
            ),
            forbidden_count=int(
                round(
                    float(summary["forbidden_violation_rate"])
                    / 100.0
                    * int(summary["case_count"])
                )
            ),
            repeat_count=1,
            answer_rule_pass_rate=float(summary["answer_rule_pass_rate"]),
            memory_grounding_pass_rate=float(summary["memory_grounding_pass_rate"]),
            forbidden_violation_rate=float(summary["forbidden_violation_rate"]),
            main_score=float(summary["main_score"]),
            baseline_score=0.0,
            uplift_points=0.0,
            uplift_pct=None,
            token_signal_kind=token_signal_kind,
            token_signal_value=token_signal_value,
            token_signal_delta="unavailable",
            latency_ms=summary.get("avg_latency_ms", "unavailable"),
            latency_delta_ms="unavailable",
            unavailable=(),
        )
        scores = calculate_balanced_scores(row)
        balanced = float(scores["balanced_score"])
        result[profile] = {
            "metric_source": "online_balanced_proxy",
            "answer_derived_retrieval_proxy_score": scores["retrieval_proxy_score"],
            "answer_score": scores["answer_score"],
            "grounding_score": scores["grounding_score"],
            "governance_score": scores["governance_score"],
            "efficiency_score": scores["efficiency_score"],
            "online_balanced_proxy_score": balanced,
            "online_balanced_proxy_delta": (
                0.0
                if previous_score is None
                else round(balanced - previous_score, 4)
            ),
            "available_dimensions": scores["balanced_score_available_dimensions"],
            "unavailable_dimensions": scores["unavailable_dimensions"],
            "formula": BALANCED_SCORE_FORMULA,
        }
        previous_score = balanced
    return result


def _ids_from_trace(case: EvalCase, family_name: str, key: str) -> tuple[str, ...]:
    trace = _family_trace_for_case(case, family_name)
    if trace is None:
        return ()
    raw_ids = trace.experimental_result.get(key, [])
    if not isinstance(raw_ids, (list, tuple)):
        return ()
    return _dedupe_ids(str(item) for item in raw_ids if str(item))


def _sleep_filtered_ids(case: EvalCase) -> tuple[str, ...]:
    base_ids = list(_ids_from_trace(case, "graph_retrieval", "graph_fused_ids"))
    if not base_ids:
        base_ids = list(_ids_from_trace(case, "version_chain_shadow", "active_leaf_ids"))
    sleep = _family_trace_for_case(case, "sleep_consolidation_shadow")
    if sleep is None:
        return tuple(base_ids)
    experimental = sleep.experimental_result
    stale = set(str(item) for item in experimental.get("stale_candidate_ids", []))
    low_value = set(
        str(item) for item in experimental.get("low_value_candidate_ids", [])
    )
    duplicate_ids = {
        str(item_id)
        for group in experimental.get("duplicate_groups", [])
        if isinstance(group, dict)
        for item_id in group.get("item_ids", [])
    }
    protected = {str(item) for item in case.expectations.get("should_recall_ids", [])}
    drop_ids = stale | low_value | duplicate_ids
    return tuple(
        item_id
        for item_id in base_ids
        if item_id not in drop_ids or item_id in protected
    )


def _dedupe_ids(ids: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    for item_id in ids:
        if item_id and item_id not in result:
            result.append(item_id)
    return tuple(result)


def _case_record(result: ComprehensiveCaseResult) -> dict[str, object]:
    return {
        "case_id": result.case_id,
        "category": result.category,
        "profile_name": result.profile_name,
        "prompt_variant": result.prompt_variant,
        "repeat_index": result.repeat_index,
        "passed": result.passed,
        "answer_rule_passed": result.answer_rule_passed,
        "memory_grounding_passed": result.memory_grounding_passed,
        "expected_memory_used": result.expected_memory_used,
        "forbidden_contains_violation_count": result.forbidden_contains_violation_count,
        "latency_ms": result.latency_ms,
        "prompt_token_count": result.prompt_token_count,
        "completion_token_count": result.completion_token_count,
        "total_token_count": result.total_token_count,
        "token_metrics_available": result.token_metrics_available,
        "provider_error": result.provider_error,
        "timeout": result.timeout,
        "answer_length": result.answer_length,
        "evidence_source": result.evidence_source,
        "used_memory_id_count": result.used_memory_id_count,
        "failures": [_sanitize_failure(failure) for failure in result.failures],
    }


def _failure_records(
    results: tuple[ComprehensiveCaseResult, ...],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for result in results:
        for failure in result.failures:
            records.append(
                {
                    "case_id": result.case_id,
                    "profile_name": result.profile_name,
                    "prompt_variant": result.prompt_variant,
                    "repeat_index": result.repeat_index,
                    "failure": _sanitize_failure(failure),
                }
            )
    return tuple(records)


def _report_to_dict(report: ComprehensiveOnlineReport) -> dict[str, object]:
    return {
        "passed": report.passed,
        "run_id": report.run_id,
        "generated_at": report.generated_at,
        "metrics": report.metrics,
        "case_records": list(report.case_records),
        "failure_records": list(report.failure_records),
    }


def _load_checkpoint_rows(
    path: Path | None,
) -> tuple[tuple[str, ComprehensiveCaseResult], ...]:
    if path is None or not path.exists():
        return ()
    rows: list[tuple[str, ComprehensiveCaseResult]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        key = str(payload.get("spec_key") or "")
        result_payload = payload.get("result")
        if key and isinstance(result_payload, dict):
            rows.append(
                (
                    key,
                    ComprehensiveCaseResult(
                        **{
                            **result_payload,
                            "failures": tuple(result_payload.get("failures", [])),
                        }
                    ),
                )
            )
    return tuple(rows)


def _checkpoint_results_from_rows(
    rows: Sequence[tuple[str, ComprehensiveCaseResult]],
    *,
    include_infra_failures: bool,
) -> dict[str, ComprehensiveCaseResult]:
    results: dict[str, ComprehensiveCaseResult] = {}
    for key, result in rows:
        if not include_infra_failures and (result.provider_error or result.timeout):
            continue
        results[key] = result
    return results


def _load_checkpoint_results(
    path: Path | None,
    *,
    include_infra_failures: bool = True,
) -> dict[str, ComprehensiveCaseResult]:
    return _checkpoint_results_from_rows(
        _load_checkpoint_rows(path),
        include_infra_failures=include_infra_failures,
    )


def _append_checkpoint_result(
    path: Path | None,
    spec_key: str,
    result: ComprehensiveCaseResult,
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {"spec_key": spec_key, "result": _case_record(result)},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


def _spec_key(spec: ComprehensiveRunSpec) -> str:
    return "|".join(
        [
            spec.case.id,
            spec.profile_name,
            spec.prompt_variant,
            str(spec.repeat_index),
        ]
    )


def _deterministic_run_id(results: Sequence[ComprehensiveCaseResult]) -> str:
    seed = "|".join(
        f"{result.case_id}:{result.profile_name}:{result.prompt_variant}:{result.repeat_index}"
        for result in results
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _profiles_in_order(results: tuple[ComprehensiveCaseResult, ...]) -> tuple[str, ...]:
    seen = {result.profile_name for result in results}
    return tuple(profile for profile in COMPREHENSIVE_CHAIN_PROFILES if profile in seen)


def _first_summary_value(
    summaries: dict[str, dict[str, object]],
    profile: str,
    key: str,
) -> object:
    summary = summaries.get(profile)
    return summary.get(key) if summary else "unavailable"


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100.0, 4)


def _avg(values: Any) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value) or "unknown"


def _sanitize_failure(failure: str) -> str:
    if failure.startswith("missing expected answer term group:"):
        return "missing_expected_answer_term_group"
    if failure.startswith("missing expected answer term:"):
        return "missing_expected_answer_term"
    if failure.startswith("found forbidden answer term:"):
        return "found_forbidden_answer_term"
    if failure.startswith("missing expected memory ids:"):
        return "missing_expected_memory_ids"
    return failure


def _fmt(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)
