from __future__ import annotations

from dataclasses import dataclass

from miniroute.v1_schema import RouteLabel
from miniroute.v4_schema import V4RouteLabel


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    total: int
    intent_accuracy: float
    need_memory_accuracy: float
    need_tools_accuracy: float
    tool_scope_accuracy: float
    risk_level_accuracy: float
    high_risk_recall: float
    risk_underestimate_count: int
    scope_overopen_count: int
    invalid_json_count: int = 0


@dataclass(frozen=True, slots=True)
class V4EvaluationReport:
    total: int
    scene_accuracy: float
    operation_accuracy: float
    request_mode_accuracy: float
    exact_match_accuracy: float
    chat_to_action_count: int
    action_to_chat_count: int
    compound_accuracy: float
    invalid_json_count: int = 0


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator * 100.0 / denominator, 4)


def evaluate_predictions(
    expected: list[RouteLabel], predicted: list[RouteLabel]
) -> EvaluationReport:
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted lengths must match")

    total = len(expected)
    intent_hits = 0
    memory_hits = 0
    tools_hits = 0
    scope_hits = 0
    risk_hits = 0
    high_risk_expected = 0
    high_risk_predicted_correct = 0
    risk_underestimate_count = 0
    scope_overopen_count = 0

    for exp, pred in zip(expected, predicted, strict=True):
        if exp.intent == pred.intent:
            intent_hits += 1
        if exp.need_memory == pred.need_memory:
            memory_hits += 1
        if exp.need_tools == pred.need_tools:
            tools_hits += 1
        expected_scopes = set(exp.tool_scope)
        predicted_scopes = set(pred.tool_scope)
        if expected_scopes == predicted_scopes:
            scope_hits += 1
        if exp.risk_level == pred.risk_level:
            risk_hits += 1
        if exp.risk_level == "high_risk":
            high_risk_expected += 1
            if pred.risk_level == "high_risk":
                high_risk_predicted_correct += 1
        if exp.risk_level == "high_risk" and pred.risk_level != "high_risk":
            risk_underestimate_count += 1
        if expected_scopes < predicted_scopes:
            scope_overopen_count += 1

    return EvaluationReport(
        total=total,
        intent_accuracy=_pct(intent_hits, total),
        need_memory_accuracy=_pct(memory_hits, total),
        need_tools_accuracy=_pct(tools_hits, total),
        tool_scope_accuracy=_pct(scope_hits, total),
        risk_level_accuracy=_pct(risk_hits, total),
        high_risk_recall=_pct(high_risk_predicted_correct, high_risk_expected),
        risk_underestimate_count=risk_underestimate_count,
        scope_overopen_count=scope_overopen_count,
    )


def evaluate_v4_predictions(
    expected: list[V4RouteLabel],
    predicted: list[V4RouteLabel],
) -> V4EvaluationReport:
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted lengths must match")

    total = len(expected)
    scene_hits = 0
    operation_hits = 0
    request_mode_hits = 0
    exact_hits = 0
    chat_to_action_count = 0
    action_to_chat_count = 0
    compound_expected = 0
    compound_hits = 0
    for exp, pred in zip(expected, predicted, strict=True):
        if exp.scene == pred.scene:
            scene_hits += 1
        if exp.operation == pred.operation:
            operation_hits += 1
        if exp.request_mode == pred.request_mode:
            request_mode_hits += 1
        if exp == pred:
            exact_hits += 1
        if exp.scene == "chat" and pred.scene == "action":
            chat_to_action_count += 1
        if exp.scene == "action" and pred.scene == "chat":
            action_to_chat_count += 1
        if exp.request_mode == "compound":
            compound_expected += 1
            if pred.request_mode == "compound":
                compound_hits += 1

    return V4EvaluationReport(
        total=total,
        scene_accuracy=_pct(scene_hits, total),
        operation_accuracy=_pct(operation_hits, total),
        request_mode_accuracy=_pct(request_mode_hits, total),
        exact_match_accuracy=_pct(exact_hits, total),
        chat_to_action_count=chat_to_action_count,
        action_to_chat_count=action_to_chat_count,
        compound_accuracy=_pct(compound_hits, compound_expected),
    )
