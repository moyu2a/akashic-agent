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
    MemoryIngestRequest,
    MemoryIngestResult,
    RememberRequest,
    RememberResult,
)
from memory2.eval_write_governance_cases import WriteGovernanceCandidate
from memory2.eval_llm_sample import _RecordingProvider, _extract_token_counts
from memory2.write_governance_review import (
    apply_final_write_safety_gate,
    resolve_write_review_candidate,
)
from plugins.default_memory.experiments import score_write_candidate_shadow
from session.manager import SessionManager


_FIXED_REPORT_TIME = datetime(2026, 7, 21, tzinfo=timezone.utc)
_CATEGORY_ORDER = (
    "valuable_preference",
    "stable_fact",
    "temporary",
    "assistant_inference",
    "duplicate",
    "conflict",
)


@dataclass(frozen=True)
class WriteGovernanceOnlineResult:
    candidate_id: str
    case_set: str
    category: str
    subtype: str
    passed: bool
    provider_error: bool
    timeout: bool
    latency_ms: int
    prompt_token_count: int
    completion_token_count: int
    total_token_count: int
    token_metrics_available: bool
    evidence_record: dict[str, object]


@dataclass(frozen=True)
class WriteGovernanceOnlineReport:
    run_id: str
    generated_at: str
    results: tuple[WriteGovernanceOnlineResult, ...]
    evidence_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]

    @property
    def infra_passed(self) -> bool:
        return bool(self.results) and all(
            not result.provider_error and not result.timeout
            for result in self.results
        )


class ScriptedWriteGovernanceOnlineProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        messages = kwargs.get("messages") or []
        text = "\n".join(
            str(message.get("content") or "")
            for message in messages
            if isinstance(message, dict)
        )
        return LLMResponse(
            content=f"已理解候选记忆测试输入。{text[:80]}",
            tool_calls=[],
            provider_fields={
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                }
            },
        )


class WriteGovernanceOnlineMemoryEngine:
    async def retrieve(
        self,
        request: MemoryEngineRetrieveRequest,
    ) -> MemoryEngineRetrieveResult:
        return MemoryEngineRetrieveResult(text_block="", hits=(), raw={})

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
        return RememberResult(
            item_id="write-governance-online-shadow",
            actual_type=request.memory_type,
        )

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


def select_write_governance_online_candidates(
    *,
    case_set: str = "all",
    limit: int = 0,
) -> tuple[WriteGovernanceCandidate, ...]:
    from memory2.eval_write_governance_cases import build_write_governance_candidates

    candidates = build_write_governance_candidates(case_set=case_set)
    if limit <= 0 or limit >= len(candidates):
        return tuple(candidates)
    by_category: dict[str, list[WriteGovernanceCandidate]] = {
        category: [] for category in _CATEGORY_ORDER
    }
    for candidate in candidates:
        by_category.setdefault(candidate.category, []).append(candidate)
    selected: list[WriteGovernanceCandidate] = []
    while len(selected) < limit:
        progressed = False
        for category in _CATEGORY_ORDER:
            bucket = by_category.get(category) or []
            if bucket:
                selected.append(bucket.pop(0))
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break
    return tuple(selected)


def label_for_candidate(candidate: WriteGovernanceCandidate) -> str:
    if candidate.category in {"valuable_preference", "stable_fact"}:
        return "useful"
    if candidate.category in {"temporary", "assistant_inference"}:
        return "pollution"
    if candidate.category == "duplicate":
        return "duplicate"
    if candidate.category == "conflict":
        return "conflict"
    raise ValueError(f"unknown write-governance category: {candidate.category}")


def final_decision_to_evidence_decision(final_decision: str) -> str:
    normalized = str(final_decision or "").strip()
    if normalized == "write":
        return "allow"
    if normalized in {"reject", "review"}:
        return normalized
    raise ValueError(f"unknown final decision: {final_decision}")


