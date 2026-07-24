from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from contextlib import suppress
from typing import Protocol, cast, runtime_checkable

from agent.plugins import Plugin
from bus.events_lifecycle import TurnCommitted
from core.memory.events import MemoryWritten, RetrievalCompleted

from .retention import run_retention_if_needed
from .writer import TraceWriter

logger = logging.getLogger("plugin.observe")


@runtime_checkable
class _ObserveWriter(Protocol):
    def emit(self, event: object) -> None: ...


class ObservePlugin(Plugin):
    name = "observe"

    async def initialize(self) -> None:
        workspace = self.context.workspace
        if workspace is None:
            logger.warning("observe 插件缺少 workspace，跳过加载")
            return

        self._writer = TraceWriter(workspace / "observe" / "observe.db")
        self._writer_task = asyncio.create_task(
            self._writer.run(),
            name="observe_writer",
        )
        self._retention_task = asyncio.create_task(
            run_retention_if_needed(workspace / "observe" / "observe.db"),
            name="observe_retention",
        )
        self.context.event_bus.on(TurnCommitted, self._observe_turn_committed)
        self.context.event_bus.on(RetrievalCompleted, self._observe_retrieval)
        self.context.event_bus.on(MemoryWritten, self._observe_memory_written)

    async def terminate(self) -> None:
        for task in (
            getattr(self, "_retention_task", None),
            getattr(self, "_writer_task", None),
        ):
            if task is None:
                continue
            _ = task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def _observe_turn_committed(self, event: TurnCommitted) -> None:
        writer = getattr(self, "_writer", None)
        if not isinstance(writer, _ObserveWriter):
            return
        _emit_turn_trace(writer, event)

    def _observe_retrieval(self, event: RetrievalCompleted) -> None:
        writer = getattr(self, "_writer", None)
        if not isinstance(writer, _ObserveWriter):
            return
        writer.emit(_to_rag_query_log(event))

    def _observe_memory_written(self, event: MemoryWritten) -> None:
        writer = getattr(self, "_writer", None)
        if not isinstance(writer, _ObserveWriter):
            return
        writer.emit(_to_memory_write_trace(event))


def _emit_turn_trace(writer: _ObserveWriter, event: TurnCommitted) -> None:
    from .events import TurnTrace as TurnTraceEvent

    post_reply_budget = event.post_reply_budget
    react_stats = event.react_stats
    tool_chain = event.tool_chain_raw
    tool_chain_json = (
        json.dumps(_slim_tool_chain(tool_chain), ensure_ascii=False)
        if tool_chain
        else None
    )
    tool_calls = _slim_tool_calls(tool_chain)
    writer.emit(
        TurnTraceEvent(
            source="agent",
            session_key=event.session_key,
            user_msg=event.persisted_user_message,
            llm_output=event.assistant_response,
            raw_llm_output=event.raw_reply,
            meme_tag=event.meme_tag,
            meme_media_count=event.meme_media_count,
            tool_calls=tool_calls,
            tool_chain_json=tool_chain_json,
            history_window=post_reply_budget.get("history_window"),
            history_messages=post_reply_budget.get("history_messages"),
            history_chars=post_reply_budget.get("history_chars"),
            history_tokens=post_reply_budget.get("history_tokens"),
            prompt_tokens=post_reply_budget.get("prompt_tokens"),
            next_turn_baseline_tokens=post_reply_budget.get(
                "next_turn_baseline_tokens"
            ),
            react_iteration_count=react_stats.get("iteration_count"),
            react_input_sum_tokens=react_stats.get("turn_input_sum_tokens"),
            react_input_peak_tokens=react_stats.get("turn_input_peak_tokens"),
            react_final_input_tokens=react_stats.get("final_call_input_tokens"),
            react_cache_prompt_tokens=react_stats.get("cache_prompt_tokens"),
            react_cache_hit_tokens=react_stats.get("cache_hit_tokens"),
        )
    )
    logger.info(
        "[observe] turn_trace 已入队 session=%s tool_calls=%d",
        event.session_key,
        len(tool_calls),
    )


