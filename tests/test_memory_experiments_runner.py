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


def test_record_tri_retrieval_shadow_writes_trace(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_tri_retrieval_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_hit_count": 1, "baseline_ids": ["m1"]},
        experimental_result={
            "semantic_hit_count": 1,
            "keyword_hit_count": 1,
            "provenance_hit_count": 0,
            "fused_hit_count": 2,
            "fused_ids": ["m1", "m2"],
        },
        metrics={
            "lane_contribution": {"semantic": 1, "keyword": 1, "provenance": 0},
            "retrieval_latency_ms": 4.2,
        },
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["feature_name"] == "tri_retrieval"
    assert row["baseline_result"]["baseline_ids"] == ["m1"]
    assert row["experimental_result"]["fused_ids"] == ["m1", "m2"]
    assert row["metrics_json"]["retrieval_latency_ms"] == 4.2


def test_record_graph_retrieval_shadow_writes_trace(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_graph_retrieval_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_ids": ["m1"]},
        experimental_result={
            "graph_hit_count": 2,
            "graph_ids": ["m1", "m2"],
            "graph_fused_ids": ["m1", "m2"],
        },
        metrics={
            "graph_lane_contribution": {"graph": 2},
            "graph_path_count": 2,
            "avg_graph_path_length": 2.5,
            "entity_match_count": 2,
        },
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["feature_name"] == "graph_retrieval"
    assert row["experimental_result"]["graph_fused_ids"] == ["m1", "m2"]


def test_record_rerank_shadow_writes_trace(tmp_path: Path) -> None:
    trace_path = tmp_path / "observe" / "memory_experiments.jsonl"
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(
            enabled=True,
            mode="shadow",
            trace_path=str(trace_path),
        ),
    )

    runner.record_rerank_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_ids": ["m1"]},
        experimental_result={"reranked_ids": ["m2", "m1"]},
        metrics={"rerank_changed_count": 2},
    )

    row = _read_jsonl(trace_path)[0]
    assert row["feature_name"] == "rerank_shadow"
    assert row["experimental_result"]["reranked_ids"] == ["m2", "m1"]
    assert row["metrics_json"]["rerank_changed_count"] == 2


def test_record_injection_governance_shadow_writes_trace(tmp_path: Path) -> None:
    trace_path = tmp_path / "observe" / "memory_experiments.jsonl"
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(
            enabled=True,
            mode="shadow",
            trace_path=str(trace_path),
        ),
    )

    runner.record_injection_governance_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_injected_ids": ["m1"]},
        experimental_result={"experimental_injected_ids": ["m2"]},
        metrics={"prompt_token_delta": -12},
    )

    row = _read_jsonl(trace_path)[0]
    assert row["feature_name"] == "injection_governance_shadow"
    assert row["experimental_result"]["experimental_injected_ids"] == ["m2"]
    assert row["metrics_json"]["prompt_token_delta"] == -12


