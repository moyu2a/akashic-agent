from __future__ import annotations

from scripts.run_memory_governance_stability_eval import summarize_stability


def test_summarize_stability_passes_when_range_is_within_gate() -> None:
    summary = summarize_stability({"0.0": 0.975, "0.3": 0.9625, "0.7": 0.95})

    assert summary["deterministic_accuracy"] == 0.975
    assert summary["sampling_robustness_range"] == 0.025
    assert summary["gate_passed"] is True
