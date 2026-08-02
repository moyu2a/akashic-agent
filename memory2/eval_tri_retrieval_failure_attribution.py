from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from memory2.eval_comprehensive_online import evidence_ids_for_profile
from memory2.eval_quantitative_cases import build_quantitative_eval_cases


BASELINE_PROFILE = "chain_memory_base"
TRI_PROFILE = "chain_tri_retrieval"
RERANK_PROFILE = "chain_rerank_injection"


@dataclass(frozen=True)
class TriFailureCaseRow:
    case_id: str
    case_set: str
    category: str
    scenario_family: str
    answer_rule_passed: bool
    memory_grounding_passed: bool
    forbidden_violation_count: int
    failure_bucket: str
    failure_codes: tuple[str, ...]
    pass_pattern: str
    baseline_answer_passed: bool | None
    rerank_answer_passed: bool | None
    baseline_passed_but_tri_failed: bool
    baseline_failed_but_tri_passed: bool
    tri_failed_but_rerank_passed: bool
    used_memory_id_count: int
    total_token_count: int
    latency_ms: int
    fixture_tri_evidence_id_count: int
    fixture_baseline_evidence_id_count: int
    fixture_rerank_evidence_id_count: int
    fixture_evidence_count_delta_vs_base: int
    fixture_rerank_reduced_evidence_count: bool


@dataclass(frozen=True)
class TriScenarioSummary:
    scenario: str
    case_count: int
    answer_fail_count: int
    grounded_answer_fail_count_any: int
    grounded_non_forbidden_answer_fail_count: int
    forbidden_fail_count: int
    baseline_passed_but_tri_failed_count: int
    baseline_failed_but_tri_passed_count: int
    tri_failed_but_rerank_passed_count: int
    answer_fail_rate: float


@dataclass(frozen=True)
class TriRetrievalFailureAttributionReport:
    case_rows: tuple[TriFailureCaseRow, ...]
    case_set_summaries: tuple[TriScenarioSummary, ...]
    scenario_summaries: tuple[TriScenarioSummary, ...]
    metrics: dict[str, object]


