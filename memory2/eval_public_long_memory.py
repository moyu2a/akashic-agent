from __future__ import annotations

import hashlib
import json
import math
import random
import re
import unicodedata
from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from memory2.eval_cases import EVAL_CONFIG_PROFILES, EVAL_PHASE_TARGETS, EvalCase


PUBLIC_LONG_MEMORY_PROFILE = "chain_tri_governed_answer_contract"


@dataclass(frozen=True)
class PublicLongMemoryCase:
    source_id: str
    category: str
    question: str
    gold_answer: str
    history: tuple[dict[str, Any], ...]
    question_date: str = ""
    answer_aliases: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None


PublicEvidenceRenderMode = Literal["compact", "long_context", "answer_window", "auto"]


@dataclass(frozen=True)
class PublicEvidenceRenderConfig:
    mode: PublicEvidenceRenderMode = "answer_window"
    long_evidence_token_limit: int = 3000
    reserved_prompt_token_budget: int = 2000
    model_context_window: int = 8192
    answer_window_turns: int = 2

    @property
    def effective_token_budget(self) -> int:
        available = max(1, self.model_context_window - self.reserved_prompt_token_budget)
        return max(1, min(self.long_evidence_token_limit, available))


@dataclass(frozen=True)
class PublicAnswerScore:
    passed: bool
    method: str
    normalized_gold: str
    normalized_answer: str
    needs_manual_review: bool = False


SemanticJudge = Callable[..., Literal["pass", "fail", "uncertain"]]


def build_public_evidence_render_config(
    *,
    mode: PublicEvidenceRenderMode = "answer_window",
    long_evidence_token_limit: int = 3000,
    reserved_prompt_token_budget: int = 2000,
    model_context_window: int = 8192,
    answer_window_turns: int = 2,
) -> PublicEvidenceRenderConfig:
    if mode not in {"compact", "long_context", "answer_window", "auto"}:
        raise ValueError(f"unknown evidence render mode: {mode}")
    if long_evidence_token_limit < 1:
        raise ValueError("long_evidence_token_limit must be at least 1")
    if reserved_prompt_token_budget < 0:
        raise ValueError("reserved_prompt_token_budget must be non-negative")
    if model_context_window < 1:
        raise ValueError("model_context_window must be at least 1")
    if answer_window_turns < 0:
        raise ValueError("answer_window_turns must be non-negative")
    return PublicEvidenceRenderConfig(
        mode=mode,
        long_evidence_token_limit=long_evidence_token_limit,
        reserved_prompt_token_budget=reserved_prompt_token_budget,
        model_context_window=model_context_window,
        answer_window_turns=answer_window_turns,
    )


def load_longmemeval_cases(path: Path) -> tuple[PublicLongMemoryCase, ...]:
    rows = _load_json_or_jsonl(path)
    cases: list[PublicLongMemoryCase] = []
    for index, row in enumerate(rows, start=1):
        cases.append(_case_from_payload(row, index=index))
    return tuple(cases)


def dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stratified_sample_cases(
    cases: tuple[PublicLongMemoryCase, ...],
    *,
    sample_size: int,
    seed: int,
) -> tuple[PublicLongMemoryCase, ...]:
    if sample_size <= 0:
        return ()
    if sample_size >= len(cases):
        return tuple(cases)
    by_category: dict[str, list[PublicLongMemoryCase]] = {}
    for case in cases:
        by_category.setdefault(case.category, []).append(case)
    categories = sorted(by_category)
    if sample_size < len(categories):
        raise ValueError("sample_size must be at least the category count")

    raw_allocations = {
        category: len(rows) * sample_size / len(cases)
        for category, rows in by_category.items()
    }
    allocations = {
        category: max(1, int(math.floor(raw_allocations[category])))
        for category in categories
    }
    while sum(allocations.values()) > sample_size:
        category = max(
            categories,
            key=lambda item: (
                allocations[item] > 1,
                allocations[item] - raw_allocations[item],
                item,
            ),
        )
        if allocations[category] <= 1:
            break
        allocations[category] -= 1
    while sum(allocations.values()) < sample_size:
        category = max(
            categories,
            key=lambda item: (
                raw_allocations[item] - allocations[item],
                len(by_category[item]) - allocations[item],
                item,
            ),
        )
        allocations[category] += 1

    rng = random.Random(seed)
    sampled: list[PublicLongMemoryCase] = []
    for category in categories:
        rows = list(by_category[category])
        rows.sort(key=lambda case: case.source_id)
        rng.shuffle(rows)
        selected = sorted(rows[: allocations[category]], key=lambda case: case.source_id)
        sampled.extend(selected)
    return tuple(sampled)


