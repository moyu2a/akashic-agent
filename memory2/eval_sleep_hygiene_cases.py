from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class SleepHygieneCase:
    case_id: str
    label: str
    memory_items: tuple[dict[str, object], ...]
    expected_item_ids: tuple[str, ...]
    case_set: str = "standard"
    scenario: str = ""
    expected_item_states: dict[str, str] = field(default_factory=dict)

    def evaluated_item_ids(self) -> tuple[str, ...]:
        if self.expected_item_states:
            return tuple(self.expected_item_states)
        return self.expected_item_ids

    def expected_state_for(self, item_id: str) -> str:
        if self.expected_item_states:
            return self.expected_item_states[str(item_id)]
        return _expected_state_for_label(self.label)


def build_sleep_hygiene_cases(
    *,
    duplicate_groups: int = 120,
    stale_count: int = 120,
    low_value_count: int = 120,
    retained_count: int = 120,
    missing_source_count: int = 40,
    case_set: str = "standard",
    hard_per_scenario: int = 40,
) -> tuple[SleepHygieneCase, ...]:
    if case_set == "standard":
        return build_sleep_hygiene_standard_cases(
            duplicate_groups=duplicate_groups,
            stale_count=stale_count,
            low_value_count=low_value_count,
            retained_count=retained_count,
            missing_source_count=missing_source_count,
        )
    if case_set == "hard":
        return build_sleep_hygiene_hard_cases(
            per_scenario=hard_per_scenario,
            missing_source_count=missing_source_count,
        )
    if case_set == "all":
        return (
            build_sleep_hygiene_standard_cases(
                duplicate_groups=duplicate_groups,
                stale_count=stale_count,
                low_value_count=low_value_count,
                retained_count=retained_count,
                missing_source_count=missing_source_count,
            )
            + build_sleep_hygiene_hard_cases(
                per_scenario=hard_per_scenario,
                missing_source_count=missing_source_count,
            )
        )
    raise ValueError(f"unsupported sleep hygiene case_set: {case_set}")


def build_sleep_hygiene_standard_cases(
    *,
    duplicate_groups: int = 120,
    stale_count: int = 120,
    low_value_count: int = 120,
    retained_count: int = 120,
    missing_source_count: int = 40,
) -> tuple[SleepHygieneCase, ...]:
    cases: list[SleepHygieneCase] = []
    missing_budget = max(0, int(missing_source_count))

    for idx in range(max(0, int(duplicate_groups))):
        case_id = f"dup_group_{idx:03d}"
        first_id = f"dup-{idx:03d}-a"
        second_id = f"dup-{idx:03d}-b"
        source_ref = _source_ref("dup", idx)
        items = (
            _item(
                first_id,
                "用户偏好中文回答，并希望面试表达直接清晰",
                scope_chat_id=case_id,
                source_ref=source_ref,
            ),
            _item(
                second_id,
                "用户偏好中文回答，并希望面试表达直接清晰",
                scope_chat_id=case_id,
                source_ref=source_ref,
            ),
        )
        cases.append(
            SleepHygieneCase(
                case_id=case_id,
                label="duplicate",
                memory_items=items,
                expected_item_ids=(second_id,),
                expected_item_states={second_id: "merged"},
            )
        )

    for idx in range(max(0, int(stale_count))):
        case_id = f"stale_{idx:03d}"
        item_id = f"stale-{idx:03d}"
        source_ref, missing_budget = _maybe_missing_source("stale", idx, missing_budget)
        cases.append(
            SleepHygieneCase(
                case_id=case_id,
                label="stale",
                memory_items=(
                    _item(
                        item_id,
                        f"用户曾经关注旧版入口方案编号 {idx}",
                        scope_chat_id=case_id,
                        updated_at="2025-01-01T00:00:00+00:00",
                        reinforcement=1,
                        emotional_weight=0,
                        source_ref=source_ref,
                    ),
                ),
                expected_item_ids=(item_id,),
                expected_item_states={item_id: "stale"},
            )
        )

    for idx in range(max(0, int(low_value_count))):
        case_id = f"low_value_{idx:03d}"
        item_id = f"low-{idx:03d}"
        source_ref, missing_budget = _maybe_missing_source("low", idx, missing_budget)
        cases.append(
            SleepHygieneCase(
                case_id=case_id,
                label="low_value",
                memory_items=(
                    _item(
                        item_id,
                        f"用户本次临时测试变量编号 {idx}",
                        scope_chat_id=case_id,
                        memory_type="event",
                        updated_at="2025-01-01T00:00:00+00:00",
                        reinforcement=1,
                        emotional_weight=0,
                        source_ref=source_ref,
                    ),
                ),
                expected_item_ids=(item_id,),
                expected_item_states={item_id: "low_value_removed"},
            )
        )

    for idx in range(max(0, int(retained_count))):
        case_id = f"retained_{idx:03d}"
        item_id = f"retain-{idx:03d}"
        source_ref, missing_budget = _maybe_missing_source("retain", idx, missing_budget)
        cases.append(
            SleepHygieneCase(
                case_id=case_id,
                label="retained",
                memory_items=(
                    _item(
                        item_id,
                        f"用户稳定偏好编号 {idx}：回答架构问题时先讲主链路再讲边界",
                        scope_chat_id=case_id,
                        updated_at="2026-07-17T00:00:00+00:00",
                        reinforcement=5,
                        emotional_weight=4,
                        source_ref=source_ref,
                    ),
                ),
                expected_item_ids=(item_id,),
                expected_item_states={item_id: "active"},
            )
        )

    return tuple(cases)


