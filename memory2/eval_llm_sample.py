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
    forbidden_answer_contains: tuple[str, ...] = ()
    expected_memory_ids: tuple[str, ...] = ()
    expected_language: str = ""
    grounding_required: bool = False


@dataclass(frozen=True)
class AnswerScoreResult:
    passed: bool
    expected_contains_pass_count: int
    expected_contains_miss_count: int
    forbidden_contains_violation_count: int
    expected_memory_used: bool
    language_passed: bool
    failures: tuple[str, ...]


@dataclass(frozen=True)
class LLMSampleCaseResult:
    case_id: str
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

    def __init__(self, case: EvalCase) -> None:
        self.case = case
        self.retrieve_requests: list[MemoryEngineRetrieveRequest] = []
        self.used_memory_ids: list[str] = []

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
        block = "\n".join(
            f"- memory_id={item_id}; summary={summaries.get(item_id, '')}"
            for item_id in ids
        )
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
    expected_pass_count = 0
    expected_miss_count = 0
    for term in expectation.expected_answer_contains:
        if _contains_term(answer, term):
            expected_pass_count += 1
        else:
            expected_miss_count += 1
            failures.append(f"missing expected answer term: {term}")

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

    language_passed = True
    if expectation.expected_language == "zh":
        language_passed = bool(_CJK_RE.search(answer))
        if not language_passed:
            failures.append("answer is not detected as Chinese")

    return AnswerScoreResult(
        passed=not failures,
        expected_contains_pass_count=expected_pass_count,
        expected_contains_miss_count=expected_miss_count,
        forbidden_contains_violation_count=forbidden_violation_count,
        expected_memory_used=expected_memory_used,
        language_passed=language_passed,
        failures=tuple(failures),
    )


async def run_llm_sample_case(
    case: EvalCase,
    workspace: Path,
    provider: object,
    model: str,
    timeout_s: float = 60.0,
) -> LLMSampleCaseResult:
    workspace.mkdir(parents=True, exist_ok=True)
    memory = LLMSampleMemoryEngine(case)
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
    return LLMSampleCaseResult(
        case_id=case.id,
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
        provider_error=provider_error,
        timeout=timeout,
        used_memory_ids=tuple(memory.used_memory_ids),
        failures=tuple(failures),
    )


async def run_llm_sample_cases(
    cases: Sequence[EvalCase],
    workspace: Path,
    provider: object,
    model: str,
    timeout_s: float = 60.0,
    real_llm_enabled: bool = False,
) -> LLMSampleReport:
    selected = [
        case
        for case in cases
        if isinstance(case.expectations.get("answer_expectations"), dict)
    ]
    results: list[LLMSampleCaseResult] = []
    for index, case in enumerate(selected):
        result = await run_llm_sample_case(
            case,
            workspace / f"case-{index:03d}-{case.id}",
            provider,
            model,
            timeout_s=timeout_s,
        )
        results.append(result)
    return _build_llm_sample_report(tuple(results), real_llm_enabled=real_llm_enabled)


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


def _contains_term(text: str, term: str) -> bool:
    if _CJK_RE.search(term):
        return term in text
    return term.lower() in text.lower()


def _build_llm_sample_report(
    results: tuple[LLMSampleCaseResult, ...],
    *,
    real_llm_enabled: bool,
) -> LLMSampleReport:
    passed_count = sum(1 for result in results if result.passed)
    failed_count = len(results) - passed_count
    token_metrics_available = any(result.token_metrics_available for result in results)
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
        "category": result.category,
        "session_key": result.session_key,
        "channel": result.channel,
        "chat_id": result.chat_id,
        "passed": result.passed,
        "answer_length": result.answer_length,
        "latency_ms": result.latency_ms,
        "expected_memory_used": result.expected_memory_used,
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
            records.append({"case_id": result.case_id, "failure": failure})
    return tuple(records)


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
    prompt = _optional_int(usage_dict.get("prompt_tokens"))
    completion = _optional_int(usage_dict.get("completion_tokens"))
    total = _optional_int(usage_dict.get("total_tokens"))
    if prompt is None:
        prompt = _optional_int(response.cache_prompt_tokens)
    available = any(value is not None for value in (prompt, completion, total))
    prompt_count = prompt or 0
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