def public_case_to_eval_case(
    case: PublicLongMemoryCase,
    *,
    phase: str,
    profile: str = PUBLIC_LONG_MEMORY_PROFILE,
    evidence_render_config: PublicEvidenceRenderConfig | None = None,
) -> EvalCase:
    scope_id = f"longmemeval_{phase}_{_safe_id(case.source_id)}"
    render_config = evidence_render_config or build_public_evidence_render_config()
    memory_items = [
        {
            "id": f"{case.source_id}_history_{index:04d}",
            "memory_type": "public_long_memory_history",
            "summary": f"{message['role']}: {message['content']}",
            "content": message["content"],
            "status": "active",
            "source_ref": f"longmemeval://{case.source_id}/history/{index}",
            "confidence": "high",
            "scope_channel": "public_long_memory_eval",
            "scope_chat_id": case.source_id,
            "extra_json": {
                "benchmark": "longmemeval",
                "category": case.category,
                "source_id": case.source_id,
                "role": message["role"],
                "turn_index": message.get("turn_index", index),
                "has_answer": bool(message.get("has_answer", False)),
                "turns": list(message.get("turns", ()))
                if isinstance(message.get("turns"), list)
                else [],
                "session_id": message.get("session_id", ""),
                "session_date": message.get("session_date", ""),
                "phase": phase,
            },
        }
        for index, message in enumerate(case.history, start=1)
    ]
    return EvalCase(
        id=case.source_id,
        title=f"LongMemEval {case.source_id}",
        category=f"public_long_memory_{case.category}",
        phase_targets=EVAL_PHASE_TARGETS,
        config_profiles=EVAL_CONFIG_PROFILES,
        setup={
            "scope": {
                "session_key": scope_id,
                "channel": "public_long_memory_eval",
                "chat_id": case.source_id,
            },
            "measurement_family": "public_long_memory",
            "target_profile": profile,
            "query": case.question,
            "memory_items": memory_items,
            "memory_replacements": [],
            "public_long_memory": {
                "benchmark": "longmemeval",
                "source_id": case.source_id,
                "category": case.category,
                "question_date": case.question_date,
                "profile": profile,
                "phase": phase,
            },
            "public_long_memory_evidence_render": asdict(render_config),
        },
        expectations={
            "answer_expectations": {
                "expected_answer_contains": [case.gold_answer],
                "expected_answer_contains_any": [
                    [case.gold_answer, *case.answer_aliases]
                ],
                "forbidden_answer_contains": [],
                "expected_memory_ids": [item["id"] for item in memory_items],
                "expected_language": "",
                "grounding_required": bool(memory_items),
            },
            "public_long_memory": {
                "benchmark": "longmemeval",
                "source_id": case.source_id,
                "category": case.category,
                "gold_answer": case.gold_answer,
                "answer_aliases": list(case.answer_aliases),
                "question_date": case.question_date,
                "profile": profile,
                "phase": phase,
            },
        },
        source_path="public_long_memory_longmemeval",
    )