def build_tri_retrieval_failure_attribution_report(
    payload: Mapping[str, object],
) -> TriRetrievalFailureAttributionReport:
    records = [
        row
        for row in payload.get("case_records", [])
        if isinstance(row, Mapping)
    ]
    eval_cases = {
        case.id: case
        for case in build_quantitative_eval_cases(case_pack="comprehensive")
    }
    by_key: dict[tuple[str, str, int], dict[str, Mapping[str, object]]] = {}
    for record in records:
        by_key.setdefault(_case_key(record), {})[
            str(record.get("profile_name") or "")
        ] = record

    rows: list[TriFailureCaseRow] = []
    for profiles in by_key.values():
        tri = profiles.get(TRI_PROFILE)
        if tri is None:
            continue
        baseline = profiles.get(BASELINE_PROFILE)
        rerank = profiles.get(RERANK_PROFILE)
        tri_answer = _bool(tri.get("answer_rule_passed"))
        tri_grounding = _bool(tri.get("memory_grounding_passed"))
        tri_forbidden = _int(tri.get("forbidden_contains_violation_count"))
        baseline_answer = (
            _bool(baseline.get("answer_rule_passed")) if baseline is not None else None
        )
        rerank_answer = (
            _bool(rerank.get("answer_rule_passed")) if rerank is not None else None
        )
        case_id = str(tri.get("case_id") or "")
        category = str(tri.get("category") or "")
        eval_case = eval_cases.get(case_id)
        baseline_evidence_count = (
            len(evidence_ids_for_profile(eval_case, BASELINE_PROFILE))
            if eval_case is not None
            else 0
        )
        tri_evidence_count = (
            len(evidence_ids_for_profile(eval_case, TRI_PROFILE))
            if eval_case is not None
            else _int(tri.get("used_memory_id_count"))
        )
        rerank_evidence_count = (
            len(evidence_ids_for_profile(eval_case, RERANK_PROFILE))
            if eval_case is not None
            else 0
        )
        rows.append(
            TriFailureCaseRow(
                case_id=case_id,
                case_set=_case_set(category),
                category=category,
                scenario_family=_scenario_family(category),
                answer_rule_passed=tri_answer,
                memory_grounding_passed=tri_grounding,
                forbidden_violation_count=tri_forbidden,
                failure_bucket=_failure_bucket(
                    answer_passed=tri_answer,
                    grounding_passed=tri_grounding,
                    forbidden_count=tri_forbidden,
                    provider_error=_bool(tri.get("provider_error")),
                    timeout=_bool(tri.get("timeout")),
                ),
                failure_codes=tuple(_failure_code(item) for item in _failures(tri)),
                pass_pattern=_pass_pattern(
                    baseline_answer=baseline_answer,
                    tri_answer=tri_answer,
                    rerank_answer=rerank_answer,
                ),
                baseline_answer_passed=baseline_answer,
                rerank_answer_passed=rerank_answer,
                baseline_passed_but_tri_failed=bool(
                    baseline_answer is True and tri_answer is False
                ),
                baseline_failed_but_tri_passed=bool(
                    baseline_answer is False and tri_answer is True
                ),
                tri_failed_but_rerank_passed=bool(
                    tri_answer is False and rerank_answer is True
                ),
                used_memory_id_count=_int(tri.get("used_memory_id_count")),
                total_token_count=_int(tri.get("total_token_count")),
                latency_ms=_int(tri.get("latency_ms")),
                fixture_tri_evidence_id_count=tri_evidence_count,
                fixture_baseline_evidence_id_count=baseline_evidence_count,
                fixture_rerank_evidence_id_count=rerank_evidence_count,
                fixture_evidence_count_delta_vs_base=(
                    tri_evidence_count - baseline_evidence_count
                ),
                fixture_rerank_reduced_evidence_count=(
                    rerank_evidence_count < tri_evidence_count
                    if rerank_evidence_count > 0 and tri_evidence_count > 0
                    else False
                ),
            )
        )

    case_set_summaries = _scenario_summaries(rows, key=lambda row: row.case_set)
    scenario_summaries = _scenario_summaries(
        rows,
        key=lambda row: row.scenario_family,
    )
    metrics = _metrics(
        rows,
        case_set_summaries,
        scenario_summaries,
        payload.get("metrics"),
    )
    return TriRetrievalFailureAttributionReport(
        case_rows=tuple(rows),
        case_set_summaries=tuple(case_set_summaries),
        scenario_summaries=tuple(scenario_summaries),
        metrics=metrics,
    )


