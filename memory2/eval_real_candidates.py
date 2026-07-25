from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from memory2.eval_real_samples import RealSampleSet


@dataclass(frozen=True)
class CandidateEvalResult:
    sample_results: tuple[dict[str, object], ...]
    metrics: dict[str, Any]


def evaluate_unforced_candidates(sample_set: RealSampleSet) -> CandidateEvalResult:
    sample_results: list[dict[str, object]] = []
    hit_count = 0
    miss_count = 0
    wrong_scope_count = 0
    by_category: dict[str, int] = {}
    for sample in sample_set.samples:
        query_terms = _terms(sample.query)
        candidate_ids: list[str] = []
        cross_scope_ids: list[str] = []
        for item in sample.memory_items:
            if str(item.get("status") or "active") != "active":
                continue
            if not (query_terms & _terms(str(item.get("summary") or ""))):
                continue
            item_id = str(item.get("id") or "").strip()
            if not item_id:
                continue
            if _same_scope(item, sample.channel, sample.chat_id):
                candidate_ids.append(item_id)
            else:
                cross_scope_ids.append(item_id)
        expected = set(sample.should_recall_ids)
        hit = bool(expected & set(candidate_ids))
        if hit:
            hit_count += 1
        else:
            miss_count += 1
        forbidden = set(sample.should_not_recall_ids)
        wrong_scope_hits = sorted(forbidden & set(cross_scope_ids))
        wrong_scope_count += len(cross_scope_ids)
        by_category[sample.category] = by_category.get(sample.category, 0) + len(
            candidate_ids
        )
        sample_results.append(
            {
                "sample_id": sample.sample_id,
                "category": sample.category,
                "candidate_ids": candidate_ids,
                "cross_scope_candidate_ids": cross_scope_ids,
                "expected_hit": hit,
                "wrong_scope_candidate_ids": wrong_scope_hits,
            }
        )
    sample_count = len(sample_set.samples)
    return CandidateEvalResult(
        sample_results=tuple(sample_results),
        metrics={
            "label_forced_recall": False,
            "sample_count": sample_count,
            "candidate_hit_count_without_label_forcing": hit_count,
            "candidate_miss_count_without_label_forcing": miss_count,
            "candidate_hit_rate_without_label_forcing": (
                round(hit_count / sample_count, 4) if sample_count else 0.0
            ),
            "candidate_wrong_scope_count": wrong_scope_count,
            "candidate_labelled_wrong_scope_count": sum(
                len(result.get("wrong_scope_candidate_ids", []))
                for result in sample_results
            ),
            "candidate_count_by_category": by_category,
        },
    )


def _same_scope(item: dict[str, object], channel: str, chat_id: str) -> bool:
    return (
        str(item.get("scope_channel") or "") == channel
        and str(item.get("scope_chat_id") or "") == chat_id
    )


def _terms(text: str) -> set[str]:
    raw = str(text or "").lower()
    words = set(re.findall(r"[a-z0-9_]+", raw))
    cjk = {raw[idx : idx + 2] for idx in range(max(0, len(raw) - 1))}
    return {term for term in words | cjk if term.strip()}
