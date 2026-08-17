from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent.provider import LLMResponse
from core.memory.engine import MemoryEngineRetrieveRequest, MemoryScope
from memory2.eval_cases import load_eval_case
from memory2.eval_llm_sample import (
    AnswerExpectation,
    LLMSampleMemoryEngine,
    LLMSampleRunSpec,
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
    assert result.memory_grounding_passed is True
    assert result.answer_rule_passed is True


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
    assert result.memory_grounding_passed is False
    assert result.answer_rule_passed is False


def test_score_answer_text_accepts_any_expected_term_group() -> None:
    expectation = AnswerExpectation(
        expected_answer_contains=("RRF",),
        expected_answer_contains_any=(("三路召回", "第三路", "融合排序"),),
        expected_memory_ids=("m_graph_1", "m_graph_2"),
        expected_language="zh",
        grounding_required=True,
    )

    result = score_answer_text(
        "这个第三路方案采用 RRF 排序。",
        expectation,
        ["m_graph_1", "m_graph_2"],
    )

    assert result.passed is True
    assert result.expected_any_pass_count == 1
    assert result.expected_any_miss_count == 0
    assert result.memory_grounding_passed is True
    assert result.answer_rule_passed is True


def test_score_answer_text_default_does_not_enable_semantic_judge() -> None:
    result = score_answer_text(
        "请继续中文输出",
        AnswerExpectation(expected_answer_contains=("中文回答",)),
        (),
    )

    assert result.answer_rule_passed is False
    assert "semantic_ambiguity" not in result.failures


def test_score_answer_text_accepts_calibrated_equivalent_terms() -> None:
    expectation = AnswerExpectation(
        expected_answer_contains=("清理",),
        expected_answer_contains_any=(
            ("冲突", "冲突偏好要保留最新明确版本"),
            ("中文回答", "用户偏好中文回答"),
        ),
        expected_memory_ids=("m_current",),
        expected_language="zh",
        grounding_required=True,
    )

    result = score_answer_text(
        "前后矛盾时按最新明确版本处理。我会保持中文，并把低价值记忆清掉。",
        expectation,
        ["m_current"],
    )

    assert result.passed is True
    assert result.expected_contains_pass_count == 1
    assert result.expected_any_pass_count == 2
    assert result.expected_any_miss_count == 0


def test_score_answer_text_accepts_calibrated_equivalent_summary_phrases() -> None:
    cross_scope = AnswerExpectation(
        expected_answer_contains=("会话", "隔离"),
        expected_answer_contains_any=(
            ("会话", "隔离"),
            ("session_key", "不同会话的偏好不能混用"),
        ),
        expected_memory_ids=("m_scope",),
        expected_language="zh",
        grounding_required=True,
    )
    version_chain = AnswerExpectation(
        expected_answer_contains=("叶子", "回滚"),
        expected_answer_contains_any=(
            ("叶子", "回滚"),
            ("版本链", "旧版本记忆被新版本替换后只保留叶子"),
        ),
        expected_memory_ids=("m_version",),
        expected_language="zh",
        grounding_required=True,
    )

    cross_scope_result = score_answer_text(
        "不同会话的偏好是隔离的，telegram 和 qq 的 session 互相独立，不会混用。",
        cross_scope,
        ["m_scope"],
    )
    version_chain_result = score_answer_text(
        "旧版本被新版本替换后，只保留叶子，也会记录回滚候选。",
        version_chain,
        ["m_version"],
    )

    assert cross_scope_result.passed is True
    assert version_chain_result.passed is True


def test_score_answer_text_still_rejects_fragment_answers_for_anchor_terms() -> None:
    expectation = AnswerExpectation(
        expected_answer_contains=("条目式",),
        expected_answer_contains_any=(("条目式", "回答时尽量用条目式"),),
        expected_memory_ids=("m_style",),
        expected_language="zh",
        grounding_required=True,
    )

    for fragment in ("可以的。", "嗯，对的。", "嗯……我查一下记忆。"):
        result = score_answer_text(fragment, expectation, ["m_style"])
        assert result.passed is False
        assert result.expected_contains_miss_count == 1
        assert result.expected_any_miss_count == 1


def test_score_answer_text_separates_memory_grounding_from_answer_rules() -> None:
    expectation = AnswerExpectation(
        expected_answer_contains=("RRF",),
        expected_answer_contains_any=(("三路召回", "第三路"),),
        expected_memory_ids=("m_graph_1",),
        expected_language="zh",
        grounding_required=True,
    )

    result = score_answer_text("我会用中文回答。", expectation, ["m_graph_1"])

    assert result.passed is False
    assert result.memory_grounding_passed is True
    assert result.answer_rule_passed is False


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
    assert result.memory_grounding_passed is True
    assert result.answer_rule_passed is True
    assert result.expected_contains_pass_count == 1
    assert result.forbidden_contains_violation_count == 0
    assert result.language_passed is True
    assert result.token_metrics_available is True
    assert result.total_token_count == 12
    assert len(provider.calls) == 1
    assert (tmp_path / "workspace" / "sessions.db").exists()


@pytest.mark.asyncio
async def test_run_llm_sample_case_writes_answer_debug_only_when_requested(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "vague_reference_graph.json")
    answer = "这个第三路方案采用 RRF 融合排序。"
    provider = _FakeLLMProvider(answer)
    debug_dir = tmp_path / "workspace" / "answer_debug"

    result = await run_llm_sample_case(
        LLMSampleRunSpec(case=case, prompt_variant="coached", repeat_index=0),
        tmp_path / "workspace",
        provider,
        model="fake-model",
        case_index=7,
        answer_debug_dir=debug_dir,
    )

    assert result.passed is True
    debug_path = debug_dir / "0007-coached-vague_reference_graph.json"
    payload = json.loads(debug_path.read_text(encoding="utf-8"))
    assert payload["case_id"] == "vague_reference_graph"
    assert payload["case_index"] == 7
    assert payload["prompt_variant"] == "coached"
    assert payload["answer_text"] == answer
    assert payload["used_memory_ids"] == ["m_graph_1", "m_graph_2"]
    assert payload["evidence_block_text"]
    assert payload["matched_expected_terms"] == ["RRF"]
    assert payload["missing_expected_terms"] == []
    assert payload["answer_rule_passed"] is True
    assert payload["memory_grounding_passed"] is True


@pytest.mark.asyncio
async def test_answer_debug_is_off_by_default(tmp_path: Path) -> None:
    case = load_eval_case(FIXTURE_ROOT / "vague_reference_graph.json")
    provider = _FakeLLMProvider("这个第三路方案采用 RRF 融合排序。")

    result = await run_llm_sample_case(
        LLMSampleRunSpec(case=case, prompt_variant="baseline", repeat_index=0),
        tmp_path / "workspace",
        provider,
        model="fake-model",
        case_index=0,
    )

    assert result.passed is True
    assert not (tmp_path / "workspace" / "answer_debug").exists()


@pytest.mark.asyncio
async def test_answer_debug_does_not_change_regular_report_privacy(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "vague_reference_graph.json")
    answer = "这个第三路方案采用 RRF 融合排序。"
    provider = _FakeLLMProvider(answer)

    report = await run_llm_sample_cases(
        [
            LLMSampleRunSpec(case=case, prompt_variant="baseline", repeat_index=0),
        ],
        tmp_path / "workspace",
        provider,
        model="fake-model",
        real_llm_enabled=False,
        answer_debug_dir=tmp_path / "workspace" / "answer_debug",
    )
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    write_llm_sample_json(report, json_path)
    write_llm_sample_markdown(report, md_path)

    combined = json_path.read_text(encoding="utf-8") + md_path.read_text(
        encoding="utf-8"
    )
    assert answer not in combined
    assert "三路召回结果使用 RRF 融合排序" not in combined
    assert (
        tmp_path
        / "workspace"
        / "answer_debug"
        / "0000-baseline-vague_reference_graph.json"
    ).exists()


@pytest.mark.asyncio
async def test_llm_sample_memory_block_changes_only_in_coached_variant() -> None:
    case = load_eval_case(FIXTURE_ROOT / "vague_reference_graph.json")
    baseline = LLMSampleMemoryEngine(case, prompt_variant="baseline")
    coached = LLMSampleMemoryEngine(case, prompt_variant="coached")

    baseline_result = await baseline.retrieve(
        MemoryEngineRetrieveRequest(
            query="之前那个第三路方案怎么排序？",
            context={},
            scope=MemoryScope(
                session_key="cli:local",
                channel="cli",
                chat_id="local",
            ),
        )
    )
    coached_result = await coached.retrieve(
        MemoryEngineRetrieveRequest(
            query="之前那个第三路方案怎么排序？",
            context={},
            scope=MemoryScope(
                session_key="cli:local",
                channel="cli",
                chat_id="local",
            ),
        )
    )

    assert "记忆评测说明" not in baseline_result.text_block
    assert "记忆评测说明" in coached_result.text_block
    assert "RRF" in coached_result.text_block


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
async def test_run_llm_sample_report_derives_completion_tokens_from_total(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    provider = _FakeLLMProvider(
        response=LLMResponse(
            content="我应该用中文回答你。",
            tool_calls=[],
            provider_fields={"usage": {"prompt_tokens": 80, "total_tokens": 95}},
        ),
    )

    report = await run_llm_sample_cases(
        [case],
        tmp_path / "workspace",
        provider,
        model="fake-model",
        real_llm_enabled=False,
    )

    assert report.metrics["prompt_token_count"] == 80
    assert report.metrics["completion_token_count"] == 15
    assert report.metrics["total_token_count"] == 95


@pytest.mark.asyncio
async def test_run_llm_sample_report_accepts_input_output_token_names(
    tmp_path: Path,
) -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    provider = _FakeLLMProvider(
        response=LLMResponse(
            content="我应该用中文回答你。",
            tool_calls=[],
            provider_fields={"usage": {"input_tokens": 80, "output_tokens": 15}},
        ),
    )

    report = await run_llm_sample_cases(
        [case],
        tmp_path / "workspace",
        provider,
        model="fake-model",
        real_llm_enabled=False,
    )

    assert report.metrics["prompt_token_count"] == 80
    assert report.metrics["completion_token_count"] == 15
    assert report.metrics["total_token_count"] == 95


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