def score_public_answer(
    *,
    question: str,
    gold_answer: str,
    model_answer: str,
    category: str,
    answer_aliases: tuple[str, ...] = (),
    semantic_judge: SemanticJudge | None = None,
) -> PublicAnswerScore:
    answer = str(model_answer or "").strip()
    normalized_answer = normalize_public_answer(answer)
    normalized_gold = normalize_public_answer(gold_answer)
    if not answer:
        return PublicAnswerScore(False, "empty_answer", normalized_gold, normalized_answer)
    if _is_tool_call_only(answer):
        return PublicAnswerScore(False, "tool_call_style_output", normalized_gold, normalized_answer)
    candidates = (gold_answer, *answer_aliases)
    for candidate in candidates:
        normalized_candidate = normalize_public_answer(candidate)
        if normalized_candidate and normalized_candidate in normalized_answer:
            method = "exact" if str(candidate).strip() in answer else "normalized"
            return PublicAnswerScore(
                True,
                method,
                normalized_candidate,
                normalized_answer,
            )
    if semantic_judge is None:
        return PublicAnswerScore(False, "deterministic_mismatch", normalized_gold, normalized_answer)
    judgement = semantic_judge(
        question=question,
        gold_answer=gold_answer,
        model_answer=model_answer,
        category=category,
    )
    if judgement == "pass":
        return PublicAnswerScore(True, "semantic_judge", normalized_gold, normalized_answer)
    if judgement == "uncertain":
        return PublicAnswerScore(
            False,
            "semantic_ambiguity",
            normalized_gold,
            normalized_answer,
            needs_manual_review=True,
        )
    return PublicAnswerScore(False, "semantic_judge_fail", normalized_gold, normalized_answer)


