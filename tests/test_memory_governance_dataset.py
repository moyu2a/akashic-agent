from __future__ import annotations

import json
from pathlib import Path

from memory2.eval_memory_governance_dataset import (
    MemoryGovernanceEvalCase,
    load_memory_governance_cases,
    validate_memory_governance_cases,
)


def _case_payload(case_id: str = "mgov_001") -> dict[str, object]:
    return {
        "case_id": case_id,
        "scenario": "preference_replace",
        "user_question": "我现在偏好的回答语言是什么？",
        "eval_base_time": "2026-08-16T00:00:00Z",
        "memories": [
            {
                "id": f"{case_id}_old",
                "summary": "用户过去偏好英文回答",
                "content": "用户过去偏好英文回答",
                "status": "superseded",
                "relative_timestamp_days": -120,
                "confidence": "medium",
                "source_ref": f"eval://{case_id}/old",
            },
            {
                "id": f"{case_id}_new",
                "summary": "用户现在偏好中文回答",
                "content": "用户现在偏好中文回答",
                "status": "active",
                "relative_timestamp_days": -3,
                "confidence": "high",
                "source_ref": f"eval://{case_id}/new",
            },
        ],
        "should_recall_ids": [f"{case_id}_new"],
        "should_not_recall_ids": [f"{case_id}_old"],
        "expected_answer_contains": ["中文"],
        "expected_answer_contains_any": [["中文回答", "保持中文"]],
        "forbidden_answer_contains": ["英文", "English"],
        "evidence_graph": {
            "nodes": [f"{case_id}_old", f"{case_id}_new"],
            "edges": [
                {
                    "from": f"{case_id}_old",
                    "to": f"{case_id}_new",
                    "type": "supersedes",
                }
            ],
        },
        "profile_expectations": {
            "chain_tri_retrieval": "may_fail",
            "chain_tri_candidate_governance": "should_improve",
            "chain_tri_evidence_only": "should_improve",
            "chain_tri_governed_answer_contract": "should_pass",
        },
        "notes": "新旧偏好替换 case，旧值不能进入最终回答。",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_load_memory_governance_cases_reads_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_jsonl(path, [_case_payload()])

    cases = load_memory_governance_cases(path)

    assert cases == (
        MemoryGovernanceEvalCase(
            case_id="mgov_001",
            scenario="preference_replace",
            user_question="我现在偏好的回答语言是什么？",
            eval_base_time="2026-08-16T00:00:00Z",
            memories=tuple(_case_payload()["memories"]),  # type: ignore[arg-type]
            should_recall_ids=("mgov_001_new",),
            should_not_recall_ids=("mgov_001_old",),
            expected_answer_contains=("中文",),
            expected_answer_contains_any=(("中文回答", "保持中文"),),
            forbidden_answer_contains=("英文", "English"),
            evidence_graph=_case_payload()["evidence_graph"],  # type: ignore[arg-type]
            profile_expectations=_case_payload()["profile_expectations"],  # type: ignore[arg-type]
            notes="新旧偏好替换 case，旧值不能进入最终回答。",
        ),
    )


def test_validate_rejects_duplicate_case_ids() -> None:
    case = load_memory_governance_cases_from_payloads(
        [_case_payload("mgov_001"), _case_payload("mgov_001")]
    )

    assert any(
        "duplicate case_id" in error
        for error in validate_memory_governance_cases(case)
    )


def test_validate_rejects_dangling_should_recall() -> None:
    payload = _case_payload()
    payload["should_recall_ids"] = ["missing"]
    cases = load_memory_governance_cases_from_payloads([payload])

    assert any(
        "dangling should_recall_ids" in error
        for error in validate_memory_governance_cases(cases)
    )


def test_validate_rejects_superseded_should_recall() -> None:
    payload = _case_payload()
    payload["should_recall_ids"] = ["mgov_001_old"]
    cases = load_memory_governance_cases_from_payloads([payload])

    assert any(
        "superseded should_recall_ids" in error
        for error in validate_memory_governance_cases(cases)
    )


def test_validate_rejects_expected_forbidden_conflict() -> None:
    payload = _case_payload()
    payload["forbidden_answer_contains"] = ["中文"]
    cases = load_memory_governance_cases_from_payloads([payload])

    assert any(
        "expected/forbidden conflict" in error
        for error in validate_memory_governance_cases(cases)
    )


def test_validate_rejects_evidence_graph_cycle() -> None:
    payload = _case_payload()
    payload["evidence_graph"] = {
        "nodes": ["mgov_001_old", "mgov_001_new"],
        "edges": [
            {"from": "mgov_001_old", "to": "mgov_001_new", "type": "supersedes"},
            {"from": "mgov_001_new", "to": "mgov_001_old", "type": "supersedes"},
        ],
    }
    cases = load_memory_governance_cases_from_payloads([payload])

    assert any(
        "evidence_graph cycle" in error
        for error in validate_memory_governance_cases(cases)
    )


def test_default_dataset_has_80_cases_and_8_scenario_groups() -> None:
    path = Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
    cases = load_memory_governance_cases(path)

    assert len(cases) == 80
    assert len({case.scenario for case in cases}) == 8
    assert validate_memory_governance_cases(cases) == ()


def load_memory_governance_cases_from_payloads(
    payloads: list[dict[str, object]],
) -> tuple[MemoryGovernanceEvalCase, ...]:
    cases: list[MemoryGovernanceEvalCase] = []
    for payload in payloads:
        cases.append(
            MemoryGovernanceEvalCase(
                case_id=str(payload["case_id"]),
                scenario=str(payload["scenario"]),
                user_question=str(payload["user_question"]),
                eval_base_time=str(payload["eval_base_time"]),
                memories=tuple(payload["memories"]),  # type: ignore[arg-type]
                should_recall_ids=tuple(
                    str(item) for item in payload["should_recall_ids"]  # type: ignore[index]
                ),
                should_not_recall_ids=tuple(
                    str(item) for item in payload["should_not_recall_ids"]  # type: ignore[index]
                ),
                expected_answer_contains=tuple(
                    str(item) for item in payload["expected_answer_contains"]  # type: ignore[index]
                ),
                expected_answer_contains_any=tuple(
                    tuple(str(term) for term in group)
                    for group in payload["expected_answer_contains_any"]  # type: ignore[index]
                ),
                forbidden_answer_contains=tuple(
                    str(item) for item in payload["forbidden_answer_contains"]  # type: ignore[index]
                ),
                evidence_graph=dict(payload["evidence_graph"]),  # type: ignore[arg-type]
                profile_expectations=dict(payload["profile_expectations"]),  # type: ignore[arg-type]
                notes=str(payload.get("notes") or ""),
            )
        )
    return tuple(cases)
