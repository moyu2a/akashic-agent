from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock

from agent.looping.core import AgentLoop
from agent.looping.ports import AgentLoopConfig, AgentLoopDeps, LLMConfig, MemoryServices
from agent.provider import LLMResponse
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
from session.manager import SessionManager


_CJK_RE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class AnswerExpectation:
    expected_answer_contains: tuple[str, ...] = ()
    expected_answer_contains_any: tuple[tuple[str, ...], ...] = ()
    forbidden_answer_contains: tuple[str, ...] = ()
    expected_memory_ids: tuple[str, ...] = ()
    expected_language: str = ""
    grounding_required: bool = False


@dataclass(frozen=True)
class AnswerScoreResult:
    passed: bool
    answer_rule_passed: bool
    memory_grounding_passed: bool
    expected_contains_pass_count: int
    expected_contains_miss_count: int
    expected_any_pass_count: int
    expected_any_miss_count: int
    forbidden_contains_violation_count: int
    expected_memory_used: bool
    language_passed: bool
    failures: tuple[str, ...]
    matched_expected_terms: tuple[str, ...]
    missing_expected_terms: tuple[str, ...]
    matched_any_groups: tuple[tuple[str, ...], ...]
    missing_any_groups: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class LLMSampleRunSpec:
    case: EvalCase
    prompt_variant: str = "baseline"
    repeat_index: int = 0


@dataclass(frozen=True)
class LLMSampleAnswerDebugRecord:
    case_id: str
    case_index: int
    prompt_variant: str
    session_key: str
    evidence_block_text: str
    answer_text: str
    answer_length: int
    used_memory_ids: tuple[str, ...]
    matched_expected_terms: tuple[str, ...]
    missing_expected_terms: tuple[str, ...]
    matched_any_groups: tuple[tuple[str, ...], ...]
    missing_any_groups: tuple[tuple[str, ...], ...]
    failures: tuple[str, ...]
    answer_rule_passed: bool
    memory_grounding_passed: bool


