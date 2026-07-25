from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock

from agent.looping.core import AgentLoop
from agent.looping.ports import AgentLoopConfig, AgentLoopDeps, LLMConfig, MemoryServices
from agent.provider import LLMResponse
from agent.tools.registry import ToolRegistry
from bus.event_bus import EventBus
from bus.events_lifecycle import TurnCommitted
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


@dataclass(frozen=True)
class AgentDryRunCaseResult:
    case_id: str
    category: str
    session_key: str
    channel: str
    chat_id: str
    passed: bool
    reply_length: int
    retrieval_request_count: int
    fake_llm_call_count: int
    turn_committed_count: int
    session_message_count: int
    retrieval_query_matched: bool
    retrieval_history_seen: bool
    failures: tuple[str, ...]


@dataclass(frozen=True)
class AgentDryRunReport:
    cases: tuple[AgentDryRunCaseResult, ...]
    metrics: dict[str, object]
    case_records: tuple[dict[str, object], ...]
    failure_records: tuple[dict[str, object], ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)


class ScriptedDryRunProvider:
    def __init__(self, content: str = "dry-run response") -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        return LLMResponse(content=self.content, tool_calls=[])


class CaseMemoryEngine:
    """Minimal memory engine for the passive retrieval path only."""

    def __init__(self, case: EvalCase) -> None:
        self.case = case
        self.retrieve_requests: list[MemoryEngineRetrieveRequest] = []

    async def retrieve(
        self,
        request: MemoryEngineRetrieveRequest,
    ) -> MemoryEngineRetrieveResult:
        self.retrieve_requests.append(request)
        ids = [
            str(item_id)
            for item_id in _expectations(self.case).get("should_recall_ids", [])
        ]
        hits = [
            MemoryHit(
                id=item_id,
                summary="",
                content="",
                score=1.0,
                source_ref="",
                engine_kind="agent_dry_run",
                injected=True,
            )
            for item_id in ids
        ]
        block = "\n".join(f"- memory_id={item_id}" for item_id in ids)
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
        return RememberResult(item_id="dry-run-memory", actual_type=request.memory_type)

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


async def run_agent_dry_run_case(
    case: EvalCase,
    workspace: Path,
) -> AgentDryRunCaseResult:
    workspace.mkdir(parents=True, exist_ok=True)
    provider = ScriptedDryRunProvider()
    memory = CaseMemoryEngine(case)
    event_bus = EventBus()
    turn_events: list[TurnCommitted] = []
    event_bus.on(TurnCommitted, lambda event: turn_events.append(event))
    session_manager = SessionManager(workspace)
    tools = ToolRegistry()
    loop = AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=provider,  # type: ignore[arg-type]
            light_provider=provider,  # type: ignore[arg-type]
            tools=tools,
            session_manager=session_manager,
            workspace=workspace,
            event_bus=event_bus,
            memory_services=MemoryServices(engine=memory),  # type: ignore[arg-type]
        ),
        AgentLoopConfig(llm=LLMConfig(max_iterations=2)),
    )
    scope = _scope(case)
    query = _query(case)
    reply = ""
    failures: list[str] = []
    try:
        reply = await loop.process_direct(
            query,
            session_key=scope["session_key"],
            channel=scope["channel"],
            chat_id=scope["chat_id"],
            skip_post_memory=True,
        )
        await event_bus.drain()
    finally:
        await event_bus.aclose()

    if not reply:
        failures.append("empty reply")
    if len(memory.retrieve_requests) != 1:
        failures.append(
            f"expected 1 retrieval request, got {len(memory.retrieve_requests)}"
        )
    if not provider.calls:
        failures.append("fake llm was not called")
    if not turn_events:
        failures.append("TurnCommitted was not observed")
    if memory.retrieve_requests:
        _validate_retrieval_request(
            memory.retrieve_requests[0],
            query=query,
            scope=scope,
            failures=failures,
        )

    session = session_manager.get_or_create(scope["session_key"])
    return AgentDryRunCaseResult(
        case_id=case.id,
        category=case.category,
        session_key=scope["session_key"],
        channel=scope["channel"],
        chat_id=scope["chat_id"],
        passed=not failures,
        reply_length=len(reply),
        retrieval_request_count=len(memory.retrieve_requests),
        fake_llm_call_count=len(provider.calls),
        turn_committed_count=len(turn_events),
        session_message_count=len(session.messages),
        retrieval_query_matched=(
            bool(memory.retrieve_requests) and memory.retrieve_requests[0].query == query
        ),
        retrieval_history_seen=(
            bool(memory.retrieve_requests)
            and isinstance(memory.retrieve_requests[0].context.get("history", []), list)
        ),
        failures=tuple(failures),
    )


