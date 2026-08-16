from __future__ import annotations


def summarize_stability(temperature_accuracy: dict[str, float]) -> dict[str, object]:
    values = [float(value) for value in temperature_accuracy.values()]
    robustness_range = round(max(values) - min(values), 4) if values else 0.0
    return {
        "deterministic_accuracy": float(temperature_accuracy.get("0.0", 0.0)),
        "temperature_accuracy": dict(temperature_accuracy),
        "sampling_robustness_range": robustness_range,
        "gate_passed": robustness_range <= 0.05,
    }
