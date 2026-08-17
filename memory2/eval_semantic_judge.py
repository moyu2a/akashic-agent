from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SemanticJudgeConfig:
    enabled: bool
    tested_model_family: str
    arbiter_model_family: str
    threshold: float
    calibration_run_id: str


@dataclass(frozen=True)
class SemanticJudgeResult:
    passed: bool
    similarity: float | None
    reason: str
    needs_human_review: bool
    semantic_ambiguity: bool


def judge_semantic_equivalence(
    *,
    answer_text: str,
    expected_templates: Sequence[str],
    config: SemanticJudgeConfig,
) -> SemanticJudgeResult:
    if not config.enabled or not config.arbiter_model_family:
        return SemanticJudgeResult(
            passed=False,
            similarity=None,
            reason="semantic judge disabled or unavailable",
            needs_human_review=True,
            semantic_ambiguity=True,
        )
    if (
        config.tested_model_family.strip().lower()
        == config.arbiter_model_family.strip().lower()
    ):
        raise ValueError("semantic judge arbiter cannot use same model family")
    similarity = max(
        (_character_jaccard(answer_text, expected) for expected in expected_templates),
        default=0.0,
    )
    passed = similarity >= float(config.threshold)
    return SemanticJudgeResult(
        passed=passed,
        similarity=round(similarity, 4),
        reason="similarity_above_threshold" if passed else "similarity_below_threshold",
        needs_human_review=not passed,
        semantic_ambiguity=True,
    )


def choose_semantic_threshold(
    labeled_samples: Sequence[dict[str, object]],
    thresholds: Sequence[float] = (0.75, 0.80, 0.85, 0.90),
) -> dict[str, object]:
    best_threshold = float(thresholds[0])
    best_f1 = -1.0
    for threshold in thresholds:
        f1 = _f1_for_threshold(labeled_samples, float(threshold))
        if f1 > best_f1:
            best_threshold = float(threshold)
            best_f1 = f1
    return {
        "threshold_candidates": [float(item) for item in thresholds],
        "chosen_threshold": best_threshold,
        "calibration_f1": round(best_f1, 4),
    }


def _f1_for_threshold(samples: Sequence[dict[str, object]], threshold: float) -> float:
    true_positive = false_positive = false_negative = 0
    for sample in samples:
        predicted = float(sample.get("similarity") or 0.0) >= threshold
        actual = bool(sample.get("label"))
        if predicted and actual:
            true_positive += 1
        elif predicted and not actual:
            false_positive += 1
        elif not predicted and actual:
            false_negative += 1
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = (
        true_positive / precision_denominator if precision_denominator else 0.0
    )
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _character_jaccard(left: str, right: str) -> float:
    left_chars = {char for char in left if not char.isspace()}
    right_chars = {char for char in right if not char.isspace()}
    if not left_chars or not right_chars:
        return 0.0
    return len(left_chars & right_chars) / len(left_chars | right_chars)
