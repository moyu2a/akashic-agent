from __future__ import annotations

from agent.core.types import RetrievalTrace
from agent.looping.ports import MemoryServices
from agent.retrieval.protocol import (
    MemoryRetrievalPipeline,
    RetrievalRequest,
    RetrievalResult,
)
from core.memory.engine import (
    MemoryEngineRetrieveRequest,
    MemoryEngineRetrieveResult,
    MemoryScope,
)
from memory2.system_path_safe_version_contract import (
    normalize_safe_version_answer_prompt_variant,
)


class DefaultMemoryRetrievalPipeline(MemoryRetrievalPipeline):
    def __init__(
        self,
        memory: MemoryServices,
        safe_version_governed_mode: str = "off",
        safe_version_governed_replace_allowed: bool = False,
        safe_version_answer_guidance_enabled: bool = False,
        safe_version_answer_prompt_variant: str = "standard",
    ) -> None:
        self._memory = memory
        self._safe_version_governed_mode = _safe_version_mode(
            safe_version_governed_mode
        )
        self._safe_version_governed_replace_allowed = bool(
            safe_version_governed_replace_allowed
        )
        self._safe_version_answer_guidance_enabled = bool(
            safe_version_answer_guidance_enabled
        )
        self._safe_version_answer_prompt_variant = (
            normalize_safe_version_answer_prompt_variant(
                safe_version_answer_prompt_variant
            )
        )

    # 被动预检索入口：只转换请求形状，检索语义统一交给 MemoryEngine。
    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        # 1. 没有启用记忆引擎时，主链继续无记忆回复。
        if self._memory.engine is None:
            return RetrievalResult(block="", trace=None)

        # 2. 把 agent loop 的上下文转成 engine 的稳定请求协议。
        configured_mode = _safe_version_mode(self._safe_version_governed_mode)
        safe_mode = configured_mode
        session_mode_raw = request.session_metadata.get("safe_version_governed_mode")
        session_mode = (
            _safe_version_mode(session_mode_raw)
            if session_mode_raw is not None
            else ""
        )
        if session_mode in {"off", "shadow"}:
            safe_mode = session_mode
        elif session_mode == "replace" and safe_mode != "replace":
            safe_mode = "shadow"
        replace_allowed = (
            safe_mode == "replace"
            and configured_mode == "replace"
            and self._safe_version_governed_replace_allowed
        )
        if safe_mode == "replace" and not replace_allowed:
            safe_mode = "shadow"
        hints = dict(request.extra or {})
        hints.pop("safe_version_governed_mode", None)
        hints.pop("safe_version_governed_replace_allowed", None)
        hints.pop("safe_version_answer_guidance_enabled", None)
        hints.pop("safe_version_answer_prompt_variant", None)
        if safe_mode in {"shadow", "replace"}:
            hints["safe_version_governed_mode"] = safe_mode
            hints["safe_version_governed_replace_allowed"] = (
                replace_allowed and safe_mode == "replace"
            )
            if (
                safe_mode == "replace"
                and replace_allowed
                and self._safe_version_answer_guidance_enabled
            ):
                hints["safe_version_answer_guidance_enabled"] = True
                if self._safe_version_answer_prompt_variant != "standard":
                    hints["safe_version_answer_prompt_variant"] = (
                        self._safe_version_answer_prompt_variant
                    )

        result = await self._memory.engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=request.message,
                scope=MemoryScope(
                    session_key=request.session_key,
                    channel=request.channel,
                    chat_id=request.chat_id,
                ),
                context={
                    "history": request.history,
                    "session_metadata": request.session_metadata,
                },
                hints=hints,
            )
        )

        # 3. 只返回主链需要注入的文本块和可观测 trace。
        safe_metadata = dict(result.raw.get("safe_version_governed_metadata", {}) or {})
        metadata = (
            {**safe_metadata, "safe_version_governed_mode": safe_mode}
            if safe_mode in {"shadow", "replace"} and safe_metadata
            else {}
        )
        return RetrievalResult(
            block=result.text_block,
            trace=_build_retrieval_trace(result),
            metadata=metadata,
        )


def _safe_version_mode(value: object) -> str:
    mode = str(value or "off")
    if mode not in {"off", "shadow", "replace"}:
        return "off"
    return mode


# 把 engine trace 收窄成 agent loop 认识的检索 trace。
def _build_retrieval_trace(
    result: MemoryEngineRetrieveResult,
) -> RetrievalTrace | None:
    if not result.trace and not result.hits and not result.text_block:
        return None
    return RetrievalTrace(
        gate_type=str(result.trace.get("gate_type") or "") or None,
        route_decision=str(result.trace.get("route_decision") or "") or None,
        rewritten_query=str(result.raw.get("rewritten_query") or "") or None,
        injected_count=sum(1 for hit in result.hits if hit.injected),
        raw=result.raw.get("retrieval_event"),
    )