def normalize_public_answer(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = _normalize_chinese_year(text)
    text = _normalize_chinese_month(text)
    for cn, digit in _CHINESE_DIGITS.items():
        text = text.replace(cn, digit)
    text = re.sub(r"\bunknown\b|\bnot\s+known\b|\bnot\s+provided\b", "unknown", text)
    return _strip_punct_and_space(text)


def public_category_distribution(
    cases: tuple[PublicLongMemoryCase, ...],
) -> dict[str, int]:
    return dict(sorted(Counter(case.category for case in cases).items()))


def build_public_long_memory_report(
    *,
    benchmark_report: Any,
    dataset_path: Path,
    dataset_hash: str,
    dataset_cases: tuple[PublicLongMemoryCase, ...],
    sampled_cases: tuple[PublicLongMemoryCase, ...],
    phase: str,
    profile: str,
    seed: int,
    sample_size: int,
    answer_debug_dir: Path | None,
    command_shape_hash: str,
    real_llm_enabled: bool,
    fake_provider_enabled: bool,
    prompt_variants: tuple[str, ...] = ("baseline",),
    repeats: int = 1,
    evidence_render_config: PublicEvidenceRenderConfig | None = None,
    capture_provider_request: bool = False,
    provider_request_debug_dir: Path | None = None,
) -> dict[str, Any]:
    case_by_id = {case.source_id: case for case in sampled_cases}
    answer_debug_by_case = _load_answer_debug_by_case(answer_debug_dir)
    case_reviews: list[dict[str, Any]] = []
    public_pass_count = 0
    manual_review_count = 0
    unable_to_score_count = 0
    tool_call_style_count = 0
    tool_call_style_case_ids: list[str] = []
    sent_evidence_gold_hit_count = 0
    render_config = evidence_render_config or build_public_evidence_render_config()

    for record in getattr(benchmark_report, "case_records", ()):
        if not isinstance(record, dict):
            continue
        case_id = str(record.get("case_id") or "")
        case = case_by_id.get(case_id)
        debug = answer_debug_by_case.get(case_id, {})
        answer_text = str(debug.get("answer_text") or "")
        evidence_text = str(debug.get("evidence_block_text") or "")
        evidence_gold_hit = False
        public_score = None
        if case is None:
            unable_to_score_count += 1
        else:
            evidence_gold_hit = (
                bool(normalize_public_answer(case.gold_answer))
                and normalize_public_answer(case.gold_answer)
                in normalize_public_answer(evidence_text)
            )
            if evidence_gold_hit:
                sent_evidence_gold_hit_count += 1
            score = score_public_answer(
                question=case.question,
                gold_answer=case.gold_answer,
                model_answer=answer_text,
                category=case.category,
                answer_aliases=case.answer_aliases,
            )
            public_score = asdict(score)
            if score.passed:
                public_pass_count += 1
            if score.needs_manual_review:
                manual_review_count += 1
            if score.method == "tool_call_style_output":
                tool_call_style_count += 1
                tool_call_style_case_ids.append(case_id)
            if score.method in {"empty_answer", "tool_call_style_output"}:
                unable_to_score_count += 1
        render_metadata = record.get("evidence_render_metadata")
        case_reviews.append(
            {
                "source_id": case_id,
                "category": case.category if case is not None else record.get("category", ""),
                "question": case.question if case is not None else "",
                "gold_answer": case.gold_answer if case is not None else "",
                "profile": record.get("profile_name", ""),
                "prompt_variant": record.get("prompt_variant", ""),
                "repeat_index": record.get("repeat_index", 0),
                "answer_debug_available": bool(debug),
                "model_answer": answer_text,
                "sent_evidence_gold_hit": evidence_gold_hit,
                "evidence_render_metadata": render_metadata
                if isinstance(render_metadata, list)
                else [],
                "comprehensive_answer_rule_passed": record.get("answer_rule_passed", False),
                "memory_grounding_passed": record.get("memory_grounding_passed", False),
                "provider_error": record.get("provider_error", False),
                "timeout": record.get("timeout", False),
                "failures": record.get("failures", ()),
                "public_score": public_score,
            }
        )

    metrics = dict(getattr(benchmark_report, "metrics", {}) or {})
    completed = int(metrics.get("completed_call_count") or 0)
    actual_call_count = len(sampled_cases) * 1 * len(prompt_variants) * int(repeats)
    metrics.update(
        {
            "benchmark": "longmemeval",
            "phase": phase,
            "profile": profile,
            "dataset_path": str(dataset_path),
            "dataset_sha256": dataset_hash,
            "dataset_case_count": len(dataset_cases),
            "sampled_case_count": len(sampled_cases),
            "dataset_category_distribution": public_category_distribution(dataset_cases),
            "sampled_category_distribution": public_category_distribution(sampled_cases),
            "sampled_case_ids": [case.source_id for case in sampled_cases],
            "prompt_variants": list(prompt_variants),
            "repeats": int(repeats),
            "actual_call_shape": (
                f"{len(sampled_cases)} * 1 * {len(prompt_variants)} * {int(repeats)}"
                f" = {actual_call_count}"
            ),
            "evidence_render_mode": render_config.mode,
            "long_evidence_token_limit": render_config.long_evidence_token_limit,
            "reserved_prompt_token_budget": render_config.reserved_prompt_token_budget,
            "model_context_window": render_config.model_context_window,
            "answer_window_turns": render_config.answer_window_turns,
            "effective_evidence_token_budget": render_config.effective_token_budget,
            "capture_provider_request": capture_provider_request,
            "provider_request_debug_dir": str(provider_request_debug_dir or ""),
            "sampling": {
                "strategy": "stratified_by_category",
                "seed": seed,
                "requested_sample_size": sample_size,
            },
            "public_answer_pass_count": public_pass_count,
            "public_answer_pass_rate": _rate(public_pass_count, completed),
            "semantic_ambiguity_count": manual_review_count,
            "tool_call_only_count": tool_call_style_count,
            "tool_call_style_output_count": tool_call_style_count,
            "tool_call_style_output_case_ids": tool_call_style_case_ids,
            "sent_evidence_gold_hit_count": sent_evidence_gold_hit_count,
            "sent_evidence_gold_hit_rate": _rate(sent_evidence_gold_hit_count, completed),
            "scorer_unable_to_score_count": unable_to_score_count,
            "scorer_unable_to_score_rate": _rate(unable_to_score_count, completed),
            "command_shape_hash": command_shape_hash,
            "real_llm_enabled": real_llm_enabled,
            "fake_provider_enabled": fake_provider_enabled,
            "result_boundary": "LongMemEval P5-only public benchmark; not a P1-P5 ablation.",
            "gold_answer_memory_policy": "gold answers are only used by scorer/report and are never written into memory",
            "answer_writeback_policy": "model answers are not written back into memory",
        }
    )
    return {
        "run_id": getattr(benchmark_report, "run_id", ""),
        "generated_at": getattr(benchmark_report, "generated_at", ""),
        "metrics": metrics,
        "case_reviews": case_reviews,
        "failure_records": list(getattr(benchmark_report, "failure_records", ())),
    }


def write_public_long_memory_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_public_long_memory_markdown(report: dict[str, Any], path: Path) -> None:
    metrics = dict(report.get("metrics") or {})
    lines = [
        "# Public Long Memory Eval Report",
        "",
        "This report evaluates LongMemEval through the existing AgentLoop memory path.",
        "It is a P5-only public benchmark run, not a P1-P5 ablation.",
        "",
        "## Metrics",
        "",
    ]
    for key in (
        "benchmark",
        "phase",
        "profile",
        "dataset_case_count",
        "sampled_case_count",
        "completed_call_count",
        "provider_error_count",
        "timeout_count",
        "malformed_checkpoint_line_count",
        "checkpoint_provenance_mismatch_count",
        "public_answer_pass_rate",
        "tool_call_style_output_count",
        "sent_evidence_gold_hit_count",
        "evidence_render_mode",
        "effective_evidence_token_budget",
        "scorer_unable_to_score_rate",
        "real_llm_enabled",
        "fake_provider_enabled",
    ):
        lines.append(f"- `{key}`: `{metrics.get(key, '')}`")
    lines.extend(
        [
            "",
            "## Category Distribution",
            "",
            "| category | dataset | sampled |",
            "| --- | ---: | ---: |",
        ]
    )
    dataset_dist = dict(metrics.get("dataset_category_distribution") or {})
    sampled_dist = dict(metrics.get("sampled_category_distribution") or {})
    for category in sorted(set(dataset_dist) | set(sampled_dist)):
        lines.append(
            f"| {category} | {dataset_dist.get(category, 0)} | {sampled_dist.get(category, 0)} |"
        )
    lines.extend(
        [
            "",
            "## Case Reviews",
            "",
            "| source_id | category | provider_error | timeout | public_method | public_pass |",
            "| --- | --- | ---: | ---: | --- | ---: |",
        ]
    )
    for row in report.get("case_reviews") or ():
        if not isinstance(row, dict):
            continue
        score = row.get("public_score") if isinstance(row.get("public_score"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("source_id", "")),
                    str(row.get("category", "")),
                    str(row.get("provider_error", "")),
                    str(row.get("timeout", "")),
                    str(score.get("method", "")),
                    str(score.get("passed", "")),
                ]
            )
            + " |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        payload = json.loads(stripped)
        if not isinstance(payload, list):
            raise ValueError(f"{path}: JSON payload must be a list")
        return [dict(item) for item in payload]
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number}: JSONL row must be object")
        rows.append(payload)
    return rows


