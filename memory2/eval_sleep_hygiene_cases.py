from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SleepHygieneCase:
    case_id: str
    label: str
    memory_items: tuple[dict[str, object], ...]
    expected_item_ids: tuple[str, ...]


def build_sleep_hygiene_cases(
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
            )
        )

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
