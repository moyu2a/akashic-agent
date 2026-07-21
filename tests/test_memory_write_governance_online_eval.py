from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory2.eval_write_governance_cases import build_write_governance_candidates
from memory2.eval_write_governance_online import (
    ScriptedWriteGovernanceOnlineProvider,
    build_write_evidence_record,
    final_decision_to_evidence_decision,
    label_for_candidate,
    run_write_governance_online_eval,
    select_write_governance_online_candidates,
    write_write_governance_evidence_jsonl,
)


def _candidate(category: str):
    return next(
        candidate
        for candidate in build_write_governance_candidates(case_set="common")
        if candidate.category == category
    )


def test_label_for_candidate_maps_write_governance_categories() -> None:
    assert label_for_candidate(_candidate("valuable_preference")) == "useful"
    assert label_for_candidate(_candidate("stable_fact")) == "useful"
    assert label_for_candidate(_candidate("temporary")) == "pollution"
    assert label_for_candidate(_candidate("assistant_inference")) == "pollution"
    assert label_for_candidate(_candidate("duplicate")) == "duplicate"
    assert label_for_candidate(_candidate("conflict")) == "conflict"


def test_final_decision_to_evidence_decision_maps_write_to_allow() -> None:
    assert final_decision_to_evidence_decision("write") == "allow"
    assert final_decision_to_evidence_decision("reject") == "reject"
    assert final_decision_to_evidence_decision("review") == "review"


def test_build_write_evidence_record_has_target_metric_required_fields() -> None:
    record = build_write_evidence_record(_candidate("temporary"))

    assert record["candidate_id"]
    assert record["baseline_decision"] == "allow"
    assert record["after_decision"] in {"allow", "reject", "review"}
    assert record["label"] == "pollution"
    assert record["infra_error"] is False


def test_select_write_governance_online_candidates_balances_categories() -> None:
    candidates = select_write_governance_online_candidates(case_set="all", limit=24)

    labels = [label_for_candidate(candidate) for candidate in candidates]
    categories = {candidate.category for candidate in candidates}

    assert len(candidates) == 24
    assert categories == {
        "valuable_preference",
        "stable_fact",
        "temporary",
        "assistant_inference",
        "duplicate",
        "conflict",
    }
    assert "useful" in labels
    assert "pollution" in labels
    assert "duplicate" in labels
    assert "conflict" in labels


@pytest.mark.asyncio
async def test_run_write_governance_online_eval_fake_provider_outputs_evidence(
    tmp_path: Path,
) -> None:
    candidates = build_write_governance_candidates(case_set="common", limit=6)

    report = await run_write_governance_online_eval(
        candidates,
        tmp_path / "workspace",
        ScriptedWriteGovernanceOnlineProvider(),
        "fake-write-governance-model",
        timeout_s=5,
        real_llm_enabled=False,
        checkpoint_jsonl=None,
        resume=False,
        concurrency=1,
    )

    assert report.metrics["candidate_count"] == 6
    assert report.metrics["infra_passed"] is True
    assert report.metrics["total_token_count"] == 180
    assert len(report.evidence_records) == 6
    assert all(
        record["baseline_decision"] == "allow"
        for record in report.evidence_records
    )
    assert all(
        record["after_decision"] in {"allow", "reject", "review"}
        for record in report.evidence_records
    )


def test_write_write_governance_evidence_jsonl_is_target_metric_compatible(
    tmp_path: Path,
) -> None:
    candidates = build_write_governance_candidates(case_set="common", limit=2)
    records = [build_write_evidence_record(candidate) for candidate in candidates]
    path = tmp_path / "write_evidence.jsonl"

    write_write_governance_evidence_jsonl(records, path)

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 2
    assert {
        "candidate_id",
        "baseline_decision",
        "after_decision",
        "label",
        "infra_error",
    } <= set(rows[0])