def _to_rag_query_log(event: RetrievalCompleted):
    from .events import RagHitLog, RagQueryLog

    return RagQueryLog(
        caller="passive",
        session_key=event.session_key,
        query=event.query,
        orig_query=event.orig_query,
        aux_queries=list(event.aux_queries),
        hits=[
            RagHitLog(
                item_id=hit.item_id,
                memory_type=hit.memory_type,
                score=hit.score,
                summary=hit.summary[:120],
                injected=hit.injected,
                confidence_label=hit.confidence_label,
                forced=hit.forced,
            )
            for hit in event.hits
        ],
        injected_count=event.injected_count,
        route_decision=event.route_decision,
        error=event.error,
    )


def _to_memory_write_trace(event: MemoryWritten):
    from .events import MemoryWriteTrace

    return MemoryWriteTrace(
        session_key=event.session_key,
        source_ref=event.source_ref,
        action=event.action,
        memory_type=event.memory_type,
        item_id=event.item_id,
        summary=event.summary,
        superseded_ids=list(event.superseded_ids),
        error=event.error,
    )


def _slim_tool_calls(tool_chain: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        _slim_call(call, args_limit=300, result_limit=500)
        for group in tool_chain
        for call in _group_calls(group)
    ]


def _slim_tool_chain(tool_chain: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "text": str(group.get("text") or ""),
            "calls": [
                _slim_call(call, args_limit=800, result_limit=1200)
                for call in _group_calls(group)
            ],
        }
        for group in tool_chain
    ]


def _tool_error_code(call: dict[str, object]) -> str:
    direct = call.get("error_code")
    if isinstance(direct, str) and direct:
        return direct
    try:
        payload = json.loads(str(call.get("result", "") or ""))
    except (TypeError, ValueError):
        return ""
    if isinstance(payload, dict):
        value = payload.get("error_code")
        return value if isinstance(value, str) else ""
    return ""


def _slim_call(
    call: dict[str, object], *, args_limit: int, result_limit: int
) -> dict[str, object]:
    out = {
        "name": str(call.get("name", "")),
        "args": str(call.get("arguments", ""))[:args_limit],
        "result": str(call.get("result", ""))[:result_limit],
    }
    for key in ("status", "boundary_reason", "boundary_action"):
        value = call.get(key)
        if isinstance(value, str) and value:
            out[key] = value
    error_code = _tool_error_code(call)
    if error_code:
        out["error_code"] = error_code
    audit_trace = call.get("audit_trace")
    if isinstance(audit_trace, Mapping):
        out["audit_trace"] = {
            key: audit_trace.get(key)
            for key in (
                "event_type",
                "request_id",
                "session_key",
                "channel",
                "chat_id",
                "tool_name",
                "source",
                "risk",
                "policy_action",
                "policy_reason",
                "args_hash",
                "invoker_reached",
                "invoker_succeeded",
            )
            if key in audit_trace
        }
    approval_lifecycle = call.get("approval_lifecycle")
    if isinstance(approval_lifecycle, list):
        events = [
            _slim_approval_lifecycle_event(event)
            for event in approval_lifecycle
            if isinstance(event, Mapping)
        ]
        if events:
            out["approval_lifecycle"] = events
    return out


def _slim_approval_lifecycle_event(event: Mapping[object, object]) -> dict[str, object]:
    return {
        key: event.get(key)
        for key in (
            "event_type",
            "approval_request_id",
            "request_id",
            "session_key",
            "actor",
            "source",
            "tool_name",
            "risk",
            "approval_scope",
            "policy_reason",
            "status",
            "args_hash",
            "created_at",
            "decided_at",
            "consumed_at",
            "executed_at",
        )
        if key in event
    }


def _group_calls(group: dict[str, object]) -> list[dict[str, object]]:
    calls = group.get("calls")
    if not isinstance(calls, list):
        return []
    raw_calls = cast(list[object], calls)
    out: list[dict[str, object]] = []
    for call in raw_calls:
        if isinstance(call, Mapping):
            mapping = cast(Mapping[object, object], call)
            out.append(
                {
                    str(key): value
                    for key, value in mapping.items()
                    if isinstance(key, str)
                }
            )
    return out
