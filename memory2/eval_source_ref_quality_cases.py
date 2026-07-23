from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memory2.eval_source_ref_quality import (
    mark_source_ref_quality_fixture_db,
    reset_source_ref_quality_fixture_db_if_safe,
)
from memory2.source_ref_quality import SourceRefQualityInput
from session.store import SessionStore


SOURCE_REF_QUALITY_EXPANDED_SCENARIOS = (
    "already_message_supported",
    "session_level_upgradable",
    "missing_upgradable",
    "malformed_upgradable",
    "unsupported_message_kept",
    "foreign_candidate_filtered",
    "foreign_baseline_replaced",
    "invalid_same_session_baseline",
    "missing_message_id",
    "multi_message_supported",
)


@dataclass(frozen=True)
class SourceRefQualityCasePack:
    candidates: tuple[SourceRefQualityInput, ...]
    scenario_counts: dict[str, int]
    case_set_counts: dict[str, int]
    metadata: dict[str, object]


def build_source_ref_quality_case_pack(
    db_path: Path,
    *,
    common_per_scenario: int = 20,
    hard_per_scenario: int = 20,
) -> SourceRefQualityCasePack:
    if common_per_scenario <= 0 or hard_per_scenario <= 0:
        raise ValueError("common_per_scenario and hard_per_scenario must be positive")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    reset_source_ref_quality_fixture_db_if_safe(db_path)
    candidates: list[SourceRefQualityInput] = []
    scenario_counts: dict[str, int] = {}
    case_set_counts = {"common": 0, "hard": 0}
    store = SessionStore(db_path)
    try:
        store.create_session(key="cli:local")
        store.create_session(key="qq:local")
        seq = 0
        foreign_seq = 0
        for scenario in SOURCE_REF_QUALITY_EXPANDED_SCENARIOS:
            case_set = _case_set_for_scenario(scenario)
            count = common_per_scenario if case_set == "common" else hard_per_scenario
            for index in range(count):
                candidate, seq, foreign_seq = _candidate_for_scenario(
                    store,
                    scenario=scenario,
                    index=index,
                    seq=seq,
                    foreign_seq=foreign_seq,
                )
                candidates.append(candidate)
                scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
                case_set_counts[case_set] += 1
    finally:
        store.close()
    mark_source_ref_quality_fixture_db(db_path)
    return SourceRefQualityCasePack(
        candidates=tuple(candidates),
        scenario_counts=scenario_counts,
        case_set_counts=case_set_counts,
        metadata={
            "case_pack": "expanded",
            "synthetic_fixture": True,
            "common_per_scenario": common_per_scenario,
            "hard_per_scenario": hard_per_scenario,
        },
    )


def _case_set_for_scenario(scenario: str) -> str:
    if scenario in {
        "already_message_supported",
        "session_level_upgradable",
        "missing_upgradable",
        "malformed_upgradable",
        "unsupported_message_kept",
    }:
        return "common"
    return "hard"


def _candidate_for_scenario(
    store: SessionStore,
    *,
    scenario: str,
    index: int,
    seq: int,
    foreign_seq: int,
) -> tuple[SourceRefQualityInput, int, int]:
    support_term = f"{scenario}-term-{index}"
    if scenario == "multi_message_supported":
        first_id = f"cli:local:{seq}"
        _insert(store, seq, f"{support_term} 第一条来源")
        seq += 1
        second_id = f"cli:local:{seq}"
        _insert(store, seq, f"{support_term} 第二条来源")
        seq += 1
        return (
            _input(
                scenario,
                index,
                baseline_source_ref="cli:local@post_response",
                candidate_message_ids=(first_id, second_id),
                expected_terms=(support_term,),
            ),
            seq,
            foreign_seq,
        )

    current_id = f"cli:local:{seq}"
    if scenario != "missing_message_id":
        content = f"{support_term} 支持当前记忆摘要"
        if scenario == "unsupported_message_kept":
            content = "这条原始消息故意不包含候选摘要关键词"
        _insert(store, seq, content)
    seq += 1

    if scenario == "already_message_supported":
        baseline = current_id
        candidate_ids = (current_id,)
    elif scenario == "session_level_upgradable":
        baseline = "cli:local@post_response"
        candidate_ids = (current_id,)
    elif scenario == "missing_upgradable":
        baseline = ""
        candidate_ids = (current_id,)
    elif scenario == "malformed_upgradable":
        baseline = '["broken"'
        candidate_ids = (current_id,)
    elif scenario == "unsupported_message_kept":
        baseline = current_id
        candidate_ids = (current_id,)
    elif scenario == "foreign_candidate_filtered":
        foreign_id = f"qq:local:{foreign_seq}"
        _insert(store, foreign_seq, f"{support_term} foreign", session_key="qq:local")
        foreign_seq += 1
        baseline = "cli:local@post_response"
        candidate_ids = (foreign_id,)
    elif scenario == "foreign_baseline_replaced":
        foreign_id = f"qq:local:{foreign_seq}"
        _insert(store, foreign_seq, f"{support_term} foreign", session_key="qq:local")
        foreign_seq += 1
        baseline = foreign_id
        candidate_ids = (current_id,)
    elif scenario == "invalid_same_session_baseline":
        baseline = f"cli:local:bad-{index}"
        candidate_ids = (current_id,)
    elif scenario == "missing_message_id":
        missing_id = f"cli:local:{seq + 100000}"
        baseline = "cli:local@post_response"
        candidate_ids = (missing_id,)
    else:
        raise ValueError(f"unsupported source_ref quality scenario: {scenario}")

    return (
        _input(
            scenario,
            index,
            baseline_source_ref=baseline,
            candidate_message_ids=candidate_ids,
            expected_terms=(support_term,),
        ),
        seq,
        foreign_seq,
    )


def _input(
    scenario: str,
    index: int,
    *,
    baseline_source_ref: str,
    candidate_message_ids: tuple[str, ...],
    expected_terms: tuple[str, ...],
) -> SourceRefQualityInput:
    return SourceRefQualityInput(
        candidate_id=f"{_case_set_for_scenario(scenario)}::{scenario}::{index}",
        session_key="cli:local",
        baseline_source_ref=baseline_source_ref,
        candidate_message_ids=candidate_message_ids,
        expected_terms=expected_terms,
    )


def _insert(
    store: SessionStore,
    seq: int,
    content: str,
    *,
    session_key: str = "cli:local",
) -> None:
    store.insert_message(
        session_key,
        role="user",
        content=content,
        ts="2026-07-22T00:00:00+08:00",
        seq=seq,
        extra={"source_ref_quality_expanded_fixture": True},
    )
