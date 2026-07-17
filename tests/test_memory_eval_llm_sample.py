from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent.provider import LLMResponse
from memory2.eval_cases import load_eval_case
from memory2.eval_llm_sample import (
    AnswerExpectation,
    answer_expectation_from_case,
    run_llm_sample_case,
    run_llm_sample_cases,
    score_answer_text,
    write_llm_sample_json,
    write_llm_sample_markdown,
)


FIXTURE_ROOT = Path("tests/fixtures/memory_eval_cases")


class _FakeLLMProvider:
    def __init__(
        self,
        answer: str = "我应该用中文回答你。",
        *,
        response: LLMResponse | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.answer = answer
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return LLMResponse(
            content=self.answer,
            tool_calls=[],
            provider_fields={
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 5,
                    "total_tokens": 12,
                }
            },
        )


def test_answer_expectation_from_case_reads_optional_fields() -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")

    expectation = answer_expectation_from_case(case)

    assert "中文" in expectation.expected_answer_contains
    assert "m_pref_cn" in expectation.expected_memory_ids
    assert expectation.expected_language == "zh"


def test_score_answer_text_passes_expected_and_forbidden_rules() -> None:
    expectation = AnswerExpectation(
        expected_answer_contains=("中文",),
        forbidden_answer_contains=("英文回答",),
        expected_memory_ids=("m_pref_cn",),
        expected_language="zh",
        grounding_required=True,
    )

    result = score_answer_text("我应该用中文回答你。", expectation, ["m_pref_cn"])

    assert result.passed is True
    assert result.expected_contains_pass_count == 1
    assert result.forbidden_contains_violation_count == 0
    assert result.expected_memory_used is True


def test_score_answer_text_fails_forbidden_and_missing_memory() -> None:
    expectation = AnswerExpectation(
        expected_answer_contains=("中文",),
        forbidden_answer_contains=("英文回答",),
        expected_memory_ids=("m_pref_cn",),
        expected_language="zh",
        grounding_required=True,
    )

    result = score_answer_text("我会用英文回答。", expectation, [])

    assert result.passed is False
    assert result.forbidden_contains_violation_count == 1
    assert result.expected_memory_used is False


@pytest.mark.asyncio
async def test_run_llm_sample_case_scores_fake_provider_answer(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    provider = _FakeLLMProvider("我应该用中文回答你。")

    result = await run_llm_sample_case(
        case,
        tmp_path / "workspace",
        provider,
        model="fake-model",
    )

    assert result.passed is True
    assert result.case_id == "preference_recall"
    assert result.answer_length == len("我应该用中文回答你。")
    assert result.expected_memory_used is True
    assert result.expected_contains_pass_count == 1
    assert result.forbidden_contains_violation_count == 0
    assert result.language_passed is True
    assert result.token_metrics_available is True
    assert result.total_token_count == 12
    assert len(provider.calls) == 1
    assert (tmp_path / "workspace" / "sessions.db").exists()


@pytest.mark.asyncio
async def test_run_llm_sample_report_aggregates_fake_provider_metrics(
    tmp_path: Path,
) -> None:
    cases = [
        load_eval_case(FIXTURE_ROOT / "preference_recall.json"),
        load_eval_case(FIXTURE_ROOT / "vague_reference_graph.json"),
    ]
    provider = _FakeLLMProvider("这个三路召回方案使用 RRF 融合排序。")

    report = await run_llm_sample_cases(
        cases,
        tmp_path / "workspace",
        provider,
        model="fake-model",
        real_llm_enabled=False,
    )

    assert report.metrics["phase6b_level"] == "real_llm_small_sample"
    assert report.metrics["real_llm_enabled"] is False
    assert report.metrics["answer_quality_available"] is True
    assert report.metrics["token_metrics_available"] is True
    assert report.metrics["case_count"] == 2
    assert report.metrics["provider_error_count"] == 0
    assert len(report.case_records) == 2


@pytest.mark.asyncio
async def test_run_llm_sample_report_marks_missing_token_metadata(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    provider = _FakeLLMProvider(
        response=LLMResponse(content="我应该用中文回答你。", tool_calls=[]),
    )

    report = await run_llm_sample_cases(
        [case],
        tmp_path / "workspace",
        provider,
        model="fake-model",
        real_llm_enabled=False,
    )

    assert report.metrics["token_metrics_available"] is False
    assert report.case_records[0]["token_metrics_available"] is False


@pytest.mark.asyncio
async def test_run_llm_sample_report_sanitizes_provider_errors(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    provider = _FakeLLMProvider(error=RuntimeError("secret raw provider detail"))

    report = await run_llm_sample_cases(
        [case],
        tmp_path / "workspace",
        provider,
        model="fake-model",
        real_llm_enabled=False,
    )

    assert report.passed is False
    assert report.metrics["provider_error_count"] == 1
    assert "provider_error" in report.failure_records[0]["failure"]
    assert "secret raw provider detail" not in json.dumps(
        {
            "metrics": report.metrics,
            "case_records": report.case_records,
            "failure_records": report.failure_records,
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_llm_sample_reports_do_not_include_raw_private_text(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    fake_answer = "我应该用中文回答你。"
    provider = _FakeLLMProvider(fake_answer)
    report = await run_llm_sample_cases(
        [case],
        tmp_path / "workspace",
        provider,
        model="fake-model",
        real_llm_enabled=False,
    )
    json_path = tmp_path / "memory_llm_sample_eval.json"
    md_path = tmp_path / "memory_llm_sample_eval.md"

    write_llm_sample_json(report, json_path)
    write_llm_sample_markdown(report, md_path)

    combined = (
        json_path.read_text(encoding="utf-8")
        + "\n"
        + md_path.read_text(encoding="utf-8")
    )
    for forbidden in (
        "用户偏好中文回答",
        "你应该用什么语言回答我",
        fake_answer,
        "sk-test-secret",
        "fake-model-api-key",
    ):
        assert forbidden not in combined
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["case_records"][0]["answer_length"] == len(fake_answer)
    assert "answer" not in payload["case_records"][0]
    assert "query" not in payload["case_records"][0]