def test_record_version_chain_shadow_writes_trace(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_version_chain_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_recalled_ids": ["old"]},
        experimental_result={"chain_count": 1, "active_leaf_ids": ["new"]},
        metrics={"stale_recalled_count": 1, "max_chain_depth": 2},
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["feature_name"] == "version_chain_shadow"
    assert row["experimental_result"]["active_leaf_ids"] == ["new"]
    assert row["metrics_json"]["stale_recalled_count"] == 1


def test_record_provenance_shadow_writes_trace(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_provenance_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_recalled_ids": ["m1"]},
        experimental_result={"parsed_source_refs": [{"item_id": "m1"}]},
        metrics={"source_ref_coverage": 1.0, "parse_success_rate": 1.0},
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["feature_name"] == "provenance_shadow"
    assert row["metrics_json"]["source_ref_coverage"] == 1.0


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


def test_score_write_candidate_shadow_outputs_structured_signals() -> None:
    result = score_write_candidate_shadow(
        "用户明确要求记住：以后都用中文回答",
        source_ref="cli:local@post_response",
    )

    assert result["decision"] == "allow"
    assert result["reason"] == "explicit_memory_signal"
    assert result["final_score"] >= 0.7
    assert result["score"] == result["final_score"]
    assert "explicit_user_intent" in result["reasons"]
    signals = result["signals"]
    assert signals["explicit_user_intent_score"] >= 0.8
    assert signals["long_term_stability_score"] >= 0.6
    assert signals["source_ref_confidence_score"] >= 0.8
    assert signals["temporary_risk_score"] == 0.0
    assert signals["assistant_inference_risk_score"] == 0.0


def test_score_write_candidate_shadow_rejects_assistant_inference() -> None:
    result = score_write_candidate_shadow(
        "助手推断用户可能喜欢极简风格",
        source_ref="cli:local@post_response",
    )

    assert result["decision"] == "reject"
    assert result["reason"] == "assistant_inference"
    assert result["final_score"] < 0.5
    assert "assistant_inference" in result["reasons"]
    assert result["signals"]["assistant_inference_risk_score"] >= 0.8


def test_score_write_candidate_shadow_marks_review_for_ambiguous_stable_text() -> None:
    result = score_write_candidate_shadow(
        "用户常用 Linux 环境处理本地项目",
        source_ref="cli:local@post_response",
    )

    assert result["decision"] == "review"
    assert result["reason"] == "moderate_value_signal"
    assert 0.45 <= result["final_score"] < 0.7
    assert "moderate_information_value" in result["reasons"]


def test_score_write_candidate_shadow_detects_duplicate_existing_memory() -> None:
    result = score_write_candidate_shadow(
        "用户明确要求记住：以后都用中文回答",
        source_ref="cli:local@post_response",
        existing_memories=[
            {"id": "mem_1", "summary": "用户明确要求记住：以后都用中文回答"},
            {"id": "mem_2", "summary": "用户喜欢 Python 自动化"},
        ],
    )

    assert result["signals"]["duplicate_risk_score"] >= 0.8
    assert result["signals"]["novelty_score"] <= 0.3
    assert result["signals"]["entropy_score"] <= 0.3
    assert result["similar_memory_count"] == 1
    assert result["nearest_memory_ids"] == ["mem_1"]
    assert "duplicate_existing_memory" in result["reasons"]
    assert result["decision"] == "reject"
    assert result["reason"] == "duplicate_existing_memory"


def test_score_write_candidate_shadow_scores_novel_existing_memory() -> None:
    result = score_write_candidate_shadow(
        "用户明确要求记住：以后代码示例优先使用 pytest",
        source_ref="cli:local@post_response",
        existing_memories=[
            {"id": "mem_1", "summary": "用户喜欢中文回答"},
            {"id": "mem_2", "summary": "用户使用 Linux 处理本地项目"},
        ],
    )

    assert result["signals"]["duplicate_risk_score"] < 0.5
    assert result["signals"]["novelty_score"] >= 0.6
    assert result["signals"]["entropy_score"] >= 0.6
    assert result["similar_memory_count"] == 0
    assert result["nearest_memory_ids"] == []
    assert "novel_information" in result["reasons"]


def test_score_write_candidate_shadow_keeps_phase1b_shape_without_existing_memory() -> (
    None
):
    result = score_write_candidate_shadow(
        "用户明确要求记住：以后代码示例优先使用 pytest",
        source_ref="cli:local@post_response",
        existing_memories=[],
    )

    assert "entropy_score" in result["signals"]
    assert result["similar_memory_count"] == 0
    assert result["nearest_memory_ids"] == []


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


def test_record_write_value_shadow_writes_detailed_metrics(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_write_value_shadow(
        session_key="cli:local",
        turn_id="cli:local@post_response",
        memorize_calls=[
            {
                "summary": "用户明确要求记住：以后都用中文回答",
                "result": "ok item_id=mem_1 status=new",
            },
            {
                "summary": "助手推断用户可能喜欢极简风格",
                "result": "ok item_id=mem_2 status=new",
            },
        ],
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    metrics = row["metrics_json"]
    assert metrics["candidate_count"] == 2
    assert metrics["baseline_written_count"] == 2
    assert metrics["policy_allow_count"] == 1
    assert metrics["policy_reject_count"] == 1
    assert metrics["policy_review_count"] == 0
    assert metrics["assistant_inference_risk_count"] == 1
    assert metrics["temporary_risk_count"] == 0
    assert metrics["duplicate_risk_count"] == 0
    assert 0.0 < metrics["avg_final_score"] <= 1.0

    candidates = row["experimental_result"]["candidates"]
    assert candidates[0]["summary"] == "用户明确要求记住：以后都用中文回答"
    assert candidates[0]["signals"]["explicit_user_intent_score"] >= 0.8
    assert candidates[1]["reason"] == "assistant_inference"


def test_record_write_value_shadow_uses_existing_memory_snapshot(
    tmp_path: Path,
) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
        existing_memory_provider=lambda: [
            {"id": "mem_existing", "summary": "用户明确要求记住：以后都用中文回答"},
        ],
    )

    runner.record_write_value_shadow(
        session_key="cli:local",
        turn_id="cli:local@post_response",
        memorize_calls=[
            {
                "summary": "用户明确要求记住：以后都用中文回答",
                "result": "ok item_id=mem_1 status=new",
            },
            {
                "summary": "用户明确要求记住：以后代码示例优先使用 pytest",
                "result": "ok item_id=mem_2 status=new",
            },
        ],
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    metrics = row["metrics_json"]
    assert metrics["existing_memory_count"] == 1
    assert metrics["similar_memory_count"] == 1
    assert metrics["duplicate_risk_count"] == 1
    assert 0.0 <= metrics["avg_entropy_score"] <= 1.0
    assert 0.0 <= metrics["avg_novelty_score"] <= 1.0
    assert metrics["write_reduction_rate"] == 0.5

    candidates = row["experimental_result"]["candidates"]
    assert candidates[0]["nearest_memory_ids"] == ["mem_existing"]
    assert candidates[0]["similar_memory_count"] == 1
    assert candidates[1]["similar_memory_count"] == 0


def test_record_write_value_shadow_excludes_current_turn_written_ids(
    tmp_path: Path,
) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
        existing_memory_provider=lambda: [
            {"id": "mem_1", "summary": "用户明确要求记住：以后都用中文回答"},
        ],
    )

    runner.record_write_value_shadow(
        session_key="cli:local",
        turn_id="cli:local@post_response",
        memorize_calls=[
            {
                "summary": "用户明确要求记住：以后都用中文回答",
                "result": "ok item_id=mem_1 status=new",
            },
        ],
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    candidate = row["experimental_result"]["candidates"][0]
    assert row["metrics_json"]["existing_memory_count"] == 0
    assert candidate["similar_memory_count"] == 0
    assert candidate["nearest_memory_ids"] == []


def test_record_write_value_shadow_reduction_rate_uses_written_candidates_only(
    tmp_path: Path,
) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
        existing_memory_provider=lambda: [
            {"id": "mem_existing", "summary": "用户明确要求记住：以后都用中文回答"},
        ],
    )

    runner.record_write_value_shadow(
        session_key="cli:local",
        turn_id="cli:local@post_response",
        memorize_calls=[
            {
                "summary": "用户明确要求记住：以后都用中文回答",
                "result": "ok item_id=mem_1 status=new",
            },
            {
                "summary": "用户明确要求记住：以后代码示例优先使用 pytest",
                "result": '{"ok": false, "error": "denied"}',
            },
        ],
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["metrics_json"]["baseline_written_count"] == 1
    assert row["metrics_json"]["policy_allow_count"] == 1
    assert row["metrics_json"]["policy_reject_count"] == 1
    assert row["metrics_json"]["write_reduction_rate"] == 1.0
    assert row["metrics_json"]["written_candidate_allow_count"] == 0
    assert row["metrics_json"]["existing_memory_snapshot_count"] == 1