def _case_from_payload(payload: dict[str, Any], *, index: int) -> PublicLongMemoryCase:
    source_id = str(
        payload.get("source_id")
        or payload.get("id")
        or payload.get("question_id")
        or f"longmemeval_{index:04d}"
    )
    question = str(payload.get("question") or payload.get("query") or "").strip()
    gold_answer = str(
        payload.get("gold_answer")
        or payload.get("answer")
        or payload.get("target")
        or payload.get("reference")
        or ""
    ).strip()
    category = str(
        payload.get("category")
        or payload.get("question_type")
        or payload.get("type")
        or "unknown"
    ).strip()
    if source_id.endswith("_abs"):
        category = "abstention"
    aliases = payload.get("answer_aliases") or payload.get("aliases") or ()
    if not question:
        raise ValueError(f"{source_id}: missing question")
    if not gold_answer:
        raise ValueError(f"{source_id}: missing gold answer")
    return PublicLongMemoryCase(
        source_id=source_id,
        category=category,
        question=question,
        gold_answer=gold_answer,
        history=_normalize_history(payload),
        question_date=_question_date_from_payload(payload),
        answer_aliases=tuple(str(item) for item in aliases if str(item)),
        raw=dict(payload),
    )


def _question_date_from_payload(payload: dict[str, Any]) -> str:
    for key in (
        "question_date",
        "question_time",
        "question_timestamp",
        "query_date",
        "query_time",
        "query_timestamp",
    ):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _normalize_history(payload: dict[str, Any]) -> tuple[dict[str, str], ...]:
    haystack_sessions = payload.get("haystack_sessions")
    if isinstance(haystack_sessions, list):
        return _normalize_session_chunks(
            haystack_sessions,
            session_ids=payload.get("haystack_session_ids"),
            session_dates=payload.get("haystack_dates"),
        )
    raw = (
        payload.get("history")
        or payload.get("conversation")
        or payload.get("messages")
        or payload.get("haystack")
        or payload.get("sessions")
        or ()
    )
    messages: list[dict[str, str]] = []
    _append_messages(messages, raw)
    return tuple(messages)


