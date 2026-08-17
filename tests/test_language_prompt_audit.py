from __future__ import annotations

from pathlib import Path

from memory2.eval_language_prompt_audit import audit_language_prompt_sources


def test_language_prompt_audit_separates_production_from_legacy_and_fixtures() -> None:
    report = audit_language_prompt_sources(Path("."))

    assert report["metrics"]["production_hidden_answer_language_bias_count"] == 0
    assert report["metrics"]["public_p5_hidden_answer_language_bias_count"] == 0
    assert report["metrics"]["legacy_benchmark_answer_language_bias_count"] >= 1
    assert report["metrics"]["fixture_answer_language_bias_count"] >= 1

    legacy_paths = {
        item["path"]
        for item in report["findings"]
        if item["classification"] == "legacy_benchmark"
    }
    assert "eval/longmemeval/runtime.py" in legacy_paths
    assert "eval/longmemeval/qa_runner.py" in legacy_paths

    for finding in report["findings"]:
        if finding["classification"] in {"production", "public_p5"}:
            assert finding["risk"] != "hidden_answer_language_bias"