def build_write_evidence_record(
    candidate: WriteGovernanceCandidate,
    *,
    llm_answer: str = "",
    provider_error: bool = False,
    timeout: bool = False,
) -> dict[str, object]:
    source_ref = f"{candidate.case_set}:write_governance_online_eval:{candidate.id}"
    if provider_error or timeout:
        return {
            "candidate_id": candidate.id,
            "case_set": candidate.case_set,
            "category": candidate.category,
            "subtype": candidate.subtype,
            "summary": candidate.summary,
            "source_ref": source_ref,
            "baseline_decision": "allow",
            "after_decision": "review",
            "label": label_for_candidate(candidate),
            "infra_error": True,
            "provider_error": bool(provider_error),
            "timeout": bool(timeout),
        }

    scored = score_write_candidate_shadow(
        candidate.summary,
        source_ref=source_ref,
        existing_memories=list(candidate.existing_memories),
    )
    first_stage_decision = str(scored.get("decision") or "reject")
    review_resolution_decision = "not_applicable"
    review_resolution_reason = "not_applicable"
    if first_stage_decision == "allow":
        final_decision = "write"
        final_reason = str(scored.get("reason") or "")
    elif first_stage_decision == "review":
        resolution = resolve_write_review_candidate(
            summary=candidate.summary,
            score_result=scored,
            existing_memories=list(candidate.existing_memories),
            source_ref=source_ref,
        )
        review_resolution_decision = resolution.decision
        review_resolution_reason = resolution.reason
        if resolution.decision == "approve_write":
            final_decision = "write"
        elif resolution.decision == "keep_review":
            final_decision = "review"
        else:
            final_decision = "reject"
        final_reason = resolution.reason
    else:
        final_decision = "reject"
        final_reason = str(scored.get("reason") or "")

    final_safety_decision = "not_applicable"
    final_safety_reason = "not_applicable"
    if final_decision == "write":
        safety = apply_final_write_safety_gate(
            summary=candidate.summary,
            score_result=scored,
            existing_memories=list(candidate.existing_memories),
            source_ref=source_ref,
        )
        if safety is not None:
            final_safety_decision = safety.decision
            final_safety_reason = safety.reason
            final_decision = "review" if safety.decision == "keep_review" else "reject"
            final_reason = safety.reason

    return {
        "candidate_id": candidate.id,
        "case_set": candidate.case_set,
        "category": candidate.category,
        "subtype": candidate.subtype,
        "summary": candidate.summary,
        "source_ref": source_ref,
        "existing_memory_count": len(candidate.existing_memories),
        "baseline_decision": "allow",
        "after_decision": final_decision_to_evidence_decision(final_decision),
        "first_stage_decision": first_stage_decision,
        "review_resolution_decision": review_resolution_decision,
        "review_resolution_reason": review_resolution_reason,
        "final_safety_decision": final_safety_decision,
        "final_safety_reason": final_safety_reason,
        "final_decision": final_decision,
        "final_reason": final_reason,
        "label": label_for_candidate(candidate),
        "infra_error": False,
        "provider_error": False,
        "timeout": False,
        "llm_answer_length": len(llm_answer),
        "score": float(scored.get("final_score") or 0.0),
        "signals": _safe_dict(scored.get("signals")),
        "reasons": list(scored.get("reasons") or ()),
    }


def _safe_dict(value: Any) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


