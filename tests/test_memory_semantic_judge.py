from __future__ import annotations

import pytest

from memory2.eval_llm_sample import AnswerExpectation, score_answer_text
from memory2.eval_semantic_judge import (
    SemanticJudgeConfig,
    choose_semantic_threshold,
    judge_semantic_equivalence,
)


def test_forbidden_failure_never_uses_semantic_judge() -> None:
    config = SemanticJudgeConfig(
        enabled=True,
        tested_model_family="deepseek",
        arbiter_model_family="qwen-max",
        threshold=0.8,
        calibration_run_id="cal-1",
    )
    result = score_answer_text(
        "当前是英文，但也可以中文",
        AnswerExpectation(
            expected_answer_contains=("中文",),
            forbidden_answer_contains=("英文",),
        ),
        (),
        semantic_judge_config=config,
    )

    assert result.answer_rule_passed is False
    assert "semantic_ambiguity" not in result.failures


def test_same_model_family_is_rejected() -> None:
    config = SemanticJudgeConfig(
        enabled=True,
        tested_model_family="deepseek",
        arbiter_model_family="deepseek",
        threshold=0.8,
        calibration_run_id="cal-1",
    )

    with pytest.raises(ValueError, match="same model family"):
        judge_semantic_equivalence(
            answer_text="保持中文回答",
            expected_templates=("中文",),
            config=config,
        )


def test_no_arbiter_conservative_fail() -> None:
    result = judge_semantic_equivalence(
        answer_text="保持中文回答",
        expected_templates=("中文",),
        config=SemanticJudgeConfig(
            enabled=False,
            tested_model_family="deepseek",
            arbiter_model_family="",
            threshold=0.8,
            calibration_run_id="cal-1",
        ),
    )

    assert result.passed is False
    assert result.needs_human_review is True


def test_threshold_scan_selects_best_f1() -> None:
    result = choose_semantic_threshold(
        [
            {"similarity": 0.95, "label": True},
            {"similarity": 0.86, "label": True},
            {"similarity": 0.82, "label": False},
            {"similarity": 0.70, "label": False},
        ],
        thresholds=(0.75, 0.8, 0.85, 0.9),
    )

    assert result["chosen_threshold"] == 0.85
    assert result["calibration_f1"] == 1.0


def test_semantic_ambiguity_is_reported_when_rule_fail_semantic_pass() -> None:
    result = score_answer_text(
        "请继续中文输出",
        AnswerExpectation(expected_answer_contains=("中文回答",)),
        (),
        semantic_judge_config=SemanticJudgeConfig(
            enabled=True,
            tested_model_family="deepseek",
            arbiter_model_family="qwen-max",
            threshold=0.2,
            calibration_run_id="cal-1",
        ),
    )

    assert result.answer_rule_passed is True
    assert "semantic_ambiguity" in result.failures


def test_score_answer_text_default_does_not_use_semantic_judge() -> None:
    result = score_answer_text(
        "请继续中文输出",
        AnswerExpectation(expected_answer_contains=("中文回答",)),
        (),
    )

    assert result.answer_rule_passed is False
    assert "semantic_ambiguity" not in result.failures
