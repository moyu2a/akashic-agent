from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

DEFAULT_STAGE1_PROFILES: tuple[str, ...] = (
    "baseline",
    "simple_fast_path",
)


@dataclass(frozen=True)
class Stage1Case:
    case_id: str
    category: str
    prompt: str
    expected_fast_path: bool
    expected_correctness: str = "PASS"
    suite: str = "cost_latency"
    expected_tools: tuple[str, ...] = ()
    forbidden_reply_patterns: tuple[str, ...] = (
        "<｜｜DSML｜｜tool_calls>",
        "invoke name=",
    )
    required_reply_patterns: tuple[str, ...] = ()
    allow_in_cost_latency: bool = True


@dataclass(frozen=True)
class Stage1Record:
    profile: str
    case_id: str
    category: str
    prompt: str
    correctness: str
    simple_fast_path: bool
    tool_error_count: int
    actual_prompt_tokens_sum: int
    actual_total_tokens_sum: int
    turn_duration_ms: int
    llm_duration_ms_sum: int
    react_iteration_count: int
    note: str


@dataclass(frozen=True)
class Stage1Report:
    metrics: dict[str, Any]
    profile_summaries: dict[str, dict[str, Any]]
    category_summaries: dict[str, dict[str, Any]]
    records: list[Stage1Record]


DEFAULT_STAGE1_CASES: tuple[Stage1Case, ...] = (
    Stage1Case("simple_001", "simple_no_tool", "不用工具，一句话回答：你是谁？", True),
    Stage1Case("simple_002", "simple_no_tool", "一句话说明 memory_window 是什么。", True),
    Stage1Case("simple_003", "simple_no_tool", "简单解释一下 token 成本是什么。", True),
    Stage1Case(
        "simple_004",
        "simple_no_tool",
        "不用工具，用一句话说明后台提醒在个人 AI 伙伴里的作用。",
        False,
    ),
    Stage1Case("simple_005", "simple_no_tool", "不用工具，概括一下优化 profile 的意义。", True),
    Stage1Case(
        "tool_001",
        "tool_task",
        "保存这个内容链接并标记为 AI：https://example.com/video/1",
        False,
        suite="disabled_tool_policy",
        expected_tools=("save_content_item",),
        required_reply_patterns=("保存", "AI"),
        allow_in_cost_latency=False,
    ),
    Stage1Case("tool_002", "tool_task", "搜索我保存过的装修内容。", False),
    Stage1Case("tool_003", "tool_task", "查看最近保存的 B 站内容。", False),
    Stage1Case("tool_004", "tool_task", "帮我列出内容库里带游戏标签的条目。", False),
    Stage1Case(
        "tool_005",
        "tool_task",
        "给这个保存操作生成审批详情。",
        False,
        suite="disabled_tool_policy",
        allow_in_cost_latency=False,
    ),
    Stage1Case(
        "memory_001",
        "memory_task",
        "只根据记忆和历史消息回答：我之前说过我关注哪些内容方向？找不到就说明没有记录，不要查文件。",
        False,
    ),
    Stage1Case(
        "memory_002",
        "memory_task",
        "只根据记忆和历史消息回答：我之前收藏过哪些 AI 相关内容？找不到就说明没有记录，不要查文件。",
        False,
    ),
    Stage1Case(
        "memory_003",
        "memory_task",
        "只根据记忆和历史消息回答：根据记忆总结我的内容偏好。找不到就说明没有记录，不要查文件。",
        False,
    ),
    Stage1Case(
        "memory_004",
        "memory_task",
        "只根据记忆和历史消息回答：我上次提到的主动推送主线是什么？找不到就说明没有记录，不要查文件。",
        False,
    ),
    Stage1Case(
        "memory_005",
        "memory_task",
        "只根据记忆和历史消息回答：回忆一下我对 QQBot 接入的要求。找不到就说明没有记录，不要查文件。",
        False,
    ),
    Stage1Case(
        "proactive_001",
        "proactive_task",
        "只使用内容库回顾工具回答：立即生成最近 24 小时内容回顾。必须优先调用 list_recent_content_items(hours=24, for_push=true)，不要查文件或技能说明。",
        False,
        expected_tools=("list_recent_content_items",),
    ),
    Stage1Case("proactive_002", "proactive_task", "查看每日回顾 schedule 状态。", False),
)


def run_stage1_fake_profile_ab(
    profiles: Sequence[str] = DEFAULT_STAGE1_PROFILES,
    cases: Sequence[Stage1Case] = DEFAULT_STAGE1_CASES,
) -> Stage1Report:
    profile_order = tuple(profiles)
    case_list = tuple(cases)
    records: list[Stage1Record] = []
    for profile in profile_order:
        _assert_known_profile(profile)
        for case in case_list:
            records.append(_run_fake_turn(profile, case))

    profile_summaries = {
        profile: _summarize_records([r for r in records if r.profile == profile])
        for profile in profile_order
    }
    categories = tuple(dict.fromkeys(case.category for case in case_list))
    category_summaries = {
        category: _summarize_records([r for r in records if r.category == category])
        for category in categories
    }
    metrics = {
        "mode": "fake",
        "real_llm": False,
        "profile_count": len(profile_order),
        "case_count": len(case_list),
        "turn_count": len(records),
        "all_profiles_pass": all(r.correctness != "FAIL" for r in records),
        "profile_order": list(profile_order),
        "categories": list(categories),
    }
    return Stage1Report(
        metrics=metrics,
        profile_summaries=profile_summaries,
        category_summaries=category_summaries,
        records=records,
    )


