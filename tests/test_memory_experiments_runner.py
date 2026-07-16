from __future__ import annotations

import json
from pathlib import Path

from plugins.default_memory.config import MemoryExperimentsConfig
from plugins.default_memory.experiments import (
    extract_explicit_memorize_baseline,
    MemoryExperimentRunner,
    score_write_candidate_shadow,
)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_runner_disabled_does_not_create_trace_file(tmp_path: Path) -> None:
    trace_path = tmp_path / "observe" / "memory_experiments.jsonl"
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=False, mode="off"),
    )

    runner.record(
        feature_name="write_value_score",
        session_key="cli:local",
        turn_id="cli:local@post_response",
        baseline_result={"written": True},
        experimental_result={"decision": "allow"},
        metrics={"candidate_count": 1},
    )

    assert trace_path.exists() is False


def test_runner_shadow_writes_required_trace_shape(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    trace = runner.record(
        feature_name="write_value_score",
        session_key="telegram:123",
        turn_id="telegram:123@post_response",
        baseline_result={"explicit_memorized_count": 1},
        experimental_result={"decision": "allow", "score": 0.8},
        metrics={"candidate_count": 1, "policy_allow_count": 1},
    )

    assert trace is not None
    path = tmp_path / "observe" / "memory_experiments.jsonl"
    rows = _read_jsonl(path)
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"]
    assert row["session_key"] == "telegram:123"
    assert row["turn_id"] == "telegram:123@post_response"
    assert row["feature_name"] == "write_value_score"
    assert row["mode"] == "shadow"
    assert row["baseline_result"] == {"explicit_memorized_count": 1}
    assert row["experimental_result"] == {"decision": "allow", "score": 0.8}
    assert row["diff_json"] == {
        "decision": {"baseline": None, "experimental": "allow"},
        "explicit_memorized_count": {"baseline": 1, "experimental": None},
        "score": {"baseline": None, "experimental": 0.8},
    }
    assert row["metrics_json"] == {"candidate_count": 1, "policy_allow_count": 1}
    assert "created_at" in row


def test_runner_active_mode_records_as_shadow_for_phase0(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="active"),
    )

    trace = runner.record(
        feature_name="write_value_score",
        session_key="cli:local",
        turn_id="turn-1",
        baseline_result={},
        experimental_result={},
        metrics={},
    )

    assert trace is not None
    rows = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")
    assert rows[0]["mode"] == "shadow"


def test_runner_ab_mode_records_as_shadow_for_phase0(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="ab"),
    )

    trace = runner.record(
        feature_name="write_value_score",
        session_key="cli:local",
        turn_id="turn-1",
        baseline_result={},
        experimental_result={},
        metrics={},
    )

    assert trace is not None
    rows = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")
    assert rows[0]["mode"] == "shadow"


def test_score_write_candidate_shadow_rejects_temporary_text() -> None:
    result = score_write_candidate_shadow("临时测试变量 value-a-012，不要写入长期记忆")

    assert result["decision"] == "reject"
    assert result["reason"] == "temporary_state"
    assert result["score"] < 0.5


def test_score_write_candidate_shadow_allows_explicit_memory() -> None:
    result = score_write_candidate_shadow("用户明确要求记住：喜欢中文回答")

    assert result["decision"] == "allow"
    assert result["reason"] == "explicit_memory_signal"
    assert result["score"] >= 0.7


def test_extract_explicit_memorize_baseline_counts_successful_results() -> None:
    calls = [
        {
            "summary": "用户明确要求记住：喜欢中文回答",
            "result": "ok item_id=mem_1 status=new",
        },
        {
            "summary": "用户明确要求记住：使用中文",
            "result": "ok item_id=mem_2 status=reinforced",
        },
        {
            "summary": "失败候选",
            "result": '{"ok": false, "error": "denied"}',
        },
    ]

    baseline = extract_explicit_memorize_baseline(calls)

    assert baseline["attempted_count"] == 3
    assert baseline["baseline_written_count"] == 2
    assert baseline["written_item_ids"] == ["mem_1", "mem_2"]
    assert baseline["write_status_counts"] == {"new": 1, "reinforced": 1, "failed": 1}


def test_runner_appends_multiple_records(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    for idx in range(2):
        runner.record(
            feature_name="write_value_score",
            session_key="cli:local",
            turn_id=f"turn-{idx}",
            baseline_result={"idx": idx},
            experimental_result={"idx": idx, "decision": "allow"},
            metrics={"candidate_count": 1},
        )

    rows = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")
    assert [row["turn_id"] for row in rows] == ["turn-0", "turn-1"]