async def run_write_governance_online_eval(
    candidates: Sequence[WriteGovernanceCandidate],
    workspace: Path,
    provider: object,
    model: str,
    *,
    timeout_s: float = 60.0,
    real_llm_enabled: bool = False,
    checkpoint_jsonl: Path | None = None,
    resume: bool = False,
    concurrency: int = 1,
) -> WriteGovernanceOnlineReport:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    workspace.mkdir(parents=True, exist_ok=True)
    existing = _load_checkpoint_results(checkpoint_jsonl) if resume else {}
    results: list[WriteGovernanceOnlineResult] = list(existing.values())
    pending = [
        (index, candidate)
        for index, candidate in enumerate(candidates)
        if candidate.id not in existing
    ]

    if concurrency == 1:
        for index, candidate in pending:
            result = await _run_write_governance_candidate(
                candidate,
                workspace / f"candidate-{index:04d}-{_safe_name(candidate.id)}",
                provider,
                model,
                timeout_s=timeout_s,
            )
            results.append(result)
            _append_checkpoint_result(checkpoint_jsonl, candidate.id, result)
    else:
        semaphore = asyncio.Semaphore(concurrency)

        async def run_pending(
            index: int,
            candidate: WriteGovernanceCandidate,
        ) -> tuple[str, WriteGovernanceOnlineResult]:
            async with semaphore:
                return (
                    candidate.id,
                    await _run_write_governance_candidate(
                        candidate,
                        workspace / f"candidate-{index:04d}-{_safe_name(candidate.id)}",
                        provider,
                        model,
                        timeout_s=timeout_s,
                    ),
                )

        tasks = [
            asyncio.create_task(run_pending(index, candidate))
            for index, candidate in pending
        ]
        for task in asyncio.as_completed(tasks):
            key, result = await task
            results.append(result)
            _append_checkpoint_result(checkpoint_jsonl, key, result)

    return _build_online_report(
        tuple(results),
        real_llm_enabled=real_llm_enabled,
        completed_call_count=len(results),
        skipped_from_checkpoint_count=len(candidates) - len(pending),
        concurrency=concurrency,
    )