@dataclass(frozen=True)
class LLMSampleCaseResult:
    case_id: str
    prompt_variant: str
    repeat_index: int
    category: str
    session_key: str
    channel: str
    chat_id: str
    passed: bool
    answer_length: int
    latency_ms: int
    expected_memory_used: bool
    expected_contains_pass_count: int
    expected_contains_miss_count: int
    forbidden_contains_violation_count: int
    language_passed: bool
    prompt_token_count: int
    completion_token_count: int
    total_token_count: int
    token_metrics_available: bool
    answer_rule_passed: bool
    memory_grounding_passed: bool
    provider_error: bool
    timeout: bool
    used_memory_ids: tuple[str, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class LLMSampleReport:
    cases: tuple[LLMSampleCaseResult, ...]
    metrics: dict[str, object]
    case_records: tuple[dict[str, object], ...]
    failure_records: tuple[dict[str, object], ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)


class LLMSampleMemoryEngine:
    """Memory engine for answer-quality evals. Reports only ids, never summaries."""

    def __init__(self, case: EvalCase, *, prompt_variant: str = "baseline") -> None:
        if prompt_variant not in {"baseline", "coached"}:
            raise ValueError("prompt_variant must be 'baseline' or 'coached'")
        self.case = case
        self.prompt_variant = prompt_variant
        self.retrieve_requests: list[MemoryEngineRetrieveRequest] = []
        self.used_memory_ids: list[str] = []
        self.last_text_block = ""

    async def retrieve(
        self,
        request: MemoryEngineRetrieveRequest,
    ) -> MemoryEngineRetrieveResult:
        self.retrieve_requests.append(request)
        ids = list(answer_expectation_from_case(self.case).expected_memory_ids)
        summaries = _memory_summaries_by_id(self.case)
        self.used_memory_ids = ids
        hits = [
            MemoryHit(
                id=item_id,
                summary=summaries.get(item_id, ""),
                content=summaries.get(item_id, ""),
                score=1.0,
                source_ref="",
                engine_kind="llm_sample_eval",
                injected=True,
            )
            for item_id in ids
        ]
        lines = [
            f"- memory_id={item_id}; summary={summaries.get(item_id, '')}"
            for item_id in ids
        ]
        if self.prompt_variant == "coached":
            lines.insert(
                0,
                "记忆评测说明：请优先使用下列记忆回答；"
                "如果记忆包含具体方案名、排序方式、工具名或关键术语，"
                "请在答案中保留这些关键术语。",
            )
        block = "\n".join(lines)
        self.last_text_block = block
        return MemoryEngineRetrieveResult(
            text_block=block,
            hits=hits,
            raw={"ids": ids},
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
        return RememberResult(item_id="llm-sample-memory", actual_type=request.memory_type)

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


class _RecordingProvider:
    def __init__(self, provider: object) -> None:
        self.provider = provider
        self.responses: list[LLMResponse] = []
        self.errors: list[Exception] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        chat = getattr(self.provider, "chat")
        try:
            response = await chat(**kwargs)
        except Exception as exc:
            self.errors.append(exc)
            raise
        self.responses.append(response)
        return response


def answer_expectation_from_case(case: EvalCase) -> AnswerExpectation:
    raw = case.expectations.get("answer_expectations")
    if not isinstance(raw, dict):
        return AnswerExpectation()
    return AnswerExpectation(
        expected_answer_contains=_string_tuple(raw.get("expected_answer_contains")),
        expected_answer_contains_any=_string_groups(
            raw.get("expected_answer_contains_any")
        ),
        forbidden_answer_contains=_string_tuple(raw.get("forbidden_answer_contains")),
        expected_memory_ids=_string_tuple(raw.get("expected_memory_ids")),
        expected_language=str(raw.get("expected_language") or ""),
        grounding_required=bool(raw.get("grounding_required")),
    )


def score_answer_text(
    answer: str,
    expectation: AnswerExpectation,
    used_memory_ids: Sequence[str],
) -> AnswerScoreResult:
    failures: list[str] = []
    matched_expected_terms: list[str] = []
    missing_expected_terms: list[str] = []
    expected_pass_count = 0
    expected_miss_count = 0
    for term in expectation.expected_answer_contains:
        if _contains_term(answer, term):
            expected_pass_count += 1
            matched_expected_terms.append(term)
        else:
            expected_miss_count += 1
            missing_expected_terms.append(term)
            failures.append(f"missing expected answer term: {term}")

    matched_any_groups: list[tuple[str, ...]] = []
    missing_any_groups: list[tuple[str, ...]] = []
    expected_any_pass_count = 0
    expected_any_miss_count = 0
    for group in expectation.expected_answer_contains_any:
        if any(_contains_term(answer, term) for term in group):
            expected_any_pass_count += 1
            matched_any_groups.append(group)
        else:
            expected_any_miss_count += 1
            missing_any_groups.append(group)
            failures.append(
                "missing expected answer term group: " + "|".join(group)
            )

    forbidden_violation_count = 0
    for term in expectation.forbidden_answer_contains:
        if _contains_term(answer, term):
            forbidden_violation_count += 1
            failures.append(f"found forbidden answer term: {term}")

    used_ids = set(str(item_id) for item_id in used_memory_ids)
    missing_memory_ids = [
        item_id
        for item_id in expectation.expected_memory_ids
        if item_id not in used_ids
    ]
    expected_memory_used = not missing_memory_ids
    if missing_memory_ids:
        failures.append(f"missing expected memory ids: {','.join(missing_memory_ids)}")

    memory_grounding_passed = expected_memory_used
    language_passed = True
    if expectation.expected_language == "zh":
        language_passed = bool(_CJK_RE.search(answer))
        if not language_passed:
            failures.append("answer is not detected as Chinese")

    answer_rule_passed = (
        expected_miss_count == 0
        and expected_any_miss_count == 0
        and forbidden_violation_count == 0
        and language_passed
    )
    return AnswerScoreResult(
        passed=answer_rule_passed and memory_grounding_passed,
        answer_rule_passed=answer_rule_passed,
        memory_grounding_passed=memory_grounding_passed,
        expected_contains_pass_count=expected_pass_count,
        expected_contains_miss_count=expected_miss_count,
        expected_any_pass_count=expected_any_pass_count,
        expected_any_miss_count=expected_any_miss_count,
        forbidden_contains_violation_count=forbidden_violation_count,
        expected_memory_used=expected_memory_used,
        language_passed=language_passed,
        failures=tuple(failures),
        matched_expected_terms=tuple(matched_expected_terms),
        missing_expected_terms=tuple(missing_expected_terms),
        matched_any_groups=tuple(matched_any_groups),
        missing_any_groups=tuple(missing_any_groups),
    )


async def run_llm_sample_case(
    run: EvalCase | LLMSampleRunSpec,
    workspace: Path,
    provider: object,
    model: str,
    timeout_s: float = 60.0,
    *,
    case_index: int = 0,
    answer_debug_dir: Path | None = None,
) -> LLMSampleCaseResult:
    if isinstance(run, LLMSampleRunSpec):
        case = run.case
        prompt_variant = run.prompt_variant
        repeat_index = run.repeat_index
    else:
        case = run
        prompt_variant = "baseline"
        repeat_index = 0
    workspace.mkdir(parents=True, exist_ok=True)
    memory = LLMSampleMemoryEngine(case, prompt_variant=prompt_variant)
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
    scope = _scope(case)
    query = _query(case)
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
        answer_expectation_from_case(case),
        memory.used_memory_ids,
    )
    failures.extend(score.failures)
    token_counts = _extract_token_counts(
        recording_provider.responses[-1] if recording_provider.responses else None
    )
    result = LLMSampleCaseResult(
        case_id=case.id,
        prompt_variant=prompt_variant,
        repeat_index=repeat_index,
        category=case.category,
        session_key=scope["session_key"],
        channel=scope["channel"],
        chat_id=scope["chat_id"],
        passed=not failures,
        answer_length=len(answer),
        latency_ms=latency_ms,
        expected_memory_used=score.expected_memory_used,
        expected_contains_pass_count=score.expected_contains_pass_count,
        expected_contains_miss_count=score.expected_contains_miss_count,
        forbidden_contains_violation_count=score.forbidden_contains_violation_count,
        language_passed=score.language_passed,
        prompt_token_count=token_counts["prompt_token_count"],
        completion_token_count=token_counts["completion_token_count"],
        total_token_count=token_counts["total_token_count"],
        token_metrics_available=bool(token_counts["token_metrics_available"]),
        answer_rule_passed=score.answer_rule_passed,
        memory_grounding_passed=score.memory_grounding_passed,
        provider_error=provider_error,
        timeout=timeout,
        used_memory_ids=tuple(memory.used_memory_ids),
        failures=tuple(failures),
    )
    if answer_debug_dir is not None:
        write_llm_sample_answer_debug(
            LLMSampleAnswerDebugRecord(
                case_id=case.id,
                case_index=case_index,
                prompt_variant=prompt_variant,
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
            / f"{case_index:04d}-{_safe_debug_name(prompt_variant)}-{_safe_debug_name(case.id)}.json",
        )
    return result


async def run_llm_sample_cases(
    cases: Sequence[EvalCase | LLMSampleRunSpec],
    workspace: Path,
    provider: object,
    model: str,
    timeout_s: float = 60.0,
    real_llm_enabled: bool = False,
    *,
    answer_debug_dir: Path | None = None,
) -> LLMSampleReport:
    selected = [_coerce_run_spec(case) for case in cases]
    selected = [
        run
        for run in selected
        if isinstance(run.case.expectations.get("answer_expectations"), dict)
    ]
    results: list[LLMSampleCaseResult] = []
    for index, run in enumerate(selected):
        result = await run_llm_sample_case(
            run,
            workspace
            / f"case-{index:03d}-{_safe_debug_name(run.prompt_variant)}-{_safe_debug_name(run.case.id)}",
            provider,
            model,
            timeout_s=timeout_s,
            case_index=index,
            answer_debug_dir=answer_debug_dir,
        )
        results.append(result)
    return _build_llm_sample_report(tuple(results), real_llm_enabled=real_llm_enabled)


def write_llm_sample_answer_debug(
    record: LLMSampleAnswerDebugRecord,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": record.case_id,
        "case_index": record.case_index,
        "prompt_variant": record.prompt_variant,
        "session_key": record.session_key,
        "evidence_block_text": record.evidence_block_text,
        "answer_text": record.answer_text,
        "answer_length": record.answer_length,
        "used_memory_ids": list(record.used_memory_ids),
        "matched_expected_terms": list(record.matched_expected_terms),
        "missing_expected_terms": list(record.missing_expected_terms),
        "matched_any_groups": [list(group) for group in record.matched_any_groups],
        "missing_any_groups": [list(group) for group in record.missing_any_groups],
        "failures": list(record.failures),
        "answer_rule_passed": record.answer_rule_passed,
        "memory_grounding_passed": record.memory_grounding_passed,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_llm_sample_json(report: LLMSampleReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _llm_sample_report_to_dict(report),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def write_llm_sample_markdown(report: LLMSampleReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Memory Real LLM Small-Sample Evaluation Report",
        "",
        "本报告只记录答案质量指标、延迟、token 元数据和脱敏失败原因。",
        "报告不包含原始 query、memory summary、prompt、session 原文或完整回答。",
        "",
        "## Summary",
        "",
    ]
    for key in sorted(report.metrics):
        lines.append(f"- `{key}`: `{report.metrics[key]}`")
    lines.extend(["", "## Case Records", ""])
    for record in report.case_records:
        lines.append(
            f"- `{record['case_id']}`: "
            f"`{json.dumps(record, ensure_ascii=False, sort_keys=True)}`"
        )
    lines.extend(["", "## Failure Records", ""])
    for record in report.failure_records:
        lines.append(f"- `{json.dumps(record, ensure_ascii=False, sort_keys=True)}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_gated_llm_sample_report(reason: str) -> LLMSampleReport:
    metrics: dict[str, object] = {
        "phase6b_level": "real_llm_small_sample",
        "real_llm_enabled": False,
        "answer_quality_available": True,
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "session_text_included": False,
        "full_answer_included": False,
        "case_count": 0,
        "repeat_count": 0,
        "prompt_variant_mode": "baseline",
        "repeat_pass_rate": 0.0,
        "repeat_answer_rule_pass_rate": 0.0,
        "repeat_memory_grounding_pass_rate": 0.0,
        "pass_count_by_prompt_variant": {},
        "answer_rule_pass_count_by_prompt_variant": {},
        "memory_grounding_pass_count_by_prompt_variant": {},
        "passed_case_count": 0,
        "failed_case_count": 0,
        "answer_contains_pass_count": 0,
        "answer_contains_miss_count": 0,
        "forbidden_contains_violation_count": 0,
        "expected_memory_used_count": 0,
        "language_pass_count": 0,
        "provider_error_count": 0,
        "timeout_count": 0,
        "total_latency_ms": 0,
        "avg_latency_ms": 0,
        "prompt_token_count": 0,
        "completion_token_count": 0,
        "total_token_count": 0,
        "token_metrics_available": False,
        "gate_reason": reason,
    }
    return LLMSampleReport(
        cases=(),
        metrics=metrics,
        case_records=(),
        failure_records=({"case_id": "", "failure": reason},),
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value if str(item))


def _string_groups(value: Any) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list | tuple):
        return ()
    groups: list[tuple[str, ...]] = []
    for group in value:
        terms = _string_tuple(group)
        if terms:
            groups.append(terms)
    return tuple(groups)


def _coerce_run_spec(run: EvalCase | LLMSampleRunSpec) -> LLMSampleRunSpec:
    if isinstance(run, LLMSampleRunSpec):
        return run
    return LLMSampleRunSpec(case=run, prompt_variant="baseline", repeat_index=0)


def _contains_term(text: str, term: str) -> bool:
    if _CJK_RE.search(term):
        return term in text
    return term.lower() in text.lower()


def _safe_debug_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return safe or "unknown"


def _build_llm_sample_report(
    results: tuple[LLMSampleCaseResult, ...],
    *,
    real_llm_enabled: bool,
) -> LLMSampleReport:
    passed_count = sum(1 for result in results if result.passed)
    failed_count = len(results) - passed_count
    token_metrics_available = any(result.token_metrics_available for result in results)
    variant_order = _prompt_variants_in_order(results)
    repeat_count = _repeat_count(results)
    variant_mode = _prompt_variant_mode(variant_order)
    pass_by_variant = {
        variant: sum(
            1
            for result in results
            if result.prompt_variant == variant and result.passed
        )
        for variant in variant_order
    }
    answer_rule_by_variant = {
        variant: sum(
            1
            for result in results
            if result.prompt_variant == variant and result.answer_rule_passed
        )
        for variant in variant_order
    }
    memory_grounding_by_variant = {
        variant: sum(
            1
            for result in results
            if result.prompt_variant == variant and result.memory_grounding_passed
        )
        for variant in variant_order
    }
    metrics: dict[str, object] = {
        "phase6b_level": "real_llm_small_sample",
        "real_llm_enabled": real_llm_enabled,
        "answer_quality_available": True,
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "session_text_included": False,
        "full_answer_included": False,
        "case_count": len(results),
        "repeat_count": repeat_count,
        "prompt_variant_mode": variant_mode,
        "repeat_pass_rate": _rate(passed_count, len(results)),
        "repeat_answer_rule_pass_rate": _rate(
            sum(1 for result in results if result.answer_rule_passed),
            len(results),
        ),
        "repeat_memory_grounding_pass_rate": _rate(
            sum(1 for result in results if result.memory_grounding_passed),
            len(results),
        ),
        "pass_count_by_prompt_variant": pass_by_variant,
        "answer_rule_pass_count_by_prompt_variant": answer_rule_by_variant,
        "memory_grounding_pass_count_by_prompt_variant": memory_grounding_by_variant,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "answer_contains_pass_count": sum(
            result.expected_contains_pass_count for result in results
        ),
        "answer_contains_miss_count": sum(
            result.expected_contains_miss_count for result in results
        ),
        "forbidden_contains_violation_count": sum(
            result.forbidden_contains_violation_count for result in results
        ),
        "expected_memory_used_count": sum(
            1 for result in results if result.expected_memory_used
        ),
        "answer_rule_pass_count": sum(
            1 for result in results if result.answer_rule_passed
        ),
        "memory_grounding_pass_count": sum(
            1 for result in results if result.memory_grounding_passed
        ),
        "language_pass_count": sum(1 for result in results if result.language_passed),
        "provider_error_count": sum(1 for result in results if result.provider_error),
        "timeout_count": sum(1 for result in results if result.timeout),
        "total_latency_ms": sum(result.latency_ms for result in results),
        "avg_latency_ms": (
            sum(result.latency_ms for result in results) // len(results)
            if results
            else 0
        ),
        "prompt_token_count": sum(result.prompt_token_count for result in results),
        "completion_token_count": sum(
            result.completion_token_count for result in results
        ),
        "total_token_count": sum(result.total_token_count for result in results),
        "token_metrics_available": token_metrics_available,
    }
    return LLMSampleReport(
        cases=results,
        metrics=metrics,
        case_records=tuple(_llm_sample_case_record(result) for result in results),
        failure_records=_llm_sample_failure_records(results),
    )


def _llm_sample_case_record(result: LLMSampleCaseResult) -> dict[str, object]:
    return {
        "case_id": result.case_id,
        "prompt_variant": result.prompt_variant,
        "repeat_index": result.repeat_index,
        "category": result.category,
        "session_key": result.session_key,
        "channel": result.channel,
        "chat_id": result.chat_id,
        "passed": result.passed,
        "answer_length": result.answer_length,
        "latency_ms": result.latency_ms,
        "expected_memory_used": result.expected_memory_used,
        "memory_grounding_passed": result.memory_grounding_passed,
        "answer_rule_passed": result.answer_rule_passed,
        "expected_contains_pass_count": result.expected_contains_pass_count,
        "expected_contains_miss_count": result.expected_contains_miss_count,
        "forbidden_contains_violation_count": result.forbidden_contains_violation_count,
        "language_passed": result.language_passed,
        "prompt_token_count": result.prompt_token_count,
        "completion_token_count": result.completion_token_count,
        "total_token_count": result.total_token_count,
        "token_metrics_available": result.token_metrics_available,
        "provider_error": result.provider_error,
        "timeout": result.timeout,
        "used_memory_ids": list(result.used_memory_ids),
        "failures": list(result.failures),
    }


def _llm_sample_failure_records(
    results: tuple[LLMSampleCaseResult, ...],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for result in results:
        for failure in result.failures:
            records.append(
                {
                    "case_id": result.case_id,
                    "prompt_variant": result.prompt_variant,
                    "repeat_index": result.repeat_index,
                    "failure": failure,
                }
            )
    return tuple(records)


def _prompt_variants_in_order(
    results: tuple[LLMSampleCaseResult, ...],
) -> tuple[str, ...]:
    variants: list[str] = []
    for result in results:
        if result.prompt_variant not in variants:
            variants.append(result.prompt_variant)
    return tuple(variants)


def _prompt_variant_mode(variants: tuple[str, ...]) -> str:
    if variants == ("baseline",):
        return "baseline"
    if variants == ("coached",):
        return "coached"
    if set(variants) == {"baseline", "coached"}:
        return "both"
    return ",".join(variants)


def _repeat_count(results: tuple[LLMSampleCaseResult, ...]) -> int:
    if not results:
        return 0
    return max(result.repeat_index for result in results) + 1


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _llm_sample_report_to_dict(report: LLMSampleReport) -> dict[str, object]:
    return {
        "passed": report.passed,
        "metrics": report.metrics,
        "case_records": list(report.case_records),
        "failure_records": list(report.failure_records),
    }


def _extract_token_counts(response: LLMResponse | None) -> dict[str, object]:
    if response is None:
        return {
            "prompt_token_count": 0,
            "completion_token_count": 0,
            "total_token_count": 0,
            "token_metrics_available": False,
        }
    usage = response.provider_fields.get("usage")
    usage_dict = usage if isinstance(usage, dict) else {}
    prompt = _first_int(
        usage_dict,
        ("prompt_tokens", "input_tokens", "prompt_token_count", "input_token_count"),
    )
    completion = _first_int(
        usage_dict,
        (
            "completion_tokens",
            "output_tokens",
            "completion_token_count",
            "output_token_count",
        ),
    )
    total = _first_int(usage_dict, ("total_tokens", "total_token_count"))
    if prompt is None:
        prompt = _optional_int(response.cache_prompt_tokens)
    available = any(value is not None for value in (prompt, completion, total))
    prompt_count = prompt or 0
    if completion is None and total is not None and prompt is not None:
        completion = max(0, total - prompt)
    completion_count = completion or 0
    total_count = total if total is not None else prompt_count + completion_count
    return {
        "prompt_token_count": prompt_count,
        "completion_token_count": completion_count,
        "total_token_count": total_count,
        "token_metrics_available": available,
    }


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(payload: dict[str, object], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = _optional_int(payload.get(key))
        if value is not None:
            return value
    return None


def _memory_summaries_by_id(case: EvalCase) -> dict[str, str]:
    items = case.setup.get("memory_items", [])
    if not isinstance(items, list):
        return {}
    summaries: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if item_id:
            summaries[item_id] = str(item.get("summary") or "")
    return summaries


def _scope(case: EvalCase) -> dict[str, str]:
    scope = case.setup.get("scope", {})
    if not isinstance(scope, dict):
        return {"session_key": "", "channel": "", "chat_id": ""}
    return {
        "session_key": str(scope.get("session_key") or ""),
        "channel": str(scope.get("channel") or ""),
        "chat_id": str(scope.get("chat_id") or ""),
    }


def _query(case: EvalCase) -> str:
    query = str(case.setup.get("query") or "").strip()
    if query:
        return query
    conversation = case.setup.get("conversation", [])
    if not isinstance(conversation, list):
        return ""
    return "\n".join(
        str(message.get("content") or "")
        for message in conversation
        if isinstance(message, dict)
    ).strip()
