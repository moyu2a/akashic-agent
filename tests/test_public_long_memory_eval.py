from __future__ import annotations

from pathlib import Path

from memory2.eval_public_long_memory import (
    PublicLongMemoryCase,
    load_longmemeval_cases,
    public_case_to_eval_case,
    score_public_answer,
    stratified_sample_cases,
)


FIXTURE = Path("tests/fixtures/longmemeval_sample.jsonl")


def test_load_longmemeval_cases_normalizes_fixture_fields() -> None:
    cases = load_longmemeval_cases(FIXTURE)

    assert len(cases) == 6
    assert cases[0].source_id == "lme_001"
    assert cases[0].category == "single-session-user"
    assert cases[0].question == "What drink does Alice prefer?"
    assert cases[0].gold_answer == "green tea"
    assert cases[0].history[0]["role"] == "user"
    assert cases[0].history[0]["content"] == "Alice says she prefers green tea."


def test_load_longmemeval_cases_treats_abs_suffix_as_abstention(tmp_path: Path) -> None:
    dataset = tmp_path / "longmemeval_abs.jsonl"
    dataset.write_text(
        '{"question_id":"case_001_abs","question_type":"single-session-user",'
        '"question":"What is the passport number?","answer":"unknown",'
        '"haystack_sessions":[[{"role":"user","content":"No passport number was shared."}]]}\n',
        encoding="utf-8",
    )

    cases = load_longmemeval_cases(dataset)

    assert cases[0].category == "abstention"


def test_stratified_sample_cases_preserves_categories_with_seed() -> None:
    cases = load_longmemeval_cases(FIXTURE)

    sample = stratified_sample_cases(cases, sample_size=5, seed=42)

    assert [case.source_id for case in sample] == [
        "lme_006",
        "lme_005",
        "lme_003",
        "lme_002",
        "lme_004",
    ]
    assert {case.category for case in sample} == {
        "abstention",
        "single-session-user",
        "multi-session",
        "temporal-reasoning",
        "knowledge-update",
    }


def test_public_case_to_eval_case_uses_question_isolated_scope_without_gold() -> None:
    case = load_longmemeval_cases(FIXTURE)[0]

    eval_case = public_case_to_eval_case(case, phase="phase_a", profile="chain_tri_governed_answer_contract")

    assert eval_case.id == "lme_001"
    assert eval_case.setup["scope"]["session_key"] == "longmemeval_phase_a_lme_001"
    assert eval_case.setup["query"] == case.question
    assert eval_case.expectations["public_long_memory"]["gold_answer"] == "green tea"
    memory_text = "\n".join(item["summary"] for item in eval_case.setup["memory_items"])
    assert "green tea" in memory_text
    assert "gold_answer" not in memory_text
    assert "chain_tri_governed_answer_contract" == eval_case.expectations["public_long_memory"]["profile"]


def test_score_public_answer_uses_normalized_and_semantic_judge() -> None:
    exact = score_public_answer(
        question="When was the meeting?",
        gold_answer="2023 年 5 月",
        model_answer="二零二三年五月。",
        category="temporal-reasoning",
    )
    assert exact.passed
    assert exact.method == "normalized"

    judged = score_public_answer(
        question="When was the meeting?",
        gold_answer="2023 年 5 月",
        model_answer="五月份。",
        category="temporal-reasoning",
        semantic_judge=lambda **_: "pass",
    )
    assert judged.passed
    assert judged.method == "semantic_judge"

    uncertain = score_public_answer(
        question="Where did Alice go?",
        gold_answer="Paris",
        model_answer="I need to check memory first.",
        category="single-session-user",
        semantic_judge=lambda **_: "uncertain",
    )
    assert not uncertain.passed
    assert uncertain.needs_manual_review
    assert uncertain.method == "semantic_ambiguity"


def test_score_public_answer_rejects_empty_and_tool_call_answers() -> None:
    empty = score_public_answer(
        question="What drink?",
        gold_answer="green tea",
        model_answer=" ",
        category="single-session-user",
    )
    assert not empty.passed
    assert empty.method == "empty_answer"

    tool_call = score_public_answer(
        question="What drink?",
        gold_answer="green tea",
        model_answer="<tool_call>recall_memory</tool_call>",
        category="single-session-user",
    )
    assert not tool_call.passed
    assert tool_call.method == "tool_call_only"