def write_stage1_report_json(report: Stage1Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metrics": report.metrics,
        "profile_summaries": report.profile_summaries,
        "category_summaries": report.category_summaries,
        "records": [asdict(record) for record in report.records],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_stage1_report_markdown(report: Stage1Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Optimization Profile Stage 1 Fake Run",
        "",
        "本报告用于验证阶段一混合任务 A/B 的 case、profile、分组和报告链路，不代表真实 token/时延收益。",
        "",
        "## Summary",
        "",
        f"- mode: `{report.metrics['mode']}`",
        f"- real_llm: `{str(report.metrics['real_llm']).lower()}`",
        f"- profiles: `{', '.join(report.metrics['profile_order'])}`",
        f"- cases: `{report.metrics['case_count']}`",
        f"- turns: `{report.metrics['turn_count']}`",
        "",
        "## Profile Summary",
        "",
        "| profile | cases | pass | warn | fail | fast hits | tool errors | avg prompt | avg total | avg turn |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for profile, row in report.profile_summaries.items():
        lines.append(
            "| {profile} | {case_count} | {pass_count} | {warn_count} | "
            "{fail_count} | {fast_hits} | {tool_errors} | {avg_prompt_tokens} | "
            "{avg_total_tokens} | {avg_turn_ms}ms |".format(profile=profile, **row)
        )
    lines.extend(
        [
            "",
            "## Category Summary",
            "",
            "| category | turns | pass | warn | fail | fast hits | tool errors |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for category, row in report.category_summaries.items():
        lines.append(
            "| {category} | {case_count} | {pass_count} | {warn_count} | "
            "{fail_count} | {fast_hits} | {tool_errors} |".format(
                category=category,
                **row,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _assert_known_profile(profile: str) -> None:
    if profile not in DEFAULT_STAGE1_PROFILES:
        allowed = ", ".join(DEFAULT_STAGE1_PROFILES)
        raise ValueError(
            f"profile is not allowed for stage 1: {profile}; allowed: {allowed}"
        )


def _run_fake_turn(profile: str, case: Stage1Case) -> Stage1Record:
    uses_fast_path = profile == "simple_fast_path" and case.expected_fast_path
    baseline_prompt = _base_prompt_tokens(case)
    prompt_tokens = int(baseline_prompt * (0.44 if uses_fast_path else 1.0))
    completion_tokens = 48 if uses_fast_path else 96
    total_tokens = prompt_tokens + completion_tokens
    iterations = 1 if uses_fast_path or case.category == "simple_no_tool" else 2
    llm_ms = int(total_tokens / 7) + 250
    turn_ms = llm_ms + (120 if case.category.endswith("_task") else 40)
    return Stage1Record(
        profile=profile,
        case_id=case.case_id,
        category=case.category,
        prompt=case.prompt,
        correctness=case.expected_correctness,
        simple_fast_path=uses_fast_path,
        tool_error_count=0,
        actual_prompt_tokens_sum=prompt_tokens,
        actual_total_tokens_sum=total_tokens,
        turn_duration_ms=turn_ms,
        llm_duration_ms_sum=llm_ms,
        react_iteration_count=iterations,
        note="fake deterministic route check; not real usage or savings benchmark",
    )


def _base_prompt_tokens(case: Stage1Case) -> int:
    by_category = {
        "simple_no_tool": 16_000,
        "tool_task": 22_000,
        "memory_task": 24_000,
        "proactive_task": 20_000,
    }
    return by_category[case.category] + len(case.prompt)


def _summarize_records(records: Sequence[Stage1Record]) -> dict[str, Any]:
    if not records:
        return {
            "case_count": 0,
            "pass_count": 0,
            "warn_count": 0,
            "fail_count": 0,
            "fast_hits": 0,
            "tool_errors": 0,
            "avg_prompt_tokens": 0.0,
            "avg_total_tokens": 0.0,
            "avg_turn_ms": 0.0,
            "avg_llm_ms": 0.0,
            "avg_iterations": 0.0,
        }
    return {
        "case_count": len(records),
        "pass_count": sum(1 for r in records if r.correctness == "PASS"),
        "warn_count": sum(1 for r in records if r.correctness == "WARN"),
        "fail_count": sum(1 for r in records if r.correctness == "FAIL"),
        "fast_hits": sum(1 for r in records if r.simple_fast_path),
        "tool_errors": sum(r.tool_error_count for r in records),
        "avg_prompt_tokens": round(mean(r.actual_prompt_tokens_sum for r in records), 1),
        "avg_total_tokens": round(mean(r.actual_total_tokens_sum for r in records), 1),
        "avg_turn_ms": round(mean(r.turn_duration_ms for r in records), 1),
        "avg_llm_ms": round(mean(r.llm_duration_ms_sum for r in records), 1),
        "avg_iterations": round(mean(r.react_iteration_count for r in records), 2),
    }
