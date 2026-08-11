from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

from miniroute.tools.validate_dataset import validate_dataset_files


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _input_text(record) -> str:
    return record.input


def _label_tuple(record) -> tuple[str, bool, bool, tuple[str, ...], str]:
    label = record.label
    return (
        label.intent,
        label.need_memory,
        label.need_tools,
        tuple(label.tool_scope),
        label.risk_level,
    )


def test_v3_1_delta_sources_are_targeted_and_small() -> None:
    from miniroute.tools.generate_v3_1_dataset import build_v3_1_delta_records

    records = build_v3_1_delta_records()
    source_counts = Counter(record.source for record in records)

    assert set(source_counts) == {
        "v3_1:trace_status_query_schema_fix",
        "v3_1:task_plan_chat_profile_boundary",
        "v3_1:profile_memory_content_boundary",
        "v3_1:file_read_tool_execution_boundary",
        "v3_1:unknown_tools_boundary",
    }
    assert sum(source_counts.values()) <= 360
    assert all(count <= 80 for count in source_counts.values())
    assert len({_input_text(record) for record in records}) == len(records)


def test_v3_1_delta_contains_required_contrast_labels() -> None:
    from miniroute.tools.generate_v3_1_dataset import build_v3_1_delta_records

    by_text = {_input_text(record): record for record in build_v3_1_delta_records()}

    assert _label_tuple(by_text["查询最近的 trace，不要把 trace 当成 intent。"]) == (
        "status_query",
        False,
        True,
        ("observe_tools",),
        "read_only",
    )
    assert _label_tuple(by_text["把 V3.1 的工作拆成阶段。"]) == (
        "task_plan",
        False,
        True,
        ("task_tools",),
        "write",
    )
    assert _label_tuple(by_text["解释一下任务拆分是什么意思。"]) == (
        "chat",
        False,
        False,
        ("none",),
        "none",
    )
    assert _label_tuple(by_text["以后帮我排计划时先给优先级。"]) == (
        "profile_update",
        True,
        True,
        ("memory_tools",),
        "write",
    )
    assert _label_tuple(by_text["我之前说过喜欢什么输出方式？"]) == (
        "memory_query",
        True,
        True,
        ("memory_tools",),
        "read_only",
    )
    assert _label_tuple(by_text["保存这个链接，不是更新我的个人偏好。"]) == (
        "content_save",
        False,
        True,
        ("content_tools",),
        "write",
    )
    assert _label_tuple(by_text["覆盖这个配置文件，这是高风险执行。"]) == (
        "tool_execution",
        False,
        True,
        ("shell_tools",),
        "high_risk",
    )
    assert _label_tuple(by_text["识别图片文字不是读取本地 markdown。"]) == (
        "tool_execution",
        False,
        True,
        ("unknown_tools",),
        "read_only",
    )


def test_v3_1_preserves_v3_split_membership(tmp_path: Path) -> None:
    from miniroute.tools.generate_v3_1_dataset import write_v3_1_dataset_files

    data_dir = Path("miniroute/data")
    splits = write_v3_1_dataset_files(tmp_path)

    original_train = set(
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in _load_jsonl(data_dir / "route_v3_train.jsonl")
    )
    original_valid = set(
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in _load_jsonl(data_dir / "route_v3_valid.jsonl")
    )
    original_test = set(
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in _load_jsonl(data_dir / "route_v3_test.jsonl")
    )

    new_train = set(
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in _load_jsonl(tmp_path / "route_v3_1_train.jsonl")
    )
    new_valid = set(
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in _load_jsonl(tmp_path / "route_v3_1_valid.jsonl")
    )
    new_test = set(
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in _load_jsonl(tmp_path / "route_v3_1_test.jsonl")
    )

    assert original_train <= new_train
    assert original_valid <= new_valid
    assert original_test <= new_test
    assert len(splits.train) > len(original_train)
    assert len(splits.valid) > len(original_valid)
    assert len(splits.test) > len(original_test)


def test_v3_1_generated_dataset_passes_validator(tmp_path: Path) -> None:
    from miniroute.tools.generate_v3_1_dataset import write_v3_1_dataset_files

    write_v3_1_dataset_files(tmp_path)
    report = validate_dataset_files(
        {
            "train": tmp_path / "route_v3_1_train.jsonl",
            "valid": tmp_path / "route_v3_1_valid.jsonl",
            "test": tmp_path / "route_v3_1_test.jsonl",
        }
    )

    assert report.ok is True
    assert report.high_risk_test_count >= 30
    assert report.issues == []
