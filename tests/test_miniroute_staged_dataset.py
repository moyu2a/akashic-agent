from __future__ import annotations

import json
from pathlib import Path

from miniroute.tools.generate_staged_dataset import (
    build_intent_record,
    build_property_record,
    write_staged_dataset_files,
)
from miniroute.v1_schema import RouteLabel, TrainingRecord


def _record() -> TrainingRecord:
    return TrainingRecord(
        instruction="原始路由指令",
        input="查询会议记录并创建任务。",
        label=RouteLabel(
            intent="task_plan",
            need_memory=True,
            need_tools=True,
            tool_scope=["memory_tools", "task_tools"],
            risk_level="write",
        ),
        source="test:compound",
    )


def test_intent_record_contains_only_internal_intent_fields() -> None:
    row = build_intent_record(_record())
    output = json.loads(row["conversations"][1]["content"])

    assert output == {
        "intent": "task_plan",
        "operation": "plan",
        "request_mode": "compound",
    }
    assert "工具注册表" not in row["conversations"][0]["content"]


def test_property_record_contains_stage_one_result_and_route_attributes() -> None:
    row = build_property_record(_record())
    user_content = row["conversations"][0]["content"]
    output = json.loads(row["conversations"][1]["content"])

    assert "阶段一结果" in user_content
    assert '"intent": "task_plan"' in user_content
    assert output == {
        "need_memory": True,
        "tool_scope": ["memory_tools", "task_tools"],
        "risk_level": "write",
    }


def test_staged_writer_preserves_source_splits(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    for split in ("train", "valid", "test"):
        path = source_dir / f"route_v3_1_{split}.jsonl"
        path.write_text(
            json.dumps(_record().to_training_json(), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    result = write_staged_dataset_files(source_dir, tmp_path / "out", "route_v3_1")

    assert result == {"train": 1, "valid": 1, "test": 1}
    intent_row = json.loads(
        (tmp_path / "out" / "route_v3_1_intent_train.jsonl").read_text(
            encoding="utf-8"
        )
    )
    property_row = json.loads(
        (tmp_path / "out" / "route_v3_1_property_train.jsonl").read_text(
            encoding="utf-8"
        )
    )
    assert len(intent_row["conversations"]) == 2
    assert len(property_row["conversations"]) == 2
