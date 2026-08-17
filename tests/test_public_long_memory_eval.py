from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from memory2.eval_public_long_memory import (
    PublicEvidenceRenderConfig,
    PublicLongMemoryCase,
    build_public_evidence_render_config,
    build_public_long_memory_report,
    load_longmemeval_cases,
    public_case_to_eval_case,
    render_public_long_memory_evidence,
    score_public_answer,
    stratified_sample_cases,
)


FIXTURE = Path("tests/fixtures/longmemeval_sample.jsonl")


def _report_for_public_answer(
    tmp_path: Path,
    *,
    case: PublicLongMemoryCase,
    answer_text: str,
    evidence_text: str = "",
) -> dict:
    answer_debug_dir = tmp_path / "answer_debug"
    answer_debug_dir.mkdir()
    (answer_debug_dir / f"{case.source_id}.json").write_text(
        json.dumps(
            {
                "case_id": case.source_id,
                "answer_text": answer_text,
                "evidence_block_text": evidence_text,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    benchmark_report = SimpleNamespace(
        run_id="run",
        generated_at="2026-08-17T00:00:00+00:00",
        metrics={"completed_call_count": 1},
        case_records=[
            {
                "case_id": case.source_id,
                "category": f"public_long_memory_{case.category}",
                "profile_name": "chain_tri_governed_answer_contract",
                "prompt_variant": "baseline",
                "repeat_index": 0,
                "answer_rule_passed": False,
                "memory_grounding_passed": False,
                "provider_error": False,
                "timeout": False,
                "failures": (),
            }
        ],
        failure_records=(),
    )
    return build_public_long_memory_report(
        benchmark_report=benchmark_report,
        dataset_path=tmp_path / "dataset.jsonl",
        dataset_hash="hash",
        dataset_cases=(case,),
        sampled_cases=(case,),
        phase="phase_a",
        profile="chain_tri_governed_answer_contract",
        seed=42,
        sample_size=1,
        answer_debug_dir=answer_debug_dir,
        command_shape_hash="shape",
        real_llm_enabled=False,
        fake_provider_enabled=True,
    )


def test_load_longmemeval_cases_normalizes_fixture_fields() -> None:
    cases = load_longmemeval_cases(FIXTURE)

    assert len(cases) == 6
    assert cases[0].source_id == "lme_001"
    assert cases[0].category == "single-session-user"
    assert cases[0].question == "What drink does Alice prefer?"
    assert cases[0].gold_answer == "green tea"
    assert cases[0].history[0]["role"] == "user"
    assert cases[0].history[0]["content"] == "Alice says she prefers green tea."


def test_load_longmemeval_cases_preserves_question_date(tmp_path: Path) -> None:
    dataset = tmp_path / "longmemeval_date.jsonl"
    dataset.write_text(
        '{"question_id":"case_date","question_type":"temporal-reasoning",'
        '"question":"What happened yesterday?","answer":"roadmap review",'
        '"question_date":"2024-02-03T00:00:00+00:00",'
        '"haystack_sessions":[[{"role":"user","content":"The roadmap review was yesterday.","has_answer":true}]],'
        '"haystack_session_ids":["s1"],"haystack_dates":["2024-02-02"]}\n',
        encoding="utf-8",
    )

    case = load_longmemeval_cases(dataset)[0]
    eval_case = public_case_to_eval_case(case, phase="phase_a")

    assert case.question_date == "2024-02-03T00:00:00+00:00"
    assert eval_case.setup["public_long_memory"]["question_date"] == "2024-02-03T00:00:00+00:00"
    assert eval_case.expectations["public_long_memory"]["question_date"] == "2024-02-03T00:00:00+00:00"


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


def test_load_longmemeval_cases_preserves_haystack_sessions_as_memory_chunks(tmp_path: Path) -> None:
    dataset = tmp_path / "longmemeval_sessions.jsonl"
    dataset.write_text(
        '{"question_id":"case_002","question_type":"multi-session",'
        '"question":"What was the final amount?","answer":"$400",'
        '"haystack_session_ids":["s1","s2"],'
        '"haystack_dates":["2024-01-01","2024-01-02"],'
        '"haystack_sessions":['
        '[{"role":"user","content":"First amount was $300."},'
        '{"role":"assistant","content":"Noted."}],'
        '[{"role":"user","content":"Final amount became $400.","has_answer":true}]'
        ']}\n',
        encoding="utf-8",
    )

    case = load_longmemeval_cases(dataset)[0]
    eval_case = public_case_to_eval_case(case, phase="phase_a")

    assert len(case.history) == 2
    assert case.history[0]["role"] == "session"
    assert "user: First amount was $300." in case.history[0]["content"]
    assert "assistant: Noted." in case.history[0]["content"]
    assert len(eval_case.setup["memory_items"]) == 2
    assert eval_case.setup["memory_items"][0]["extra_json"]["session_id"] == "s1"
    assert eval_case.setup["memory_items"][0]["extra_json"]["session_date"] == "2024-01-01"
    assert eval_case.setup["memory_items"][1]["extra_json"]["turns"][0]["turn_index"] == 1
    assert eval_case.setup["memory_items"][1]["extra_json"]["turns"][0]["has_answer"] is True


def test_answer_window_rendering_uses_answer_turn_and_token_budget() -> None:
    item = {
        "summary": "session: " + "leading filler " * 80,
        "content": "session: " + "leading filler " * 80,
        "extra_json": {
            "benchmark": "longmemeval",
            "session_id": "session-9",
            "session_date": "2024-01-02",
            "turns": [
                {"turn_index": 1, "role": "user", "content": "irrelevant opening " * 40, "has_answer": False},
                {"turn_index": 2, "role": "assistant", "content": "ack", "has_answer": False},
                {"turn_index": 3, "role": "user", "content": "The final amount became $400.", "has_answer": True},
                {"turn_index": 4, "role": "assistant", "content": "Recorded.", "has_answer": False},
                {"turn_index": 5, "role": "user", "content": "unrelated closing " * 40, "has_answer": False},
            ],
        },
    }

    rendered, metadata = render_public_long_memory_evidence(
        item,
        PublicEvidenceRenderConfig(
            mode="answer_window",
            long_evidence_token_limit=16,
            reserved_prompt_token_budget=2000,
            model_context_window=8192,
            answer_window_turns=1,
        ),
    )

    assert "The final amount became $400." in rendered
    assert "session_id=session-9; session_date=2024-01-02" in rendered
    assert "irrelevant opening" not in rendered
    assert metadata["answer_window_source"] == "has_answer_turn"
    assert metadata["effective_evidence_token_budget"] == 16


def test_answer_window_rendering_falls_back_to_last_third_without_has_answer() -> None:
    item = {
        "summary": "session summary",
        "content": "session content",
        "extra_json": {
            "benchmark": "longmemeval",
            "turns": [
                {"turn_index": 1, "role": "user", "content": "first", "has_answer": False},
                {"turn_index": 2, "role": "assistant", "content": "second", "has_answer": False},
                {"turn_index": 3, "role": "user", "content": "third", "has_answer": False},
                {"turn_index": 4, "role": "assistant", "content": "fourth", "has_answer": False},
                {"turn_index": 5, "role": "user", "content": "fifth", "has_answer": False},
                {"turn_index": 6, "role": "assistant", "content": "sixth", "has_answer": False},
            ],
        },
    }

    rendered, metadata = render_public_long_memory_evidence(
        item,
        PublicEvidenceRenderConfig(mode="answer_window"),
    )

    assert "user: fifth" in rendered
    assert "assistant: sixth" in rendered
    assert "user: first" not in rendered
    assert metadata["answer_window_source"] == "last_third"
    assert metadata["answer_window_fallback_reason"] == "oracle_missing_has_answer"


def test_build_public_evidence_render_config_records_token_budget() -> None:
    config = build_public_evidence_render_config(
        mode="answer_window",
        long_evidence_token_limit=3000,
        reserved_prompt_token_budget=2000,
        model_context_window=4096,
        answer_window_turns=2,
    )

    assert config.effective_token_budget == 2096


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
    assert tool_call.method == "tool_call_style_output"


def test_public_report_flags_language_mismatch_without_overwriting_score(tmp_path: Path) -> None:
    case = PublicLongMemoryCase(
        source_id="lang_001",
        category="single-session-user",
        question="What drink does Alice prefer?",
        gold_answer="green tea",
        history=({"role": "user", "content": "Alice prefers green tea."},),
    )

    report = _report_for_public_answer(
        tmp_path,
        case=case,
        answer_text="绿茶。",
        evidence_text="user: Alice prefers green tea.",
    )
    review = report["case_reviews"][0]

    assert review["public_score"]["passed"] is False
    assert review["public_score"]["method"] == "deterministic_mismatch"
    assert review["question_language"] == "en"
    assert review["response_language"] == "zh"
    assert review["language_mismatch"] is True
    assert "language_mismatch_scorer_false_negative_possible" in review["failure_attribution"]
    assert report["metrics"]["language_mismatch_count"] == 1


def test_public_report_marks_abstention_intent_as_secondary_pass(tmp_path: Path) -> None:
    case = PublicLongMemoryCase(
        source_id="abs_001",
        category="abstention",
        question="What is the passport number?",
        gold_answer="unknown",
        history=({"role": "user", "content": "No passport number was shared."},),
    )

    report = _report_for_public_answer(
        tmp_path,
        case=case,
        answer_text="I don't know; the history does not provide it.",
        evidence_text="user: No passport number was shared.",
    )
    review = report["case_reviews"][0]

    assert review["public_score"]["passed"] is False
    assert review["strict_public_score"]["passed"] is False
    assert review["secondary_public_score"]["passed"] is True
    assert review["secondary_public_score"]["method"] == "abstention_intent"
    assert review["abstention_intent_passed"] is True
    assert "abstention_intent_passed_deterministic_fail" in review["failure_attribution"]
    assert report["metrics"]["abstention_intent_pass_count"] == 1
    assert report["metrics"]["secondary_public_answer_pass_count"] == 1
    assert report["metrics"]["strict_public_answer_pass_count"] == 0


def test_public_report_marks_preference_cases_for_semantic_review(tmp_path: Path) -> None:
    case = PublicLongMemoryCase(
        source_id="pref_001",
        category="single-session-preference",
        question="What kind of cafe does Alice prefer?",
        gold_answer="quiet cafes",
        history=({"role": "user", "content": "Alice likes calm places to work."},),
    )

    report = _report_for_public_answer(
        tmp_path,
        case=case,
        answer_text="Alice prefers calm places for working.",
        evidence_text="user: Alice likes calm places to work.",
    )
    review = report["case_reviews"][0]

    assert review["semantic_review_needed"] is True
    assert "semantic_review_needed" in review["failure_attribution"]
    assert report["metrics"]["semantic_review_needed_count"] == 1


def test_public_report_splits_literal_and_reasoning_evidence_support(tmp_path: Path) -> None:
    case = PublicLongMemoryCase(
        source_id="support_001",
        category="multi-session",
        question="Which city did Carol visit after Rome?",
        gold_answer="Berlin",
        history=({"role": "user", "content": "After Rome, Carol went to Berlin."},),
    )

    report = _report_for_public_answer(
        tmp_path,
        case=case,
        answer_text="Berlin.",
        evidence_text="user: After Rome, Carol went to Berlin.",
    )
    review = report["case_reviews"][0]

    assert review["literal_gold_hit"] is True
    assert review["supporting_fact_hit"] is True
    assert review["requires_reasoning_gold"] is False
    assert report["metrics"]["literal_gold_hit_count"] == 1
    assert report["metrics"]["supporting_fact_hit_count"] == 1