def render_public_long_memory_evidence(
    item: dict[str, Any],
    config: PublicEvidenceRenderConfig,
) -> tuple[str, dict[str, object]]:
    metadata: dict[str, object] = {
        "evidence_render_mode": config.mode,
        "long_evidence_token_limit": config.long_evidence_token_limit,
        "reserved_prompt_token_budget": config.reserved_prompt_token_budget,
        "model_context_window": config.model_context_window,
        "answer_window_turns": config.answer_window_turns,
        "effective_evidence_token_budget": config.effective_token_budget,
        "answer_window_source": "",
        "answer_window_fallback_reason": "",
    }
    mode = config.mode
    if mode == "auto":
        extra = item.get("extra_json") if isinstance(item.get("extra_json"), dict) else {}
        mode = "answer_window" if extra.get("benchmark") == "longmemeval" else "compact"
        metadata["evidence_render_mode"] = mode
    if mode == "compact":
        metadata["answer_window_source"] = "compact"
        text = _compact_text(str(item.get("summary") or item.get("content") or ""))
        return _with_session_header(item, text), metadata

    turns = _turns_from_item(item)
    if mode == "long_context" or not turns:
        metadata["answer_window_source"] = "long_context"
        if not turns:
            metadata["answer_window_fallback_reason"] = "missing_turn_metadata"
        text = _format_turns(turns) if turns else str(item.get("summary") or item.get("content") or "")
        return (
            _with_session_header(
                item,
                _trim_text_to_token_budget(text, config.effective_token_budget),
            ),
            metadata,
        )

    selected = _answer_window_turns(turns, config.answer_window_turns)
    if selected[1] == "has_answer_turn":
        metadata["answer_window_source"] = "has_answer_turn"
    else:
        metadata["answer_window_source"] = "last_third"
        metadata["answer_window_fallback_reason"] = "oracle_missing_has_answer"
    return (
        _with_session_header(
            item,
            _trim_text_to_token_budget(
                _format_turns(selected[0]),
                config.effective_token_budget,
            ),
        ),
        metadata,
    )


def _append_messages(messages: list[dict[str, Any]], raw: object) -> None:
    if isinstance(raw, str):
        if raw.strip():
            messages.append({"role": "user", "content": raw.strip()})
        return
    if isinstance(raw, dict):
        content = str(
            raw.get("content")
            or raw.get("text")
            or raw.get("message")
            or raw.get("utterance")
            or ""
        ).strip()
        role = str(raw.get("role") or raw.get("speaker") or "user").strip() or "user"
        if content:
            message: dict[str, Any] = {"role": role, "content": content}
            if "has_answer" in raw:
                message["has_answer"] = bool(raw.get("has_answer"))
            messages.append(message)
        return
    if isinstance(raw, list):
        for item in raw:
            _append_messages(messages, item)


def _normalize_session_chunks(
    sessions: list[object],
    *,
    session_ids: object,
    session_dates: object,
) -> tuple[dict[str, Any], ...]:
    normalized_ids = session_ids if isinstance(session_ids, list) else []
    normalized_dates = session_dates if isinstance(session_dates, list) else []
    chunks: list[dict[str, Any]] = []
    for index, session in enumerate(sessions):
        turns: list[dict[str, Any]] = []
        _append_messages(turns, session)
        preserved_turns = [
            {
                "turn_index": turn_index,
                "role": str(turn.get("role") or "user"),
                "content": str(turn.get("content") or ""),
                "has_answer": bool(turn.get("has_answer", False)),
            }
            for turn_index, turn in enumerate(turns, start=1)
            if str(turn.get("content") or "")
        ]
        content = "\n".join(
            f"{turn['role']}: {turn['content']}" for turn in turns if turn.get("content")
        ).strip()
        if not content:
            continue
        chunk = {
            "role": "session",
            "content": content,
            "session_id": str(normalized_ids[index])
            if index < len(normalized_ids)
            else str(index + 1),
            "session_date": str(normalized_dates[index])
            if index < len(normalized_dates)
            else "",
            "turns": preserved_turns,
        }
        chunks.append(chunk)
    return tuple(chunks)


