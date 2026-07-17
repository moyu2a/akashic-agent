from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory2.eval_agent_dry_run import (
    run_agent_dry_run_case,
    run_agent_dry_run_cases,
    write_agent_dry_run_json,
    write_agent_dry_run_markdown,
)
from memory2.eval_cases import load_eval_case


FIXTURE_ROOT = Path("tests/fixtures/memory_eval_cases")


@pytest.mark.asyncio
async def test_agent_dry_run_processes_case_through_real_agent_loop(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")

    result = await run_agent_dry_run_case(case, tmp_path / "workspace")

    assert result.passed is True
    assert result.case_id == "preference_recall"
    assert result.session_key == "cli:local"
    assert result.reply_length > 0
    assert result.retrieval_request_count == 1
    assert result.fake_llm_call_count == 1
    assert result.turn_committed_count == 1
    assert result.session_message_count >= 2
    assert result.retrieval_query_matched is True
    assert result.retrieval_history_seen is True
    assert result.failures == ()
    assert (tmp_path / "workspace" / "sessions.db").exists()


@pytest.mark.asyncio
async def test_agent_dry_run_report_aggregates_counts(tmp_path: Path) -> None:
    cases = [
        load_eval_case(FIXTURE_ROOT / "preference_recall.json"),
        load_eval_case(FIXTURE_ROOT / "cross_scope_isolation.json"),
    ]

    report = await run_agent_dry_run_cases(cases, tmp_path / "workspace")

    assert report.passed is True
    assert report.metrics["phase6b_level"] == "agent_dry_run"
    assert report.metrics["agent_loop_enabled"] is True
    assert report.metrics["fake_llm_enabled"] is True
    assert report.metrics["llm_calls_enabled"] is False
    assert report.metrics["embedding_calls_enabled"] is False
    assert report.metrics["answer_quality_available"] is False
    assert report.metrics["raw_query_included"] is False
    assert report.metrics["raw_memory_summary_included"] is False
    assert report.metrics["prompt_included"] is False
    assert report.metrics["session_text_included"] is False
    assert report.metrics["case_count"] == 2
    assert report.metrics["passed_case_count"] == 2
    assert report.metrics["failed_case_count"] == 0
    assert report.metrics["retrieval_request_count"] == 2
    assert len(report.case_records) == 2


@pytest.mark.asyncio
async def test_agent_dry_run_report_does_not_include_raw_memory_text(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    report = await run_agent_dry_run_cases([case], tmp_path / "workspace")
    json_path = tmp_path / "agent_dry_run.json"
    md_path = tmp_path / "agent_dry_run.md"

    write_agent_dry_run_json(report, json_path)
    write_agent_dry_run_markdown(report, md_path)

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    assert "用户偏好中文回答" not in json_text
    assert "用户偏好中文回答" not in md_text
    assert "你应该用什么语言回答我" not in json_text
    assert "你应该用什么语言回答我" not in md_text
    assert "dry-run response" not in json_text
    assert "dry-run response" not in md_text
    payload = json.loads(json_text)
    assert payload["case_records"][0]["case_id"] == "preference_recall"
    assert "query" not in payload["case_records"][0]
