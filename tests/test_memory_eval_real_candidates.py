from __future__ import annotations

from pathlib import Path

from memory2.eval_real_candidates import evaluate_unforced_candidates
from memory2.eval_real_samples import collect_real_memory_samples
from tests.test_memory_eval_real_samples import _create_memory_db


def test_unforced_candidates_do_not_label_force_should_recall(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")
    sample_set = collect_real_memory_samples(workspace, limit_per_category=5)

    result = evaluate_unforced_candidates(sample_set)

    assert result.metrics["label_forced_recall"] is False
    assert result.metrics["sample_count"] == len(sample_set.samples)
    assert "candidate_hit_rate_without_label_forcing" in result.metrics
    assert "candidate_miss_count_without_label_forcing" in result.metrics
    assert "candidate_wrong_scope_count" in result.metrics
    assert "candidate_count_by_category" in result.metrics


def test_unforced_candidates_can_miss_when_query_terms_do_not_match_labels(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")
    sample_set = collect_real_memory_samples(workspace, limit_per_category=5)
    broken = sample_set.samples[0]
    broken = type(broken)(
        sample_id=broken.sample_id,
        category=broken.category,
        session_key=broken.session_key,
        channel=broken.channel,
        chat_id=broken.chat_id,
        query="完全无关的问题",
        should_recall_ids=broken.should_recall_ids,
        should_not_recall_ids=broken.should_not_recall_ids,
        memory_items=broken.memory_items,
        memory_replacements=broken.memory_replacements,
    )
    sample_set = type(sample_set)(
        samples=(broken, *sample_set.samples[1:]),
        metrics=sample_set.metrics,
        issues=sample_set.issues,
    )

    result = evaluate_unforced_candidates(sample_set)

    assert result.metrics["candidate_miss_count_without_label_forcing"] >= 1