def write_write_governance_online_json(
    report: WriteGovernanceOnlineReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_write_governance_online_markdown(
    report: WriteGovernanceOnlineReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 写入治理线上 shadow 评测",
        "",
        "本报告使用测试集候选穿过真实 AgentLoop 和可选真实 LLM。",
        "候选摘要和标签来自测试集，写入治理是 shadow 判断，不改生产记忆库。",
        "",
        "## 总览",
        "",
        f"- `candidate_count`: `{report.metrics.get('candidate_count')}`",
        f"- `real_llm_enabled`: `{report.metrics.get('real_llm_enabled')}`",
        f"- `infra_passed`: `{report.metrics.get('infra_passed')}`",
        f"- `provider_error_count`: `{report.metrics.get('provider_error_count')}`",
        f"- `timeout_count`: `{report.metrics.get('timeout_count')}`",
        f"- `total_token_count`: `{report.metrics.get('total_token_count')}`",
        f"- `avg_latency_ms`: `{report.metrics.get('avg_latency_ms')}`",
        "",
        "## Evidence 分布",
        "",
        "| label | count | after allow | after reject | after review |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, row in sorted(_evidence_distribution(report.evidence_records).items()):
        lines.append(
            f"| {label} | {row['count']} | {row['allow']} | {row['reject']} | {row['review']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_write_governance_evidence_jsonl(
    records: Sequence[dict[str, object]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


async def _run_write_governance_candidate(
    candidate: WriteGovernanceCandidate,
    workspace: Path,
    provider: object,
    model: str,
    *,
    timeout_s: float,
) -> WriteGovernanceOnlineResult:
    workspace.mkdir(parents=True, exist_ok=True)
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
            memory_services=MemoryServices(
                engine=WriteGovernanceOnlineMemoryEngine(),  # type: ignore[arg-type]
            ),
        ),
        AgentLoopConfig(llm=LLMConfig(model=model, max_iterations=2)),
    )
    query = (
        "这是写入治理评测。请阅读下面候选内容，并用一句中文回复你已理解。\n"
        f"候选内容：{candidate.summary}"
    )
    started = time.perf_counter()
    answer = ""
    provider_error = False
    timeout = False
    try:
        answer = await asyncio.wait_for(
            loop.process_direct(
                query,
                session_key=f"write-governance-online:{candidate.id}",
                channel="write_governance_online",
                chat_id=candidate.id,
                skip_post_memory=True,
            ),
            timeout=max(0.001, float(timeout_s)),
        )
        await event_bus.drain()
    except TimeoutError:
        timeout = True
    except Exception:
        provider_error = True
    finally:
        await event_bus.aclose()
    if recording_provider.errors and not provider_error:
        provider_error = True
    latency_ms = int((time.perf_counter() - started) * 1000)
    token_counts = _extract_token_counts(
        recording_provider.responses[-1] if recording_provider.responses else None
    )
    evidence = build_write_evidence_record(
        candidate,
        llm_answer=answer,
        provider_error=provider_error,
        timeout=timeout,
    )
    return WriteGovernanceOnlineResult(
        candidate_id=candidate.id,
        case_set=candidate.case_set,
        category=candidate.category,
        subtype=candidate.subtype,
        passed=not provider_error and not timeout,
        provider_error=provider_error,
        timeout=timeout,
        latency_ms=latency_ms,
        prompt_token_count=int(token_counts["prompt_token_count"]),
        completion_token_count=int(token_counts["completion_token_count"]),
        total_token_count=int(token_counts["total_token_count"]),
        token_metrics_available=bool(token_counts["token_metrics_available"]),
        evidence_record=evidence,
    )


def _build_online_report(
    results: tuple[WriteGovernanceOnlineResult, ...],
    *,
    real_llm_enabled: bool,
    completed_call_count: int,
    skipped_from_checkpoint_count: int,
    concurrency: int,
) -> WriteGovernanceOnlineReport:
    evidence_records = tuple(result.evidence_record for result in results)
    metrics = _metrics_from_results(
        results,
        real_llm_enabled=real_llm_enabled,
        completed_call_count=completed_call_count,
        skipped_from_checkpoint_count=skipped_from_checkpoint_count,
        concurrency=concurrency,
    )
    return WriteGovernanceOnlineReport(
        run_id=_deterministic_run_id(results),
        generated_at=_FIXED_REPORT_TIME.isoformat(),
        results=results,
        evidence_records=evidence_records,
        metrics=metrics,
    )


def _metrics_from_results(
    results: Sequence[WriteGovernanceOnlineResult],
    *,
    real_llm_enabled: bool,
    completed_call_count: int,
    skipped_from_checkpoint_count: int,
    concurrency: int,
) -> dict[str, object]:
    provider_errors = sum(1 for result in results if result.provider_error)
    timeouts = sum(1 for result in results if result.timeout)
    return {
        "evaluation_level": "write_governance_online_shadow",
        "candidate_count": len(results),
        "real_llm_enabled": bool(real_llm_enabled),
        "infra_passed": bool(results) and provider_errors == 0 and timeouts == 0,
        "provider_error_count": provider_errors,
        "timeout_count": timeouts,
        "completed_call_count": completed_call_count,
        "skipped_from_checkpoint_count": skipped_from_checkpoint_count,
        "concurrency": concurrency,
        "total_token_count": sum(result.total_token_count for result in results),
        "avg_latency_ms": _avg([result.latency_ms for result in results]),
        "evidence_record_count": len(results),
    }


def _evidence_distribution(
    records: Sequence[dict[str, object]],
) -> dict[str, dict[str, int]]:
    distribution: dict[str, dict[str, int]] = {}
    for record in records:
        label = str(record.get("label") or "unknown")
        decision = str(record.get("after_decision") or "unknown")
        row = distribution.setdefault(
            label,
            {"count": 0, "allow": 0, "reject": 0, "review": 0},
        )
        row["count"] += 1
        if decision in {"allow", "reject", "review"}:
            row[decision] += 1
    return distribution


def _load_checkpoint_results(
    path: Path | None,
) -> dict[str, WriteGovernanceOnlineResult]:
    if path is None or not path.exists():
        return {}
    results: dict[str, WriteGovernanceOnlineResult] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        key = str(payload.get("key") or payload.get("spec_key") or "")
        result_payload = payload.get("result")
        if key and isinstance(result_payload, dict):
            result = WriteGovernanceOnlineResult(**result_payload)
            if not result.provider_error and not result.timeout:
                results[key] = result
    return results


def _append_checkpoint_result(
    path: Path | None,
    key: str,
    result: WriteGovernanceOnlineResult,
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {"key": key, "result": asdict(result)},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


def _deterministic_run_id(results: Sequence[WriteGovernanceOnlineResult]) -> str:
    digest = hashlib.sha1()
    for result in sorted(results, key=lambda item: item.candidate_id):
        digest.update(result.candidate_id.encode("utf-8"))
        digest.update(str(result.provider_error).encode("utf-8"))
        digest.update(str(result.timeout).encode("utf-8"))
    return "write-governance-online-" + digest.hexdigest()[:12]


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)[
        :96
    ]


def _avg(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)