async def run_agent_dry_run_cases(
    cases: Sequence[EvalCase],
    workspace: Path,
) -> AgentDryRunReport:
    results: list[AgentDryRunCaseResult] = []
    for index, case in enumerate(cases):
        result = await run_agent_dry_run_case(
            case,
            workspace / f"case-{index:03d}-{case.id}",
        )
        results.append(result)
    return _build_report(tuple(results))


def write_agent_dry_run_json(report: AgentDryRunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_agent_dry_run_markdown(report: AgentDryRunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Memory Agent Dry-Run Evaluation Report",
        "",
        "本报告使用真实 AgentLoop 和 fake LLM，不调用真实 LLM，不代表最终回答质量。",
        "报告默认不包含真实 query、memory summary、prompt 或 session 原文。",
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


def _validate_retrieval_request(
    request: MemoryEngineRetrieveRequest,
    *,
    query: str,
    scope: dict[str, str],
    failures: list[str],
) -> None:
    if request.scope.session_key != scope["session_key"]:
        failures.append("retrieval session_key mismatch")
    if request.scope.channel != scope["channel"]:
        failures.append("retrieval channel mismatch")
    if request.scope.chat_id != scope["chat_id"]:
        failures.append("retrieval chat_id mismatch")
    if request.query != query:
        failures.append("retrieval query mismatch")
    if not isinstance(request.context.get("history", []), list):
        failures.append("retrieval history missing")


def _build_report(results: tuple[AgentDryRunCaseResult, ...]) -> AgentDryRunReport:
    passed_count = sum(1 for result in results if result.passed)
    failed_count = len(results) - passed_count
    metrics: dict[str, object] = {
        "phase6b_level": "agent_dry_run",
        "agent_loop_enabled": True,
        "fake_llm_enabled": True,
        "llm_calls_enabled": False,
        "embedding_calls_enabled": False,
        "answer_quality_available": False,
        "raw_query_included": False,
        "raw_memory_summary_included": False,
        "prompt_included": False,
        "session_text_included": False,
        "case_count": len(results),
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "agent_turn_count": len(results),
        "turn_committed_count": sum(
            result.turn_committed_count for result in results
        ),
        "retrieval_request_count": sum(
            result.retrieval_request_count for result in results
        ),
        "fake_llm_call_count": sum(result.fake_llm_call_count for result in results),
        "session_message_count": sum(result.session_message_count for result in results),
    }
    case_records = tuple(_case_record(result) for result in results)
    return AgentDryRunReport(
        cases=results,
        metrics=metrics,
        case_records=case_records,
        failure_records=_failure_records(results),
    )


def _case_record(result: AgentDryRunCaseResult) -> dict[str, object]:
    return {
        "case_id": result.case_id,
        "category": result.category,
        "session_key": result.session_key,
        "channel": result.channel,
        "chat_id": result.chat_id,
        "passed": result.passed,
        "reply_length": result.reply_length,
        "retrieval_request_count": result.retrieval_request_count,
        "fake_llm_call_count": result.fake_llm_call_count,
        "turn_committed_count": result.turn_committed_count,
        "session_message_count": result.session_message_count,
        "retrieval_query_matched": result.retrieval_query_matched,
        "retrieval_history_seen": result.retrieval_history_seen,
        "failures": list(result.failures),
    }


def _failure_records(
    results: tuple[AgentDryRunCaseResult, ...],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for result in results:
        for failure in result.failures:
            records.append(
                {
                    "case_id": result.case_id,
                    "failure": failure,
                }
            )
    return tuple(records)


def _report_to_dict(report: AgentDryRunReport) -> dict[str, object]:
    return {
        "passed": report.passed,
        "metrics": report.metrics,
        "case_records": list(report.case_records),
        "failure_records": list(report.failure_records),
    }


def _scope(case: EvalCase) -> dict[str, str]:
    scope = _setup(case).get("scope", {})
    if not isinstance(scope, dict):
        return {"session_key": "", "channel": "", "chat_id": ""}
    return {
        "session_key": str(scope.get("session_key") or ""),
        "channel": str(scope.get("channel") or ""),
        "chat_id": str(scope.get("chat_id") or ""),
    }


def _query(case: EvalCase) -> str:
    setup = _setup(case)
    query = str(setup.get("query") or "").strip()
    if query:
        return query
    conversation = setup.get("conversation", [])
    if not isinstance(conversation, list):
        return ""
    return "\n".join(
        str(message.get("content") or "")
        for message in conversation
        if isinstance(message, dict)
    ).strip()


def _setup(case: EvalCase) -> dict[str, Any]:
    return dict(case.setup)


def _expectations(case: EvalCase) -> dict[str, Any]:
    return dict(case.expectations)
