from __future__ import annotations

import json
from typing import Any

from agent.tools.base import Tool
from agent.tracing.turn_trace_query import TurnTraceQueryResult, TurnTraceQueryService


class InspectTurnTraceTool(Tool):
    name = "inspect_turn_trace"
    description = (
        "读取当前 session 的结构化 turn/tool trace，用于回答“刚才用了哪些工具”、"
        "“上一轮工具链是什么”、“第 N 个问题调用了哪些工具”。"
        "这是工具历史事实的 source of truth；不要用 search_messages 的自然语言预览猜测工具链。"
        "只查询当前 session，不跨 session。若返回 ambiguous_selector，先向用户确认候选 turn。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "enum": [
                    "previous_completed",
                    "recent_nth_completed",
                    "nth_user_question_in_window",
                    "turn_id",
                    "query",
                ],
                "description": "选择要查询的 turn。",
                "default": "previous_completed",
            },
            "n": {
                "type": "integer",
                "description": "selector=recent_nth_completed 或 nth_user_question_in_window 时使用。",
                "minimum": 1,
                "maximum": 20,
            },
            "turn_id": {
                "type": "integer",
                "description": "selector=turn_id 时使用。",
                "minimum": 1,
            },
            "query": {
                "type": "string",
                "description": "selector=query 时用于匹配用户问题文本。",
            },
        },
        "required": ["selector"],
    }

    def __init__(self, service: TurnTraceQueryService) -> None:
        self._service = service

    async def execute(
        self,
        selector: str = "previous_completed",
        n: int | None = None,
        turn_id: int | None = None,
        query: str | None = None,
        _session_key: str | None = None,
        **_: Any,
    ) -> str:
        clean_session_key = str(_session_key or "").strip()
        if not clean_session_key:
            return json.dumps(
                {
                    "ok": False,
                    "error_code": "missing_session_context",
                    "message": "inspect_turn_trace requires protected current-session context.",
                },
                ensure_ascii=False,
            )
        result = self._service.resolve(
            clean_session_key,
            selector=selector,
            n=n,
            turn_id=turn_id,
            query=query,
        )
        return json.dumps(_result_to_payload(result), ensure_ascii=False)


def _result_to_payload(result: TurnTraceQueryResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": result.ok,
        "source": result.source,
    }
    if result.error_code:
        payload["error_code"] = result.error_code
    if result.message:
        payload["message"] = result.message
    if result.candidates:
        payload["candidates"] = [
            {
                "id": item.id,
                "ts": item.ts,
                "user_msg": item.user_msg,
                "real_tools": item.real_tool_counts,
            }
            for item in result.candidates
        ]
    if result.turn is not None:
        turn = result.turn
        payload["turn"] = {
            "id": turn.id,
            "ts": turn.ts,
            "current_session": True,
            "user_msg": turn.user_msg,
            "error": turn.error,
            "react_iteration_count": turn.react_iteration_count,
        }
        payload["tools"] = [
            {
                "name": tool.name,
                "status": tool.status,
                "real_executed": tool.real_executed,
                "skipped": tool.skipped,
                "error_code": tool.error_code,
                "iteration": tool.iteration,
            }
            for tool in turn.tools
        ]
        payload["summary"] = {
            "real_tools": turn.real_tool_counts,
            "skipped_tools": turn.skipped_tool_counts,
            "tool_count": len(turn.tools),
        }
    return payload
