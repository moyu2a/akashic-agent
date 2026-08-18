"""
Memory v2 检索器：查询 → top-k items + 格式化注入块
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
import re
from typing import cast

from memory2.store import MemoryStore2
from memory2.embedder import Embedder
from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_candidate_governance,
    apply_retrieval_route,
    build_retrieval_plan,
)

logger = logging.getLogger(__name__)

_RRF_K = 60
_KEYWORD_RRF_WEIGHT = 0.5
_KEYWORD_LIMIT_FLOOR = 30
_KEYWORD_LIMIT_MULTIPLIER = 2
_EMBED_TIMEOUT_S = 8.0
_LOW_CONFIDENCE_PHRASES = (
    "未在对话中明确记录",
    "无法凭记忆确认",
    "没有记录",
    "真的没有",
    "未找到",
    "不确定",
)


class Retriever:
    INJECT_MAX_CHARS = 1200
    INJECT_MAX_FORCED = 3
    INJECT_MAX_EVENTS = 4
    INJECT_LINE_MAX = 180

    def __init__(
        self,
        store: MemoryStore2,
        embedder: Embedder,
        top_k: int = 8,
        score_threshold: float = 0.45,
        score_thresholds: dict[str, float] | None = None,
        relative_delta: float = 0.06,
        inject_max_chars: int = 1200,
        inject_max_forced: int = 3,
        inject_max_procedure_preference: int = 4,
        inject_max_event_profile: int = 2,
        inject_line_max: int = 180,
        procedure_guard_enabled: bool = True,
        high_inject_delta: float = 0.15,
        hotness_alpha: float = 0.20,
        hotness_half_life_days: float = 14.0,
        candidate_governance: CandidateGovernancePolicy | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._top_k = top_k
        self._score_threshold = score_threshold
        thresholds = score_thresholds or {}
        self._score_thresholds = {
            "procedure": float(thresholds.get("procedure", score_threshold)),
            "preference": float(thresholds.get("preference", score_threshold)),
            "event": float(thresholds.get("event", score_threshold)),
            "profile": float(thresholds.get("profile", score_threshold)),
        }
        self._relative_delta = max(0.0, float(relative_delta))
        self._inject_max_chars = max(200, int(inject_max_chars))
        self._inject_max_forced = max(1, int(inject_max_forced))
        self._inject_max_procedure_preference = max(
            1, int(inject_max_procedure_preference)
        )
        self._inject_max_event_profile = max(0, int(inject_max_event_profile))
        self._inject_line_max = max(60, int(inject_line_max))
        self._procedure_guard_enabled = bool(procedure_guard_enabled)
        self._high_inject_delta = max(0.0, float(high_inject_delta))
        self._hotness_alpha = max(0.0, min(1.0, float(hotness_alpha)))
        self._hotness_half_life_days = max(1.0, float(hotness_half_life_days))
        # Production uses the safe tiered policy by default. Eval callers may
        # still pass an explicit policy, including an eval-only protected one.
        self._candidate_governance = candidate_governance or CandidateGovernancePolicy(
            enabled=True,
            mode="tiered",
        )

    # 统一检索入口：recall_memory 和被动预检索都复用这条查库路径。
    async def retrieve(
        self,
        query: str,
        memory_types: list[str] | None = None,
        top_k: int | None = None,
        scope_channel: str | None = None,
        scope_chat_id: str | None = None,
        require_scope_match: bool = False,
        aux_queries: list[str] | None = None,
        score_threshold: float | None = None,
        time_start: datetime | None = None,
        time_end: datetime | None = None,
        keyword_enabled: bool = True,
    ) -> list[dict]:
        items, _trace = await self.retrieve_with_trace(
            query,
            memory_types=memory_types,
            top_k=top_k,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            require_scope_match=require_scope_match,
            aux_queries=aux_queries,
            score_threshold=score_threshold,
            time_start=time_start,
            time_end=time_end,
            keyword_enabled=keyword_enabled,
        )
        return items

    async def retrieve_with_trace(
        self,
        query: str,
        memory_types: list[str] | None = None,
        top_k: int | None = None,
        scope_channel: str | None = None,
        scope_chat_id: str | None = None,
        require_scope_match: bool = False,
        aux_queries: list[str] | None = None,
        score_threshold: float | None = None,
        time_start: datetime | None = None,
        time_end: datetime | None = None,
        keyword_enabled: bool = True,
    ) -> tuple[list[dict], dict[str, object]]:
        """返回治理后的召回结果及其路由 trace；不改变 ``retrieve`` 的旧契约。"""
        actual_top_k = self._top_k if top_k is None else max(1, int(top_k))
        plan = build_retrieval_plan(
            query,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            memory_types=memory_types,
            top_k=actual_top_k,
            aux_queries=aux_queries,
            score_threshold=score_threshold,
            keyword_enabled=keyword_enabled,
            candidate_governance=self._candidate_governance,
        )
        semantic_items, keyword_items = await self._retrieve_semantic_keyword_lanes(
            query,
            memory_types=memory_types,
            top_k=actual_top_k,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            require_scope_match=require_scope_match,
            aux_queries=aux_queries,
            score_threshold=score_threshold,
            time_start=time_start,
            time_end=time_end,
            keyword_enabled=keyword_enabled,
        )
        decision = plan.to_routing_decision().with_candidate_governance(
            CandidateGovernancePolicy(enabled=False)
        )
        provenance_items, graph_items = self._retrieve_evidence_lanes(
            query,
            decision_graph_enabled=decision.graph_enabled,
            memory_types=memory_types,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            require_scope_match=require_scope_match,
            top_k=actual_top_k,
        )
        candidates_by_lane = {
            "semantic": _mark_scope_matches(
                semantic_items, scope_channel=scope_channel, scope_chat_id=scope_chat_id
            ),
            "keyword": _mark_scope_matches(
                keyword_items, scope_channel=scope_channel, scope_chat_id=scope_chat_id
            ),
            "provenance": provenance_items,
            "graph": graph_items,
        }
        _accepted, trace = apply_retrieval_route(decision, candidates_by_lane)
        accepted_by_lane = cast(dict[str, list[dict]], trace["accepted_items_by_lane"])
        fused_items = _rrf_merge_lanes(accepted_by_lane, top_n=actual_top_k)
        items, governance_trace = apply_candidate_governance(
            fused_items,
            plan.candidate_governance,
        )
        trace["retrieval_plan"] = plan.to_dict()
        trace["fused_items"] = fused_items
        trace["post_rrf_candidate_governance"] = governance_trace
        trace["final_allowed_candidates"] = governance_trace["allowed_candidates"]
        trace["final_uncertain_candidates"] = governance_trace[
            "uncertain_candidates"
        ]
        trace["final_dropped_candidates"] = governance_trace[
            "dropped_candidates"
        ]
        trace["candidate_drop_counts"] = dict(
            cast(dict[str, int], trace["dropped_by_reason"])
        )
        trace["post_rrf_candidate_drop_counts"] = dict(
            cast(dict[str, int], governance_trace["dropped_risks_by_reason"])
        )
        trace["graph_used"] = bool(graph_items)
        trace["candidates_by_lane"] = candidates_by_lane
        trace["final_count"] = len(items)
        logger.debug(
            "memory2 governed retrieve: query=%r scene=%s fused=%d graph=%d",
            query[:60],
            decision.scene,
            len(items),
            len(graph_items),
        )
        return items, trace

    async def retrieve_with_lanes(
        self,
        query: str,
        memory_types: list[str] | None = None,
        top_k: int | None = None,
        scope_channel: str | None = None,
        scope_chat_id: str | None = None,
        require_scope_match: bool = False,
        aux_queries: list[str] | None = None,
        score_threshold: float | None = None,
        time_start: datetime | None = None,
        time_end: datetime | None = None,
        keyword_enabled: bool = True,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        vector_items, keyword_items = await self._retrieve_semantic_keyword_lanes(
            query,
            memory_types=memory_types,
            top_k=top_k,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            require_scope_match=require_scope_match,
            aux_queries=aux_queries,
            score_threshold=score_threshold,
            time_start=time_start,
            time_end=time_end,
            keyword_enabled=keyword_enabled,
        )
        actual_top_k = self._top_k if top_k is None else max(1, int(top_k))
        items = _rrf_merge(vector_items, keyword_items, top_n=actual_top_k)
        return items, vector_items, keyword_items

    async def _retrieve_semantic_keyword_lanes(
        self,
        query: str,
        *,
        memory_types: list[str] | None,
        top_k: int | None,
        scope_channel: str | None,
        scope_chat_id: str | None,
        require_scope_match: bool,
        aux_queries: list[str] | None,
        score_threshold: float | None,
        time_start: datetime | None,
        time_end: datetime | None,
        keyword_enabled: bool,
    ) -> tuple[list[dict], list[dict]]:
        # 1. query 与辅助 query 一起进入向量 lane，避免多入口语义漂移。
        actual_top_k = self._top_k if top_k is None else max(1, int(top_k))
        actual_threshold = (
            self._score_threshold if score_threshold is None else float(score_threshold)
        )
        query_texts = _dedupe_texts([query, *(aux_queries or [])])
        vector_items = await self._retrieve_vector_lanes(
            query_texts,
            actual_top_k=actual_top_k,
            memory_types=memory_types,
            score_threshold=actual_threshold,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            require_scope_match=require_scope_match,
            time_start=time_start,
            time_end=time_end,
        )

        # 2. 关键词 lane 只用原始 query，保留用户字面命中的召回能力。
        keyword_items: list[dict] = []
        if keyword_enabled:
            keyword_items = self._retrieve_keyword_lane(
                query,
                actual_top_k=actual_top_k,
                memory_types=memory_types,
                scope_channel=scope_channel,
                scope_chat_id=scope_chat_id,
                require_scope_match=require_scope_match,
                time_start=time_start,
                time_end=time_end,
            )

        return vector_items, keyword_items

    def _retrieve_evidence_lanes(
        self,
        query: str,
        *,
        decision_graph_enabled: bool,
        memory_types: list[str] | None,
        scope_channel: str | None,
        scope_chat_id: str | None,
        require_scope_match: bool,
        top_k: int,
    ) -> tuple[list[dict], list[dict]]:
        try:
            active_items, _total = self._store.list_items_for_dashboard(
                status="active",
                page_size=max(200, top_k * 20),
            )
        except Exception as exc:
            logger.debug("memory2 retrieve: evidence lanes unavailable: %s", exc)
            return [], []

        filtered_items = [
            dict(item)
            for item in active_items
            if isinstance(item, dict)
            and (not memory_types or item.get("memory_type") in memory_types)
            and (
                not require_scope_match
                or _scope_matches(
                    item, scope_channel=scope_channel, scope_chat_id=scope_chat_id
                )
            )
        ]
        from memory2.retrieval_experiments import build_provenance_lane

        provenance_items = _mark_scope_matches(
            build_provenance_lane(
                query,
                filtered_items,
                scope_channel=scope_channel or "",
                scope_chat_id=scope_chat_id or "",
                limit=max(20, top_k * 2),
            ).items,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
        )
        graph_items: list[dict] = []
        if decision_graph_enabled:
            from memory2.retrieval_graph_experiments import build_graph_lane

            graph_items = _mark_scope_matches(
                build_graph_lane(
                    query,
                    filtered_items,
                    scope_channel=scope_channel or "",
                    scope_chat_id=scope_chat_id or "",
                    limit=max(20, top_k * 2),
                ).items,
                scope_channel=scope_channel,
                scope_chat_id=scope_chat_id,
            )
        return provenance_items, graph_items

    async def _retrieve_vector_lanes(
        self,
        query_texts: list[str],
        *,
        actual_top_k: int,
        memory_types: list[str] | None,
        score_threshold: float,
        scope_channel: str | None,
        scope_chat_id: str | None,
        require_scope_match: bool,
        time_start: datetime | None,
        time_end: datetime | None,
    ) -> list[dict]:
        if not query_texts:
            return []
        vectors = await self._embed_lanes(query_texts)
        if not vectors:
            return []
        hit_groups: list[list[dict]] = []
        try:
            hit_groups = self._store.vector_search_batch(
                vectors,
                top_k=actual_top_k,
                memory_types=memory_types,
                score_threshold=score_threshold,
                scope_channel=scope_channel,
                scope_chat_id=scope_chat_id,
                require_scope_match=require_scope_match,
                hotness_alpha=self._hotness_alpha,
                hotness_half_life_days=self._hotness_half_life_days,
                time_start=time_start,
                time_end=time_end,
            )
        except Exception as e:
            logger.debug("memory2 retrieve: vector_search_batch failed: %s", e)

        seen: dict[str, dict] = {}
        if hit_groups:
            for hits in hit_groups:
                for hit in hits:
                    _remember_vector_hit(seen, hit)
            return list(seen.values())

        for vector in vectors:
            try:
                hits = self._store.vector_search(
                    query_vec=vector,
                    top_k=actual_top_k,
                    memory_types=memory_types,
                    score_threshold=score_threshold,
                    scope_channel=scope_channel,
                    scope_chat_id=scope_chat_id,
                    require_scope_match=require_scope_match,
                    hotness_alpha=self._hotness_alpha,
                    hotness_half_life_days=self._hotness_half_life_days,
                    time_start=time_start,
                    time_end=time_end,
                )
            except Exception as e:
                logger.debug("memory2 retrieve: vector_search failed: %s", e)
                continue
            for hit in hits:
                _remember_vector_hit(seen, hit)
        return list(seen.values())

    async def _embed_lanes(self, query_texts: list[str]) -> list[list[float]]:
        results = await asyncio.gather(
            *(
                asyncio.wait_for(
                    self._embedder.embed(text),
                    timeout=_EMBED_TIMEOUT_S,
                )
                for text in query_texts
            ),
            return_exceptions=True,
        )
        vectors: list[list[float]] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.warning(
                    "memory2 retrieve: embed failed, fallback lane skipped: %s", result
                )
                continue
            vectors.append(cast(list[float], result))
        return vectors

    def _retrieve_keyword_lane(
        self,
        query: str,
        *,
        actual_top_k: int,
        memory_types: list[str] | None,
        scope_channel: str | None,
        scope_chat_id: str | None,
        require_scope_match: bool,
        time_start: datetime | None,
        time_end: datetime | None,
    ) -> list[dict]:
        terms = _extract_terms(query)
        if not terms:
            return []
        return self._store.keyword_search_summary(
            terms,
            memory_types=memory_types,
            limit=max(_KEYWORD_LIMIT_FLOOR, actual_top_k * _KEYWORD_LIMIT_MULTIPLIER),
            time_start=time_start,
            time_end=time_end,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            require_scope_match=require_scope_match,
        )

    async def embed(self, query: str) -> list[float]:
        """仅做 embedding，不触发 vector_search。"""
        return await self._embedder.embed(query)

    async def retrieve_with_vec(
        self,
        query_vec: list[float],
        memory_types: list[str] | None = None,
        top_k: int | None = None,
        scope_channel: str | None = None,
        scope_chat_id: str | None = None,
        require_scope_match: bool = False,
    ) -> list[dict]:
        """复用已有 query_vec 做本地 vector_search，跳过 embedding 步骤。"""
        actual_top_k = self._top_k if top_k is None else max(1, int(top_k))
        items = self._store.vector_search(
            query_vec=query_vec,
            top_k=actual_top_k,
            memory_types=memory_types,
            score_threshold=self._score_threshold,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
            require_scope_match=require_scope_match,
            hotness_alpha=self._hotness_alpha,
            hotness_half_life_days=self._hotness_half_life_days,
        )
        logger.debug(f"memory2 retrieve_with_vec: hits={len(items)}")
        return items

    def build_injection_block(self, items: list[dict]) -> tuple[str, list[str]]:
        """单次流程：筛选条目 → 分段格式化 → 应用字符预算。"""
        selected, forced, norms, events = self._select_injection_sections(items)
        if not selected:
            return "", []

        parts = self._build_section_parts(forced, norms, events)
        return self._apply_char_budget(parts, has_forced=bool(forced))

    def _select_for_injection(self, items: list[dict]) -> list[dict]:
        selected, _forced, _norms, _events = self._select_injection_sections(items)
        return selected

    def _select_injection_sections(
        self,
        items: list[dict],
    ) -> tuple[
        list[dict], list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]
    ]:
        """1. 筛选条目 2. 按段落准备格式化文本。"""
        if not items:
            return [], [], [], []

        sorted_items = sorted(
            [i for i in items if isinstance(i, dict)],
            key=lambda x: float(x.get("score", 0.0) or 0.0),
            reverse=True,
        )
        if not sorted_items:
            return [], [], [], []

        selected: list[dict] = []
        forced: list[tuple[str, str]] = []
        norms: list[tuple[str, str]] = []
        events: list[tuple[str, str]] = []
        forced_count = 0
        norm_count = 0
        event_count = 0
        for item in sorted_items:
            mtype = str(item.get("memory_type", "") or "")
            score = float(item.get("score", 0.0) or 0.0)
            extra = item.get("extra_json") or {}
            item_id = str(item.get("id", "") or "")
            summary = str(item.get("summary", "") or "").strip()
            happened_at = item.get("happened_at") or ""
            if (
                self._procedure_guard_enabled
                and mtype == "procedure"
                and extra.get("tool_requirement")
            ):
                if forced_count >= self._inject_max_forced:
                    continue
                forced_count += 1
                item["forced"] = True
                selected.append(item)
                if summary:
                    tool_req = extra.get("tool_requirement")
                    forced.append(
                        (
                            item_id,
                            f"- [{item_id}] {summary}（必须调用工具：{tool_req}）",
                        )
                    )
                continue
            type_th = self._score_thresholds.get(mtype, self._score_threshold)
            if score < type_th:
                continue
            if mtype in ("procedure", "preference"):
                if norm_count >= self._inject_max_procedure_preference:
                    continue
                norm_count += 1
            elif mtype in ("event", "profile"):
                if event_count >= self._inject_max_event_profile:
                    continue
                event_count += 1
            else:
                continue
            selected.append(item)
            if not summary:
                continue
            confidence_label = ""
            if score < type_th + self._high_inject_delta:
                confidence_label = "有印象，不确定"
            item["confidence_label"] = confidence_label
            if mtype == "procedure":
                steps = extra.get("steps") or []
                if steps:
                    step_text = "；".join(str(s) for s in steps)
                    norms.append(
                        (
                            item_id,
                            f"- [{item_id}] {summary}{_format_memory_meta(item, mtype, confidence_label=confidence_label)}（步骤：{step_text}）",
                        )
                    )
                else:
                    norms.append(
                        (
                            item_id,
                            f"- [{item_id}] {summary}{_format_memory_meta(item, mtype, confidence_label=confidence_label)}",
                        )
                    )
            elif mtype == "preference":
                norms.append(
                    (
                        item_id,
                        f"- [{item_id}] {summary}{_format_memory_meta(item, mtype, confidence_label=confidence_label)}",
                    )
                )
            elif mtype in ("event", "profile"):
                ts = f"[{happened_at}] " if happened_at else ""
                events.append(
                    (
                        item_id,
                        f"- [{item_id}] {ts}{summary}{_format_memory_meta(item, mtype, confidence_label=confidence_label)}",
                    )
                )

        return selected, forced, norms, events

    def _build_section_parts(
        self,
        forced: list[tuple[str, str]],
        norms: list[tuple[str, str]],
        events: list[tuple[str, str]],
    ) -> list[tuple[str, list[str]]]:
        parts: list[tuple[str, list[str]]] = []
        if forced:
            parts.append(
                (
                    "## 【强制约束】记忆规则（必须执行）\n"
                    + "\n".join(line for _, line in forced),
                    [item_id for item_id, _ in forced if item_id],
                )
            )
        if norms:
            parts.append(
                (
                    "## 【流程规范】用户偏好与规则\n"
                    + "\n".join(line for _, line in norms),
                    [item_id for item_id, _ in norms if item_id],
                )
            )
        if events:
            parts.append(
                (
                    "## 【相关历史】你与当前用户的过往对话（来自记忆检索，时间戳可信，可直接引用，不得自行否定；数字/金额/地名等具体值以记录为准，不得用常识替换；可根据上下文合理推断，如去某城市探望姐姐可推断姐姐住在该城市）\n"
                    + "\n".join(line for _, line in events),
                    [item_id for item_id, _ in events if item_id],
                )
            )
        return parts

    def _apply_char_budget(
        self,
        parts: list[tuple[str, list[str]]],
        *,
        has_forced: bool,
    ) -> tuple[str, list[str]]:
        if not parts:
            return "", []

        final_parts: list[str] = []
        injected_ids: list[str] = []
        seen_ids: set[str] = set()
        total = 0
        for idx, (part, part_ids) in enumerate(parts):
            add_len = len(part) + (2 if final_parts else 0)
            is_forced_part = idx == 0 and has_forced
            if total + add_len > self._inject_max_chars and not is_forced_part:
                continue
            final_parts.append(part)
            total += add_len
            for item_id in part_ids:
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    injected_ids.append(item_id)
        return "\n\n".join(final_parts), injected_ids


def _dedupe_texts(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for text in texts:
        normalized = (text or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _remember_vector_hit(
    seen: dict[str, dict],
    hit: dict,
) -> None:
    hit_id = _hit_id(hit)
    hit_score = _hit_score(hit)
    seen_score = _hit_score(seen.get(hit_id, {}))
    if hit_id and (hit_id not in seen or hit_score > seen_score):
        seen[hit_id] = hit


def _hit_id(item: dict) -> str:
    return str(item.get("id", "") or "")


def _hit_score(item: dict, fallback_key: str = "score") -> float:
    raw = item.get(fallback_key)
    if raw is None and fallback_key != "score":
        raw = item.get("score")
    return float(raw) if isinstance(raw, int | float) else 0.0


_CJK_STOPWORDS = {
    "用户",
    "助手",
    "我们",
    "他们",
    "这个",
    "那个",
    "什么",
    "如何",
    "是否",
    "有没",
    "没有",
    "有过",
    "做过",
    "进行",
    "完成",
    "包括",
    "通过",
    "实现",
    "行为",
    "内容",
    "相关",
    "情况",
    "问题",
    "方式",
    "时候",
    "时间",
    "目前",
    "当前",
    "最近",
    "之前",
    "以前",
    "后来",
    "然后",
    "因为",
    "所以",
    "但是",
    "用户在",
    "用户对",
    "的行为吗",
    "进行了",
}


def _extract_terms(query: str) -> list[str]:
    terms: list[str] = []
    ascii_tokens = re.findall(r"[a-zA-Z0-9_\-\.]{2,}", query)
    terms.extend(ascii_tokens)

    cjk_chunks = re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]{2,}", query)
    for chunk in cjk_chunks:
        if len(chunk) <= 4:
            if chunk not in _CJK_STOPWORDS:
                terms.append(chunk)
            continue
        for i in range(len(chunk) - 1):
            bigram = chunk[i : i + 2]
            if bigram not in _CJK_STOPWORDS:
                terms.append(bigram)

    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        result.append(term)
    return result[:20]


def _scope_matches(
    item: dict,
    *,
    scope_channel: str | None,
    scope_chat_id: str | None,
) -> bool:
    if not scope_channel and not scope_chat_id:
        return True
    return str(item.get("scope_channel") or "") == str(scope_channel or "") and str(
        item.get("scope_chat_id") or ""
    ) == str(scope_chat_id or "")


def _mark_scope_matches(
    items: list[dict],
    *,
    scope_channel: str | None,
    scope_chat_id: str | None,
) -> list[dict]:
    marked: list[dict] = []
    for item in items:
        candidate = dict(item)
        candidate["scope_match"] = _scope_matches(
            candidate,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
        )
        marked.append(candidate)
    return marked


def _rrf_merge(
    vector_items: list[dict],
    keyword_items: list[dict],
    *,
    top_n: int,
    k: int = _RRF_K,
) -> list[dict]:
    vec_rank: dict[str, int] = {}
    for index, item in enumerate(sorted(vector_items, key=_hit_score, reverse=True)):
        item_id = _hit_id(item)
        if item_id and item_id not in vec_rank:
            vec_rank[item_id] = index + 1

    keyword_rank: dict[str, int] = {}
    for index, item in enumerate(keyword_items):
        item_id = _hit_id(item)
        if item_id and item_id not in keyword_rank:
            keyword_rank[item_id] = index + 1

    id_to_item: dict[str, dict] = {}
    for item in keyword_items:
        item_id = _hit_id(item)
        if item_id:
            merged_item = dict(item)
            if "score" not in merged_item:
                merged_item["score"] = _hit_score(
                    merged_item, fallback_key="keyword_score"
                )
            id_to_item[item_id] = merged_item
    for item in vector_items:
        item_id = _hit_id(item)
        if item_id:
            id_to_item[item_id] = item

    scored: list[tuple[str, float, float]] = []
    for item_id in set(vec_rank) | set(keyword_rank):
        rrf_score = 0.0
        if item_id in vec_rank:
            rrf_score += 1.0 / (k + vec_rank[item_id])
        if item_id in keyword_rank:
            rrf_score += _KEYWORD_RRF_WEIGHT / (k + keyword_rank[item_id])
        scored.append((item_id, rrf_score, _hit_score(id_to_item.get(item_id, {}))))

    scored.sort(key=lambda item: (item[1], item[2]), reverse=True)
    result: list[dict] = []
    for item_id, rrf_score, _score in scored[:top_n]:
        item = dict(id_to_item[item_id])
        item["rrf_score"] = rrf_score
        result.append(item)
    return result


def _rrf_merge_lanes(
    items_by_lane: dict[str, list[dict]],
    *,
    top_n: int,
    k: int = _RRF_K,
) -> list[dict]:
    weights = {"keyword": _KEYWORD_RRF_WEIGHT}
    id_to_item: dict[str, dict] = {}
    id_to_rrf: dict[str, float] = {}
    id_to_best_score: dict[str, float] = {}
    id_to_lane_hits: dict[str, list[str]] = {}
    id_to_lane_ranks: dict[str, dict[str, int]] = {}
    id_to_lane_scores: dict[str, dict[str, float]] = {}
    lane_submitted_counts = {lane: len(items) for lane, items in items_by_lane.items()}

    for lane, items in items_by_lane.items():
        weight = weights.get(lane, 1.0)
        seen_in_lane: set[str] = set()
        for index, item in enumerate(items):
            item_id = _hit_id(item)
            if not item_id or item_id in seen_in_lane:
                continue
            seen_in_lane.add(item_id)
            fused_item = dict(item)
            if lane == "keyword" and "score" not in fused_item:
                fused_item["score"] = _hit_score(
                    fused_item, fallback_key="keyword_score"
                )
            id_to_item.setdefault(item_id, fused_item)
            id_to_rrf[item_id] = id_to_rrf.get(item_id, 0.0) + weight / (k + index + 1)
            id_to_best_score[item_id] = max(
                id_to_best_score.get(item_id, 0.0), _hit_score(item)
            )
            id_to_lane_hits.setdefault(item_id, []).append(lane)
            id_to_lane_ranks.setdefault(item_id, {})[lane] = index + 1
            id_to_lane_scores.setdefault(item_id, {})[lane] = _hit_score(
                item,
                fallback_key=f"{lane}_score",
            )

    ordered_ids = sorted(
        id_to_rrf,
        key=lambda item_id: (
            id_to_rrf[item_id],
            len(id_to_lane_hits[item_id]),
            id_to_best_score[item_id],
            item_id,
        ),
        reverse=True,
    )
    result: list[dict] = []
    for fused_index, item_id in enumerate(ordered_ids[:top_n], start=1):
        item = dict(id_to_item[item_id])
        item["rrf_score"] = id_to_rrf[item_id]
        item["lane_hits"] = id_to_lane_hits[item_id]
        item["retrieval"] = {
            "fused_rank": fused_index,
            "rrf_score": id_to_rrf[item_id],
            "lane_hits": list(id_to_lane_hits[item_id]),
            "lane_ranks": dict(id_to_lane_ranks.get(item_id, {})),
            "lane_scores": dict(id_to_lane_scores.get(item_id, {})),
            "lane_submitted_counts": dict(lane_submitted_counts),
        }
        result.append(item)
    return result


def _format_source_tag(source_ref: str | None) -> str:
    """从 source_ref（格式如 '["id1","id2"]#h:abc' 或 'channel@seq1-seq2#tag'）中提取消息 ID，
    返回供注入块附加的短标记，如 ' (src: telegram:<chat_id>:<message_id>)'。
    最多显示 2 个 ID，保持注入文本简洁。
    """
    if not source_ref:
        return ""
    raw = source_ref.split("#h:")[0].strip()
    ids: list[str] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            ids = [str(i) for i in parsed if i]
    except json.JSONDecodeError, ValueError:
        if raw:
            ids = [raw]
    if not ids:
        return ""
    shown = ids[:2]
    tag = ", ".join(shown)
    return f" (src: {tag})"


def _format_memory_meta(
    item: dict,
    memory_type: str,
    *,
    confidence_label: str = "",
) -> str:
    parts: list[str] = []
    if confidence_label:
        parts.append(confidence_label)
    happened_at_raw = item.get("happened_at")
    happened_at = _normalize_happened_at(happened_at_raw)
    if happened_at:
        parts.append(f"发生于: {happened_at}")
        age = _format_relative_age(happened_at_raw)
        if age:
            parts.append(age)
    source_ref = item.get("source_ref")
    src_tag = _format_source_tag(source_ref)
    if src_tag:
        parts.append("证据: 可回源原文")
        parts.append(src_tag.strip())
    else:
        parts.append("证据: 记忆摘要")
    if memory_type == "preference" and _looks_low_confidence_memory(
        item.get("summary", "")
    ):
        parts.append("低置信线索: 不能单独证明历史细节")
    if not parts:
        return ""
    return "（" + "；".join(parts) + "）"


def _normalize_happened_at(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return text
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and "T" not in text:
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_relative_age(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.fromisoformat(f"{text}T00:00:00")
        except ValueError:
            return ""
    now = datetime.now(dt.tzinfo)
    delta = now - dt
    if delta.days >= 1:
        return f"距今约 {delta.days} 天"
    hours = max(0, int(delta.total_seconds() // 3600))
    if hours >= 1:
        return f"距今约 {hours} 小时"
    minutes = max(0, int(delta.total_seconds() // 60))
    return f"距今约 {minutes} 分钟"


def _looks_low_confidence_memory(summary: object) -> bool:
    text = str(summary or "")
    return any(phrase in text for phrase in _LOW_CONFIDENCE_PHRASES)