def _turns_from_item(item: dict[str, Any]) -> list[dict[str, object]]:
    extra = item.get("extra_json") if isinstance(item.get("extra_json"), dict) else {}
    turns = extra.get("turns")
    if isinstance(turns, list):
        normalized = []
        for index, turn in enumerate(turns, start=1):
            if not isinstance(turn, dict):
                continue
            content = str(turn.get("content") or "").strip()
            if not content:
                continue
            normalized.append(
                {
                    "turn_index": int(turn.get("turn_index") or index),
                    "role": str(turn.get("role") or "user"),
                    "content": content,
                    "has_answer": bool(turn.get("has_answer", False)),
                }
            )
        if normalized:
            return normalized
    content = str(item.get("content") or "").strip()
    role = str(extra.get("role") or item.get("role") or "user")
    if content:
        return [
            {
                "turn_index": int(extra.get("turn_index") or 1),
                "role": role,
                "content": content,
                "has_answer": bool(extra.get("has_answer", False)),
            }
        ]
    return []


def _answer_window_turns(
    turns: list[dict[str, object]],
    window_turns: int,
) -> tuple[list[dict[str, object]], str]:
    answer_index = next(
        (index for index, turn in enumerate(turns) if turn.get("has_answer") is True),
        None,
    )
    if answer_index is not None:
        start = max(0, answer_index - window_turns)
        end = min(len(turns), answer_index + window_turns + 1)
        return turns[start:end], "has_answer_turn"
    start = max(0, (len(turns) * 2) // 3)
    return turns[start:], "last_third"


def _format_turns(turns: list[dict[str, object]]) -> str:
    return "\n".join(
        f"{str(turn.get('role') or 'user')}: {str(turn.get('content') or '').strip()}"
        for turn in turns
        if str(turn.get("content") or "").strip()
    )


def _with_session_header(item: dict[str, Any], text: str) -> str:
    extra = item.get("extra_json") if isinstance(item.get("extra_json"), dict) else {}
    session_id = str(extra.get("session_id") or "").strip()
    session_date = str(extra.get("session_date") or "").strip()
    if not session_id and not session_date:
        return text
    header = f"session_id={session_id}; session_date={session_date}"
    body = str(text or "").strip()
    return f"{header}\n{body}" if body else header


def _trim_text_to_token_budget(text: str, token_budget: int) -> str:
    compact = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    if token_budget <= 0:
        return ""
    tokens = _rough_tokens(compact)
    if len(tokens) <= token_budget:
        return compact
    return " ".join(tokens[-token_budget:])


def _rough_tokens(text: str) -> list[str]:
    return re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9_.$/-]+|[^\w\s]", text)


def _compact_text(text: str, *, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _is_tool_call_only(answer: str) -> bool:
    text = answer.strip().lower()
    return "<tool_call" in text or "<｜｜dsml｜｜tool_calls>" in text


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "case"


_CHINESE_DIGITS = {
    "零": "0",
    "〇": "0",
    "一": "1",
    "二": "2",
    "两": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
}


def _normalize_chinese_year(text: str) -> str:
    pattern = re.compile(r"([零〇一二三四五六七八九]{4})年")

    def repl(match: re.Match[str]) -> str:
        return "".join(_CHINESE_DIGITS.get(ch, ch) for ch in match.group(1)) + "年"

    return pattern.sub(repl, text)


def _normalize_chinese_month(text: str) -> str:
    month_map = {
        "一月": "1月",
        "二月": "2月",
        "两月": "2月",
        "三月": "3月",
        "四月": "4月",
        "五月": "5月",
        "六月": "6月",
        "七月": "7月",
        "八月": "8月",
        "九月": "9月",
        "十月": "10月",
        "十一月": "11月",
        "十二月": "12月",
    }
    for source, target in month_map.items():
        text = text.replace(source, target)
    return text


def _strip_punct_and_space(text: str) -> str:
    return "".join(
        ch
        for ch in text
        if not ch.isspace() and not unicodedata.category(ch).startswith("P")
    )


def _load_answer_debug_by_case(answer_debug_dir: Path | None) -> dict[str, dict[str, Any]]:
    if answer_debug_dir is None or not answer_debug_dir.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(answer_debug_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        case_id = str(payload.get("case_id") or "")
        if case_id:
            rows[case_id] = payload
    return rows


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, 4)