def build_sleep_hygiene_hard_cases(
    *,
    per_scenario: int = 40,
    missing_source_count: int = 40,
) -> tuple[SleepHygieneCase, ...]:
    cases: list[SleepHygieneCase] = []
    missing_budget = max(0, int(missing_source_count))
    for idx in range(max(0, int(per_scenario))):
        cases.append(_near_merge_not_duplicate_case(idx))
        cases.append(_old_high_value_case(idx))
        cases.append(_temporary_but_pinned_case(idx))
        cases.append(_cross_scope_identical_case(idx))
        cases.append(_opposite_preference_conflict_case(idx))
        cases.append(_multi_duplicate_pairwise_case(idx))
        case, missing_budget = _missing_source_but_important_case(idx, missing_budget)
        cases.append(case)
        cases.append(_mixed_signal_low_value_case(idx))
    return tuple(cases)


def flatten_sleep_hygiene_memory_items(
    cases: Sequence[SleepHygieneCase],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for case in cases:
        items.extend(dict(item) for item in case.memory_items)
    return items


def _item(
    item_id: str,
    summary: str,
    *,
    scope_chat_id: str,
    memory_type: str = "preference",
    updated_at: str = "2026-07-17T00:00:00+00:00",
    reinforcement: int = 1,
    emotional_weight: int = 0,
    source_ref: str = "cli:local@post_response",
) -> dict[str, object]:
    return {
        "id": item_id,
        "summary": summary,
        "memory_type": memory_type,
        "updated_at": updated_at,
        "reinforcement": reinforcement,
        "emotional_weight": emotional_weight,
        "source_ref": source_ref,
        "status": "active",
        "scope_channel": "cli",
        "scope_chat_id": scope_chat_id,
    }


def _expected_state_for_label(label: str) -> str:
    if label == "duplicate":
        return "merged"
    if label == "stale":
        return "stale"
    if label == "low_value":
        return "low_value_removed"
    return "active"


def _hard_case(
    *,
    case_id: str,
    scenario: str,
    label: str,
    items: tuple[dict[str, object], ...],
    expected_item_states: dict[str, str],
) -> SleepHygieneCase:
    return SleepHygieneCase(
        case_id=case_id,
        label=label,
        memory_items=items,
        expected_item_ids=tuple(
            item_id for item_id, state in expected_item_states.items() if state != "active"
        ),
        case_set="hard",
        scenario=scenario,
        expected_item_states=expected_item_states,
    )


def _near_merge_not_duplicate_case(idx: int) -> SleepHygieneCase:
    case_id = f"hard_near_merge_{idx:03d}"
    first_id = f"hard-near-merge-{idx:03d}-a"
    second_id = f"hard-near-merge-{idx:03d}-b"
    items = (
        _item(
            first_id,
            f"用户偏好 面试 讲 memory 架构 分层 编号 {idx}",
            scope_chat_id=case_id,
            source_ref=_source_ref("hard-near-merge", idx),
        ),
        _item(
            second_id,
            f"用户偏好 面试 讲 memory 架构 边界 编号 {idx}",
            scope_chat_id=case_id,
            source_ref=_source_ref("hard-near-merge", idx),
        ),
    )
    return _hard_case(
        case_id=case_id,
        scenario="near_merge_not_duplicate",
        label="retained",
        items=items,
        expected_item_states={first_id: "active", second_id: "active"},
    )


def _old_high_value_case(idx: int) -> SleepHygieneCase:
    case_id = f"hard_old_high_value_{idx:03d}"
    item_id = f"hard-old-high-value-{idx:03d}"
    return _hard_case(
        case_id=case_id,
        scenario="old_high_value",
        label="retained",
        items=(
            _item(
                item_id,
                f"用户长期稳定偏好编号 {idx}：架构回答需要先讲主链路",
                scope_chat_id=case_id,
                updated_at="2025-01-01T00:00:00+00:00",
                reinforcement=5,
                emotional_weight=4,
                source_ref=_source_ref("hard-old-high-value", idx),
            ),
        ),
        expected_item_states={item_id: "active"},
    )


def _temporary_but_pinned_case(idx: int) -> SleepHygieneCase:
    case_id = f"hard_temporary_pinned_{idx:03d}"
    item_id = f"hard-temporary-pinned-{idx:03d}"
    return _hard_case(
        case_id=case_id,
        scenario="temporary_but_pinned",
        label="retained",
        items=(
            _item(
                item_id,
                f"用户说本次测试编号 {idx} 很重要，以后都要保留这个偏好",
                scope_chat_id=case_id,
                memory_type="event",
                updated_at="2025-01-01T00:00:00+00:00",
                reinforcement=5,
                emotional_weight=3,
                source_ref=_source_ref("hard-temporary-pinned", idx),
            ),
        ),
        expected_item_states={item_id: "active"},
    )


def _cross_scope_identical_case(idx: int) -> SleepHygieneCase:
    case_id = f"hard_cross_scope_{idx:03d}"
    first_id = f"hard-cross-scope-{idx:03d}-a"
    second_id = f"hard-cross-scope-{idx:03d}-b"
    summary = f"用户偏好中文回答，并希望面试表达直接清晰，编号 {idx}"
    items = (
        _item(
            first_id,
            summary,
            scope_chat_id=f"{case_id}:telegram",
            source_ref=_source_ref("hard-cross-scope", idx),
        ),
        _item(
            second_id,
            summary,
            scope_chat_id=f"{case_id}:qq",
            source_ref=_source_ref("hard-cross-scope", idx),
        ),
    )
    return _hard_case(
        case_id=case_id,
        scenario="cross_scope_identical",
        label="retained",
        items=items,
        expected_item_states={first_id: "active", second_id: "active"},
    )


def _opposite_preference_conflict_case(idx: int) -> SleepHygieneCase:
    case_id = f"hard_opposite_conflict_{idx:03d}"
    first_id = f"hard-opposite-conflict-{idx:03d}-a"
    second_id = f"hard-opposite-conflict-{idx:03d}-b"
    items = (
        _item(
            first_id,
            f"用户喜欢在 memory 面试回答中先讲架构 编号 {idx}",
            scope_chat_id=case_id,
            source_ref=_source_ref("hard-opposite-conflict", idx),
        ),
        _item(
            second_id,
            f"用户不喜欢在 memory 面试回答中先讲架构 编号 {idx}",
            scope_chat_id=case_id,
            source_ref=_source_ref("hard-opposite-conflict", idx),
        ),
    )
    return _hard_case(
        case_id=case_id,
        scenario="opposite_preference_conflict",
        label="retained",
        items=items,
        expected_item_states={first_id: "active", second_id: "active"},
    )


def _multi_duplicate_pairwise_case(idx: int) -> SleepHygieneCase:
    case_id = f"hard_multi_duplicate_{idx:03d}"
    item_ids = tuple(f"hard-multi-duplicate-{idx:03d}-{suffix}" for suffix in ("a", "b", "c"))
    summary = f"用户偏好中文回答，并希望面试表达直接清晰，重复组编号 {idx}"
    items = tuple(
        _item(
            item_id,
            summary,
            scope_chat_id=case_id,
            source_ref=_source_ref("hard-multi-duplicate", idx),
        )
        for item_id in item_ids
    )
    sorted_ids = tuple(sorted(item_ids))
    return _hard_case(
        case_id=case_id,
        scenario="multi_duplicate_pairwise",
        label="duplicate",
        items=items,
        expected_item_states={
            sorted_ids[0]: "active",
            sorted_ids[1]: "merged",
            sorted_ids[2]: "merged",
        },
    )


def _missing_source_but_important_case(
    idx: int,
    missing_budget: int,
) -> tuple[SleepHygieneCase, int]:
    case_id = f"hard_missing_source_important_{idx:03d}"
    item_id = f"hard-missing-source-important-{idx:03d}"
    case = _hard_case(
        case_id=case_id,
        scenario="missing_source_but_important",
        label="retained",
        items=(
            _item(
                item_id,
                f"用户强调缺少来源但仍然重要的长期偏好编号 {idx}",
                scope_chat_id=case_id,
                reinforcement=5,
                emotional_weight=4,
                source_ref="",
            ),
        ),
        expected_item_states={item_id: "active"},
    )
    return case, max(0, missing_budget - 1)


def _mixed_signal_low_value_case(idx: int) -> SleepHygieneCase:
    case_id = f"hard_mixed_low_value_{idx:03d}"
    item_id = f"hard-mixed-low-value-{idx:03d}"
    return _hard_case(
        case_id=case_id,
        scenario="mixed_signal_low_value",
        label="low_value",
        items=(
            _item(
                item_id,
                f"用户本次临时测试变量编号 {idx}，仅用于一次性验证",
                scope_chat_id=case_id,
                memory_type="event",
                updated_at="2025-01-01T00:00:00+00:00",
                reinforcement=1,
                emotional_weight=0,
                source_ref=_source_ref("hard-mixed-low-value", idx),
            ),
        ),
        expected_item_states={item_id: "low_value_removed"},
    )


def _source_ref(prefix: str, idx: int) -> str:
    return f"cli:local:{prefix}-{idx:03d}"


def _maybe_missing_source(
    prefix: str,
    idx: int,
    missing_budget: int,
) -> tuple[str, int]:
    if missing_budget <= 0:
        return _source_ref(prefix, idx), missing_budget
    return "", missing_budget - 1