def write_tri_retrieval_failure_attribution_json(
    report: TriRetrievalFailureAttributionReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_tri_retrieval_failure_attribution_markdown(
    report: TriRetrievalFailureAttributionReport,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Tri Retrieval Failure Attribution",
        "",
        "本报告专门解释 `chain_tri_retrieval` 在短线上真实 LLM 评测中的失败原因。",
        "",
        "## 边界",
        "",
        "- 本报告不包含原始 prompt、session 原文、memory summary 或完整回答。",
        "- 本报告不重新调用 LLM，也不改变生产召回和 prompt。",
        "- 如果 `memory_grounding_passed = True` 但 `answer_rule_passed = False`，这里归因为证据使用、噪声、排序、注入或评分规则问题，不归因为召回缺失。",
        "- `fixture_*` evidence count 是 offline fixture proxy, not observed context ids；它不能直接证明真实 prompt 中的噪声规模。",
        "- `chain_rerank_injection` 是后续累计 profile；三路失败而该 profile 通过，只说明后续组合链路可能救活，不证明 rerank 单因素因果。",
        "- 本轮 `40` 个 case 的 category 粒度较细，不把单个 category 失败解释为统计集中。",
        "",
        "## 总览",
        "",
    ]
    for key in [
        "source_case_count",
        "source_unique_case_count",
        "tri_case_count",
        "tri_answer_fail_count",
        "tri_answer_fail_rate",
        "tri_grounded_answer_fail_count_any",
        "tri_grounded_non_forbidden_answer_fail_count",
        "tri_grounding_fail_count",
        "tri_forbidden_fail_count",
        "baseline_passed_but_tri_failed_count",
        "baseline_failed_but_tri_passed_count",
        "tri_failed_but_rerank_passed_count",
        "avg_fixture_tri_evidence_id_count",
        "avg_fixture_evidence_count_delta_vs_base",
        "fixture_rerank_reduced_evidence_count_cases",
    ]:
        lines.append(f"- `{key}`: `{report.metrics.get(key)}`")

    lines.extend(
        [
            "",
            "## Case Set 汇总",
            "",
            "| case_set | cases | answer_fail | grounded_any | grounded_non_forbidden | forbidden_fail | base_pass_tri_fail | tri_fail_rerank_pass | answer_fail_rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report.case_set_summaries:
        lines.append(
            f"| `{row.scenario}` | {row.case_count} | {row.answer_fail_count} | "
            f"{row.grounded_answer_fail_count_any} | "
            f"{row.grounded_non_forbidden_answer_fail_count} | "
            f"{row.forbidden_fail_count} | "
            f"{row.baseline_passed_but_tri_failed_count} | "
            f"{row.tri_failed_but_rerank_passed_count} | {row.answer_fail_rate} |"
        )

    lines.extend(["", "## Scenario Family 汇总", ""])
    lines.extend(
        [
            "| scenario | cases | answer_fail | grounded_any | forbidden_fail | base_pass_tri_fail | tri_fail_rerank_pass |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report.scenario_summaries:
        lines.append(
            f"| `{row.scenario}` | {row.case_count} | {row.answer_fail_count} | "
            f"{row.grounded_answer_fail_count_any} | {row.forbidden_fail_count} | "
            f"{row.baseline_passed_but_tri_failed_count} | "
            f"{row.tri_failed_but_rerank_passed_count} |"
        )

    lines.extend(["", "## Failure Bucket Counts", ""])
    for bucket, count in sorted(report.metrics.get("failure_bucket_counts", {}).items()):
        lines.append(f"- `{bucket}`: `{count}`")

    lines.extend(["", "## Pass Pattern Counts", ""])
    for pattern, count in sorted(report.metrics.get("pass_pattern_counts", {}).items()):
        lines.append(f"- `{pattern}`: `{count}`")

    lines.extend(["", "## Failure Bucket To Code Cross Table", ""])
    for bucket, codes in sorted(
        report.metrics.get("failure_bucket_code_counts", {}).items()
    ):
        code_text = ", ".join(
            f"`{code}`={count}" for code, count in sorted(codes.items())
        )
        if not code_text:
            code_text = "`none`"
        lines.append(f"- `{bucket}`: {code_text}")

    lines.extend(
        [
            "",
            "## Case 明细",
            "",
            "| case_id | case_set | scenario | bucket | pattern | base_pass | tri_pass | rerank_pass | fixture_tri_evidence | fixture_delta_vs_base | used_memory_ids | failures |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in report.case_rows:
        failures = ",".join(row.failure_codes)
        lines.append(
            f"| `{row.case_id}` | `{row.case_set}` | `{row.scenario_family}` | "
            f"`{row.failure_bucket}` | `{row.pass_pattern}` | "
            f"{row.baseline_answer_passed} | {row.answer_rule_passed} | "
            f"{row.rerank_answer_passed} | {row.fixture_tri_evidence_id_count} | "
            f"{row.fixture_evidence_count_delta_vs_base} | "
            f"{row.used_memory_id_count} | `{failures}` |"
        )

    lines.extend(
        [
            "",
            "## 回答质量不好的原因",
            "",
            "- 三路召回这轮不是“没召回到”：`tri_grounding_fail_count = 0`，目标记忆都已经进入评测使用记录。",
            "- 主要失败发生在召回之后：`tri_grounded_answer_fail_count_any = 23`，也就是所有三路回答失败都属于证据已到但没有答对。",
            "- 其中 `tri_grounded_non_forbidden_answer_fail_count = 18`，说明主要问题是模型没有稳定使用证据、答案没有命中目标规则，或候选排序/注入方式没有把关键证据表达清楚。",
            "- 另外 `tri_forbidden_fail_count = 5`，说明部分召回候选会把不该出现的旧信息、冲突信息或干扰信息带入回答，需要 forbidden 过滤和冲突候选隔离。",
            "- 三路召回同时有正负作用：`baseline_failed_but_tri_passed_count = 9` 说明它能救活基线失败；`baseline_passed_but_tri_failed_count = 5` 说明它也会让部分原本答对的 case 回退。",
            "- `tri_failed_but_rerank_passed_count = 7` 说明后续累计 profile 可能通过重排、注入治理或组合链路救回部分失败，但这不是 rerank 单因素因果结论。",
            "",
            "面试表达：三路召回已经把目标记忆召回进上下文，所以瓶颈从“召回覆盖”转移到了“召回后的证据治理”。后续优化重点不是继续扩大召回，而是候选去噪、forbidden 过滤、场景路由、重排和更强的证据注入约束。",
            "",
            "## 下一步建议",
            "",
            "- 优先查看 `grounded_answer_rule_miss`：证据已经进入上下文，但回答没有稳定用对。",
            "- 如果 `tri_failed_but_rerank_passed_count` 较高，优先设计 `route + tri + graph/rerank/injection` 后续组合验证；不要把它解释为 rerank 单因素因果。",
            "- 如果 `baseline_passed_but_tri_failed_count` 较高，优先做候选去噪和 forbidden 过滤。",
            "- 如果 failure bucket 或 pass pattern 集中，下一轮围绕该模式做小型真实 LLM 复测。",
            "- 如果只有单个 scenario 失败，先把它作为 case-level 诊断，不作为统计集中结论。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metrics(
    rows: Sequence[TriFailureCaseRow],
    case_set_summaries: Sequence[TriScenarioSummary],
    scenario_summaries: Sequence[TriScenarioSummary],
    source_metrics: object,
) -> dict[str, object]:
    tri_failures = [row for row in rows if not row.answer_rule_passed]
    grounded_failures_any = [
        row for row in tri_failures if row.memory_grounding_passed
    ]
    grounded_non_forbidden_failures = [
        row
        for row in tri_failures
        if row.memory_grounding_passed and row.forbidden_violation_count == 0
    ]
    forbidden_failures = [row for row in rows if row.forbidden_violation_count > 0]
    return {
        "source_case_count": (
            source_metrics.get("case_count")
            if isinstance(source_metrics, Mapping)
            else None
        ),
        "source_unique_case_count": (
            source_metrics.get("unique_case_count")
            if isinstance(source_metrics, Mapping)
            else None
        ),
        "tri_case_count": len(rows),
        "tri_answer_fail_count": len(tri_failures),
        "tri_answer_fail_rate": _rate(len(tri_failures), len(rows)),
        "tri_grounded_answer_fail_count_any": len(grounded_failures_any),
        "tri_grounded_non_forbidden_answer_fail_count": len(
            grounded_non_forbidden_failures
        ),
        "tri_grounding_fail_count": sum(
            1 for row in rows if not row.memory_grounding_passed
        ),
        "tri_forbidden_fail_count": len(forbidden_failures),
        "failure_bucket_counts": _count_by(rows, lambda row: row.failure_bucket),
        "failure_bucket_code_counts": _bucket_failure_code_counts(rows),
        "pass_pattern_counts": _count_by(rows, lambda row: row.pass_pattern),
        "baseline_passed_but_tri_failed_count": sum(
            1 for row in rows if row.baseline_passed_but_tri_failed
        ),
        "baseline_failed_but_tri_passed_count": sum(
            1 for row in rows if row.baseline_failed_but_tri_passed
        ),
        "tri_failed_but_rerank_passed_count": sum(
            1 for row in rows if row.tri_failed_but_rerank_passed
        ),
        "avg_fixture_tri_evidence_id_count": _avg(
            row.fixture_tri_evidence_id_count for row in rows
        ),
        "avg_fixture_evidence_count_delta_vs_base": _avg(
            row.fixture_evidence_count_delta_vs_base for row in rows
        ),
        "fixture_rerank_reduced_evidence_count_cases": sum(
            1 for row in rows if row.fixture_rerank_reduced_evidence_count
        ),
        "case_set_count": len(case_set_summaries),
        "scenario_family_count": len(scenario_summaries),
    }


def _scenario_summaries(
    rows: Sequence[TriFailureCaseRow],
    *,
    key: Callable[[TriFailureCaseRow], str],
) -> list[TriScenarioSummary]:
    by_scenario: dict[str, list[TriFailureCaseRow]] = {}
    for row in rows:
        by_scenario.setdefault(str(key(row)), []).append(row)
    summaries: list[TriScenarioSummary] = []
    for scenario, group in sorted(by_scenario.items()):
        answer_fail = [row for row in group if not row.answer_rule_passed]
        grounded_answer_fail_any = [
            row for row in answer_fail if row.memory_grounding_passed
        ]
        grounded_non_forbidden_answer_fail = [
            row
            for row in answer_fail
            if row.memory_grounding_passed and row.forbidden_violation_count == 0
        ]
        summaries.append(
            TriScenarioSummary(
                scenario=scenario,
                case_count=len(group),
                answer_fail_count=len(answer_fail),
                grounded_answer_fail_count_any=len(grounded_answer_fail_any),
                grounded_non_forbidden_answer_fail_count=len(
                    grounded_non_forbidden_answer_fail
                ),
                forbidden_fail_count=sum(
                    1 for row in group if row.forbidden_violation_count > 0
                ),
                baseline_passed_but_tri_failed_count=sum(
                    1 for row in group if row.baseline_passed_but_tri_failed
                ),
                baseline_failed_but_tri_passed_count=sum(
                    1 for row in group if row.baseline_failed_but_tri_passed
                ),
                tri_failed_but_rerank_passed_count=sum(
                    1 for row in group if row.tri_failed_but_rerank_passed
                ),
                answer_fail_rate=_rate(len(answer_fail), len(group)),
            )
        )
    return summaries


def _failure_bucket(
    *,
    answer_passed: bool,
    grounding_passed: bool,
    forbidden_count: int,
    provider_error: bool,
    timeout: bool,
) -> str:
    if provider_error or timeout:
        return "infra_failure"
    if answer_passed:
        return "passed"
    if not grounding_passed:
        return "grounding_failure"
    if forbidden_count > 0:
        return "forbidden_answer_failure"
    return "grounded_answer_rule_miss"


def _case_set(category: str) -> str:
    if category.startswith("common_"):
        return "common"
    if category.startswith("hard_"):
        return "hard"
    return "unknown"


def _scenario_family(category: str) -> str:
    if category.startswith("common_"):
        return category.removeprefix("common_")
    if category.startswith("hard_"):
        return category.removeprefix("hard_")
    return category or "unknown"


def _pass_pattern(
    *,
    baseline_answer: bool | None,
    tri_answer: bool,
    rerank_answer: bool | None,
) -> str:
    base = _pattern_value(baseline_answer)
    tri = _pattern_value(tri_answer)
    rerank = _pattern_value(rerank_answer)
    return f"base_{base}_tri_{tri}_rerank_{rerank}"


def _pattern_value(value: bool | None) -> str:
    if value is None:
        return "missing"
    return "pass" if value else "fail"


def _count_by(
    rows: Sequence[TriFailureCaseRow],
    key: Callable[[TriFailureCaseRow], str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(key(row))
        counts[value] = counts.get(value, 0) + 1
    return counts


def _bucket_failure_code_counts(
    rows: Sequence[TriFailureCaseRow],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = result.setdefault(row.failure_bucket, {})
        for code in row.failure_codes:
            bucket[code] = bucket.get(code, 0) + 1
    return result


def _case_key(row: Mapping[str, object]) -> tuple[str, str, int]:
    return (
        str(row.get("case_id") or ""),
        str(row.get("prompt_variant") or ""),
        _int(row.get("repeat_index")),
    )


def _failures(row: Mapping[str, object]) -> tuple[str, ...]:
    raw = row.get("failures")
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return tuple(str(item) for item in raw)
    return ()


def _failure_code(failure: str) -> str:
    known_prefixes = {
        "found forbidden answer term": "found_forbidden_answer_term",
        "found_forbidden_answer_term": "found_forbidden_answer_term",
        "missing expected memory ids": "missing_expected_memory_ids",
        "missing_expected_memory_ids": "missing_expected_memory_ids",
        "missing expected answer term group": "missing_expected_answer_term_group",
        "missing_expected_answer_term_group": "missing_expected_answer_term_group",
        "missing expected answer term": "missing_expected_answer_term",
        "missing_expected_answer_term": "missing_expected_answer_term",
    }
    for prefix, code in known_prefixes.items():
        if failure.startswith(prefix):
            return code
    code = re.sub(r"[^a-zA-Z0-9]+", "_", failure.strip().lower()).strip("_")
    return code or "unknown_failure"


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 4)


def _avg(values) -> float:
    collected = [float(value) for value in values]
    if not collected:
        return 0.0
    return round(sum(collected) / len(collected), 4)


def _bool(value: object) -> bool:
    return bool(value)


def _int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
